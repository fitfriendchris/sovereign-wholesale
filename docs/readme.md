# Sovereign Multi-Agent Orchestration Kit

A 24/7 multi-agent business portfolio. You message a single agent (Hermes) on Telegram;
the system scans for opportunities, builds approved businesses, runs them, allocates
profit, and reports back.

---

## What's in this directory

```
prompts/    — system prompts for every agent role
docs/       — operating rules (this file, plus 4 governance docs)
dispatch/   — Python runtime: routing, scanner, treasury, scheduler, telegram
state/      — live state (registry, opportunities, revenue, inbox/outbox, skills)
```

---

## The 5-second mental model

```
You ↔ Telegram ↔ Hermes ↔ OpenClaw ↔ Managers ↔ Workers
                              ↑
                    Opportunity Scanner (24/7)
```

- **You** are the Operator. You approve, override, and receive distributions.
- **Hermes** (Kimi 2.6 via Ollama) is your single point of contact.
- **OpenClaw** routes prompts to the right model.
- **Managers** are 10 specialized agents (Strategy, Engineering, Sales, etc.).
- **Workers** are short-lived, scoped task runners (Haiku 4.5 by default).
- **Scanner** finds revenue gaps and feeds Strategy.

Read these in order to understand the system:
1. `docs/order_flow.md` — the 12 rules every agent enforces
2. `docs/operator_review_loop.md` — how new businesses get approved
3. `docs/opportunity_scanner.md` — what gets scanned and how it's scored
4. `docs/capital_allocation.md` — how profits flow

---

## Setup (first time)

### 1. Prerequisites

- macOS (this kit assumes launchd; tested on Darwin 24.6)
- Python 3.11+
- Ollama running locally with Kimi 2.6 model pulled
- OpenRouter API key with credits
- Telegram bot token (you can reuse the Omni bot or create a new one)
- OpenClaw configured (or use the OpenRouter fallback path; see `dispatch/dispatch.py`)

### 2. Install

```bash
cd ~/Desktop/Sovereign
cp .env.example .env
# edit .env with your keys
python3 -m pip install --user requests python-dotenv
```

### 3. Smoke tests (run in order)

```bash
# 1. Registry round-trip
python3 -m dispatch.registry --selftest

# 2. OpenRouter ping (1-token cost; ~$0.0001)
python3 -m dispatch.openrouter_client --ping

# 3. OpenClaw smoke (will fall back to OpenRouter if OpenClaw unreachable)
python3 -m dispatch.dispatch --selftest

# 4. Scanner dry-run (no real spend)
python3 -m dispatch.scanner --once --dry

# 5. Telegram round-trip
python3 -m dispatch.telegram_bridge --ping
```

### 4. Seed Treasury

In Telegram, message Hermes:
```
/treasury seed war_chest=200 api_budget=100
```

This sets initial balances so the Scanner can run within a budget.

### 5. Boot

```bash
./run_hermes.sh   # starts Hermes + telegram bridge + scheduler in foreground
```

For 24/7 operation, install the launchd plists:
```bash
cp ~/Desktop/Sovereign/launchd/com.sovereign.hermes.plist  ~/Library/LaunchAgents/
cp ~/Desktop/Sovereign/launchd/com.sovereign.scanner.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.sovereign.hermes.plist
launchctl load ~/Library/LaunchAgents/com.sovereign.scanner.plist
```

---

## Daily Operator commands (Telegram)

| Command | Effect |
|---------|--------|
| `/digest` | Pulls today's digest on demand |
| `/inbox` | Lists pending Business Reviews |
| `/show <opp_id>` | Renders one Business Review |
| `/audit recent <n>` | Last n audit-log events |
| `/scanner pause` `/scanner resume` | Toggle scanner |
| `/scanner budget <usd>` | Per-cycle scanner budget cap |
| `/treasury status` | Current allocations + balances |
| `/treasury distribute` | Initiate Operator transfer of held funds |
| `/treasury topup` | Confirm OpenRouter top-up done |
| `/treasury pause <engine>` | Pause an engine (all its active projects → blocked) |
| `/projects` | List active projects |
| `/kill <project_id>` | Operator-initiated kill |
| `/help` | Full command list |

When approving a Business Review, the reply is one word: `yes` / `no` / `edit` / `hold`
(optionally followed by a reason).

---

## What happens when

| Event | Who handles | Operator sees |
|-------|-------------|---------------|
| Scanner finds gap | Scanner → Strategy | Nothing yet |
| Strategy promotes to Review | Strategy → Compliance → Hermes | BUSINESS REVIEW in Telegram |
| Operator says `yes` | Hermes → Owner Manager → workers | Confirmation in Telegram |
| Project hits 50% budget | Owner Manager | In tomorrow's Daily Digest |
| Project trips kill criterion | Owner Manager | Immediate `decision_required` |
| Engine net loss for 14d | Treasury | `decision_required` to pause |
| Weekly Sunday 23:00 | Treasury reconciles | TREASURY ACTION REQUEST in Telegram |
| Daily 07:00 local | Hermes assembles | DAILY DIGEST in Telegram |

---

## Safety / what this system will never do

- Move real money. Treasury computes; you execute.
- Change Omni risk parameters or pause Omni without your `yes`.
- Launch a business without your `yes`.
- Spend on ads without your `yes`.
- Ship a payment integration without a successful test transaction logged.
- Scrape behind login walls or violate `robots.txt`.
- Spam (comment marketing must be value-add per platform TOS).

Anything above this line that Hermes attempts to do anyway is a bug. Report it.

---

## Reuse from existing Omni bot

This kit reuses patterns from `/Users/yuhfriendchris/Desktop/Omni-full-ALGO-Trading-Bot/`:

- Telegram long-polling structure → `dispatch/telegram_bridge.py`
- launchd plist template → both `com.sovereign.*.plist` files
- Watchdog supervision idea → `dispatch/scheduler.py`

Omni continues to run independently. Sovereign reads its PnL via Treasury and treats it
as one Revenue Engine among many.
