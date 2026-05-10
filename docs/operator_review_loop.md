# Operator Review Loop — The Ask-Before-Launch Gate

No business launches without Operator approval in Telegram. This doc defines the
exact path from Scanner finding to live project.

---

## The Path

```
Scanner cycle
   └─> opportunity (score >= 75) → state/opportunities.json
        └─> Strategy Manager triages (max 10/day)
             └─> Compliance Manager pre-checks (legal/TOS/regulatory)
                  └─> Hermes drafts BUSINESS REVIEW
                       └─> Telegram push to Operator
                            └─> Operator replies: yes / no / edit / hold
                                 ├─ yes  → Strategy creates project, status=approved → Owner Manager dispatches → status=active
                                 ├─ no   → opportunity archived with reason
                                 ├─ edit → Operator states changes → Hermes redrafts → re-asks
                                 └─ hold → opportunity parks for 7 days, then re-asks
```

---

## BUSINESS REVIEW Format

The exact text the Operator receives in Telegram:

```
┌─ BUSINESS REVIEW ─────────────────────────────┐
│ Name:        <short brand-tone name>          │
│ Engine:      <archetype, e.g. RE Wholesale>   │
│ Score:       <0-100>                          │
│ Source:      <one-line where this was found>  │
└───────────────────────────────────────────────┘

OPPORTUNITY
<one paragraph: the gap, who has it, why now>

NUMBERS
  TAM estimate:        $<x>/month
  Time-to-first-$:     <n> days
  Build cost:          $<x> + <n> agent-hours
  Projected 30d net:   $<x> (low) / $<x> (high)

KILL CRITERIA
  • <measurable condition 1>
  • <measurable condition 2>
  • <measurable condition 3>

COMPLIANCE
  ✓/⚠/✗ <flag 1>: <one-line explanation>
  ✓/⚠/✗ <flag 2>: <…>

PROPOSED OWNER
  <Manager>

FIRST 3 STEPS
  1. <step>
  2. <step>
  3. <step>

BUDGET
  $<x> (drawn from war_chest)

REPLY:
  yes    → launch
  no     → archive (optionally add reason)
  edit   → state changes; I'll redraft
  hold   → park for 7 days
```

---

## Operator Reply Handling

### `yes`
1. Hermes calls `dispatch.assign_owner(project_id, proposed_owner)`.
2. Registry transitions opportunity → project, status `approved`.
3. Owner Manager receives a brief in `state/inbox/<project>/brief.md`.
4. Owner Manager submits a worker plan (per Order Flow rule 4).
5. Hermes acks → Owner transitions `approved → active` and spawns workers.
6. Project appears in tomorrow's Daily Digest.

### `no`
- Hermes archives the opportunity (`status: archived`).
- Operator can add a reason: `no — too risky` or `no — wrong vertical`.
- Reasons are tagged into `state/skills/<engine>_rejected_patterns.md` so Scanner
  scoring can be adjusted (penalize similar future findings).

### `edit`
- Operator states changes: e.g. `edit — change owner to Engineering, drop budget to $50`.
- Hermes redrafts the BUSINESS REVIEW with the changes applied.
- Pushes again. Loop continues until `yes` / `no` / `hold`.

### `hold`
- Opportunity parks in `state/opportunities.json` with `status: hold` and
  `hold_until: <now + 7d>`.
- After 7 days, Hermes re-runs the score (in case TAM or compliance changed) and
  pushes a fresh BUSINESS REVIEW.
- After 3 holds without a `yes`, opportunity auto-archives.

---

## Volume Caps

To prevent decision fatigue:

- **Max 3 BUSINESS REVIEWs per day** in the Daily Digest pipeline.
- Overflow parks at status `pending_review` (separate from `hold`).
- Operator can pull manually: `/inbox` lists all `pending_review`, then
  `/show <opp_id>` renders that BUSINESS REVIEW on demand.

If urgency is high (e.g. tax-deed auction with 48-hour deadline), Hermes sets
`urgent: true` and pushes immediately even if the daily cap is hit.

---

## Audit Trail

Every reply is logged to `state/registry.json` under `audit_log`:

```json
{
  "timestamp": "...",
  "actor": "operator",
  "event": "business_review_response",
  "opportunity_id": "...",
  "reply": "yes|no|edit|hold",
  "note": "..."
}
```

The Operator can pull recent decisions: `/audit recent 10`.

---

## Failure Modes

- **Operator unreachable for >24h:** Hermes batches all pending BUSINESS REVIEWs into
  the next digest. No auto-launches.
- **Compliance Manager flags `block`:** opportunity is auto-archived before reaching
  Operator. Logged so Operator can override on next pull if desired.
- **Reply ambiguous:** Hermes asks one clarifying question, max. If second reply is
  still ambiguous, defaults to `hold`.
