# Applied changes — run 2026-05-28-1552

## Ingestion
- [x] **ingestion-P1** Treat IG `feedback_required` / 429 / rate-limit / checkpoint_required as transient — `scrapers/sources/instagram.py:792` (transient guard in `_record_account_failure`) + skip-set builder (auto-revive of mass-killed accounts). Closes follow-graph 0-yield root cause.
- [x] **ingestion-P2** Mirror `instagramAccount` → `account` field — `scrapers/sources/instagram.py:2533`. Fixes the metric reading 0/246.
- [x] **ingestion-P3 (Critic MODIFY)** Promote 15 socializing-oriented user_following signal_accounts to `IG_ACCOUNTS` — `scrapers/config.py`. (Critic excluded `timeoutnewyork`; user mid-run excluded the 4 individual-person accounts `alvinzx`, `j_palmer_7`, `leahcanel`, `sophiareed5` per fb-106.)
- [ ] **ingestion-P4 REJECTED** — Critic replaced with D2 (the Lu.ma scandal).
- [x] **ingestion-P5 (Critic MODIFY)** Added `_looks_like_glued_handle` predicate (safer alt over the camel-case regex). `scrapers/sources/instagram.py:3017-3037` + applied in `_extract_title`.
- [x] **ingestion-P6** `bk` ↔ `brooklyn` synonym fold in `interest_profile_boost` — `scrapers/utils/interest_profile.py:222`.

## Source pool
- [x] **source-pool-S1** Added 9 Brooklyn URLs to `GENERIC_URLS` — `scrapers/sources/generic.py:117`. All live-probed yield ≥ 8.
- [x] **source-pool-S2 (subsumed)** Both `silentbookclub.nyc` and `crownheightscraftclub` are in the modified P3 add-list.

## UI
- [x] **ui-U1** Card-level sky/amber ring + "Because you follow @X" ribbon on FeedCard and MediaFirstCard — `site/app/components/EventCard.tsx`. Filtered `following`/`affinity` out of the in-card chip row to avoid duplication. Used `event.account || event.instagramAccount` per Critic note.
- [x] **ui-U2 (Critic MODIFY)** Glyph-only `★` (follow) / `♥` (affinity) corner badge on GridCard (dropped "★ FOLLOW" all-caps loudness per user-restraint preference).
- [x] **ui-U3 (Critic MODIFY)** "location in caption" placeholder gated on `!neighborhood` — `EventCard.tsx` FeedCard location row.
- [x] **ui-U4 (Critic MODIFY)** Conviction-first sort in `diversifyByCategory` gated by `score ≥ maxScore - 0.2` — `site/app/components/TopPicks.tsx`.

## Types
- [x] Added `account?: string` to the Event type — `site/app/lib/types.ts`.

## Backlog mutations
- [x] **fb-106** added: socializing-only IG accounts; no individual people. Status `addressed: 2026-05-28-1552` (in-run scrub of 4 personal accounts).
- [x] **fb-104** added (deferred): Prune redundant `/nyc/<topic>` URLs from `LUMA_PAGES` after D1 grows the curator-calendar list. Status `open` per Critic D2 DREAM-DEFER.
- [x] **fb-105** added (deferred): Curator-calendar lu.ma path probing for every `signal_account`. Status `open` per Critic D1 APPROVE-DREAM (script not shipped this round).

## Cross-check
- No removals of `IG_ACCOUNTS`/`LUMA_PAGES`/`GENERIC_URLS`/keyword lists. All additive.
- No localStorage `:v1` bumps.
- No empty-gray-box additions.
- Sidebar untouched (`TopPicks`/`page.tsx` still omit TopAccounts/ActivityPanel).
- This Weekend hero parties-exclusion untouched.
