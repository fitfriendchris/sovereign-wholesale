# Engine Archetype: Curriculum Product (Biblical Life Mastery)

```yaml
engine_id: curriculum_product
display_name: Curriculum / Educational Content Product
one_liner: Multi-pillar educational curriculum + companion app — Biblical Life Mastery is the canonical instance.
```

## Project status
Biblical Life Mastery is a curriculum + app combo covering Health/Wealth/Relationships
pillars, scripture-rooted, with both publish-ready markdown deliverables and full app
architecture (Postgres schemas, REST/GraphQL endpoints, RBAC).

## Workdir + key paths
```
~/Biblical_Life_Mastery/
  curriculum/                  # publish-ready markdown lessons (NOT outlines)
  architecture/                # PostgreSQL schemas, API specs, RBAC matrix
  brand/                       # voice + visual guidelines
```

## Tone + voice
Authoritative, inspiring, disciplined, scripture-rooted. Cross-pollinate Health/Wealth/Relationships pillars in every lesson — never silo a pillar.

## Default Owner: Engineering
Engineering Manager owns both curriculum and app architecture. Branding owns the voice
guide. Marketing owns distribution.

## Hard rules
- **Publish-ready markdown only** — never deliver bullet outlines as the final artifact
- **Cross-pillar by default** — a Health lesson should reference Wealth/Relationships connections
- **Cite scripture accurately** — chapter:verse, book in full
- **For app specs**: explicit Postgres schemas, REST/GraphQL endpoint contracts, RBAC matrix

## Common Manager dispatch patterns
```
sovereign /dispatch engineering biblical "draft a publish-ready 1500-word lesson on stewardship — cross-pollinate Health (body as temple) + Wealth (Parable of Talents)"
sovereign /dispatch engineering biblical "design Postgres schema for user_progress, lessons, badges with RLS for tier-gated content"
sovereign /dispatch branding biblical "name + tagline for a bundled 'Armour of God 12-week program' — 8 words max"
sovereign /dispatch marketing biblical "draft a launch email for the 'Spiritual Formation' module to existing waitlist"
sovereign /dispatch compliance biblical "review claims in module 1 against FTC substantiation rules + religious-content advertising guidelines"
```

## KPIs tracked
- Lessons published per week
- Module completion rate (per pillar)
- Email engagement (open/click) per launch
- Revenue per launched module

## Kill criteria
- 90 days, no published modules
- Module launches < $100 net
- Compliance flag escalation on faith-based claims
