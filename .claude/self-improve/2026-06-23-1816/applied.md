# Applied changes — run 2026-06-23-1816

## scrapers/
- [x] ingestion-P1 (MODIFY): fb-184 score-recovery boost — +0.05 for fitness/wellness/outdoors (or run-club/yoga/pilates/contra/swing text) events, HARD-GATED on `startTime AND location.name` (preserves the 0.55 floor for low-info events; self-limited by the existing +0.06 clamp) — `scrapers/ranking.py:537-555`.
- [x] ingestion-P2 (APPROVE): fb-183 — extracted `_is_distinct_schedule_source(ev)` helper; both call-sites (`_dedup_same_account_recurring`, `_dedup_fuzzy_title`) now use it — `scrapers/normalize.py:161-171, :191, :433`. + unit test `TestDistinctScheduleSources` (3 cases: helper membership, bypasses BOTH passes, control still merges) — `scrapers/tests/test_normalize.py`.
- [x] source-pool S1–S4 + trivia + climbing (APPROVE / MODIFY-promote): +6 Eventbrite slugs (hiking, walking-tour, board-games, chess, trivia, climbing) — `scrapers/sources/generic.py`. trivia/climbing exclusion-rechecked (slugs absent from title_hints/hosts/accounts). Also corrected the now-disproven "INERT slugs" comment (fb-184 reframe).

## site/
- [x] ui-U1 (APPROVE, fb-182): qualitative low-commitment price pill (`/donation|pay what|pwyc|sliding scale|suggested/i`), sky-50/sky-700, numeric-wins precedence (`!/\d/` guard) — `site/app/components/EventCard.tsx` (after the numeric pill).

## Dreams
- [x] D1 (APPROVE-DREAM): STALE-FEED warning surfaced in this run's report + journal (no scraper code change) — 2 consecutive code-only rounds, ~3 rounds of levers unlanded; highest-leverage action is a scrape.
- Deferred D2 → fb-186 (strengthen body-text time inference; compounds with P1).

## Backlog additions / status
- fb-185 (P1b): prune dup Brooklyn running slug — open, blocked-on user opt-in.
- fb-186 (D2): body-text time inference strengthening — open.
- fb-187: folk-dance provisional watch — open (watch).
- fb-188: EventModal price-pill consistency nicety — open (low).
- fb-184 → set `addressed: <sha>` in Phase 6, RE-SCOPED (parse-fix → score-recovery): premise overturned (slugs parse ~20 events each; events died at MIN_SCORE+cap, not extraction). P1 recovers well-formed ones. Verify next scrape's fitness count lift + no music-count regression.
- fb-183 → set `addressed: <sha>`.
- fb-182 → set `addressed: <sha>`.

## Skipped / rejected
- None. All proposals APPROVE/MODIFY. folk-dance retire NOT done (additive-only; watch via fb-187). P1b removal NOT done (additive-only; fb-185).
