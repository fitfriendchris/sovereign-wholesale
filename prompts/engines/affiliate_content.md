# Engine: Affiliate Content

```yaml
engine_id: affiliate_content
display_name: Affiliate / Content Marketing
one_liner: Build niche content that ranks for buyer-intent queries and earns commission on referred sales.

target_buyer:
  who: Consumers researching a specific purchase decision
  pain: Existing top-result content is shallow, biased, or outdated
  willingness_to_pay_usd_range: [0, 0]   # The buyer pays the merchant; we earn commission

revenue_model:
  primary: commission
  rationale: Affiliate networks (Amazon, Impact, ShareASale, individual programs) pay 3-30% on referred purchases

standard_milestones:
  - id: m1
    name: Niche + program selection
    typical_hours: 4
    acceptance: Niche with 3+ buyer-intent queries totaling 5k+ monthly searches AND 1+ affiliate program with ≥10% commission AND average commission $20+ per sale
  - id: m2
    name: Pillar content piece
    typical_hours: 10
    acceptance: One 2,500-4,000 word pillar article with FTC disclosure, comparison table, real-experience-style review
  - id: m3
    name: Distribution v1
    typical_hours: 6
    acceptance: 5 TOS-respecting comments on relevant threads with value-first answers (link only when genuinely helpful); 1 social distribution channel set up
  - id: m4
    name: First click-through
    typical_hours: variable
    acceptance: First tracked affiliate click
  - id: m5
    name: First commission
    typical_hours: variable
    acceptance: First paid commission

typical_kpis:
  - Article ranks top 30 within 60 days
  - Click-through rate from article to merchant: ≥4%
  - Conversion rate (clicks → commission): ≥2%
  - Earnings per 1k visits (EPMV): ≥$10

common_kill_criteria:
  - Article doesn't index in 14 days (technical SEO is broken)
  - 60 days, article still outside top 50 (niche is too competitive)
  - 90 days, $0 commission (offer or content is broken)

recommended_tech_stack:
  - Static site: 11ty, Astro, or Hugo (Cloudflare Pages free hosting)
  - Comments distribution: real Reddit account >90 days old + >100 karma; LinkedIn personal profile; Twitter/X account
  - Tracking: affiliate program's native + UTM tags + Plausible
  - Content production: Sonnet workers for first draft + Operator final-pass review
  - Image: free stock (Unsplash, Pexels) or generated

owner_manager: Marketing
contributors:
  - role: Research
    when: m1 (niche/program selection, competitor SERP audit)
  - role: Compliance
    when: m2 (FTC disclosure), m3 (per-platform TOS)
  - role: Sales
    when: m3 (comment-marketing distribution — value-first only)
  - role: Engineering
    when: m2 (site build), m4 (analytics setup)
  - role: Branding
    when: m1-m2 (site identity if it's a new niche site)

compliance_hot_spots:
  - **FTC 16 CFR 255:** Every affiliate link in user-facing content must have a CLEAR and CONSPICUOUS disclosure ("This post contains affiliate links — we may earn a commission if you buy through them at no extra cost to you"). NOT optional.
  - **Reddit subreddit rules:** many forbid affiliate links entirely. Compliance Manager checks per-subreddit rules before Sales runs comment marketing.
  - **Amazon Associates TOS:** prohibits price quoting (it changes), prohibits offline use of links, requires disclosure
  - **Trademark in domain/title:** never include a competitor's trademark in your domain
  - **Health/financial claims:** if the niche is supplements, investing, weight loss, etc., FTC substantiation rules apply harshly

typical_budget_usd: 80
time_to_first_dollar_days: 45

skills_to_consult:
  - state/skills/research_reddit_question_intent.md
  - state/skills/marketing_seo_brief_template.md
  - state/skills/marketing_reddit_value_first.md
  - state/skills/sales_reddit_value_first.md

playbook_steps:
  - Find a buyer-intent query Scanner flagged with weak SERP (e.g. "best [X] for [specific use case]")
  - Confirm an affiliate program exists with decent commission and reasonable cookie window
  - Plan the article around the exact buyer questions with a comparison table near the top
  - FTC disclosure at top, before any links
  - Publish to a fast static site (Pagespeed >90)
  - Submit to Google Search Console for indexing
  - Distribution: 5 high-value comment-marketing posts on Reddit/forum threads where the question was already asked — answer fully, link only if it directly helps
  - Track clicks in real time; iterate the article when CTR is low
  - Once article ranks top 30, scale by adding 2-3 supporting articles that internal-link to the pillar
```
