# Metrics — before (run 2026-07-13-2033)

Feed: `site/public/events.json`, 423 events, updated 2026-07-13T20:00 (FRESH — CI scraping normally on main since the merge).

- **Follow-graph coverage:** 15/50 (30.0%)
- **Topic coverage:** all present — ny 106, nyc 70, club 72, run 46, bk 38, book 107, brooklyn 38, ai 93, read 38. No zero topics. (Note: "ai"=93 is a substring artifact — "ai" in hair/brain/available/etc — not real AI-event coverage; pre-existing metric noise.)
- **High-conviction ratio:** 95/423 (22.5%)
- taste-active events: 423 (P6 follow-graph cold-start live)

## Trajectory (program landing)
- run coverage 26→46 (fitness/run-club work), conviction 17.5%→22.5% (taste + conviction), saturation fixed (critic P1), junk purged (critic P5), taste loop active (critic P6). All shipped + deployed.

## Open critic items to target this round (from the deployed-feed review)
- **P3:** Queens/LIC neighborhood mistag (MoMA PS1 → "midtown"; ~19% null neighborhoods) — normalizer data bug, scrape-independent + testable.
- **P7:** coverage gaps — no backgammon/chess (user named them), underground-electronic thin beyond Warm Up, social-dance contra-only.
- openbookclub still missing (IG-blocked, fb-174).

---
# AFTER (code changes committed f53488a; feed metrics unchanged until next scrape)
- Follow-graph coverage: 15/50 (30.0%) → 15/50 (30.0%)
- Topic coverage: all present → all present
- High-conviction ratio: 95/423 (22.5%) → 95/423 (22.5%) (this round's source/neighborhood adds land next scrape)
- Verification: 310 tests pass; sanity_check Critical failures 0; next build clean.
- Next-scrape expected: backgammon/chess/swing events appear; Elsewhere electronic lifts (boost-only); MoMA PS1→long island city; openbookclub on a future-dated post.
