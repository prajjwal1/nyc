# Applied changes — run 2026-06-22-1501

## Already-implemented this session (uncommitted; land in this run's commit) — fb-179 + fb-180
- [x] fb-179 fitness/run-clubs: `scrapers/sources/meetup.py` (+4 run-club/running/fitness searches); `scrapers/quality.py` (removed `"running club"` soft-penalty); `scrapers/config.py` (fitness 1.1→1.3, wellness 1.05→1.2, +10 run-club/fitness IG seeds).
- [x] fb-180 Brooklyn Contra: new `scrapers/sources/brooklyncontra.py` + `run_all.py` + `SOURCE_QUALITY` reg + `normalize.py` DISTINCT_SCHEDULE_SOURCES recurring-merge exemption.

## scrapers/ (this round's Critic-approved edits)
- [x] ingestion-P1 (APPROVE): scope-skip "every <weekday>" soft-penalty for fitness/wellness/outdoors text — `scrapers/quality.py::quality_signals` (~1140).
- [x] ingestion-P2 (MODIFY): generalized `\b<hint>\b` word-boundary matching for short single-word exclusion title-hints (len≤6, no-space, alpha), precompiled+cached in `_load_user_excluded_sources`; matcher loop in `is_user_excluded` — `scrapers/ranking.py`. Fixes fb-181 ('rave'→"Raven").
- [x] ingestion-P3 (APPROVE): exempt DISTINCT_SCHEDULE_SOURCES from `_dedup_fuzzy_title`; promoted `DISTINCT_SCHEDULE_SOURCES` to module scope — `scrapers/normalize.py`. Recovers both Sep-26 Harvest Ball sessions.
- [x] source-pool-S1..S3,S5,S6 (APPROVE) + S4 (MODIFY, provisional): +6 Eventbrite category slugs (run-club, contra-dance, swing-dance, folk-dance[provisional], salsa, pilates) — `scrapers/sources/generic.py`.

## site/
- [x] ui-U1 (APPROVE): non-free digit-price pill on FeedCard — `site/app/components/EventCard.tsx` (~222). Qualitative-price words deferred to D1/fb-182.

## Dreams (DREAM-DEFER → backlog)
- Deferred: D1 → fb-182 (qualitative price pills). D2 → fb-183 (shared DISTINCT_SCHEDULE_SOURCES helper + queued fb-106-clean IG fitness/dance candidates for when fb-174 clears).

## Skipped / rejected
- None. All worker proposals APPROVED or MODIFIED; zero directives deferred-rejected.

## Backlog status (for Phase 6)
- fb-179, fb-180 → set `addressed: <sha>` once commit lands.
- fb-181 → addressed by P2 this round → set `addressed: <sha>`.
- fb-182, fb-183 → new open agent-proposals.
