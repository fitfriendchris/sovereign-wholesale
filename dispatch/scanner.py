"""24/7 Opportunity Scanner.

Runs in cycles (default every 4h). Each cycle:
  1. Loads scan-target config (below — extend as Operator approves new sources)
  2. For each enabled target, dispatches a Haiku worker with a per-target brief
  3. Normalizes the worker output into opportunity records
  4. Scores each via the rubric (TAM, TTFD, build cost, defensibility, legal, fit)
  5. Calls dispatch.ingest_opportunity for storage + compliance hard-blocks
  6. Surfaces the top batch to Strategy by writing an inbox notice

CLI:
    python -m dispatch.scanner --once         # one cycle, real spend
    python -m dispatch.scanner --once --dry   # synthetic, no API spend
    python -m dispatch.scanner --loop         # continuous (4h cycles)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from dispatch import dispatch, registry

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "state" / "inbox"
LOGS = ROOT / "state" / "logs"

CYCLE_INTERVAL_SECONDS = 4 * 60 * 60  # 4h
DEFAULT_CYCLE_BUDGET_USD = 1.50
SCORE_THRESHOLD_TO_STRATEGY = 75
TOP_N_TO_STRATEGY = 10


@dataclass
class ScanTarget:
    target_id: str
    engine: str
    enabled: bool
    query_template: str
    score_weights: dict | None = None


# Initial scan-target catalog. Extend via state/inbox/research/scanner_brief.md.
SCAN_TARGETS: list[ScanTarget] = [
    ScanTarget(
        target_id="re_fsbo_craigslist",
        engine="re_wholesale",
        enabled=False,  # gated on Compliance + Operator state confirmation
        query_template=(
            "List 5 motivated-seller signals you can hypothetically extract from public "
            "FSBO listings without scraping behind a login wall. For each, output JSON: "
            '{"raw_finding": <signal description>, "tam_usd": <est assignment fee>, '
            '"ttfd_days": <days to first $>, "build_cost_usd": <0-500>, "source": <kind>, '
            '"defensibility": <0-10>}. Return a JSON array.'
        ),
    ),
    ScanTarget(
        target_id="local_smb_no_website",
        engine="local_services",
        enabled=True,
        query_template=(
            "Suggest 5 specific, distinct patterns for finding small local businesses "
            "without websites — based on publicly available info (Google Maps, Yelp, BBB). "
            "Each pattern should target a different segment (vertical/region/buyer-tier). "
            "For each, ESTIMATE realistic numbers based on the segment's economics (do NOT "
            "copy template values). Return JSON array of: "
            '{"raw_finding": <2-3 sentence specific pattern + why those SMBs would pay>, '
            '"tam_usd": <realistic monthly retainer estimate, $300-$3000 typical>, '
            '"ttfd_days": <days from outbound start to first signed retainer, 14-60>, '
            '"build_cost_usd": <total build + first-month outbound cost, $100-$1500>, '
            '"source": <which platform/data source>, '
            '"defensibility": <0-10, how hard to copy>}. '
            "Vary the numbers across findings — don't return identical $1500/$250."
        ),
    ),
    ScanTarget(
        target_id="digital_question_gaps",
        engine="digital_products",
        enabled=True,
        query_template=(
            "Identify 5 specific niches where Reddit/forum threads show high question intent "
            "but no consolidated guide exists, justifying a $7-$97 paid digital product. "
            "For each, ESTIMATE realistic numbers (do NOT copy template values). Return JSON: "
            '{"raw_finding": <niche + the exact question pattern + why people will pay>, '
            '"tam_usd": <realistic monthly revenue estimate based on search volume × conv × price, $200-$8000>, '
            '"ttfd_days": <days to first sale after launch, 7-45>, '
            '"build_cost_usd": <total to draft + landing + checkout, $30-$300>, '
            '"source": <subreddit/forum URL pattern>, '
            '"defensibility": <0-10>}. '
            "Vary numbers across findings based on actual niche economics."
        ),
    ),
    ScanTarget(
        target_id="affiliate_weak_serp",
        engine="affiliate_content",
        enabled=True,
        query_template=(
            "Suggest 5 specific buyer-intent comparison queries with weak top-result content, "
            "where an affiliate program with ≥10%% commission and ≥$20 avg sale exists. "
            "For each, ESTIMATE realistic numbers (do NOT copy template values). Return JSON: "
            '{"raw_finding": <exact query + which affiliate program + commission rate>, '
            '"tam_usd": <realistic monthly affiliate revenue est, $100-$5000>, '
            '"ttfd_days": <days to ranking + first commission, 30-90>, '
            '"build_cost_usd": <pillar article + supporting + light SEO, $50-$400>, '
            '"source": <SERP query>, '
            '"defensibility": <0-10>}. '
            "Vary the numbers based on each query's actual competitiveness."
        ),
    ),
    ScanTarget(
        target_id="lead_brokerage_b2b",
        engine="lead_brokerage",
        enabled=False,  # gated on per-vertical Compliance check first
        query_template=(
            "Suggest 3 B2B service verticals with high LTV (>$1k/customer) and scattered "
            "lead acquisition, where lead brokerage could fit. Output JSON array of "
            '{"raw_finding": <vertical + buyer profile>, "tam_usd": <per-lead × 100>, '
            '"ttfd_days": 30, "build_cost_usd": 400, "source": <kind>, '
            '"defensibility": <0-10>}.'
        ),
    ),
]


SCANNER_SYSTEM_PROMPT = """You are a Sovereign Opportunity Scanner worker.

You output JSON arrays only. Each array element is one opportunity finding.
You never invent sources you cannot defend. You never include personal data.
You never claim certainty you do not have.

When in doubt, return an empty array."""


# ---------------------------------------------------------------- scoring ---


SCORE_WEIGHTS = {
    "tam": 25,
    "ttfd": 20,
    "build_cost": 15,
    "defensibility": 10,
    "legal": 15,
    "operator_fit": 15,
}


def _operator_fit_score(opp: dict) -> int:
    """Match Operator profile: gold/silver focus, no in-person, terse, profit-driven.

    The fit signal is mostly negative-screen — penalize obvious bad-fit, give a
    modestly positive baseline to most viable opportunities.
    """
    raw = (opp.get("raw_finding", "") or "").lower()
    score = OPERATOR_FIT_BASELINE
    if "in-person" in raw or "in person" in raw or "must meet" in raw:
        score -= 10
    if "long-term commitment" in raw or "5+ year" in raw:
        score -= 4
    if "license required" in raw or "regulated profession" in raw:
        score -= 5
    if any(k in raw for k in ("gold", "silver", "trading", "metals")):
        score = min(15, score + 2)
    return max(0, min(15, score))


TAM_FULL_CREDIT_USD = 2_500     # $2.5k/mo recurring is solid for an SMB retainer
TTFD_FULL_PENALTY_DAYS = 90     # be patient with longer builds
COST_FULL_PENALTY_USD = 3_000   # accept higher upfront for higher LTV opportunities
OPERATOR_FIT_BASELINE = 13      # solid baseline; penalize bad-fit, reward gold/silver


def compute_score(opp: dict, max_tam_seen: float = TAM_FULL_CREDIT_USD) -> tuple[int, dict]:
    """Score 0-100 with a breakdown dict.

    Calibrated for SMB/digital-product opportunities where realistic TAM is $1-5k/mo,
    realistic build cost is $50-2000, realistic TTFD is 7-60 days. Rewards good
    findings rather than only catastrophically-good ones.
    """
    tam_pts = round(min(opp.get("tam_usd", 0) / max(max_tam_seen, 1), 1.0) * SCORE_WEIGHTS["tam"])
    ttfd = opp.get("ttfd_days", TTFD_FULL_PENALTY_DAYS)
    ttfd_pts = round(
        max(0, (TTFD_FULL_PENALTY_DAYS - min(ttfd, TTFD_FULL_PENALTY_DAYS)) / TTFD_FULL_PENALTY_DAYS)
        * SCORE_WEIGHTS["ttfd"]
    )
    cost = opp.get("build_cost_usd", 0)
    cost_pts = round(
        max(0, (COST_FULL_PENALTY_USD - min(cost, COST_FULL_PENALTY_USD)) / COST_FULL_PENALTY_USD)
        * SCORE_WEIGHTS["build_cost"]
    )
    defensibility = float(opp.get("defensibility", 5))
    def_pts = round(min(defensibility, 10) / 10 * SCORE_WEIGHTS["defensibility"])
    flags = opp.get("compliance_flags", [])
    has_block = any(f.get("severity") == "block" for f in flags)
    has_warn = any(f.get("severity") == "warn" for f in flags)
    if has_block:
        legal_pts = 0
    elif has_warn:
        legal_pts = SCORE_WEIGHTS["legal"] // 2
    else:
        legal_pts = SCORE_WEIGHTS["legal"]
    fit_pts = _operator_fit_score(opp)
    total = tam_pts + ttfd_pts + cost_pts + def_pts + legal_pts + fit_pts
    breakdown = {
        "tam": tam_pts, "ttfd": ttfd_pts, "build_cost": cost_pts,
        "defensibility": def_pts, "legal": legal_pts, "operator_fit": fit_pts,
    }
    return min(100, total), breakdown


# ------------------------------------------------------------ cycle runner ---


def _parse_findings(text: str) -> list[dict]:
    """The worker should return a JSON array. Be tolerant of markdown fences."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to find a JSON array inside the text
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return []
        else:
            return []
    if not isinstance(data, list):
        return []
    return data


def _max_tam_seen() -> float:
    """Use the calibrated TAM_FULL_CREDIT_USD baseline as the floor.

    Without the floor, a single $50k outlier early in the queue would crush every
    subsequent finding's TAM score by stretching the normalization range.
    """
    return TAM_FULL_CREDIT_USD


def run_cycle(
    cycle_budget_usd: float = DEFAULT_CYCLE_BUDGET_USD,
    dry: bool = False,
    only_target: str | None = None,
) -> dict:
    """Execute one scan cycle. Returns a summary dict."""
    LOGS.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    targets = [t for t in SCAN_TARGETS if t.enabled and (only_target is None or t.target_id == only_target)]
    if not targets:
        return {"started": started, "ok": False, "reason": "no enabled targets"}

    per_target_budget = cycle_budget_usd / max(len(targets), 1)
    total_ingested = 0
    total_promoted_to_strategy = 0
    promoted_for_inbox: list[dict] = []
    total_cost = 0.0

    for t in targets:
        if dry:
            findings = _synthetic_findings(t)
            cost = 0.0
            via = "dry"
        else:
            try:
                result = dispatch.dispatch_worker(
                    project_id="_adhoc",
                    role="research_scanner",
                    task=t.query_template,
                    system_prompt=SCANNER_SYSTEM_PROMPT,
                    max_cost_usd=per_target_budget,
                )
                findings = _parse_findings(result.get("text", ""))
                cost = float(result.get("cost_usd", 0))
                via = result.get("via", "unknown")
            except Exception as e:
                _log_cycle("target_failed", target=t.target_id, err=str(e))
                continue

        total_cost += cost

        for f in findings:
            opp = {
                "engine": t.engine,
                "raw_finding": str(f.get("raw_finding", ""))[:600],
                "tam_usd": float(f.get("tam_usd", 0)),
                "ttfd_days": int(f.get("ttfd_days", 30)),
                "build_cost_usd": float(f.get("build_cost_usd", 100)),
                "defensibility": float(f.get("defensibility", 5)),
                "compliance_flags": f.get("compliance_flags", []),
                "source": f.get("source", t.target_id),
                "discovered_at": datetime.now(timezone.utc).isoformat(),
            }
            score, breakdown = compute_score(opp, max_tam_seen=_max_tam_seen())
            opp["score"] = score
            opp["score_breakdown"] = breakdown
            oid = registry.ingest_opportunity(opp)
            opp["id"] = oid
            total_ingested += 1
            if score >= SCORE_THRESHOLD_TO_STRATEGY:
                promoted_for_inbox.append(opp)

        _log_cycle(
            "target_done",
            target=t.target_id,
            findings=len(findings),
            cost_usd=cost,
            via=via,
        )

    promoted_for_inbox.sort(key=lambda o: o["score"], reverse=True)
    promoted_for_inbox = promoted_for_inbox[:TOP_N_TO_STRATEGY]
    total_promoted_to_strategy = len(promoted_for_inbox)

    if promoted_for_inbox:
        _notify_strategy(promoted_for_inbox)

    summary = {
        "started": started,
        "finished": datetime.now(timezone.utc).isoformat(),
        "targets": [t.target_id for t in targets],
        "ingested": total_ingested,
        "promoted_to_strategy": total_promoted_to_strategy,
        "cost_usd": round(total_cost, 6),
        "dry": dry,
    }
    _log_cycle("cycle_complete", **summary)
    return summary


def _synthetic_findings(t: ScanTarget) -> list[dict]:
    return [
        {
            "raw_finding": f"[dry-run] synthetic finding for {t.target_id} ({t.engine})",
            "tam_usd": 1500,
            "ttfd_days": 14,
            "build_cost_usd": 80,
            "defensibility": 6,
            "source": "synthetic",
        }
    ]


def _notify_strategy(opps: list[dict]) -> None:
    INBOX.mkdir(parents=True, exist_ok=True)
    d = INBOX / "strategy"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"scanner_batch_{int(time.time())}.md"
    lines = ["# Scanner batch — top opportunities", ""]
    for o in opps:
        lines.append(
            f"- **{o['id']}** | engine: `{o['engine']}` | score: {o['score']} "
            f"| TAM: ${o['tam_usd']:.0f} | TTFD: {o['ttfd_days']}d"
        )
        lines.append(f"  - {o['raw_finding'][:300]}")
    p.write_text("\n".join(lines) + "\n")


def _log_cycle(event: str, **fields) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    line = json.dumps({"ts": time.time(), "event": event, **fields}) + "\n"
    (LOGS / "scanner.log").open("a").write(line)


# ----------------------------------------------------------------- runner ---


def loop_forever(cycle_seconds: int = CYCLE_INTERVAL_SECONDS) -> None:
    while True:
        try:
            run_cycle()
        except Exception as e:
            _log_cycle("cycle_exception", err=str(e))
        time.sleep(cycle_seconds)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--once", action="store_true")
    p.add_argument("--loop", action="store_true")
    p.add_argument("--dry", action="store_true")
    p.add_argument("--target", help="only this target_id")
    p.add_argument("--budget", type=float, default=DEFAULT_CYCLE_BUDGET_USD)
    args = p.parse_args()

    if args.once or args.dry:
        summary = run_cycle(
            cycle_budget_usd=args.budget, dry=args.dry, only_target=args.target
        )
        print(json.dumps(summary, indent=2))
        return 0
    if args.loop:
        loop_forever()
        return 0
    p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
