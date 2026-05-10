"""Treasury — capital allocation engine.

Runs weekly (default Sundays 23:00 local). Reads state/revenue.json, computes
allocations per docs/capital_allocation.md, flags negative-margin engines, and
writes a TREASURY ACTION REQUEST to state/outbox/treasury/<date>.md for Hermes.

Treasury never moves real money — it computes and reports. The Operator executes.

CLI:
    python -m dispatch.treasury --reconcile         # one weekly pass
    python -m dispatch.treasury --status            # current balances
    python -m dispatch.treasury --set <splits>      # update splits
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dispatch import dispatch, registry

ROOT = Path(__file__).resolve().parent.parent
OUTBOX = ROOT / "state" / "outbox" / "treasury"
LOGS = ROOT / "state" / "logs"
SPLITS_FILE = ROOT / "state" / "treasury_splits.json"

DEFAULT_SPLITS = {
    "operator": 0.50,
    "reinvest": 0.30,
    "war_chest": 0.15,
    "api_budget": 0.05,
}

NEGATIVE_MARGIN_PAUSE_DAYS = 14
LOW_API_BUDGET_FACTOR = 2.0  # alert if balance < weekly_burn * factor


def load_splits() -> dict:
    if SPLITS_FILE.exists():
        try:
            data = json.loads(SPLITS_FILE.read_text())
            if abs(sum(data.values()) - 1.0) < 1e-6:
                return data
        except json.JSONDecodeError:
            pass
    return dict(DEFAULT_SPLITS)


def save_splits(splits: dict) -> None:
    if abs(sum(splits.values()) - 1.0) > 1e-6:
        raise ValueError("splits must sum to 1.0")
    SPLITS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SPLITS_FILE.write_text(json.dumps(splits, indent=2) + "\n")


# ---------------------------------------------------------- per-engine ops ---


def _engine_recent_net(engine_id: str, days: int) -> float:
    rev = registry.read_revenue()
    eng = rev["engines"].get(engine_id)
    if not eng:
        return 0.0
    cutoff = (datetime.now(timezone.utc).date() - timedelta(days=days)).isoformat()
    return sum(e["net"] for e in eng.get("ledger", []) if e["date"] >= cutoff)


def _negative_margin_engines() -> list[str]:
    """Return engine_ids with consecutive net loss across NEGATIVE_MARGIN_PAUSE_DAYS."""
    rev = registry.read_revenue()
    out = []
    for eid, eng in rev["engines"].items():
        ledger = eng.get("ledger", [])
        if not ledger:
            continue
        cutoff = (
            datetime.now(timezone.utc).date()
            - timedelta(days=NEGATIVE_MARGIN_PAUSE_DAYS)
        ).isoformat()
        recent = [e for e in ledger if e["date"] >= cutoff]
        if len(recent) >= NEGATIVE_MARGIN_PAUSE_DAYS // 2 and all(e["net"] < 0 for e in recent):
            out.append(eid)
    return out


def _weekly_summary() -> dict:
    rev = registry.read_revenue()
    cutoff = (datetime.now(timezone.utc).date() - timedelta(days=7)).isoformat()
    summary = {"per_engine": {}, "total_gross": 0.0, "total_costs": 0.0, "total_net": 0.0}
    for eid, eng in rev["engines"].items():
        gross = sum(e["gross"] for e in eng.get("ledger", []) if e["date"] >= cutoff)
        costs = sum(e["costs"] for e in eng.get("ledger", []) if e["date"] >= cutoff)
        net = sum(e["net"] for e in eng.get("ledger", []) if e["date"] >= cutoff)
        summary["per_engine"][eid] = {"gross": gross, "costs": costs, "net": net}
        summary["total_gross"] += gross
        summary["total_costs"] += costs
        summary["total_net"] += net
    return summary


# ---------------------------------------------------------- reconciliation ---


def reconcile(persist: bool = True) -> dict:
    """One weekly reconciliation pass. Returns the action-request dict."""
    rev = registry.read_revenue()
    splits = load_splits()
    summary = _weekly_summary()
    net = summary["total_net"]

    # Allocations are computed only on positive net (negative net doesn't refund anything;
    # losses just don't generate Operator distribution).
    allocations = {k: 0.0 for k in splits}
    if net > 0:
        for k, pct in splits.items():
            allocations[k] = round(net * pct, 4)

    # Persist treasury balance changes (computed; no real money moved).
    if persist and net > 0:
        registry.update_treasury_balance("war_chest_usd", allocations["war_chest"])
        registry.update_treasury_balance("operator_held_usd", allocations["operator"])
        registry.update_treasury_balance("api_budget_usd", allocations["api_budget"])
        # Reinvest goes back to engine via record_revenue note (not a balance change here)

    # Flags
    flags = []
    neg_engines = _negative_margin_engines()
    for eid in neg_engines:
        flags.append({"type": "negative_margin", "engine": eid, "days": NEGATIVE_MARGIN_PAUSE_DAYS})

    api_balance = rev.get("treasury", {}).get("api_budget_usd", 0)
    weekly_burn = max(summary["total_costs"], 0.01)
    if api_balance < weekly_burn * LOW_API_BUDGET_FACTOR:
        flags.append({
            "type": "api_budget_low",
            "balance_usd": api_balance,
            "weekly_burn_usd": weekly_burn,
            "recommended_topup_usd": round(weekly_burn * 4, 2),
        })

    request = {
        "type": "TREASURY_ACTION_REQUEST",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "week_summary": summary,
        "allocations": allocations,
        "splits": splits,
        "balances": rev.get("treasury", {}),
        "flags": flags,
        "actions": _build_actions(allocations, flags),
    }

    if persist:
        OUTBOX.mkdir(parents=True, exist_ok=True)
        out_path = OUTBOX / f"weekly_{datetime.now(timezone.utc).date().isoformat()}.md"
        out_path.write_text(_format_request_md(request))
        # Also drop a JSON copy for Hermes / other readers
        (OUTBOX / f"weekly_{datetime.now(timezone.utc).date().isoformat()}.json").write_text(
            json.dumps(request, indent=2) + "\n"
        )
        _log("reconcile", **{k: v for k, v in request.items() if k != "week_summary"})

    return request


def _build_actions(allocations: dict, flags: list[dict]) -> list[dict]:
    actions: list[dict] = []
    if allocations["operator"] > 0:
        actions.append({
            "command": "/treasury distribute",
            "description": f"Transfer ${allocations['operator']:.2f} to Operator account",
        })
    for f in flags:
        if f["type"] == "api_budget_low":
            actions.append({
                "command": "/treasury topup",
                "description": f"Top up OpenRouter by ~${f['recommended_topup_usd']:.2f}",
            })
        if f["type"] == "negative_margin":
            actions.append({
                "command": f"/treasury pause {f['engine']}",
                "description": f"Pause {f['engine']} (net loss for {f['days']} days)",
            })
    return actions


def _format_request_md(req: dict) -> str:
    lines = [
        "# TREASURY ACTION REQUEST",
        f"generated_at: {req['generated_at']}",
        "",
        "## Week summary",
        f"- Total gross:  ${req['week_summary']['total_gross']:.2f}",
        f"- Total costs:  ${req['week_summary']['total_costs']:.2f}",
        f"- Total net:    ${req['week_summary']['total_net']:.2f}",
        "",
        "## Per engine (net)",
    ]
    for eid, e in req["week_summary"]["per_engine"].items():
        lines.append(f"- {eid}: ${e['net']:.2f}")
    lines += [
        "",
        f"## Allocation (splits = {req['splits']})",
    ]
    for k, v in req["allocations"].items():
        lines.append(f"- {k}: ${v:.2f}")
    lines += ["", "## Balances after this allocation"]
    for k, v in req["balances"].items():
        lines.append(f"- {k}: ${v:.4f}")
    lines += ["", "## Flags"]
    if not req["flags"]:
        lines.append("- (none)")
    for f in req["flags"]:
        lines.append(f"- {f}")
    lines += ["", "## Actions requested"]
    if not req["actions"]:
        lines.append("- (none)")
    for a in req["actions"]:
        lines.append(f"- `{a['command']}` — {a['description']}")
    return "\n".join(lines) + "\n"


def _log(event: str, **fields) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    line = json.dumps({"ts": datetime.now(timezone.utc).isoformat(), "event": event, **fields}, default=str) + "\n"
    (LOGS / "treasury.log").open("a").write(line)


# -------------------------------------------------------------- pause logic ---


def pause_engine(engine_id: str, actor: str = "operator") -> int:
    """Move every active project of `engine_id` to blocked. Returns count."""
    paused = 0
    for proj in registry.list_projects(status="active"):
        if proj.get("engine") == engine_id:
            registry.update_status(
                proj["id"], "blocked", actor="hermes",
                note=f"engine paused by {actor}"
            )
            paused += 1
    _log("pause_engine", engine=engine_id, paused=paused, actor=actor)
    return paused


# ------------------------------------------------------------------ CLI ---


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--reconcile", action="store_true")
    p.add_argument("--status", action="store_true")
    p.add_argument("--no-persist", action="store_true")
    p.add_argument("--set", nargs="+", help="e.g. operator=0.6 reinvest=0.25 war_chest=0.10 api_budget=0.05")
    p.add_argument("--pause-engine")
    args = p.parse_args()

    if args.set:
        new = {}
        for kv in args.set:
            k, _, v = kv.partition("=")
            new[k.strip()] = float(v)
        save_splits(new)
        print(f"saved splits: {new}")
        return 0

    if args.pause_engine:
        n = pause_engine(args.pause_engine, actor="cli")
        print(f"paused {n} active project(s) of engine {args.pause_engine}")
        return 0

    if args.reconcile:
        req = reconcile(persist=not args.no_persist)
        print(_format_request_md(req))
        return 0

    if args.status:
        rev = registry.read_revenue()
        print(json.dumps({"treasury": rev.get("treasury", {}), "splits": load_splits()}, indent=2))
        return 0

    p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
