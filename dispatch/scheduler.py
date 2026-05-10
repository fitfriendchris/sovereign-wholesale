"""Cron-like task runner. Owns:
  - Scanner cycles (every 4h)
  - Auto-promote ≥75 opportunities + push BUSINESS REVIEWs to Operator (every 10 min)
  - Daily digest assembly + Telegram push (07:00 local)
  - Weekly Treasury reconciliation + push (Sundays 23:00 local)
  - Health checks every 5 min (registry parse, disk space)

Single-process. Run under launchd via com.sovereign.scheduler.plist.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dispatch import registry, scanner, treasury

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "state" / "logs"
OPERATOR_PUSH_STATE = ROOT / "state" / "logs" / "operator_pushed.json"


# Schedule entries: (name, every_seconds, run_func, only_if_predicate)
def _is_07_local() -> bool:
    return datetime.now().hour == 7 and datetime.now().minute < 5


def _is_sunday_23_local() -> bool:
    n = datetime.now()
    return n.weekday() == 6 and n.hour == 23 and n.minute < 5


def _every_4h() -> bool:
    return datetime.now().hour % 4 == 0 and datetime.now().minute < 5


SCHEDULE = [
    # (name, min interval seconds between runs, run callable, predicate)
    ("scanner_cycle",     4 * 3600,        lambda: scanner.run_cycle(),    _every_4h),
    ("review_push",       10 * 60,         lambda: _push_pending_reviews(),lambda: True),
    ("daily_digest",      24 * 3600,       lambda: _push_daily_digest(),   _is_07_local),
    ("weekly_treasury",   7 * 24 * 3600,   lambda: _run_weekly_treasury(), _is_sunday_23_local),
    ("health_check",      5 * 60,          lambda: _health_check(),        lambda: True),
]


_LAST_RUN: dict[str, float] = {}


def _operator_chat_id() -> str:
    """Read TELEGRAM_OPERATOR_CHAT_ID from .env."""
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("TELEGRAM_OPERATOR_CHAT_ID="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return os.environ.get("TELEGRAM_OPERATOR_CHAT_ID", "")


def _openclaw_send(text: str) -> bool:
    """Push text to Operator via OpenClaw → hermes telegram channel. Returns success."""
    chat = _operator_chat_id()
    if not chat:
        _log("openclaw_send_skipped", reason="no chat id")
        return False
    try:
        res = subprocess.run(
            ["openclaw", "message", "send",
             "--channel", "telegram",
             "--account", "hermes",
             "--target", chat,
             "--message", text[:4000],
             "--json"],
            capture_output=True, text=True, timeout=30,
        )
        if res.returncode != 0:
            _log("openclaw_send_fail", err=res.stderr[-500:])
            return False
        return True
    except Exception as e:
        _log("openclaw_send_exception", err=str(e))
        return False


def _emit_daily_digest() -> dict:
    """Assemble digest text. Returns dict with `text` and `path`."""
    out_dir = ROOT / "state" / "outbox" / "hermes"
    out_dir.mkdir(parents=True, exist_ok=True)
    date = datetime.now().date().isoformat()
    active = registry.list_projects(status="active")
    blocked = registry.list_projects(status="blocked")
    opps = registry.list_opportunities(status="new", min_score=75)
    rev = registry.read_revenue()
    omni = rev["engines"].get("omni", {}).get("totals", {})
    lines = [
        f"DAILY DIGEST — {date}",
        "",
        f"ACTIVE PROJECTS ({len(active)})",
    ]
    for p in active[:10]:
        lines.append(f"  • {p['name']} [{p['engine']}] — {p.get('outcome', '')[:60]}")
    if blocked:
        lines += ["", f"BLOCKED ({len(blocked)})"]
        for p in blocked[:5]:
            lines.append(f"  • {p['name']} [{p['engine']}]")
    lines += [
        "",
        "OMNI (Trading)",
        f"  • MTD net: ${omni.get('mtd_net', 0):.2f}",
        f"  • YTD net: ${omni.get('ytd_net', 0):.2f}",
        "",
        "OPPORTUNITIES",
        f"  • {len(opps)} in queue (top score: {opps[0]['score'] if opps else 0})",
        "",
    ]
    text = "\n".join(lines) + "\n"
    p = out_dir / f"digest_{date}.md"
    p.write_text(text)
    return {"path": str(p), "text": text, "active": len(active), "opportunities": len(opps)}


def _push_daily_digest() -> dict:
    info = _emit_daily_digest()
    pushed = _openclaw_send(info["text"])
    _log("daily_digest", path=info["path"], pushed=pushed)
    return {"path": info["path"], "pushed": pushed}


def _push_pending_reviews() -> dict:
    """Auto-promote ≥75 opportunities and push BUSINESS REVIEW to Operator.

    Cap: max 3/day pushed (per docs/operator_review_loop.md).
    De-dupe: tracks pushed opp IDs in state/logs/operator_pushed.json.
    """
    OPERATOR_PUSH_STATE.parent.mkdir(parents=True, exist_ok=True)
    pushed_index = {}
    if OPERATOR_PUSH_STATE.exists():
        try:
            pushed_index = json.loads(OPERATOR_PUSH_STATE.read_text())
        except json.JSONDecodeError:
            pass

    today = datetime.now().date().isoformat()
    pushed_today = sum(1 for v in pushed_index.values() if v.startswith(today))
    DAILY_CAP = 3
    if pushed_today >= DAILY_CAP:
        return {"pushed": 0, "reason": f"daily cap reached ({DAILY_CAP})"}

    eligible = [o for o in registry.list_opportunities(status="new", min_score=75)
                if o["id"] not in pushed_index]
    if not eligible:
        return {"pushed": 0, "reason": "no new ≥75 opps"}

    # Sort by score, take up to remaining cap
    slots = DAILY_CAP - pushed_today
    eligible.sort(key=lambda o: o["score"], reverse=True)
    pushed = 0
    for opp in eligible[:slots]:
        # Promote in registry
        try:
            registry.promote_opportunity(opp["id"])
        except Exception as e:
            _log("promote_failed", id=opp["id"], err=str(e))
            continue
        review = _format_business_review(opp)
        if _openclaw_send(review):
            pushed_index[opp["id"]] = datetime.now(timezone.utc).isoformat()
            pushed += 1
        else:
            # Roll back the promotion if push failed
            try:
                registry.archive_opportunity(opp["id"], reason="push_failed; will retry")
            except Exception:
                pass

    OPERATOR_PUSH_STATE.write_text(json.dumps(pushed_index, indent=2))
    _log("review_push", pushed=pushed, eligible=len(eligible))
    return {"pushed": pushed, "eligible": len(eligible)}


def _format_business_review(opp: dict) -> str:
    """Render a BUSINESS REVIEW per docs/operator_review_loop.md format."""
    flags = opp.get("compliance_flags") or []
    flags_str = ("\n  ".join(f"⚠ {f.get('rule','?')}: {f.get('detail','')[:80]}" for f in flags)
                 if flags else "✓ none")
    proposed_owner = {
        "re_wholesale": "Sales",
        "local_services": "Sales",
        "digital_products": "Engineering",
        "lead_brokerage": "Marketing",
        "affiliate_content": "Marketing",
    }.get(opp.get("engine"), "Strategy")
    name = opp["raw_finding"][:50].replace("\n", " ").strip(". ").strip()
    return (
        f"BUSINESS REVIEW — {name}\n"
        f"ENGINE:    {opp['engine']}\n"
        f"SCORE:     {opp['score']}/100\n"
        f"OPPORTUNITY:\n  {opp['raw_finding'][:300]}\n"
        f"NUMBERS:\n"
        f"  TAM:           ${opp.get('tam_usd', 0):.0f}/mo (est)\n"
        f"  Time-to-first-$: {opp.get('ttfd_days', 0)}d\n"
        f"  Build cost:    ${opp.get('build_cost_usd', 0):.0f}\n"
        f"COMPLIANCE:\n  {flags_str}\n"
        f"PROPOSED OWNER: {proposed_owner}\n"
        f"ID: {opp['id']}\n\n"
        f"REPLY:\n  yes    → launch (Hermes will create project + dispatch Owner)\n"
        f"  no     → archive\n"
        f"  hold   → park 7 days\n"
        f"  edit   → state changes; Hermes redrafts"
    )


def _run_weekly_treasury() -> dict:
    """Reconcile + push the TREASURY ACTION REQUEST to Operator."""
    req = treasury.reconcile()
    text = treasury._format_request_md(req)
    pushed = _openclaw_send(text[:4000])
    _log("weekly_treasury", pushed=pushed, has_actions=bool(req.get("actions")))
    return {"pushed": pushed, "actions": len(req.get("actions") or [])}


def _health_check() -> dict:
    """Lightweight checks. Writes to state/logs/health.log."""
    issues = []
    try:
        registry._read(registry.REGISTRY)
        registry._read(registry.OPPORTUNITIES)
        registry._read(registry.REVENUE)
    except Exception as e:
        issues.append(f"registry_parse: {e}")
    state_size_mb = sum(
        f.stat().st_size for f in (ROOT / "state").rglob("*") if f.is_file()
    ) / 1_048_576
    if state_size_mb > 500:
        issues.append(f"state_dir_large: {state_size_mb:.0f}MB")
    LOGS.mkdir(parents=True, exist_ok=True)
    line = json.dumps({
        "ts": time.time(),
        "issues": issues,
        "state_size_mb": round(state_size_mb, 1),
    }) + "\n"
    (LOGS / "health.log").open("a").write(line)
    return {"issues": issues, "state_size_mb": state_size_mb}


def _log(event: str, **fields) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    line = json.dumps({"ts": time.time(), "event": event, **fields}) + "\n"
    (LOGS / "scheduler.log").open("a").write(line)


def tick() -> None:
    now = time.time()
    for name, interval, run, pred in SCHEDULE:
        last = _LAST_RUN.get(name, 0)
        if now - last < interval:
            continue
        if not pred():
            continue
        try:
            run()
            _LAST_RUN[name] = now
            _log("ran", task=name)
        except Exception as e:
            _log("task_exception", task=name, err=str(e))


def loop_forever(tick_seconds: int = 60) -> None:
    while True:
        tick()
        time.sleep(tick_seconds)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--tick", action="store_true", help="run one tick and exit")
    p.add_argument("--loop", action="store_true")
    p.add_argument("--digest", action="store_true", help="emit a daily digest now (no push)")
    p.add_argument("--push-digest", action="store_true", help="emit + push daily digest to Operator")
    p.add_argument("--push-reviews", action="store_true", help="auto-promote ≥75 opps + push BUSINESS REVIEWs")
    p.add_argument("--health", action="store_true", help="run a health check now")
    args = p.parse_args()
    if args.tick:
        tick()
        return 0
    if args.loop:
        loop_forever()
        return 0
    if args.digest:
        info = _emit_daily_digest()
        print(json.dumps({"path": info["path"], "active": info["active"], "opportunities": info["opportunities"]}, indent=2))
        return 0
    if args.health:
        print(json.dumps(_health_check(), indent=2))
        return 0
    if args.push_reviews:
        print(json.dumps(_push_pending_reviews(), indent=2))
        return 0
    if args.push_digest:
        print(json.dumps(_push_daily_digest(), indent=2))
        return 0
    p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
