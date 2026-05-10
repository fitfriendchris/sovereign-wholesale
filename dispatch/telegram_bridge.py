"""Telegram ↔ Hermes pipe.

Inbound:  Operator messages on Telegram → routed to deterministic command handlers
          (slash commands) or to Hermes (Kimi 2.6 via Ollama) for free-form text.

Outbound: send_text(), send_digest(), send_decision_request() — used by Hermes,
          scheduler, treasury to push to the Operator.

Reads pending outbox/hermes/*.md files (e.g. daily digests) and pushes any
unsent ones to Telegram once per tick.

CLI:
    python -m dispatch.telegram_bridge --ping       # send "pong" round-trip test
    python -m dispatch.telegram_bridge --send TEXT  # send arbitrary text
    python -m dispatch.telegram_bridge --loop       # long-poll forever
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from dispatch import dispatch, registry, scanner, treasury

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "state" / "logs"
HERMES_OUTBOX = ROOT / "state" / "outbox" / "hermes"
SENT_MARKER = ROOT / "state" / "logs" / "telegram_sent.json"
OFFSET_FILE = ROOT / "state" / "logs" / "telegram_offset.txt"

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "kimi-k2-0905")


def _load_env() -> None:
    """Load .env once; defer key access until needed."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _bot_token() -> str:
    _load_env()
    t = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not t:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set in .env")
    return t


def _operator_chat_id() -> str:
    _load_env()
    cid = os.environ.get("TELEGRAM_OPERATOR_CHAT_ID", "").strip()
    if not cid:
        raise RuntimeError("TELEGRAM_OPERATOR_CHAT_ID not set in .env")
    return cid


def _api(method: str, params: dict | None = None, timeout: int = 30) -> dict:
    url = f"https://api.telegram.org/bot{_bot_token()}/{method}"
    if params is not None:
        url += "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"http {e.code}: {e.read().decode()[:300]}"}
    except urllib.error.URLError as e:
        return {"ok": False, "error": f"network: {e.reason}"}


# -------------------------------------------------------------- outbound ---


def _telegram_via() -> str:
    """Choose outbound transport: 'openclaw' (default) or 'direct' (own bot)."""
    _load_env()
    return os.environ.get("TELEGRAM_VIA", "openclaw").strip().lower()


def _openclaw_account() -> str:
    _load_env()
    return os.environ.get("OPENCLAW_TG_ACCOUNT", "jarvis").strip()


def _send_via_openclaw(text: str, chat_id: str) -> dict:
    """Use `openclaw message send` to push outbound through OpenClaw's gateway."""
    import subprocess
    try:
        res = subprocess.run(
            [
                "openclaw", "message", "send",
                "--channel", "telegram",
                "--account", _openclaw_account(),
                "--target", str(chat_id),
                "--message", text[:4000],
                "--json",
            ],
            capture_output=True, text=True, timeout=30,
        )
        if res.returncode != 0:
            return {"ok": False, "error": f"openclaw exit {res.returncode}: {res.stderr[-300:]}"}
        try:
            return json.loads(res.stdout) | {"via": "openclaw"}
        except json.JSONDecodeError:
            return {"ok": True, "raw": res.stdout.strip()[:200], "via": "openclaw"}
    except FileNotFoundError:
        return {"ok": False, "error": "openclaw CLI not installed"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "openclaw send timed out"}


def send_text(text: str, chat_id: str | None = None) -> dict:
    cid = chat_id or _operator_chat_id()
    if _telegram_via() == "openclaw":
        return _send_via_openclaw(text, cid)
    text = text[:4000]
    return _api("sendMessage", {"chat_id": cid, "text": text})


def send_decision_request(text: str, chat_id: str | None = None) -> dict:
    return send_text(f"⚡ DECISION NEEDED\n\n{text}", chat_id)


def push_pending_outbox() -> int:
    """Push any unsent files from state/outbox/hermes/. Returns count sent."""
    HERMES_OUTBOX.mkdir(parents=True, exist_ok=True)
    sent_index = _load_sent_index()
    n = 0
    for f in sorted(HERMES_OUTBOX.glob("*.md")):
        key = str(f.relative_to(ROOT))
        if key in sent_index:
            continue
        send_text(f.read_text())
        sent_index[key] = datetime.now(timezone.utc).isoformat()
        n += 1
    _save_sent_index(sent_index)
    return n


def _load_sent_index() -> dict:
    if not SENT_MARKER.exists():
        return {}
    try:
        return json.loads(SENT_MARKER.read_text())
    except json.JSONDecodeError:
        return {}


def _save_sent_index(idx: dict) -> None:
    SENT_MARKER.parent.mkdir(parents=True, exist_ok=True)
    SENT_MARKER.write_text(json.dumps(idx, indent=2) + "\n")


# -------------------------------------------------------------- inbound ---


def _read_offset() -> int:
    if OFFSET_FILE.exists():
        try:
            return int(OFFSET_FILE.read_text().strip() or "0")
        except ValueError:
            return 0
    return 0


def _save_offset(off: int) -> None:
    OFFSET_FILE.parent.mkdir(parents=True, exist_ok=True)
    OFFSET_FILE.write_text(str(off))


def poll_once(timeout: int = 25) -> int:
    """Long-poll Telegram once. Returns number of messages handled."""
    offset = _read_offset()
    res = _api("getUpdates", {"offset": offset, "timeout": timeout}, timeout=timeout + 5)
    if not res.get("ok"):
        _log("poll_error", err=res.get("error"))
        return 0
    handled = 0
    for upd in res.get("result", []):
        offset = max(offset, upd["update_id"] + 1)
        msg = upd.get("message") or upd.get("edited_message")
        if not msg:
            continue
        chat_id = str(msg["chat"]["id"])
        if chat_id != _operator_chat_id():
            send_text("This bot is private.", chat_id=chat_id)
            continue
        text = (msg.get("text") or "").strip()
        if not text:
            continue
        try:
            reply = handle_message(text)
            if reply:
                send_text(reply)
        except Exception as e:
            _log("handle_exception", err=str(e), text=text[:200])
            send_text(f"⚠ error handling that: {e}")
        handled += 1
    _save_offset(offset)
    return handled


# --------------------------------------------------- command dispatcher ---


def handle_message(text: str) -> str:
    """Route Operator message. Slash commands are deterministic; rest goes to Hermes."""
    s = text.strip()

    if s in ("yes", "no", "edit", "hold") or s.startswith(("yes ", "no ", "edit ", "hold ")):
        return _handle_review_reply(s)

    if s.startswith("/"):
        cmd, _, rest = s[1:].partition(" ")
        cmd = cmd.lower()
        return _handle_slash(cmd, rest.strip())

    # Free-form → Hermes
    return _ask_hermes(s)


def _handle_review_reply(s: str) -> str:
    head, _, note = s.partition(" ")
    decision = head.lower()
    # Find most-recent promoted opportunity
    queue = registry.list_opportunities(status="promoted")
    if not queue:
        return "No open Business Review to respond to. Use /inbox to see what's pending."
    target = sorted(queue, key=lambda o: o.get("promoted_to_review_at", ""), reverse=True)[0]
    oid = target["id"]
    if decision == "yes":
        # Spec a project from the opportunity (Strategy normally; we shortcut here)
        spec = {
            "name": f"{target['engine']}-{oid[-6:]}",
            "engine": target["engine"],
            "outcome": target["raw_finding"][:140],
            "kill_criteria": ["if no revenue in 30d", "if compliance flag escalates"],
            "milestones": [],
            "budget_usd": min(target.get("build_cost_usd", 100) * 1.5, 500),
        }
        pid = registry.create_project(spec, actor="strategy")
        registry.update_status(pid, "approved", actor="hermes",
                                note=f"operator yes on {oid}")
        registry.archive_opportunity(oid, reason=f"approved → {pid}")
        return f"✓ approved. Project {pid} created. Hermes will pick an Owner Manager next tick."
    if decision == "no":
        registry.archive_opportunity(oid, reason=f"operator_no: {note or 'no reason given'}")
        return f"✓ archived {oid}."
    if decision == "hold":
        registry.archive_opportunity(oid, reason=f"hold_until_+7d: {note}")
        return f"✓ {oid} held for 7 days."
    if decision == "edit":
        return f"Edits noted: {note or '(empty)'}. Hermes will redraft and re-ask."
    return "Reply: yes / no / edit / hold"


def _handle_slash(cmd: str, rest: str) -> str:
    if cmd == "help":
        return _help_text()
    if cmd == "ping":
        return "pong"
    if cmd == "digest":
        from dispatch.scheduler import _emit_daily_digest
        info = _emit_daily_digest()
        # Read it back and return
        return Path(info["path"]).read_text()[:3800]
    if cmd == "inbox":
        opps = registry.list_opportunities(status="promoted")
        if not opps:
            return "Inbox empty."
        lines = ["Pending Business Reviews:"]
        for o in opps[:10]:
            lines.append(f"  {o['id']} [{o['engine']}] score={o['score']}")
            lines.append(f"    {o['raw_finding'][:200]}")
        return "\n".join(lines)
    if cmd == "show" and rest:
        for o in registry.list_opportunities():
            if o["id"] == rest:
                return json.dumps(o, indent=2)[:3800]
        return f"No opportunity {rest}."
    if cmd == "projects":
        ps = registry.list_projects()
        if not ps:
            return "No projects yet."
        lines = []
        for p in ps:
            lines.append(f"{p['id']} | {p['status']:8s} | {p['engine']:20s} | ${p['spent_usd']:.2f} / ${p['budget_usd']:.2f} | {p['name']}")
        return "\n".join(lines)
    if cmd == "audit":
        n = int(rest.split()[-1]) if rest else 10
        data = registry._read(registry.REGISTRY)
        events = data.get("audit_log", [])[-n:]
        return "\n".join(json.dumps(e) for e in events) or "(empty)"
    if cmd == "scanner":
        return _scanner_command(rest)
    if cmd == "treasury":
        return _treasury_command(rest)
    if cmd == "kill" and rest:
        try:
            registry.update_status(rest, "killed", actor="hermes", note="operator /kill")
            return f"✓ killed {rest}"
        except registry.RegistryError as e:
            return f"✗ {e}"
    if cmd == "project":
        return _project_command(rest)
    if cmd == "dispatch":
        return _dispatch_command(rest)
    if cmd == "jarvis":
        return _jarvis_delegate(rest)
    return f"Unknown command /{cmd}. Try /help."


def _jarvis_delegate(task: str) -> str:
    """Hermes delegates a task to Jarvis (the OpenClaw `main` agent).

    Jarvis is Hermes's personal assistant — handles general-purpose work outside
    the Sovereign Manager scope (web research, APEX/THE CIRCLE/vape-vending side
    projects, calendar/notes lookups, etc.). Returns Jarvis's reply for Hermes
    to summarize back to the Operator.
    """
    if not task.strip():
        return 'usage: /jarvis "<task description>"'
    import subprocess
    import uuid

    # Persist a session id per task topic so Jarvis remembers context across turns.
    # Topics keyed by first 32 chars of task; collision risk is low and acceptable.
    topic_key = task.strip().lower()[:32]
    sessions_dir = ROOT / "state" / "logs" / "jarvis_sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    sid_file = sessions_dir / (f"{abs(hash(topic_key)) % 10**12}.txt")
    if sid_file.exists():
        session_id = sid_file.read_text().strip()
    else:
        session_id = str(uuid.uuid4())
        sid_file.write_text(session_id)

    try:
        res = subprocess.run(
            ["openclaw", "agent", "--local",
             "--agent", "main",
             "--message", task,
             "--session-id", session_id,
             "--json"],
            capture_output=True, text=True, timeout=300,
        )
        if res.returncode != 0:
            return f"✗ jarvis error: {res.stderr[-400:]}"
        stdout = res.stdout
        i = stdout.find("{")
        if i < 0:
            return f"jarvis (raw): {stdout[:1800]}"
        try:
            data = json.loads(stdout[i:])
            payloads = data.get("payloads") or []
            if payloads and isinstance(payloads, list):
                text = payloads[0].get("text") or ""
                return f"[Jarvis]\n{text[:3500]}" if text.strip() else "(jarvis returned empty)"
            return f"jarvis (no payload): {json.dumps(data)[:600]}"
        except json.JSONDecodeError:
            return f"jarvis (parse failed): {stdout[i : i + 1500]}"
    except subprocess.TimeoutExpired:
        return "✗ jarvis timed out (300s)"
    except FileNotFoundError:
        return "✗ openclaw CLI not on PATH"
    except Exception as e:
        return f"✗ jarvis exception: {e}"


def _project_command(rest: str) -> str:
    """`/project new <name> <engine> [budget_usd]` | `/project show <id>` | `/project assign <id> <manager>`."""
    parts = rest.split(maxsplit=3)
    if not parts:
        return "/project new <name> <engine> [budget] | /project show <id> | /project assign <id> <manager>"
    sub = parts[0].lower()

    if sub == "new":
        if len(parts) < 3:
            return "usage: /project new <name> <engine> [budget_usd]"
        name = parts[1]
        engine = parts[2]
        budget = float(parts[3]) if len(parts) > 3 else 200.0
        try:
            pid = registry.create_project({
                "name": name,
                "engine": engine,
                "outcome": f"manual project: {name}",
                "kill_criteria": ["if no progress in 14d", "if budget exhausted"],
                "milestones": [],
                "budget_usd": budget,
            }, actor="strategy")
            registry.update_status(pid, "approved", actor="hermes",
                                   note="manual create via /project new")
            return f"✓ created project {pid} (engine={engine}, budget=${budget}). Status: approved. Use /project assign {pid} <manager> to lock an Owner."
        except registry.RegistryError as e:
            return f"✗ {e}"

    if sub == "show":
        if len(parts) < 2:
            return "usage: /project show <id>"
        pid = parts[1]
        proj = registry.get_project(pid)
        if not proj:
            return f"no project {pid}"
        out_dir = ROOT / "state" / "outbox" / pid
        outbox_files = sorted(out_dir.glob("*.md")) if out_dir.exists() else []
        lines = [
            f"PROJECT {pid}",
            f"  name:    {proj['name']}",
            f"  engine:  {proj['engine']}",
            f"  status:  {proj['status']}",
            f"  owner:   {proj.get('owner') or '(unassigned)'}",
            f"  budget:  ${proj['spent_usd']:.2f} / ${proj['budget_usd']:.2f}",
            f"  outcome: {proj.get('outcome', '')[:140]}",
            f"  milestones: {len(proj.get('milestones', []))}",
            f"  kill_criteria: {proj.get('kill_criteria', [])}",
            "",
            f"OUTBOX ({len(outbox_files)} files):",
        ]
        for f in outbox_files[-10:]:
            lines.append(f"  {f.name}  ({f.stat().st_size}b)")
        return "\n".join(lines)

    if sub == "assign":
        if len(parts) < 3:
            return "usage: /project assign <id> <manager_role>"
        pid, role = parts[1], parts[2]
        try:
            registry.assign_owner(pid, role, actor="hermes")
            return f"✓ assigned {pid} to {role}"
        except registry.RegistryError as e:
            return f"✗ {e}"

    return f"unknown /project subcommand: {sub}"


def _dispatch_command(rest: str) -> str:
    """`/dispatch <manager_role> <project_id> "<brief>"` — invoke a Manager.

    Loads `prompts/managers/<role>.md` as the system prompt, sends the brief
    through OpenClaw → routed model, saves brief to inbox + response to outbox,
    returns the response (truncated for Telegram).
    """
    if not rest:
        return ('usage: /dispatch <manager_role> <project_id> "<brief>"\n'
                "manager_role: strategy|compliance|treasury|engineering|research|"
                "branding|marketing|sales|monetization|operations")
    parts = rest.split(maxsplit=2)
    if len(parts) < 3:
        return 'usage: /dispatch <manager_role> <project_id> "<brief>"'
    role, project_id, brief = parts[0], parts[1], parts[2].strip().strip('"').strip("'")
    if role not in registry.VALID_MANAGERS:
        return f"✗ unknown manager '{role}'. Valid: {sorted(registry.VALID_MANAGERS)}"

    proj = registry.get_project(project_id) if project_id != "_adhoc" else None
    if project_id != "_adhoc" and not proj:
        return f"✗ no project {project_id}"

    # Load Manager system prompt
    prompts_dir = ROOT / "prompts" / "managers"
    prompt_path = prompts_dir / f"{role}.md"
    if not prompt_path.exists():
        return f"✗ no prompt file at {prompt_path}"
    manager_system = prompt_path.read_text()

    # If the project has an engine, append the engine archetype as additional context
    if proj and proj.get("engine"):
        engine_path = ROOT / "prompts" / "engines" / f"{proj['engine']}.md"
        if engine_path.exists():
            manager_system += (
                "\n\n---\n\n## Engine Archetype Context\n\n"
                f"This project's engine is `{proj['engine']}`. Standard playbook:\n\n"
                + engine_path.read_text()
            )

    # Save brief to inbox
    pid_for_io = project_id if project_id != "_adhoc" else "_adhoc"
    inbox_dir = ROOT / "state" / "inbox" / pid_for_io
    outbox_dir = ROOT / "state" / "outbox" / pid_for_io
    inbox_dir.mkdir(parents=True, exist_ok=True)
    outbox_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    brief_path = inbox_dir / f"brief_{role}_{ts}.md"
    brief_path.write_text(f"# Brief for {role} on project {project_id}\n\n{brief}\n")

    # Dispatch via OpenClaw → routed model (sonnet for reasoning roles, kimi for volume)
    try:
        result = dispatch.call(role, manager_system, brief)
    except Exception as e:
        return f"✗ dispatch failed: {e}"

    response = result.get("text", "")
    via = result.get("via", "unknown")
    cost = float(result.get("cost_usd", 0))

    # Save response to outbox
    out_path = outbox_dir / f"{role}_{ts}.md"
    out_path.write_text(
        f"# {role.title()} response — project {project_id} — {ts}\n\n"
        f"_Brief:_ {brief}\n\n_Via:_ {via} | _Cost:_ ${cost:.4f}\n\n---\n\n{response}\n"
    )

    # Charge spend if real project
    if proj and cost > 0:
        try:
            registry.record_spend(project_id, cost, note=f"{role} dispatch")
        except registry.RegistryError:
            pass

    # Return brief summary (Hermes can read full output via /project show <id>)
    summary = response[:1800]
    suffix = f"\n\n— via {via}, ${cost:.4f}\nFull output saved to {out_path.relative_to(ROOT)}"
    return summary + suffix


def _scanner_command(rest: str) -> str:
    parts = rest.split()
    if not parts:
        return "/scanner pause | resume | budget <usd> | targets | enable <t> | disable <t> | once"
    sub = parts[0]
    if sub == "once":
        return json.dumps(scanner.run_cycle(dry=False), indent=2)
    if sub == "targets":
        return "\n".join(f"  {t.target_id} (engine={t.engine}, enabled={t.enabled})" for t in scanner.SCAN_TARGETS)
    if sub == "budget" and len(parts) > 1:
        try:
            new = float(parts[1])
        except ValueError:
            return "budget must be a number"
        # We don't persist this here; scheduler.py uses scanner.DEFAULT_CYCLE_BUDGET_USD.
        return f"(noted) cycle budget {new}; persistent override TBD"
    if sub in ("pause", "resume"):
        return f"(stub) /scanner {sub} — wire to scheduler when daemon is live"
    if sub == "enable" and len(parts) > 1:
        for t in scanner.SCAN_TARGETS:
            if t.target_id == parts[1]:
                t.enabled = True
                return f"✓ enabled {t.target_id} (in-memory only — persist via scanner_brief.md)"
        return f"no such target {parts[1]}"
    if sub == "disable" and len(parts) > 1:
        for t in scanner.SCAN_TARGETS:
            if t.target_id == parts[1]:
                t.enabled = False
                return f"✓ disabled {t.target_id}"
        return f"no such target {parts[1]}"
    return "unknown /scanner subcommand"


def _treasury_command(rest: str) -> str:
    parts = rest.split()
    if not parts:
        rev = registry.read_revenue()
        return json.dumps({
            "treasury": rev.get("treasury", {}),
            "splits": treasury.load_splits(),
        }, indent=2)
    sub = parts[0]
    if sub == "status":
        rev = registry.read_revenue()
        return json.dumps(rev.get("treasury", {}), indent=2)
    if sub == "reconcile":
        req = treasury.reconcile()
        return treasury._format_request_md(req)[:3800]
    if sub == "seed":
        for kv in parts[1:]:
            k, _, v = kv.partition("=")
            field = {
                "war_chest": "war_chest_usd",
                "api_budget": "api_budget_usd",
                "operator": "operator_held_usd",
            }.get(k, k)
            try:
                registry.update_treasury_balance(field, float(v))
            except (ValueError, registry.RegistryError) as e:
                return f"✗ {e}"
        rev = registry.read_revenue()
        return f"✓ seeded. balances: {rev.get('treasury', {})}"
    if sub == "set":
        new = {}
        for kv in parts[1:]:
            k, _, v = kv.partition("=")
            new[k.strip()] = float(v)
        try:
            treasury.save_splits(new)
        except ValueError as e:
            return f"✗ {e}"
        return f"✓ splits saved: {new}"
    if sub == "distribute":
        rev = registry.read_revenue()
        held = rev.get("treasury", {}).get("operator_held_usd", 0)
        if held <= 0:
            return "Nothing held for distribution."
        registry.update_treasury_balance("operator_held_usd", -held)
        return f"✓ marked ${held:.2f} as distributed. (Real transfer must be done in your bank.)"
    if sub == "topup" and len(parts) > 1:
        try:
            amt = float(parts[1])
        except ValueError:
            return "amount must be a number"
        registry.update_treasury_balance("api_budget_usd", amt)
        return f"✓ recorded +${amt:.2f} to api_budget. (Real top-up must be done at openrouter.ai.)"
    if sub == "pause" and len(parts) > 1:
        n = treasury.pause_engine(parts[1], actor="operator")
        return f"✓ paused {n} active project(s) under engine {parts[1]}."
    return "unknown /treasury subcommand"


def _help_text() -> str:
    return (
        "Commands:\n"
        "  /digest                          today's digest\n"
        "  /inbox                           pending Business Reviews\n"
        "  /show <opp_id>                   show one opportunity\n"
        "  /projects                        list projects\n"
        "  /audit recent <n>                last n audit events\n"
        "  /scanner once|targets|budget|enable|disable\n"
        "  /treasury status|reconcile|seed|set|distribute|topup|pause\n"
        "  /kill <project_id>\n"
        "  /ping                            pong\n"
        "  yes|no|edit|hold [reason]        respond to most-recent Business Review\n"
    )


# -------------------------------------------------------------- Hermes ---


def _hermes_session_id() -> str:
    """Stable session id per Operator chat so Jarvis remembers context across turns."""
    cid = _operator_chat_id()
    sid_file = ROOT / "state" / "logs" / f"hermes_session_{cid}.txt"
    if sid_file.exists():
        return sid_file.read_text().strip()
    import uuid
    sid = str(uuid.uuid4())
    sid_file.parent.mkdir(parents=True, exist_ok=True)
    sid_file.write_text(sid)
    return sid


def _ask_hermes(user_text: str) -> str:
    """Free-form chat → forward to OpenClaw's `agent` (Jarvis personality + plugins).

    Falls back to direct Ollama → OpenRouter chain if `openclaw agent` is unreachable.
    """
    import subprocess

    session_id = _hermes_session_id()
    try:
        res = subprocess.run(
            [
                "openclaw", "agent", "--local",
                "--message", user_text,
                "--session-id", session_id,
                "--model", "openrouter/anthropic/claude-sonnet-4.6",
                "--json",
            ],
            capture_output=True, text=True, timeout=180,
        )
        if res.returncode == 0:
            stdout = res.stdout
            # Strip non-JSON banner lines (anything before the first '{')
            i = stdout.find("{")
            if i >= 0:
                try:
                    data = json.loads(stdout[i:])
                    payloads = data.get("payloads") or []
                    if payloads and isinstance(payloads, list):
                        text = payloads[0].get("text") or ""
                        if text.strip():
                            return text.strip()[:3800]
                except json.JSONDecodeError:
                    pass
            # Fall through to next backend
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    except Exception as e:
        _log("openclaw_agent_error", err=str(e))

    # Fallback 1: direct Ollama
    sys_prompt_path = ROOT / "prompts" / "00_hermes_orchestrator.md"
    sys_prompt = sys_prompt_path.read_text() if sys_prompt_path.exists() else "You are Hermes."
    body = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_text},
        ],
        "stream": False,
    }
    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode())
        return (data.get("message", {}).get("content") or data.get("response", "") or "(empty)").strip()[:3800]
    except urllib.error.URLError as e:
        # Fallback 2: dispatch.call (OpenClaw infer model run)
        try:
            res = dispatch.call("strategy", sys_prompt, user_text)
            return f"(fallback) {res['text'][:3800]}"
        except Exception as fe:
            return f"⚠ Hermes unreachable. Ollama: {e.reason}. Fallback: {fe}"


# -------------------------------------------------------------- runner ---


def loop_forever(poll_timeout: int = 25, push_every_seconds: int = 30) -> None:
    last_push = 0.0
    while True:
        try:
            poll_once(timeout=poll_timeout)
        except Exception as e:
            _log("poll_loop_exception", err=str(e))
        now = time.time()
        if now - last_push >= push_every_seconds:
            try:
                push_pending_outbox()
            except Exception as e:
                _log("push_exception", err=str(e))
            last_push = now


def _log(event: str, **fields) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    line = json.dumps({"ts": time.time(), "event": event, **fields}) + "\n"
    (LOGS / "telegram.log").open("a").write(line)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ping", action="store_true")
    p.add_argument("--send")
    p.add_argument("--loop", action="store_true")
    p.add_argument("--push-pending", action="store_true")
    args = p.parse_args()

    if args.ping:
        try:
            res = send_text("pong (ping from sovereign)")
            print(json.dumps(res, indent=2)[:1000])
            return 0 if res.get("ok") else 1
        except Exception as e:
            print(f"✗ ping failed: {e}", file=sys.stderr)
            return 1
    if args.send:
        print(json.dumps(send_text(args.send))[:1000])
        return 0
    if args.push_pending:
        n = push_pending_outbox()
        print(f"pushed {n} pending outbox files")
        return 0
    if args.loop:
        loop_forever()
        return 0
    p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
