# Metrics — after (run 2026-06-22-1501)

Code-only round: `site/public/events.json` was NOT re-scraped, so the live-feed metrics are unchanged this round by construction (same as prior code-only rounds — deltas land on the next CI scrape).

| Metric | Before | After | Delta |
|---|---|---|---|
| Follow-graph coverage | 15/50 (30.0%) | 15/50 (30.0%) | 0 (deltas land next scrape) |
| Topic coverage | 0 zero-topics | 0 zero-topics | stable |
| High-conviction ratio | 64/365 (17.5%) | 64/365 (17.5%) | 0 (deltas land next scrape) |

## Verification gates
- **sanity_check:** 2 criticals (NYC Backgammon Club, Instagram dominant) + 2 warnings — IDENTICAL to pre-run state (observed at session start before any edits). Both are pre-existing DATA conditions (fb-174 IG GraphQL block; backgammon yield), NOT regressions from this code-only round (events.json unmodified). No rollback.
- **next build:** ✓ clean (Next 16.2.4, TypeScript clean, 4 static pages).
- **tests:** 253 passed, 3 xfailed.

## Expected impact on next CI scrape (where the real deltas land)
- Fitness/wellness/dance event count rises: Meetup +4 run-club/fitness searches (live-verified 74 fitness/run events scraped), +6 Eventbrite specific slugs (run-club/contra/swing/folk/salsa/pilates, 20/20 future each), +10 run-club/fitness IG seeds (when IG sweep available).
- Recurring run clubs no longer soft-penalized (P1) and clear the 0.55 floor (fitness boost 1.1→1.3).
- Brooklyn Contra: 10 dated dances surface (verified end-to-end through normalize), incl. both Sep-26 sessions (P3) and the recovered Oct-4 Raven & Goose (P2).
- fb-181 fix recovers any legit title containing a short-hint substring ("Raven"/"travel"/"gravel"/"brave").

## State-file hygiene
Test-induced churn in `url_health.json` + `user_interest_profile.json` (from probing/normalize during verification) was reverted to HEAD — this round commits code + docs only.
