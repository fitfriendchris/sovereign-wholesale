# Engine Archetype: Mobile PWA (Flourish)

```yaml
engine_id: mobile_pwa
display_name: Mobile-First Progressive Web App
one_liner: Single-file HTML/JS PWA constrained to a phone-shell — Flourish is the canonical instance.
```

## Project status
Flourish is a luxury PWA concept — secret-society themed digital experience.
Single-file HTML, vanilla JS, Tailwind CDN. Deployed to GitHub Pages on the `gh-pages` branch.

## Workdir + key paths
```
~/git/flourish/
  index.html                   # single-file app
  assets/                      # icons, images
  .github/workflows/           # GitHub Actions for deploy
```

## Visual + structural constraints (CRITICAL)
- **390px shell**: the entire app is a `.phone-frame` container at 390px width
- **Theme**: cream `#FFF8F0` / navy `#1A3A5C` / gold `#C9A227`
- **Modals must be CHILDREN of `.phone-frame`** — never siblings. `position: absolute` anchors to the nearest positioned ancestor; siblings break on resize.
- **Stack**: vanilla JS only, Tailwind CDN, no React, no build step

## Distribution + payments
- Scarcity mechanics (waitlist, limited drops)
- Stripe payment links (no full Stripe.js integration)
- Vercel for marketing site, Namecheap for domain
- Typeform + Zapier for waitlist intake

## Default Owner: Engineering
Engineering Manager owns the single-file HTML, Tailwind classes, modal structure, deploy.

## Hard rules
- **Never break the 390px phone shell** — always test on a 390px viewport, not desktop
- **Modal anchoring rule** — never put a modal as sibling of `.phone-frame`
- **No build step** — keep it copy-pasteable HTML/JS
- **Stripe payment links only** — no full Stripe Elements integration unless explicitly approved

## Common Manager dispatch patterns
```
sovereign /dispatch engineering flourish "add a 'limited drop' modal that's child of .phone-frame, gold border, opens on CTA click"
sovereign /dispatch branding flourish "draft 3 alt taglines that fit the secret-society theme — 8 words max each"
sovereign /dispatch marketing flourish "draft a Twitter/X waitlist hype thread (8 tweets) for the next drop"
sovereign /dispatch monetization flourish "review Stripe payment link conversion vs. waitlist signup rate"
```

## KPIs tracked
- Waitlist signups
- Drop conversion rate (waitlist → purchase)
- Average drop revenue
- Time-to-sellout per drop

## Kill criteria
- 3 consecutive drops with <50% sellout
- Total revenue < $500/quarter
