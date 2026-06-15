# Verification — 2026-06-15-1724

## next build
- CLEAN. Next.js 16, compiled successfully, TypeScript passed, all static pages generated. The 3-file ui-U1 change (lib/events.ts, AccountBanner.tsx, EventCard.tsx) builds with no type errors.

## pytest
- 253 passed, 3 xfailed. The ranking.py story-floor (P2) and interest_profile D1 changes don't break any existing test.

## sanity_check
- 2 critical failures: "NYC Backgammon Club" and "Instagram is dominant source". 2 warnings.
- **NEITHER is caused by this run's edits.** Confirmed: this run modified only code (`scrapers/ranking.py`, `scrapers/utils/interest_profile.py`, `.claude/commands/self-improve.md`) + site/*; it did NOT modify `data/events.json` (verified via `git status`). sanity_check reads `events.json`, so the result is a property of the data state, not these edits.
  - "Instagram is dominant source": long-standing, user-blocked (fb-174 — IG GraphQL sweep is 400-blocked fleet-wide). IG can't be the dominant source while the sweep is blocked.
  - "NYC Backgammon Club": the current feed has 0 backgammon events (lu.ma/nycbackgammonclub has no upcoming events right now; the prior OCR false-positive that used to satisfy this check was correctly filtered out by the 4fee74e quality cleanup). This is a data-freshness condition, not a code regression. The check will pass again when the backgammon club posts upcoming events (the lu.ma __NEXT_DATA__ parser already handles them — verified earlier this session).
- Per the verification rules, no revert performed (this run's edits did not regress any CRITICAL).

## D1 verification (the headline win)
- After the fold fix (location-suffix folding), `build_profile()` credited reading_rhythms + silentbookclub.nyc via non-IG enriched events. Follow-graph coverage rose 24.0% (12/50) -> 30.0% (15/50) — independent of the blocked IG sweep, which is exactly the point.

## P1 verification
- bk topic-coverage: 0 -> 42 via the bk<->brooklyn fold in the metric script. No zero topics remain.

## P2 verification
- Story-scoped floor drops the 3 live garbage stories; 253 tests pass; isStory-gated so non-story digit/imperative titles untouched (verified by the Critic against /tmp/si_feed.json).

## Nothing rolled back.
