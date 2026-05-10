# Engine: Real Estate Wholesale

```yaml
engine_id: re_wholesale
display_name: Real Estate Wholesale (Virtual)
one_liner: Source distressed/motivated-seller property contracts and assign them to cash buyers for an assignment fee — virtually, no in-person.

target_buyer:
  who: Cash investors, fix-and-flip operators, buy-and-hold landlords, REITs, hedge-fund SFR buyers
  pain: Need consistent off-market deal flow at below-retail prices
  willingness_to_pay_usd_range: [5000, 50000]   # Assignment fee per deal

revenue_model:
  primary: escrow
  rationale: Standard wholesale: signed purchase contract → assignment to end buyer → fee collected at closing through licensed escrow

standard_milestones:
  - id: m1
    name: Compliance gate
    typical_hours: 2
    acceptance: Operator's state confirmed wholesale-friendly OR Operator has obtained appropriate license / partnered with a licensed agent. Assignment-contract permitted in state. Equitable-interest disclosure language drafted.
  - id: m2
    name: Cash-buyer list
    typical_hours: 8
    acceptance: 50+ vetted cash buyers with target criteria (geo, property type, price range, ARV minimum); contact info verified; segmented in CRM
  - id: m3
    name: Seller lead source
    typical_hours: 6
    acceptance: 1+ active seller-lead pipelines: tax-delinquent lists, FSBO scrape, expired-MLS aggregator, or paid PPC; legal sourcing only
  - id: m4
    name: First contract under contract
    typical_hours: variable
    acceptance: Signed purchase contract with motivated seller at 60-75% of ARV; equitable interest disclosure delivered to seller
  - id: m5
    name: Assignment to buyer
    typical_hours: variable
    acceptance: Signed Assignment of Contract; EMD held by licensed escrow; assignment fee disclosed
  - id: m6
    name: First close
    typical_hours: variable
    acceptance: Closing completed via title company / escrow; assignment fee received

typical_kpis:
  - Seller leads → contracts under contract: ≥3%
  - Contracts under contract → closed assignments: ≥40%
  - Average assignment fee: ≥$8,000
  - Days under contract → closed: ≤30

common_kill_criteria:
  - 60 days with no contract under contract (sourcing or pricing is broken)
  - 2 contracts that died in escrow due to title issues (sourcing quality is broken)
  - Compliance flag raised mid-deal (state law change or buyer complaint)

recommended_tech_stack:
  - CRM: Airtable or REI Reply (purpose-built CRMs exist but Airtable scales fine to 500 contacts)
  - Skip-trace: BatchSkipTracing or PropStream (paid; required for tax-delinquent and absentee leads)
  - Contract templates: state-specific Purchase Agreement + Assignment of Contract — use a real RE attorney to draft, not AI
  - Escrow: licensed title company per deal (NEVER hold EMD yourself)
  - Buyer outreach: SMS (TCPA-compliant) + email + occasional call from real number

owner_manager: Sales
contributors:
  - role: Compliance
    when: m1 (state law gate), m4 (disclosure language), m5 (assignment legality)
  - role: Research
    when: m2 (buyer list), m3 (seller leads from public records)
  - role: Engineering
    when: m2-m3 (CRM setup, scrape automation)
  - role: Marketing
    when: m3 (PPC for seller leads, if budgeted)

compliance_hot_spots:
  - **State licensing:** As of 2024-2026, several states (Illinois, Oklahoma, Pennsylvania, Mississippi, Arkansas, others) have passed laws requiring a real estate license to wholesale. CRITICAL — Compliance Manager hard-blocks this engine in restricted states unless Operator overrides with documented licensure or attorney-vetted workaround.
  - **Equitable interest disclosure:** Most states require the wholesaler to disclose to seller that wholesaler intends to assign or otherwise profit from re-sale, before contract signing.
  - **EMD handling:** EMD must go to licensed escrow / title, never to wholesaler directly.
  - **TCPA:** Cold-call/SMS to homeowners requires prior express consent in many cases.
  - **Truth-in-advertising:** "We buy houses cash" claims must be backed by ability to close (or clear assignment intent disclosure).
  - **Federal/state Do-Not-Call lists:** scrub before outreach.

typical_budget_usd: 1500
time_to_first_dollar_days: 60

skills_to_consult:
  - state/skills/research_county_records.md
  - state/skills/research_re_buyer_signals.md
  - state/skills/sales_re_buyer_intro_message.md
  - state/skills/compliance_re_wholesale_state_matrix.md

playbook_steps:
  - Compliance gate first — DO NOT skip. State-by-state rules vary and have changed recently.
  - Build cash-buyer list from public REIT filings, county records (recent cash purchases), bandit-sign reverse lookup, BiggerPockets buyer profiles
  - Build seller-lead pipeline: tax-delinquent (county website) → skip-trace → SMS/letter; FSBO Craigslist/FB scrape → SMS/email
  - Send TCPA-compliant first-touch with clear identity, opt-out
  - Negotiate purchase price at 60-75% of ARV (after-repair value, validated against comps)
  - Sign state-specific purchase agreement WITH equitable interest disclosure
  - EMD to title company; never to you
  - Disposition: send signed contract to top 10 buyers from buyer list with property details, ARV, repair estimate, asking assignment price
  - First buyer matches → sign Assignment of Contract → buyer's funds + assignment fee held by title
  - Close via title company; receive fee at closing

operator_warning: |
  RE wholesaling is a contract-and-disclosure business. AI cannot substitute for a real
  estate attorney drafting your purchase agreement and assignment contract for your state.
  Compliance Manager will hard-block this engine until the Operator confirms (1) state
  legality, (2) attorney-vetted contract templates, (3) escrow-licensed title relationship.
```
