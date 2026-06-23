# Metrics — after (run 2026-06-23-1816)

Code-only round; events.json NOT re-scraped → live-feed metrics unchanged by construction. Deltas land on the next CI scrape.

| Metric | Before | After | Delta |
|---|---|---|---|
| Follow-graph coverage | 15/50 (30.0%) | 15/50 (30.0%) | 0 (gated on scrape) |
| Topic coverage | 0 zero-topics | 0 zero-topics | stable |
| High-conviction ratio | 64/365 (17.5%) | 64/365 (17.5%) | 0 (gated on scrape) |

## ⚠ STALE-FEED WARNING (D1 — APPROVE-DREAM)
This is the **2nd consecutive code-only round with 0 observable metric movement** because no CI scrape has run since 2026-06-15. ~3 rounds of committed levers are stacked **unlanded**:
- run 2026-06-22: Meetup +4 fitness/run searches, +6 Eventbrite fitness/dance slugs, +10 run-club IG seeds, brooklyncontra scraper, fitness boost 1.1→1.3.
- run 2026-06-23 (this): fb-184 P1 fitness score-recovery boost, +6 Eventbrite slugs (hiking/walking-tour/board-games/chess/trivia/climbing), U1 qualitative price pill.

**The single highest-leverage action now is a scrape, not more code.** Metric deltas for all of the above are unverifiable until `python -m scrapers.run_all` runs (residential IP recommended per fb-173 — CI IPs are 403/429-blocked). Recommend triggering a scrape before the next code-only round.

## Verification gates
- **tests:** 256 passed (253 + 3 new fb-183 cases), 3 xfailed.
- **sanity_check:** 2 criticals (NYC Backgammon Club, IG dominant) + 2 warnings — IDENTICAL to pre-run; pre-existing data conditions (fb-174 IG block, backgammon), NOT regressions (events.json unmodified). No rollback.
- **next build:** ✓ clean (Next 16.2.4, TypeScript clean, 4 static pages).
- **P1 gate verified live:** well-formed fitness event (startTime+venue) 0.637 clears 0.55; low-info (no time/venue) 0.536 stays floored — the dual-gate preserves the quality floor.

## Expected next-scrape impact
- fitness/run/dance event count rises (P1 recovers well-formed events over the floor; +12 cumulative on-vector Eventbrite slugs deepen the cap-bound pool).
- Note fb-184 RE-SCOPED: the "inert legacy slugs" premise was disproven — they parse ~20 events each; the bottleneck was MIN_SCORE+cap. P1 is the real lever. Must confirm next scrape: fitness count up AND music CRITICAL_CHECK (≥15) not regressed by cap-eviction.
