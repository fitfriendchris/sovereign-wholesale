# Engine: Digital Products

```yaml
engine_id: digital_products
display_name: Digital Products
one_liner: Create and sell ebooks, templates, and mini-courses on niches with unmet question intent.

target_buyer:
  who: Self-learners with specific, action-oriented questions and credit-card-ready intent
  pain: Existing free content is shallow, contradictory, or scattered; they want one trusted package
  willingness_to_pay_usd_range: [7, 497]

revenue_model:
  primary: one_time
  rationale: Low friction, fits informational goods, fast feedback loop on whether the niche is real

standard_milestones:
  - id: m1
    name: Niche validation
    typical_hours: 4
    acceptance: 3+ Reddit/forum threads with 50+ engaged comments expressing the pain; Google Trends rising or stable; competitor analysis shows weak top-3 SERP
  - id: m2
    name: Outline + ToC
    typical_hours: 3
    acceptance: 8-15 chapter outline that maps to the validated questions; reviewed against existing competitor offerings
  - id: m3
    name: Draft v1
    typical_hours: 12
    acceptance: Full draft, 8k-25k words, Operator-readable
  - id: m4
    name: Cover + landing page
    typical_hours: 4
    acceptance: Cover image (3 sizes), 1-page landing with headline, subheadline, ToC, $ price, CTA
  - id: m5
    name: Stripe/Gumroad checkout live (test mode → live)
    typical_hours: 3
    acceptance: Test transaction passes; refund policy live; Operator approves go-live
  - id: m6
    name: Distribution v1
    typical_hours: 6
    acceptance: 3+ TOS-respecting comment-marketing posts; 1 SEO article; first 7 days of analytics in
  - id: m7
    name: First sale
    typical_hours: variable
    acceptance: ≥1 paying customer

typical_kpis:
  - Conversion rate landing → checkout: ≥2%
  - Refund rate: <5%
  - 30-day net revenue: ≥3× build cost

common_kill_criteria:
  - Zero sales in 21 days post-launch despite traffic
  - Refund rate >15% sustained
  - Compliance flag raised post-launch (e.g. health/financial claims)

recommended_tech_stack:
  - Gumroad (fastest live; takes 9.5% + $0.30) OR Stripe Checkout (3% but more setup)
  - Carrd or a single-file HTML LP
  - Beehiiv for email capture (optional)
  - Cloudinary for cover image variants

owner_manager: Engineering
contributors:
  - role: Branding
    when: m4 (cover + landing)
  - role: Marketing
    when: m6 (distribution)
  - role: Sales
    when: m6 (comment marketing)
  - role: Monetization
    when: m5 (checkout)

compliance_hot_spots:
  - FTC substantiation: any "make $X/month" or "lose Y pounds" claim must be substantiated or disclosed
  - Refund policy: must be displayed before checkout
  - Affiliate disclosure: any embedded affiliate links inside the product need 16 CFR 255 disclosure
  - Copyright: never use stock content claimed as original; never copy competitor outlines

typical_budget_usd: 60
time_to_first_dollar_days: 14

skills_to_consult:
  - state/skills/research_reddit_question_intent.md
  - state/skills/marketing_landing_page_anatomy.md
  - state/skills/monetization_stripe_checkout_flow.md
  - state/skills/sales_reddit_value_first.md

playbook_steps:
  - Pull Scanner finding (Reddit/forum thread with high engagement, weak existing SERP)
  - Validate with 2-3 additional sources of question intent
  - Outline the ebook around the exact questions asked
  - Draft via Sonnet workers; Operator reads draft before final pass
  - Cover via image-gen worker; landing page via Engineering
  - Set price from comparable: $7-$17 ebook, $47-$97 if it's a clear comprehensive guide
  - Live on Gumroad in test mode; Operator approves go-live
  - Comment-market on the original threads (value-first; FTC-disclosed link)
  - Write 1 SEO article that ranks for the underlying query and links to the product
  - Track for 21 days; iterate or kill
```
