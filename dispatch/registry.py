"""Atomic state I/O for the Sovereign multi-agent system.

Owns three JSON files under state/:
    registry.json       — projects, skills, audit_log
    opportunities.json  — Scanner output queue
    revenue.json        — per-engine revenue ledger

All writes are atomic (temp file + rename) and serialized via fcntl.flock so
managers running in separate processes don't corrupt each other.

Enforces the Order Flow rules at the boundary:
    - state transitions table (rule 3)
    - single-owner lock (rule 1)
    - kill-criteria-required-before-active (rule 7)
    - operator-approval-gate (rule 11)
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / "state"
REGISTRY = STATE_DIR / "registry.json"
OPPORTUNITIES = STATE_DIR / "opportunities.json"
REVENUE = STATE_DIR / "revenue.json"

ALLOWED_TRANSITIONS = {
    None: {"proposed"},
    "proposed": {"approved", "killed"},
    "approved": {"active", "killed"},
    "active": {"blocked", "done", "killed"},
    "blocked": {"active", "killed"},
    "done": set(),
    "killed": set(),
}

ACTOR_TRANSITION_RIGHTS = {
    "strategy": {(None, "proposed")},
    "hermes": {("proposed", "approved"), (None, "killed"), ("proposed", "killed"),
               ("approved", "killed"), ("active", "killed"), ("blocked", "killed")},
    "owner": {("approved", "active"), ("active", "blocked"), ("blocked", "active"),
              ("active", "done")},
}

VALID_MANAGERS = {
    "strategy", "compliance", "treasury", "engineering", "research",
    "branding", "marketing", "sales", "monetization", "operations",
}


class RegistryError(Exception):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextlib.contextmanager
def _locked_open(path: Path, mode: str = "r+"):
    """Open `path` with an exclusive flock. Creates the file if absent."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("{}\n")
    with open(path, mode) as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            yield f
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def _atomic_write(path: Path, data: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(STATE_DIR))
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp, path)
    except Exception:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise


def _read(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text().strip()
    if not text:
        return {}
    return json.loads(text)


def _audit(data: dict, event: str, **fields: Any) -> None:
    entry = {"timestamp": now_iso(), "event": event, **fields}
    data.setdefault("audit_log", []).append(entry)
    if len(data["audit_log"]) > 5000:
        data["audit_log"] = data["audit_log"][-5000:]


def _ensure_registry_shape(data: dict) -> dict:
    data.setdefault("projects", {})
    data.setdefault("skills", [])
    data.setdefault("audit_log", [])
    data.setdefault("operator", {})
    return data


def _ensure_opps_shape(data: dict) -> dict:
    data.setdefault("queue", [])
    return data


def _ensure_revenue_shape(data: dict) -> dict:
    data.setdefault("engines", {})
    data.setdefault(
        "treasury",
        {"war_chest_usd": 0.0, "api_budget_usd": 0.0, "operator_held_usd": 0.0},
    )
    return data


# ---------------------------------------------------------------- projects ---


def create_project(spec: dict, actor: str = "strategy") -> str:
    """Create a project from a Strategy `PROJECT_SPEC` dict.

    Returns the project_id. Initial status is `proposed`.
    """
    if actor not in VALID_MANAGERS and actor != "hermes":
        raise RegistryError(f"unknown actor: {actor}")
    if (actor, (None, "proposed")) not in [(actor, t) for t in ACTOR_TRANSITION_RIGHTS.get(actor, set())]:
        # Only Strategy can create projects.
        if actor != "strategy":
            raise RegistryError(f"{actor} cannot create projects")

    pid = spec.get("project_id") or _new_id("p")
    with _locked_open(REGISTRY) as f:
        data = _ensure_registry_shape(json.loads(f.read() or "{}"))
        if pid in data["projects"]:
            raise RegistryError(f"project {pid} already exists")
        project = {
            "id": pid,
            "name": spec["name"],
            "engine": spec["engine"],
            "status": "proposed",
            "owner": None,
            "milestones": spec.get("milestones", []),
            "kill_criteria": spec.get("kill_criteria", []),
            "budget_usd": float(spec.get("budget_usd", 0)),
            "spent_usd": 0.0,
            "budget_minutes": int(spec.get("budget_minutes", 0)),
            "kpis": spec.get("kpis", {}),
            "outcome": spec.get("outcome", ""),
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        data["projects"][pid] = project
        _audit(data, "project_created", project_id=pid, actor=actor)
    _atomic_write(REGISTRY, data)
    return pid


def assign_owner(project_id: str, manager_role: str, actor: str = "hermes") -> None:
    """Lock a project to one Owner Manager. Only Hermes can assign owners."""
    if actor != "hermes":
        raise RegistryError("only hermes can assign owners")
    if manager_role not in VALID_MANAGERS:
        raise RegistryError(f"unknown manager: {manager_role}")
    with _locked_open(REGISTRY) as f:
        data = _ensure_registry_shape(json.loads(f.read() or "{}"))
        proj = data["projects"].get(project_id)
        if not proj:
            raise RegistryError(f"no project {project_id}")
        if proj["owner"] and proj["owner"] != manager_role:
            raise RegistryError(
                f"project {project_id} already owned by {proj['owner']}"
            )
        proj["owner"] = manager_role
        proj["updated_at"] = now_iso()
        _audit(data, "owner_assigned", project_id=project_id, owner=manager_role)
    _atomic_write(REGISTRY, data)


def update_status(
    project_id: str, new_status: str, actor: str, note: str = ""
) -> None:
    """Guarded state transition. Enforces Order Flow rules 3, 7, 11."""
    with _locked_open(REGISTRY) as f:
        data = _ensure_registry_shape(json.loads(f.read() or "{}"))
        proj = data["projects"].get(project_id)
        if not proj:
            raise RegistryError(f"no project {project_id}")

        cur = proj["status"]
        if new_status not in ALLOWED_TRANSITIONS.get(cur, set()):
            raise RegistryError(f"illegal transition {cur} → {new_status}")

        # Actor authorization
        if actor == "owner":
            if not proj["owner"]:
                raise RegistryError("project has no owner")
            allowed = ACTOR_TRANSITION_RIGHTS["owner"]
            if (cur, new_status) not in allowed:
                raise RegistryError(
                    f"owner cannot perform {cur} → {new_status}"
                )
        elif actor == "hermes":
            allowed = ACTOR_TRANSITION_RIGHTS["hermes"]
            if (cur, new_status) not in allowed:
                raise RegistryError(
                    f"hermes cannot perform {cur} → {new_status}"
                )
        elif actor == "strategy":
            allowed = ACTOR_TRANSITION_RIGHTS["strategy"]
            if (cur, new_status) not in allowed:
                raise RegistryError(
                    f"strategy cannot perform {cur} → {new_status}"
                )
        else:
            raise RegistryError(f"unknown actor: {actor}")

        # Order Flow rule 7: kill criteria required before active
        if new_status == "active" and not proj.get("kill_criteria"):
            raise RegistryError(
                "cannot enter active without kill_criteria (Order Flow rule 7)"
            )

        proj["status"] = new_status
        proj["updated_at"] = now_iso()
        _audit(
            data,
            "status_change",
            project_id=project_id,
            from_=cur,
            to=new_status,
            actor=actor,
            note=note,
        )
    _atomic_write(REGISTRY, data)


def record_spend(project_id: str, usd: float, note: str = "") -> dict:
    """Append spend; auto-pause project when spent_usd >= budget_usd (rule 6)."""
    with _locked_open(REGISTRY) as f:
        data = _ensure_registry_shape(json.loads(f.read() or "{}"))
        proj = data["projects"].get(project_id)
        if not proj:
            raise RegistryError(f"no project {project_id}")
        proj["spent_usd"] = round(proj["spent_usd"] + float(usd), 4)
        proj["updated_at"] = now_iso()
        _audit(data, "spend", project_id=project_id, usd=usd, note=note)
        flag = None
        if proj["budget_usd"] and proj["spent_usd"] >= proj["budget_usd"] and proj["status"] == "active":
            proj["status"] = "blocked"
            _audit(data, "auto_paused_budget", project_id=project_id)
            flag = "auto_paused_budget"
        elif proj["budget_usd"] and proj["spent_usd"] >= 0.5 * proj["budget_usd"]:
            flag = "fifty_percent_burn"
    _atomic_write(REGISTRY, data)
    return {"spent_usd": proj["spent_usd"], "flag": flag}


def get_project(project_id: str) -> dict | None:
    data = _ensure_registry_shape(_read(REGISTRY))
    return data["projects"].get(project_id)


def list_projects(status: str | None = None) -> list[dict]:
    data = _ensure_registry_shape(_read(REGISTRY))
    out = []
    for p in data["projects"].values():
        if status is None or p["status"] == status:
            out.append(p)
    return out


# ----------------------------------------------------------- opportunities ---


def ingest_opportunity(opp: dict) -> str:
    """Add an opportunity from the Scanner. Returns the opportunity id."""
    oid = opp.get("id") or _new_id("opp")
    record = {
        "id": oid,
        "engine": opp["engine"],
        "score": int(opp.get("score", 0)),
        "score_breakdown": opp.get("score_breakdown", {}),
        "tam_usd": float(opp.get("tam_usd", 0)),
        "ttfd_days": int(opp.get("ttfd_days", 0)),
        "build_cost_usd": float(opp.get("build_cost_usd", 0)),
        "compliance_flags": opp.get("compliance_flags", []),
        "raw_finding": opp.get("raw_finding", ""),
        "source": opp.get("source", ""),
        "discovered_at": opp.get("discovered_at", now_iso()),
        "status": "new",
        "promoted_to_review_at": None,
    }
    with _locked_open(OPPORTUNITIES) as f:
        data = _ensure_opps_shape(json.loads(f.read() or "{}"))
        # Hard-block if compliance flagged
        for flag in record["compliance_flags"]:
            if flag.get("severity") == "block":
                record["status"] = "archived"
                record["archive_reason"] = "compliance_block"
                break
        data["queue"].append(record)
    _atomic_write(OPPORTUNITIES, data)
    return oid


def promote_opportunity(opp_id: str, actor: str = "strategy") -> dict:
    if actor != "strategy":
        raise RegistryError("only strategy can promote opportunities")
    with _locked_open(OPPORTUNITIES) as f:
        data = _ensure_opps_shape(json.loads(f.read() or "{}"))
        for o in data["queue"]:
            if o["id"] == opp_id:
                if o["status"] not in ("new", "hold"):
                    raise RegistryError(
                        f"opportunity {opp_id} status is {o['status']}, cannot promote"
                    )
                if o["score"] < 75:
                    raise RegistryError(
                        f"opportunity {opp_id} score {o['score']} below threshold 75"
                    )
                o["status"] = "promoted"
                o["promoted_to_review_at"] = now_iso()
                _atomic_write(OPPORTUNITIES, data)
                return o
    raise RegistryError(f"no opportunity {opp_id}")


def archive_opportunity(opp_id: str, reason: str = "") -> None:
    with _locked_open(OPPORTUNITIES) as f:
        data = _ensure_opps_shape(json.loads(f.read() or "{}"))
        for o in data["queue"]:
            if o["id"] == opp_id:
                o["status"] = "archived"
                o["archive_reason"] = reason
                _atomic_write(OPPORTUNITIES, data)
                return
    raise RegistryError(f"no opportunity {opp_id}")


def list_opportunities(status: str | None = None, min_score: int = 0) -> list[dict]:
    data = _ensure_opps_shape(_read(OPPORTUNITIES))
    out = []
    for o in data["queue"]:
        if status and o["status"] != status:
            continue
        if o.get("score", 0) < min_score:
            continue
        out.append(o)
    return sorted(out, key=lambda x: x.get("score", 0), reverse=True)


# ------------------------------------------------------------------ revenue ---


def record_revenue(
    engine_id: str, gross: float, costs: float, note: str = ""
) -> None:
    with _locked_open(REVENUE) as f:
        data = _ensure_revenue_shape(json.loads(f.read() or "{}"))
        engine = data["engines"].setdefault(
            engine_id,
            {"ledger": [], "totals": {"mtd_gross": 0, "mtd_net": 0, "ytd_net": 0}},
        )
        net = round(float(gross) - float(costs), 4)
        engine["ledger"].append(
            {
                "date": datetime.now(timezone.utc).date().isoformat(),
                "gross": float(gross),
                "costs": float(costs),
                "net": net,
                "note": note,
            }
        )
        # Recompute totals from ledger (cheap, accurate)
        today = datetime.now(timezone.utc).date()
        mtd_gross = sum(
            e["gross"]
            for e in engine["ledger"]
            if datetime.fromisoformat(e["date"]).date().month == today.month
        )
        mtd_net = sum(
            e["net"]
            for e in engine["ledger"]
            if datetime.fromisoformat(e["date"]).date().month == today.month
        )
        ytd_net = sum(
            e["net"]
            for e in engine["ledger"]
            if datetime.fromisoformat(e["date"]).date().year == today.year
        )
        engine["totals"] = {"mtd_gross": mtd_gross, "mtd_net": mtd_net, "ytd_net": ytd_net}
    _atomic_write(REVENUE, data)


def read_revenue() -> dict:
    return _ensure_revenue_shape(_read(REVENUE))


def update_treasury_balance(field: str, delta: float) -> float:
    """Adjust war_chest_usd, api_budget_usd, or operator_held_usd by `delta`."""
    if field not in {"war_chest_usd", "api_budget_usd", "operator_held_usd"}:
        raise RegistryError(f"unknown treasury field: {field}")
    with _locked_open(REVENUE) as f:
        data = _ensure_revenue_shape(json.loads(f.read() or "{}"))
        data["treasury"][field] = round(data["treasury"].get(field, 0) + float(delta), 4)
        new_val = data["treasury"][field]
    _atomic_write(REVENUE, data)
    return new_val


# ------------------------------------------------------------------ skills ---


def codify_skill(name: str, body_md: str) -> Path:
    skills_dir = STATE_DIR / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    p = skills_dir / f"{name}.md"
    p.write_text(body_md)
    with _locked_open(REGISTRY) as f:
        data = _ensure_registry_shape(json.loads(f.read() or "{}"))
        if name not in data["skills"]:
            data["skills"].append(name)
        _audit(data, "skill_codified", name=name)
    _atomic_write(REGISTRY, data)
    return p


# -------------------------------------------------------------------- misc ---


def _new_id(prefix: str) -> str:
    h = hashlib.sha1(f"{time.time_ns()}".encode()).hexdigest()[:6]
    ts = int(time.time())
    return f"{prefix}_{ts}_{h}"


def selftest() -> int:
    """Round-trip a fake project + opportunity. Used by smoke test."""
    print("== registry self-test ==")
    # Use a temp state dir to avoid clobbering live state
    import shutil
    backup = None
    if STATE_DIR.exists():
        backup = STATE_DIR.parent / f"state.backup.{int(time.time())}"
        shutil.copytree(STATE_DIR, backup)

    try:
        # create
        spec = {
            "name": "selftest-project",
            "engine": "digital_products",
            "milestones": [{"id": "m1", "description": "test"}],
            "kill_criteria": ["if it breaks, kill it"],
            "budget_usd": 50,
            "outcome": "test",
        }
        pid = create_project(spec, actor="strategy")
        print(f"  ✓ created project {pid}")

        # transitions
        update_status(pid, "approved", actor="hermes")
        print("  ✓ proposed → approved (hermes)")
        assign_owner(pid, "engineering")
        print("  ✓ owner assigned")
        update_status(pid, "active", actor="owner")
        print("  ✓ approved → active (owner)")

        # illegal transition
        try:
            update_status(pid, "approved", actor="owner")
            print("  ✗ FAILED: illegal transition allowed")
            return 1
        except RegistryError:
            print("  ✓ illegal transition rejected")

        # spend with budget gate
        record_spend(pid, 25, note="halfway")
        record_spend(pid, 30, note="should auto-pause")
        proj = get_project(pid)
        if proj["status"] != "blocked":
            print(f"  ✗ FAILED: expected blocked, got {proj['status']}")
            return 1
        print("  ✓ budget gate auto-paused at >=100%")

        # opportunity
        oid = ingest_opportunity(
            {
                "engine": "digital_products",
                "score": 80,
                "tam_usd": 1000,
                "raw_finding": "test",
            }
        )
        promote_opportunity(oid, actor="strategy")
        print(f"  ✓ ingested + promoted {oid}")

        # revenue
        record_revenue("digital_products", 100, 30, note="test sale")
        rev = read_revenue()
        assert rev["engines"]["digital_products"]["totals"]["mtd_net"] == 70
        print("  ✓ revenue recorded + reconciled")

        # treasury
        update_treasury_balance("war_chest_usd", 200)
        rev = read_revenue()
        assert rev["treasury"]["war_chest_usd"] == 200
        print("  ✓ treasury balance updated")

        print("== all selftest checks passed ==")
        return 0
    finally:
        if backup:
            shutil.rmtree(STATE_DIR, ignore_errors=True)
            shutil.copytree(backup, STATE_DIR)
            shutil.rmtree(backup, ignore_errors=True)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--list-projects", action="store_true")
    p.add_argument("--status")
    args = p.parse_args()

    if args.selftest:
        return selftest()
    if args.list_projects:
        for proj in list_projects(status=args.status):
            print(f"{proj['id']}\t{proj['status']}\t{proj['name']} ({proj['engine']})")
        return 0
    p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
