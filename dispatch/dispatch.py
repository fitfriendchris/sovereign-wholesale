"""Top-level dispatch module.

Routes briefs to managers/workers via:
  1. OpenClaw if configured (env: OPENCLAW_MODE = "cli" | "http")
  2. OpenRouter direct as a fallback (always available given API key)

Exposes the function set Hermes and the Managers call:
    assign_owner, dispatch_brief, dispatch_worker, collect_reports,
    update_status, codify_skill, ingest_opportunity, promote_to_review,
    record_revenue, read_omni_pnl

Role → default model mapping is defined in MODEL_BY_ROLE; override via .env.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from dispatch import openrouter_client, registry

ROOT = Path(__file__).resolve().parent.parent
PROMPTS = ROOT / "prompts"
INBOX = ROOT / "state" / "inbox"
OUTBOX = ROOT / "state" / "outbox"
LOGS = ROOT / "state" / "logs"

# ---------------------------------------------------------- model routing ---

MODEL_BY_ROLE = {
    # Strategic tier — reasoning-heavy
    "strategy":     "sonnet-4.6",
    "compliance":   "sonnet-4.6",
    "treasury":     "sonnet-4.6",
    "monetization": "sonnet-4.6",
    # Build tier
    "engineering":  "sonnet-4.6",
    "branding":     "sonnet-4.6",
    # Growth tier — volume-heavy, cheaper models
    "research":         "kimi-2.6",
    "research_scanner": "kimi-2.6",   # local Ollama — free, fast, good at brainstorm
    "marketing":        "kimi-k2",     # OpenRouter Kimi — production volume
    "sales":            "kimi-k2",
    # Run tier
    "operations": "sonnet-4.6",
    # Worker default
    "worker": "haiku-4.5",
}

# When OpenClaw is the dispatch backend, friendly aliases get translated to the
# provider/model strings OpenClaw's catalog actually knows. OpenRouter is wired
# into OpenClaw, so Claude/Kimi models route through openrouter/...
OPENCLAW_MODEL_MAP = {
    "kimi-k2":    "openrouter/moonshotai/kimi-k2",
    "kimi-2.6":   "ollama/kimi-k2.6:cloud",   # local Ollama path for Hermes
    "haiku-4.5":  "openrouter/anthropic/claude-haiku-4.5",
    "sonnet-4.6": "openrouter/anthropic/claude-sonnet-4.6",
    "opus-4.7":   "openrouter/anthropic/claude-opus-4.7",
}


def model_for(role: str, complexity: str = "normal") -> str:
    """Pick a model for a given role. `complexity=hard` bumps to opus where applicable."""
    base = MODEL_BY_ROLE.get(role, "haiku-4.5")
    if complexity == "hard" and role == "engineering":
        return "opus-4.7"
    if complexity == "hard" and base == "haiku-4.5":
        return "sonnet-4.6"
    return base


def _resolve_openclaw_model(alias: str) -> str:
    """Translate a friendly alias to OpenClaw's provider/model string."""
    if "/" in alias:
        return alias  # already provider/model
    return OPENCLAW_MODEL_MAP.get(alias, "ollama/kimi-k2.6:cloud")


# ----------------------------------------------------- OpenClaw integration ---


def _openclaw_mode() -> str:
    openrouter_client._load_env()
    return os.environ.get("OPENCLAW_MODE", "off").strip().lower()


def _call_openclaw(model: str, system: str, user: str) -> dict | None:
    """Try OpenClaw. Return result dict on success, None to signal fall-through.

    For mode=cli, shells out to:
        openclaw infer model run --gateway --json --model <provider/model> --prompt <text>

    OpenClaw's `infer model run` doesn't accept a separate --system flag, so we
    concatenate system+user into one prompt with a clear delimiter. Long prompts
    (>~100KB) may exceed argv limits — Sovereign workers stay well under that.
    """
    mode = _openclaw_mode()
    if mode == "off":
        return None

    if mode == "cli":
        provider_model = _resolve_openclaw_model(model)
        prompt = f"{system}\n\n--- USER MESSAGE ---\n{user}"
        try:
            res = subprocess.run(
                [
                    "openclaw", "infer", "model", "run",
                    "--gateway",
                    "--json",
                    "--model", provider_model,
                    "--prompt", prompt,
                ],
                capture_output=True, text=True, timeout=600,  # 10 min — long Sonnet outputs
            )
            if res.returncode != 0:
                _log("openclaw_cli_fail",
                     stderr=res.stderr[-2000:], model=provider_model)
                return None
            stdout = res.stdout.strip()
            text = stdout
            cost = 0.0
            usage: dict = {}
            try:
                data = json.loads(stdout)
                # OpenClaw `infer model run --json` returns:
                #   {"ok":true, "outputs":[{"text":"...", "mediaUrl":null}], ...}
                outputs = data.get("outputs") or []
                if outputs and isinstance(outputs, list):
                    text = outputs[0].get("text") or outputs[0].get("content") or stdout
                else:
                    text = (
                        data.get("text")
                        or data.get("output")
                        or data.get("content")
                        or data.get("message", {}).get("content")
                        or stdout
                    )
                cost = float(data.get("cost", 0) or data.get("cost_usd", 0) or 0)
                usage = data.get("usage", {}) or {}
            except json.JSONDecodeError:
                pass
            return {
                "text": text if isinstance(text, str) else json.dumps(text),
                "via": f"openclaw-cli({provider_model})",
                "cost_usd": cost,
                "usage": usage,
            }
        except FileNotFoundError:
            _log("openclaw_cli_missing")
            return None
        except subprocess.TimeoutExpired:
            _log("openclaw_cli_timeout", model=provider_model)
            return None
        except Exception as e:
            _log("openclaw_cli_error", err=str(e))
            return None

    if mode == "http":
        url = os.environ.get("OPENCLAW_URL", "").strip()
        if not url:
            return None
        body = {"model": model, "system": system, "user": user}
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {os.environ.get('OPENCLAW_KEY', '')}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode())
            return {
                "text": data.get("text") or data.get("content", ""),
                "via": "openclaw-http",
                "cost_usd": float(data.get("cost_usd", 0)),
            }
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            _log("openclaw_http_fail", err=str(e))
            return None

    return None


def _log(event: str, **fields: Any) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    line = json.dumps({"ts": time.time(), "event": event, **fields}) + "\n"
    (LOGS / "dispatch.log").open("a").write(line)


# ---------------------------------------------------- public dispatch funcs ---


def call(role: str, system: str, user: str, complexity: str = "normal") -> dict:
    """Single LLM call routed via OpenClaw → OpenRouter. Returns dict with `text`."""
    model = model_for(role, complexity)
    result = _call_openclaw(model, system, user)
    if result is None:
        result = openrouter_client.chat(model, system, user)
        result["via"] = "openrouter"
    _log("call", role=role, model=model, via=result.get("via"), cost=result.get("cost_usd"))
    return result


def assign_owner(project_id: str, manager_role: str) -> None:
    """Hermes-only: lock a project to one Owner Manager."""
    registry.assign_owner(project_id, manager_role, actor="hermes")
    _log("assign_owner", project_id=project_id, owner=manager_role)


def dispatch_brief(project_id: str, brief_md: str, manager_role: str) -> Path:
    """Write a brief to the manager's inbox; the manager runtime polls there."""
    inbox = INBOX / project_id
    inbox.mkdir(parents=True, exist_ok=True)
    p = inbox / f"brief_{manager_role}.md"
    p.write_text(brief_md)
    _log("dispatch_brief", project_id=project_id, manager=manager_role, path=str(p))
    return p


def dispatch_worker(
    project_id: str,
    role: str,
    task: str,
    system_prompt: str | None = None,
    max_cost_usd: float = 0.10,
    complexity: str = "normal",
) -> dict:
    """Spawn a one-shot worker. Returns the worker output + cost."""
    if system_prompt is None:
        wt = PROMPTS / "workers" / "worker_template.md"
        system_prompt = wt.read_text() if wt.exists() else "You are a stateless worker."
    result = call(role, system_prompt, task, complexity=complexity)
    # Persist the output
    if project_id != "_adhoc":
        wid = f"w_{int(time.time_ns())%10**8:08d}"
        d = OUTBOX / project_id / "workers" / wid
        d.mkdir(parents=True, exist_ok=True)
        (d / "result.md").write_text(result["text"])
        (d / "cost.json").write_text(
            json.dumps({"cost_usd": result.get("cost_usd", 0), "via": result.get("via")})
        )
        # Charge spend to the project
        try:
            registry.record_spend(
                project_id, float(result.get("cost_usd", 0)), note=f"worker {wid}"
            )
        except registry.RegistryError:
            pass
    return result


def collect_reports(project_id: str) -> list[dict]:
    """Read all manager + worker outputs for a project."""
    out_dir = OUTBOX / project_id
    if not out_dir.exists():
        return []
    reports = []
    for md in out_dir.rglob("*.md"):
        reports.append({"path": str(md), "content": md.read_text()})
    return reports


def update_status(project_id: str, new_status: str, actor: str, note: str = "") -> None:
    registry.update_status(project_id, new_status, actor=actor, note=note)
    _log("update_status", project_id=project_id, new=new_status, actor=actor)


def codify_skill(name: str, body_md: str) -> Path:
    p = registry.codify_skill(name, body_md)
    _log("codify_skill", name=name)
    return p


def ingest_opportunity(opp: dict) -> str:
    return registry.ingest_opportunity(opp)


def promote_to_review(opportunity_id: str) -> dict:
    return registry.promote_opportunity(opportunity_id, actor="strategy")


def record_revenue(engine_id: str, gross: float, costs: float, note: str = "") -> None:
    registry.record_revenue(engine_id, gross, costs, note=note)


def read_omni_pnl() -> dict:
    """Read Omni's daily PnL. Read-only (Order Flow rule 10).

    Looks for the Omni status JSON in known locations. Returns an empty dict if
    Omni isn't running or its files aren't reachable.
    """
    candidates = [
        Path.home() / "Library" / "Application Support" / "net.metaquotes.wine.metatrader5"
        / "drive_c" / "users" / "user" / "AppData" / "Roaming" / "MetaQuotes"
        / "Terminal" / "Common" / "Files" / "omni_status.json",
        Path("/Users/yuhfriendchris/Desktop/Omni-full-ALGO-Trading-Bot/state.json"),
    ]
    for c in candidates:
        if c.exists():
            try:
                return json.loads(c.read_text())
            except Exception:
                continue
    return {}


# ---------------------------------------------------------------- selftest ---


def selftest() -> int:
    print("== dispatch self-test ==")
    print(f"  OPENCLAW_MODE = {_openclaw_mode()}")
    print(f"  default model for engineering = {model_for('engineering')}")
    print(f"  default model for sales       = {model_for('sales')}")
    print(f"  default model for worker      = {model_for('worker')}")

    # Try a real call (cheap)
    try:
        res = call(
            "research_scanner",
            "Reply with exactly: ok",
            "Just reply: ok",
        )
        ok = res["text"].strip().lower().startswith("ok")
        print(f"  ✓ live call via {res.get('via')} (cost ${res.get('cost_usd', 0):.6f}) — reply ok? {ok}")
    except Exception as e:
        print(f"  ⚠ live call failed: {e}")
        print("    (this is expected if .env has no OPENROUTER_API_KEY)")

    # Try a worker dispatch (no-op project)
    try:
        res = dispatch_worker("_adhoc", "research_scanner", "Reply with exactly: ok")
        print(f"  ✓ worker dispatch ok via {res.get('via')}")
    except Exception as e:
        print(f"  ⚠ worker dispatch failed: {e}")

    print("== dispatch self-test complete ==")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--selftest", action="store_true")
    args = p.parse_args()
    if args.selftest:
        return selftest()
    p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
