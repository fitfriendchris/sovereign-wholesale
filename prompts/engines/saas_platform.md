# Engine Archetype: SaaS Platform (APEX Coaching)

```yaml
engine_id: saas_platform
display_name: SaaS Platform
one_liner: Multi-tier SaaS product with auth, billing, and user data — APEX Coaching is the canonical instance.
```

## Project status
APEX is a fitness coaching SaaS, single-file HTML/JS frontend on GitHub Pages,
Supabase backend (auth, realtime, edge functions), Anthropic Claude API for AI features,
Stripe for billing.

## Workdir + key paths
```
~/git/apex/                    # main repo
  index.html                   # single-file app entry
  edge-functions/              # Supabase edge functions (production-ready, audited)
  schema/                      # SQL migrations + RLS policies
  README.md                    # setup + deploy instructions
```

## Tier structure
Free / Core / Elite / VIP / Diamond — feature gating via Supabase RLS + Stripe metadata.

## Production stack
- **Hosting:** GitHub Pages (migrated from Netlify)
- **Auth:** Real Supabase Auth (gated coach dashboard)
- **DB:** Supabase Postgres with RLS policies on every table
- **Realtime:** Supabase realtime channels for messaging
- **AI:** Anthropic Claude API for meal plan builder, plateau detection, etc.
- **Payments:** Stripe billing, webhook → Supabase user.tier sync

## Default Owner: Engineering
Engineering Manager owns code, schema, edge functions, deploys.

## Hard rules
- **Always verify RLS policies** after any data-access change. Test as Free tier user, then Elite tier user, before declaring done.
- **Test edge functions locally** (`supabase functions serve <name>`) before deploying.
- **Never commit Supabase service-role key** — only anon key in client; service-role only in edge functions via Supabase secrets.
- **Stripe live keys** require Operator confirmation before going live.

## Recent feature inventory
Realtime messaging, progress photos, body measurements (Navy BF/FFMI), PR tracking,
barcode food scanner (Open Food Facts), AI meal plan builder, plateau detection,
coach analytics (ARR/LTV/retention), carb cycling, Stripe billing.

## Common Manager dispatch patterns
```
sovereign /dispatch engineering apex "fix RLS on workouts table — Elite users seeing Free user data"
sovereign /dispatch engineering apex "add a Stripe Price for Diamond annual ($2997) and gate the dashboard"
sovereign /dispatch monetization apex "audit funnel from landing → signup → upgrade; report drop-off rates"
sovereign /dispatch marketing apex "draft a Reddit post for r/fitness30plus introducing Elite tier"
sovereign /dispatch compliance apex "check current refund policy + GDPR compliance for EU coaches"
```

## KPIs tracked
- MRR per tier
- Free→Core conversion rate
- Churn (monthly + by tier)
- Coach LTV
- AI feature usage (meal plans/month, etc.)

## Kill criteria
- MRR declines for 3 consecutive months
- Stripe dispute rate >2%
- Critical security finding without fix path
