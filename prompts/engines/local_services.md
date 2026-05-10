# Engine: Local Services (Web/Marketing for SMBs)

```yaml
engine_id: local_services
display_name: Local Services
one_liner: Sell websites and marketing services to small local businesses missing them.

target_buyer:
  who: Small local businesses (SMBs) with no website OR with a poor/abandoned site; <90 days old; or with weak SEO presence
  pain: Losing customers to competitors with basic web presence; can't be found on Google
  willingness_to_pay_usd_range: [300, 3000]

revenue_model:
  primary: subscription
  rationale: $300-$2000/mo retainer for hosting + small content + Google Business management; sometimes $500-$3000 one-time build fee on top

standard_milestones:
  - id: m1
    name: Prospect list
    typical_hours: 4
    acceptance: 100-500 SMBs in target city/vertical with no website OR with sub-3-star Google presence; sourced from Google Maps, Yelp, BBB
  - id: m2
    name: Audit-as-leadgen
    typical_hours: 6
    acceptance: 25 free audits drafted (1-page PDF or video each); generic enough to scale, specific enough to land
  - id: m3
    name: Outbound v1 (25 sends)
    typical_hours: 4
    acceptance: 25 cold emails or DMs sent; reply rate baseline established
  - id: m4
    name: First demo / call
    typical_hours: variable
    acceptance: 1+ booked discovery call
  - id: m5
    name: First close
    typical_hours: variable
    acceptance: 1+ retainer signed; payment received
  - id: m6
    name: Build template + delivery
    typical_hours: 8
    acceptance: Reusable site template (next client's build is <4 hours)

typical_kpis:
  - Email open rate: ≥40%
  - Reply rate: ≥8%
  - Discovery-call → close rate: ≥20%
  - Monthly retainer churn: <5%
  - LTV: ≥$3,000

common_kill_criteria:
  - 100 sends with <2% reply rate (messaging or list is broken)
  - 5 calls with 0 closes (offer is broken)
  - Retainer churn >15%/mo (delivery is broken)

recommended_tech_stack:
  - Email: SendGrid or Postmark (warmed domain — DO NOT use personal gmail)
  - LinkedIn: real personal profile (Operator's or branded business profile)
  - Site builder: Webflow / Carrd / 11ty static — fast and cheap
  - Hosting: Cloudflare Pages or Netlify (free tier OK)
  - Booking: Cal.com (self-hosted or SaaS)
  - CRM: Airtable to start; upgrade only after 50+ leads

owner_manager: Sales
contributors:
  - role: Research
    when: m1 (prospect list)
  - role: Marketing
    when: m2 (audit template)
  - role: Engineering
    when: m6 (site template)
  - role: Branding
    when: m6 (template visual identity)
  - role: Monetization
    when: m5 (retainer pricing + Stripe Subscriptions setup)
  - role: Compliance
    when: m3 (CAN-SPAM check before sends)

compliance_hot_spots:
  - CAN-SPAM: physical address in every email, opt-out link, no deceptive subject
  - Domain warming: never blast 1000 emails from a fresh domain — get blocklisted
  - State laws: some states regulate cold sales practices for specific verticals (legal, medical) — check before targeting
  - Subscription cancel-anytime disclosure (FTC)

typical_budget_usd: 250
time_to_first_dollar_days: 21

skills_to_consult:
  - state/skills/research_smb_no_website.md
  - state/skills/sales_cold_email_first_line.md
  - state/skills/sales_objection_handling_smb.md
  - state/skills/eng_landing_page_template.md
  - state/skills/monetization_smb_retainer_close.md

playbook_steps:
  - Pull Scanner findings: SMBs in 1 target vertical/city without websites
  - Compliance pre-check: confirm CAN-SPAM-compliant outreach is allowed for that vertical
  - Build prospect list (100-500); validate phone/email; check existing presence
  - Generate 25 personalized free-audit PDFs (one per top prospect) — each shows 3 specific issues
  - Send 25-message pilot via warmed email domain
  - Measure open + reply rate; iterate on subject + first line if <30% open or <5% reply
  - Once 1 reply lands, run discovery call from a Cal.com booking link
  - Close on retainer + small build fee; Stripe Subscriptions for monthly billing
  - Build site from reusable template (target: 4 hours per client after template exists)
  - Onboard with monthly Google Business Profile updates and basic content
  - Collect testimonial; use it (with permission) in next campaign
```
