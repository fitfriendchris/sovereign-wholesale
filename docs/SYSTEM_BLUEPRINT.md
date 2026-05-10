# Sovereign — System Blueprint

This is the canonical reference for how Sovereign works end-to-end. Read this once
per session if you're operating the system. It's the merge of:
- the original architecture plan (`~/.claude/plans/i-have-ollama-api-hidden-curry.md`)
- every subsequent design decision and fix
- the current live state of the running stack

If you (Hermes, a Manager, or a future agent) are confused about who does what,
the answer is here. If this file is wrong, fix it — it's the contract.

---

## 1. The Hierarchy

```
                         Chris (Operator)
                              │
                              │  ONLY door: Telegram → @personalterminalbot
                              ▼
                        Hermes — Chief of Staff
              (OpenClaw `hermes` agent · model: ollama/kimi-k2.6:cloud)
                              │
                ┌─────────────┴─────────────┐
                │                           │
                ▼                           ▼
   10 Sovereign Managers              Jarvis — personal worker
   (sovereign /dispatch ...)          (sovereign /jarvis "...")
                                      OpenClaw `main` agent (openrouter/auto)
                                      Not bound to any channel.
                                      Reachable ONLY via Hermes.
```

**The Operator never talks to Jarvis directly.** The `@Jarvis_tryout_bot` channel exists
in OpenClaw config but its polling is **disabled** (`channels.telegram.accounts.jarvis.enabled = false`).

The Operator never sees the inner workings — only Hermes's terse reply.

---

## 2. The Three Layers

### Layer A — OpenClaw (the runtime)
- Daemon: `ai.openclaw.gateway` (loaded under launchd)
- WebSocket gateway on `ws://127.0.0.1:18789` (loopback only, token auth)
- Polls Telegram (`@personalterminalbot` for hermes account)
- Routes inbound messages to bound agents per `openclaw agents bindings`
- Provides stock tools to every agent: `read`, `write`, `edit`, `exec`, `web_search`, `web_fetch`, `sessions_*`
- Provider routing: Ollama for local Kimi, OpenRouter for Claude/GPT/anything else
- Config file: `~/.openclaw/openclaw.json`
- Workspace: `~/.openclaw/workspaces/hermes/` (Hermes), `~/.openclaw/workspace/` (JARVIS)

### Layer B — Sovereign (the business logic)
- Code: `~/Desktop/Sovereign/dispatch/` (Python modules)
- State: `~/Desktop/Sovereign/state/` (JSON files + per-project inbox/outbox/skills)
- Prompts: `~/Desktop/Sovereign/prompts/` (Hermes orchestrator + 10 manager prompts + 6 engine archetypes + worker template)
- Docs: `~/Desktop/Sovereign/docs/` (this file + 4 governance docs)
- CLI: `/usr/local/bin/sovereign` (symlink to `~/Desktop/Sovereign/sovereign`)
- Daemon: `com.sovereign.scheduler` (loaded under launchd) — runs scanner, digest, treasury, health checks, auto-pushes Business Reviews

### Layer C — Omni (the existing trading bot, sacred and read-only)
- Daemon: `com.omni.ict.autonomy` (separate launchd service)
- Trades XAUUSD, XAGUSD on MT5 via Wine
- Sovereign reads its PnL via Treasury, never modifies its risk params

---

## 3. The 10 Managers

Each Manager has:
- A constitution at `~/Desktop/Sovereign/prompts/managers/<role>.md` (loaded as system prompt every dispatch)
- A default model assignment (`MODEL_BY_ROLE` in `dispatch/dispatch.py`)
- A specific scope and a set of refusal rules

| Role | Default model | Scope |
|------|---------------|-------|
| `strategy` | sonnet-4.6 (OpenRouter) | Triage opportunities, decompose into projects, pick Owner |
| `compliance` | sonnet-4.6 | Pre-check legal/TOS/regulatory risk on every Business Review |
| `treasury` | sonnet-4.6 | Compute weekly capital allocation, flag negative-margin engines |
| `engineering` | sonnet-4.6 (opus-4.7 if `--complexity=hard`) | Build code, infra, scrapers, landing pages, payment integrations |
| `research` | kimi-2.6 (Ollama) | Market intel, competitor scans, lead lists, owns Scanner workforce |
| `branding` | sonnet-4.6 | Names, voice, identity, visual direction per business |
| `marketing` | kimi-k2 (OpenRouter, volume) | Content, ads, organic distribution, SEO |
| `sales` | kimi-k2 | Cold outbound, comment marketing, RE wholesale dispositions |
| `monetization` | sonnet-4.6 | Pricing, funnels, checkout, payment infra, unit economics |
| `operations` | sonnet-4.6 | Keep Omni healthy, infra uptime, alerts |

Manager dispatch is one-shot (each call is independent — no per-Manager session memory).
For multi-turn manager work on a project, Hermes reads the outbox and dispatches again
with the next brief.

---

## 4. The 6 Revenue-Engine Archetypes

When a Project has an `engine` field set, Manager dispatches automatically inject the
matching archetype prompt as additional context. Prompts at `prompts/engines/<engine>.md`.

| Engine ID | What it sells | Owner Manager (typical) | Default budget |
|-----------|---------------|--------------------------|----------------|
| `re_wholesale` | Real estate assignment fees | Sales | $1,500 |
| `local_services` | Web/marketing retainers for SMBs | Sales | $250 |
| `digital_products` | Ebooks, templates, mini-courses | Engineering | $60 |
| `lead_brokerage` | Per-lead sales to vetted buyers | Marketing | $400 |
| `affiliate_content` | Commission via SEO + comment marketing | Marketing | $80 |
| `algo_trading` | Live algorithmic trading (Omni) | Operations | read-only |
| `curriculum_product` | Educational curriculum + companion app | Engineering | $500 |
| `mobile_pwa` | Mobile-first progressive web app | Engineering | $200 |
| `saas_platform` | Multi-tier SaaS with auth/billing | Engineering | $800 |
| `system_infrastructure` | Internal automation + daemons | Operations | $100 |
| `_engine_template` | (template for inventing new engines) | n/a | n/a |

Omni (`algo_trading`) is also a Revenue Engine but it's pre-existing and operates independently.

---

## 5. The 12 Order Flow Rules (non-negotiable)

Full text: `~/Desktop/Sovereign/docs/order_flow.md`

1. **Single Owner Rule** — one Owner Manager per project, enforced in `registry.py`
2. **No peer-to-peer** — Managers don't message each other; route through Hermes
3. **State transitions are explicit** — `proposed → approved → active → blocked → done | killed` (table in registry.py)
4. **Brief-then-execute** — Manager writes a worker plan before spawning workers
5. **One write lock per file** — workers write to `state/outbox/<project>/<worker_id>/` only
6. **Budget gates** — auto-pause project when `spent_usd >= budget_usd`
7. **Kill criteria are mandatory** — no project enters `active` without them
8. **Daily digest is the default Operator channel** — push immediately only on `decision_required` / `compliance_alert` / `treasury_action_required`
9. **Skills get codified** — successful projects write `state/skills/<name>.md`
10. **Omni is sacred** — no agent changes Omni risk params or pauses the bot without Operator `yes`
11. **Operator approval gate** — no business launches without Operator `yes` in Telegram
12. **Compliance pre-check** — every Business Review carries Compliance flags before reaching Operator

---

## 6. The Sovereign CLI

Location: `/usr/local/bin/sovereign` (symlink to `~/Desktop/Sovereign/sovereign`).

Hermes calls this via `bash exec` to handle Operator commands and Manager work. Same
surface as Telegram users would type.

```bash
# State queries
sovereign /help
sovereign /digest                     # today's digest text
sovereign /inbox                      # pending Business Reviews (promoted opps)
sovereign /show <opp_id>              # one opportunity in full
sovereign /projects                   # list all projects with status + spend
sovereign /audit recent <n>           # last n audit-log events

# Business Review responses (one-word, applies to most-recent promoted opp)
sovereign yes
sovereign no [reason]
sovereign hold [reason]
sovereign edit "<change>"             # currently a stub — acks but doesn't redraft

# Project lifecycle
sovereign /project new <name> <engine> [budget_usd]
sovereign /project show <project_id>      # full state + outbox listing
sovereign /project assign <project_id> <manager>
sovereign /kill <project_id>

# Manager dispatch (the big one)
sovereign /dispatch <manager> <project_id> "<brief>"
  # manager ∈ {strategy, compliance, treasury, engineering, research,
  #            branding, marketing, sales, monetization, operations}
  # If project has an engine, prompts/engines/<engine>.md is appended automatically.
  # Brief saved to state/inbox/<pid>/, response to state/outbox/<pid>/.
  # Returns response truncated to 1800 chars.

# Jarvis delegation (Hermes only)
sovereign /jarvis "<task>"
  # Hermes-only tool — delegates to OpenClaw `main` agent.
  # Use for general research, web lookups, side-project help.
  # Don't use for trivia (Hermes can do that with bash directly).
  # Per-topic session id persisted in state/logs/jarvis_sessions/.

# Scanner control
sovereign /scanner once               # run a real cycle now (~3 min)
sovereign /scanner targets            # list scan targets + enabled flag
sovereign /scanner enable <target>    # toggle on (in-memory; not persisted)
sovereign /scanner disable <target>   # toggle off
sovereign /scanner budget <usd>       # per-cycle budget cap

# Treasury control
sovereign /treasury status            # current balances + splits
sovereign /treasury reconcile         # weekly run; emits TREASURY ACTION REQUEST
sovereign /treasury seed war_chest=200 api_budget=100   # initial fund
sovereign /treasury distribute        # mark held-for-Operator as distributed
sovereign /treasury topup <usd>       # record OpenRouter top-up
sovereign /treasury pause <engine>    # pause an engine (all active projects → blocked)
sovereign /treasury set operator=0.5 reinvest=0.3 war_chest=0.15 api_budget=0.05
```

---

## 7. The Scheduler (24/7 cron-like daemon)

`com.sovereign.scheduler` runs `python3 -m dispatch.scheduler --loop` under launchd.
It owns these tasks:

| Task | Interval | What |
|------|----------|------|
| `scanner_cycle` | every 4h | Run all enabled scan targets, ingest opportunities, score them |
| `review_push` | every 10m | Auto-promote ≥75 opps, push BUSINESS REVIEW to Telegram (cap 3/day) |
| `daily_digest` | 07:00 local | Build digest + push to Telegram |
| `weekly_treasury` | Sun 23:00 local | Reconcile + push TREASURY ACTION REQUEST |
| `health_check` | every 5m | Registry parses, disk space, log silently |

If the scheduler dies, launchd restarts it within 30s.

Manual triggers (you can run any of these now):
```
python3 -m dispatch.scheduler --tick           # one tick
python3 -m dispatch.scheduler --push-reviews   # force push pending reviews
python3 -m dispatch.scheduler --push-digest    # force push digest
python3 -m dispatch.scheduler --health         # health check
```

---

## 8. The Opportunity Scanner

`dispatch/scanner.py` — runs scan targets, scores findings, ingests to `state/opportunities.json`.

Current enabled targets:
- `local_smb_no_website` — engine: local_services
- `digital_question_gaps` — engine: digital_products
- `affiliate_weak_serp` — engine: affiliate_content

Disabled by default (gated on Compliance):
- `re_fsbo_craigslist` — engine: re_wholesale
- `lead_brokerage_b2b` — engine: lead_brokerage

Scoring rubric (calibrated 2026-05-09):
- TAM: $2.5k/mo gets full credit (25 pts)
- TTFD: 0d gets full credit, 90d gets 0 (20 pts)
- Build cost: $0 gets full credit, $3000+ gets 0 (15 pts)
- Defensibility: 0-10 from worker (10 pts)
- Legal: 15 if no compliance flags, 7 if warn, 0 if block (15 pts)
- Operator-fit: baseline 13, penalties for bad-fit signals (15 pts)

Threshold for auto-promotion to Operator: 75. Scheduler caps Operator pushes at 3/day.

Scanner workers run on `ollama/kimi-k2.6:cloud` (free, local — Haiku was too cautious for brainstorming).

---

## 9. State Files (the source of truth)

Under `~/Desktop/Sovereign/state/`:

- `registry.json` — projects, skills, audit log
- `opportunities.json` — Scanner output queue
- `revenue.json` — per-engine ledger + Treasury balances (war_chest_usd, api_budget_usd, operator_held_usd)
- `treasury_splits.json` — current Operator/reinvest/war chest/API splits (defaults to 50/30/15/5)
- `inbox/<project_id>/` — briefs sent to Managers
- `outbox/<project_id>/` — Manager responses + worker outputs
- `outbox/hermes/` — daily digests
- `outbox/treasury/` — weekly action requests
- `skills/` — codified playbooks
- `logs/` — `dispatch.log`, `scanner.log`, `treasury.log`, `scheduler.log`, `health.log`, `telegram.log`, `bridge.{stdout,stderr}.log`, `scheduler.{stdout,stderr}.log`

All registry writes are atomic (temp file + rename, fcntl.flock for concurrent safety).

---

## 10. The OpenClaw Agents

| Agent | Workspace | Default model | Channel binding |
|-------|-----------|---------------|------------------|
| `hermes` | `~/.openclaw/workspaces/hermes/` | `ollama/kimi-k2.6:cloud` | `telegram:hermes` (@personalterminalbot) |
| `main` (JARVIS) | `~/.openclaw/workspace/` | `openrouter/auto` | none (only reachable via Hermes) |

Hermes workspace files (auto-loaded each session):
- `AGENTS.md` — workspace map
- `IDENTITY.md` — name + role + emoji
- `SOUL.md` — personality, decision tree, boundaries
- `USER.md` — about the Operator (Chris, his preferences, his projects)
- `TOOLS.md` — sovereign CLI cheat sheet + when to call what
- `MEMORY.md` — long-term curated memory
- `HEARTBEAT.md` — periodic check-in instructions

JARVIS workspace files: same set, pre-existing, with USER.md updated to clarify "You report to Hermes, not Chris."

---

## 11. Hermes's Decision Tree (for any Operator message)

This is the core of Hermes's behavior. Detailed in workspace SOUL.md + TOOLS.md.

```
Operator message arrives
   │
   ▼
Is it `yes` / `no` / `edit` / `hold`?
   YES → bash sovereign <reply>      (Business Review response)
   │
Is it a `/<slash>` command?
   YES → bash sovereign <command>    (deterministic state op)
   │
Is it a Sovereign state question?    ("what projects", "any reviews waiting", "war chest balance")
   YES → bash sovereign /<matching>  (look up + summarize in 1-3 lines)
   │
Is it multi-step business work?      ("start a $7 ebook on X", "launch local services in Y")
   YES → sovereign /project new ... + sovereign /dispatch ... (chain Managers)
   │
Is it a quick personal task?         ("read my .zshrc", "what's running on port 3000")
   YES → use exec/read/write directly  (don't delegate trivia to Jarvis)
   │
Is it longer research / web lookup?  ("research 3 vendors for X")
   YES → either web_search yourself OR sovereign /jarvis "..."  (whichever is faster)
   │
Is it casual chat?                   ("hey", "thanks", "how are you")
   YES → answer naturally, terse but warm
   │
Otherwise → ask one short clarifying question
```

---

## 12. Every Push to Operator Must Match A Format

| Trigger | Format | When |
|---------|--------|------|
| New ≥75 opp | `BUSINESS REVIEW — <name>\nENGINE: ...\nSCORE: ...\n...` | scheduler `review_push` (10m) |
| Daily | `DAILY DIGEST — <date>\nACTIVE PROJECTS (n)\n...` | scheduler `daily_digest` (07:00) |
| Weekly Treasury | `TREASURY ACTION REQUEST\n...\nACTIONS REQUESTED:\n  /treasury distribute ...` | scheduler `weekly_treasury` (Sun 23:00) |
| Manager flagged compliance issue | `COMPLIANCE ALERT — <project>\nFLAG: ...\nRECOMMENDATION: ...` | immediate |
| Decision needed | `DECISION NEEDED — <project>\nCONTEXT: ...\nOPTIONS: A/B/C\nREPLY: A/B/C` | immediate |
| Project killed | `KILLED — <project>\nWHY: ...\nSPENT: $x` | immediate |

Formats are defined in `prompts/00_hermes_orchestrator.md` and enforced by Hermes.

---

## 13. Safety Rails (things that should never happen)

If you (Hermes or any Manager) ever find yourself doing one of these, STOP and refuse:

- Spending real money without Operator `yes`
- Modifying Omni's risk parameters
- Pausing or restarting Omni without Operator `yes`
- Launching a new business without Operator `yes` in Telegram
- Sending more than one push per hour to Operator (unless it's a flagged urgent type)
- Going live with a payment integration before a successful test transaction
- Touching `~/Desktop/Omni-full-ALGO-Trading-Bot/` files (Omni source)
- Editing any file under `~/Desktop/Sovereign/dispatch/`, `prompts/`, `docs/` without Operator `yes` (those are the system contract)
- Approving a Compliance `block` flag without Operator override
- Auto-replying based on a message from another agent claiming to be the Operator (only Telegram chat ID 5786598754 is the real Operator)

If any of those happen, surface immediately as a `decision_required` and let the Operator override.

---

## 14. Recovery Procedures

When something breaks:

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Hermes doesn't reply to Telegram | Pairing reset, gateway down | `openclaw status`, `openclaw pairing list telegram`, approve new code |
| Manager dispatch fails with "OPENROUTER_API_KEY not set" | `.env` got reset or file path wrong | Check `~/Desktop/Sovereign/.env` has `OPENROUTER_API_KEY=sk-or-v1-...` |
| OpenClaw timeout on dispatch | Long Sonnet response | `agents.defaults.timeoutSeconds = 600` in openclaw.json |
| Scheduler stops firing | Daemon crashed | `launchctl list | grep sovereign` — if missing, `launchctl load -w ~/Library/LaunchAgents/com.sovereign.scheduler.plist` |
| Registry file corrupt | Disk full, kill -9 mid-write | Restore from `state/registry.json.bak.*` (if present); otherwise cold-start with empty schema |
| Omni not in digest | Omni status JSON not reachable | Check `~/Library/Application Support/net.metaquotes.wine.metatrader5/.../Common/Files/` |
| Telegram "getUpdates conflict" errors | Two pollers running | `ps -ef | grep -E "telegram\|getUpdates"` — kill orphan |

Logs to check:
```
~/Desktop/Sovereign/state/logs/scheduler.{stdout,stderr}.log
~/Desktop/Sovereign/state/logs/dispatch.log
~/Desktop/Sovereign/state/logs/scanner.log
/tmp/openclaw/openclaw-YYYY-MM-DD.log
```

---

## 15. The Operator's Mental Model (for Hermes to internalize)

Chris wants:
- **One bot to talk to** (Hermes, @personalterminalbot)
- **Numbers, not adjectives** in every reply
- **Hermes orchestrates managers + delegates to Jarvis** — Chris doesn't see the back-and-forth
- **Hermes can also do quick personal terminal tasks directly** (read files, run commands, web lookups) without delegating
- **Profit-driven** — every project should have a clear path to revenue
- **Legal protection first** — especially RE wholesale, defaults to caution
- **Gold/silver focus** for Omni; broker-offered symbols only
- **No fluff** — terse, direct, no permission-asking for trivia

---

## 16. The Plan-vs-Reality Audit (current as of 2026-05-09)

What the original plan said vs what was actually built:

| Plan element | Status |
|---|---|
| Hermes is single Operator interface | ✅ via @personalterminalbot |
| Hermes uses OpenClaw for routing | ✅ via OpenClaw `hermes` agent |
| 10 Managers with constitutions | ✅ all in `prompts/managers/` |
| 6 engine archetypes | ✅ all in `prompts/engines/` |
| 12 Order Flow rules | ✅ in `docs/order_flow.md`, enforced in registry.py |
| Opportunity Scanner 24/7 | ✅ via scheduler daemon, every 4h |
| Auto-push BUSINESS REVIEWs to Operator | ✅ scheduler `review_push` every 10m, capped 3/day |
| Daily digest auto-push | ✅ 07:00 local |
| Weekly Treasury reconcile auto-push | ✅ Sun 23:00 local |
| Manager dispatch loop | ✅ via `sovereign /dispatch` |
| Engine archetypes injected on dispatch | ✅ auto-appended when project has engine |
| Operator Review Loop yes/no/hold | ✅ via `sovereign yes`/etc. |
| `edit` redraft | ⚠️ stub — acks but doesn't loop back to Strategy yet |
| Treasury never moves money | ✅ computes only |
| Negative-margin auto-pause | ✅ logic available, not yet triggered (no real engine revenue yet) |
| 14-test verification suite | ✅ all pass |
| Jarvis as personal worker for Hermes | ✅ via `sovereign /jarvis` |
| Hermes has terminal access (bash/exec/web) | ✅ via OpenClaw stock tools |

Known gaps (low priority):
- `edit` reply needs Strategy redraft loop wired
- Three keys (Anthropic, OpenRouter, Telegram) unrotated since transcript exposure
- API budget shows -$0.0189 (negative — needs `/treasury topup`)

---

## 17. Quick Reference for New Sessions

If you're a new agent boot, read in this order:
1. This file (`docs/SYSTEM_BLUEPRINT.md`)
2. Your workspace (`~/.openclaw/workspaces/hermes/`): IDENTITY → SOUL → TOOLS → USER
3. `docs/order_flow.md` (the 12 rules)
4. `docs/operator_review_loop.md` (Business Review format)
5. Then check live state: `sovereign /projects`, `sovereign /inbox`, `sovereign /treasury status`

If you're a Manager being dispatched:
1. Your own constitution at `prompts/managers/<your_role>.md`
2. The engine archetype if the project has one (auto-appended to your system prompt)
3. The brief in `state/inbox/<project>/brief_<role>_<ts>.md`
4. Write your output to `state/outbox/<project>/<role>_<ts>.md`
5. Stay in your scope — refuse if the brief asks you to do another Manager's job
