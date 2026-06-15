# Applied changes — 2026-06-15-1724

- [x] ingestion-P1 (APPROVE): bk↔brooklyn synonym fold in the metrics-script topic counter — `.claude/commands/self-improve.md:58-62`. Fixes the `bk`=0 measurement bug (lifts bk 0→43).
- [x] ingestion-P2 (APPROVE): story-scoped title floor in `scrapers/ranking.py::compute_score` (after the title-quality nuke). Drops digit-prefix / imperative-prefix `isStory` titles ("2 mini lobster rolls", "45 minutes of feel Sood", "Purchase a @nike kit…"); legit stories survive; non-story titles untouched (isStory-gated).
- [x] D1 (APPROVE-DREAM): credit non-IG enriched (`userFollowing`) events into `yield_map` second pass — `scrapers/utils/interest_profile.py::build_profile`. Moves reading_rhythms / nycbackgammonclub / philosophy.nyc 0→>0 (follow-graph coverage), independent of the IG block. This is the corrected form of source-pool-S1.
- [x] ui-U1 (APPROVE, ships fb-169): clickable `@account` filter for cross-source-enriched conviction handles — 3 files: `site/app/lib/events.ts` (load-bearing predicate now matches `event.account`), `site/app/components/AccountBanner.tsx` (count account-matches + `isIg` guard suppresses "Open on IG" for non-IG handles + empty-banner guard preserved), `site/app/components/EventCard.tsx` (plain span → clickable button).
- [skipped] source-pool-S1 (REJECT — diagnosis wrong): the reading_rhythms "handle-fold gap" is inert; the fold already matches (conviction fires). Replaced by D1 (the real measurement-architecture fix).
- [x] ui-U2 (APPROVE no-op): heroes already `.length>0`-guarded; no change.
- [x] source-curator 0-adds (APPROVE): honest negative; nothing cleared ≥5 live yield via a parseable path. No change.
- Deferred to backlog: D2 → fb-178 ("Did you go?" attend/skip affordance on past saved events).

## Verification — see verification.md
## Metric effects (D1 + P1 + P2) land on the next profile rebuild / metric run.
