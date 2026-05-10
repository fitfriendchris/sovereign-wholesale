# Opportunity Scanner — 24/7 Discovery System

Continuously scans the internet for revenue-generating gaps. Feeds Strategy.
Implemented in `dispatch/scanner.py`. Runs under launchd
(`~/Library/LaunchAgents/com.sovereign.scanner.plist`).

---

## Schedule

- **Cycle interval:** 4 hours (configurable in `dispatch/scheduler.py`)
- **Per-cycle budget cap:** $1.50 in API calls (default; Operator overrides via
  `/scanner budget <usd>`)
- **Daily Operator visibility cap:** max 3 Business Reviews/day (high-score overflow
  parks in `state/opportunities.json` with status `hold`)

---

## Scan Targets

Each target has:
- A `query_template` (what the worker is asked to find)
- A `source_set` (where to look — public APIs, RSS, search queries, etc.)
- A `rate_limit` (max requests/cycle)
- A `score_weights` override if needed

### Real Estate (engine: `re_wholesale`)

| Source | What to extract |
|--------|-----------------|
| County tax-delinquent lists (public records) | Owner name, parcel, amount owed, days delinquent |
| FSBO listings on Craigslist/FB Marketplace | Address (or zip), asking price, days listed |
| Expired MLS listings (from public aggregator feeds) | Address, last asking, expiration date |
| Absentee-owner public records | Owner mailing address ≠ property address |
| REIT / institutional cash-buyer announcements (10-K, pressers) | Buyer name, target geography, criteria |

Output per finding: a structured `OPPORTUNITY` record with `engine: re_wholesale`,
estimated assignment-fee TAM, time-to-close estimate, compliance flags
(state-restricted-wholesaling).

### Local Services (engine: `local_services`)

| Source | What to extract |
|--------|-----------------|
| Google Maps SMBs in target cities | Business name, no-website flag, rating, review count |
| Yelp businesses with poor SEO scores | Name, vertical, current ranking |
| BBB-registered businesses (sub-90-day-old) | Name, vertical, contact |

Output: estimated retainer TAM ($300–$2000/mo per SMB), close-rate estimate.

### Digital Products (engine: `digital_products`)

| Source | What to extract |
|--------|-----------------|
| Reddit threads with question intent + no top answer | Subreddit, thread title, comment count |
| Google Trends rising queries | Query, region, growth %, top-10 SERP weakness |
| Amazon "people also asked" gaps | Query, related-product clusters |

Output: niche, estimated monthly searches, suggested product format (ebook vs. mini-course).

### Lead Brokerage (engine: `lead_brokerage`)

| Source | What to extract |
|--------|-----------------|
| B2B SaaS niches with high LTV + scattered targeting | Niche, average ACV, fragmented buyer signals |

Output: target lead criteria, estimated per-lead price ($25–$500).

### Affiliate / Comment Marketing (engine: `affiliate_content`)

| Source | What to extract |
|--------|-----------------|
| Product comparison queries with weak top-result content | Query, current SERP, weakness |
| Active forum/Reddit threads asking for recommendations (TOS-respecting) | Thread, question, allowed networks |

Output: affiliate program candidate, estimated commission per close.

---

## Scoring Rubric (0–100)

Each opportunity is scored across 6 dimensions, weighted:

| Dimension | Weight | Notes |
|-----------|--------|-------|
| TAM | 25 | Larger market = higher score; capped at 100 → tam_usd / max_tam_seen |
| Time-to-first-dollar | 20 | Inverted: 0 days = 20pts, 30+ days = 0pts |
| Build cost (lower is better) | 15 | Inverted: $0 = 15pts, $1000+ = 0pts |
| Defensibility | 10 | Subjective 0–10 from worker; how easy is this to copy |
| Legal risk (lower is better) | 15 | Inverted from Compliance: 0 risk = 15pts, blocked = 0 |
| Operator-fit | 15 | Matches Operator stated preferences (gold/silver, terse, no in-person, etc.) |

**Trigger threshold:** Score `>= 75` surfaces to Strategy's inbox.
**Hard block:** Score `< 75` archived after 7 days unless re-scored.
**Compliance hard-block:** any `compliance_flag` of severity `block` immediately
archives the opportunity regardless of score, with a note in the audit log.

---

## Per-Cycle Workflow

```
scanner.run_cycle():
  for target in scan_targets:
    if target.disabled or rate_limited(target): continue
    worker = dispatch_worker(
      role="research_scanner",
      model="haiku-4.5",
      brief=target.query_template,
      max_cost_usd=cycle_budget / len(scan_targets),
    )
    findings = worker.collect()
    for f in findings:
      opp = normalize(f, engine=target.engine)
      opp.score = compute_score(opp)
      opp.compliance_flags = compliance.precheck(opp)
      registry.ingest_opportunity(opp)
  registry.rescan_pending()
  strategy.notify_top_n(10)
```

---

## Rate Limits & Anti-Ban

- Never scrape behind login walls.
- Honor `robots.txt` and platform TOS. Use official APIs where they exist.
- Cap requests per source: ≤ 30/cycle per domain.
- Random jitter (1–5s) between requests.
- Exponential backoff on 429/403.
- If a domain returns 3 consecutive blocks, disable that source for 24 hours and log a
  `scanner_alert`.

The Operations Manager monitors `scanner_alert` events. The Operator sees them only if
they accumulate (3+ in 24h triggers a `decision_required`).

---

## Operator Controls (via Telegram)

| Command | Effect |
|---------|--------|
| `/scanner pause` | Pauses all cycles |
| `/scanner resume` | Resumes |
| `/scanner budget <usd>` | Sets per-cycle budget |
| `/scanner targets` | Lists active targets |
| `/scanner enable <target>` / `/scanner disable <target>` | Toggle a target |
| `/scanner score <opp_id>` | Returns full scoring breakdown for one opportunity |

---

## Output: `state/opportunities.json`

```json
{
  "queue": [
    {
      "id": "opp_<timestamp>_<short_hash>",
      "engine": "digital_products",
      "score": 82,
      "score_breakdown": {"tam": 18, "ttfd": 17, "build_cost": 14, "defensibility": 6, "legal": 15, "operator_fit": 12},
      "tam_usd": 4200,
      "ttfd_days": 7,
      "build_cost_usd": 60,
      "compliance_flags": [],
      "raw_finding": "Reddit thread r/investing with 2.1k upvotes, no consolidated guide for...",
      "source": "https://...",
      "discovered_at": "2026-05-08T12:34:56Z",
      "status": "new",
      "promoted_to_review_at": null
    }
  ]
}
```
