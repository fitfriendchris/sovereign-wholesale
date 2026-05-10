# Engine: Lead Brokerage

```yaml
engine_id: lead_brokerage
display_name: Lead Brokerage
one_liner: Generate qualified leads in a vertical and sell them per-lead to vetted buyers.

target_buyer:
  who: Service businesses with high LTV and unsystematic lead acquisition (mortgage brokers, insurance agents, solar installers, attorneys in narrow practice areas, B2B SaaS sales teams)
  pain: They can sell, but they can't reliably source qualified prospects
  willingness_to_pay_usd_range: [25, 500]   # Per lead

revenue_model:
  primary: per_lead
  rationale: Performance-based, predictable per-unit economics; exclusivity premium when applicable

standard_milestones:
  - id: m1
    name: Vertical + buyer selection
    typical_hours: 6
    acceptance: One vertical chosen with: (a) buyer LTV ≥$1,000, (b) 5+ identified buyers willing to test-buy 10 leads, (c) clear qualifying criteria written down
  - id: m2
    name: Lead capture funnel
    typical_hours: 12
    acceptance: Landing page with qualifying form; quiz/survey flow if vertical needs it; analytics in
  - id: m3
    name: Traffic source v1
    typical_hours: 8
    acceptance: 1 channel driving traffic — could be SEO content, paid ads (Operator-approved), or partnership; cost-per-lead measured
  - id: m4
    name: First lead delivery
    typical_hours: variable
    acceptance: 10 leads delivered to first buyer; feedback collected on quality
  - id: m5
    name: Pricing dialed in
    typical_hours: 4
    acceptance: Per-lead price set such that gross margin ≥40% after CPL; exclusivity tier offered
  - id: m6
    name: Recurring buyer
    typical_hours: variable
    acceptance: 1+ buyer on weekly recurring purchase

typical_kpis:
  - Cost per lead (CPL): below 35% of sell price
  - Buyer reject rate: <15%
  - Buyer LTV: ≥10 leads
  - Gross margin: ≥40%

common_kill_criteria:
  - CPL > sell price (unprofitable)
  - Buyer reject rate >30% sustained (lead quality is broken)
  - 30 days, no recurring buyer (fit is broken)

recommended_tech_stack:
  - Funnel: Carrd / Tally / Typeform for quiz; Webflow for richer LP
  - Tracking: Plausible or GA4
  - CRM/lead-storage: Airtable
  - Lead delivery: real-time webhook to buyer's CRM (Zapier OK to start) OR daily CSV email
  - Payment: Stripe Invoicing (per-batch billing) or Subscriptions for retainer-style buyers

owner_manager: Marketing
contributors:
  - role: Research
    when: m1 (vertical sizing, buyer identification)
  - role: Compliance
    when: m1 (vertical-specific regs: TCPA, mortgage Reg-Z, insurance state licensing)
  - role: Sales
    when: m4 (selling leads to buyers)
  - role: Engineering
    when: m2 (funnel build), m4 (lead delivery webhooks)
  - role: Monetization
    when: m5 (pricing strategy)

compliance_hot_spots:
  - TCPA: SMS/voice consent capture is strict; must have explicit, written, prior consent
  - Vertical licensing: mortgage leads → many states require lead-broker license; insurance leads → resident agent in some states
  - Lead exclusivity claims: don't sell same lead 2x without disclosure
  - Lead consent: leads must consent to being sold/transferred; capture this on the form
  - GDPR/CCPA: data subject rights apply

typical_budget_usd: 400
time_to_first_dollar_days: 30

skills_to_consult:
  - state/skills/marketing_seo_brief_template.md
  - state/skills/sales_cold_email_first_line.md

playbook_steps:
  - Choose a vertical where 1 lead is worth $1k+ to the buyer and buyers are scattered (no dominant aggregator)
  - Identify 5+ candidate buyers and ask them what makes a "qualified" lead
  - Build a lean qualifying funnel that captures consent (TCPA-compliant if applicable)
  - Drive 1 traffic source — SEO content is cheapest if patient; paid ads faster but Operator-gated
  - Deliver first 10 leads to a single buyer at a discounted "pilot" rate
  - Collect feedback; tighten qualifying criteria
  - Offer exclusive vs. non-exclusive tiers (exclusive = 2-3x price)
  - Scale traffic; bring on second buyer
  - Set up recurring buyer billing
```
