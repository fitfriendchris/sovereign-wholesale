# Capital Allocation — Treasury Rules

Owned by the Treasury Manager. Defines how net profit from every Revenue Engine flows.

---

## Revenue Ledger

Every engine logs to `state/revenue.json` daily:

```json
{
  "engines": {
    "<engine_id>": {
      "ledger": [
        {"date": "YYYY-MM-DD", "gross": 0.00, "costs": 0.00, "net": 0.00, "note": "..."}
      ],
      "totals": {"mtd_gross": 0, "mtd_net": 0, "ytd_net": 0}
    }
  },
  "treasury": {
    "war_chest_usd": 0,
    "api_budget_usd": 0,
    "operator_held_usd": 0
  }
}
```

The Owner Manager writes the ledger entry through `dispatch.record_revenue()`. The
Treasury Manager reconciles weekly (Sundays 23:00 local).

---

## Default Allocation of Net Profit

When Treasury reconciles, net profit per engine is split:

| Slice | % | Destination |
|-------|---|-------------|
| Operator distribution | 50% | `operator_held_usd` (queued for transfer to Operator) |
| Reinvestment | 30% | back to the engine that produced it (ad spend, infra, scaling) |
| War chest | 15% | `war_chest_usd` (cross-engine fund for new launches + Scanner ops) |
| API budget | 5% | `api_budget_usd` (OpenRouter + infra recurring costs) |

The Operator can override these percentages anytime via Telegram:
```
/treasury set operator=60 reinvest=25 war=10 api=5
```

Override applies to the next reconciliation.

---

## Hard Rules

1. **Treasury never moves real money.** It computes the allocation and emits a
   `TREASURY ACTION REQUEST` to Hermes. The Operator executes the actual transfer
   (or pre-authorizes recurring transfers via their bank).

2. **Omni is read-only to Treasury.** Treasury reads Omni's daily PnL from the bot's
   reporting endpoint but cannot adjust risk parameters or pause the bot. That belongs
   to Operations.

3. **War chest deployment requires approval.** When the war chest is used to fund a new
   project's `budget_usd`, Hermes must surface a `decision_required` to the Operator if
   the deployment is `>= $X` (Operator-set threshold; default $200).

4. **Negative-margin auto-pause.** If an engine shows net loss for 14 consecutive days,
   Treasury flags it. Hermes pushes a `decision_required` to the Operator with two
   options: pause the engine, or override and continue. If no reply within 48 hours,
   the engine auto-pauses (transitions all its `active` projects to `blocked`).

5. **API budget refill.** When `api_budget_usd` falls below the weekly burn rate × 2,
   Treasury issues a `TREASURY ACTION REQUEST` asking the Operator to top up
   OpenRouter. Hard floor: when `api_budget_usd <= 0`, Hermes pauses all non-Omni
   workers.

6. **Operator distribution cadence.** `operator_held_usd` is reported weekly; transfer
   is initiated only on Operator request via `/treasury distribute`. No automatic
   payouts.

---

## Treasury Action Request Format

What the Operator receives in Telegram:

```
TREASURY ACTION REQUEST — <date>

WEEK SUMMARY:
  Total gross:       $<x>
  Total costs:       $<x>
  Total net:         $<x>

PER ENGINE (net):
  • omni:              $<x>
  • digital_products:  $<x>
  • local_services:    $<x>
  ...

ALLOCATION (this week):
  Operator distribution: $<x> (50%)
  Reinvestment:          $<x> (30%, broken down by engine below)
  War chest:             $<x> (15%) → balance now $<x>
  API budget:            $<x> (5%)  → balance now $<x>

ACTIONS REQUESTED:
  1. Transfer $<x> from <bank> to <operator account>   [/treasury distribute]
  2. Top up OpenRouter by $<x> (balance low)           [/treasury topup]

FLAGS:
  ⚠ <engine> is in net loss for <n> days. Pause? /treasury pause <engine>
```

---

## Initial Treasury State

On first run, all balances are zero. The Operator seeds via:
```
/treasury seed war_chest=200 api_budget=100
```

Until seeded, the Scanner runs on a fixed daily Operator-set budget cap (default $5/day
of API spend) so the system can't accidentally drain credits before producing revenue.
