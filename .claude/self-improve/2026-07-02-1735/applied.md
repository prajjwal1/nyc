# Applied changes — run 2026-07-02-1735

## scrapers/ (ingestion — applied by worker, APPROVED by Critic, kept)
- [x] ingestion-fb189 (APPROVE): neighborhood/name contradiction fix — new `_explicit_hood_in_text` Step-0 in `_backfill_neighborhood_from_venue` (explicit word-boundaried neighborhood token in venue name/addr wins over the venue-table default + address inference) + word-boundary matching for short ≤3-char keywords (les/ues/uws) in `infer_neighborhood`. `scrapers/normalize.py`, `scrapers/utils/event_parser.py`. Critic-verified on the frozen feed: conflicts 10→0, also fixed "Singles Night"→LES mistag, WGB CRITICAL_CHECK strengthened 36→38, no correct case regressed. +5 tests.
- [x] ingestion-fb186 (APPROVE): rebuilt `_infer_time_from_text` — two tiers (keyword-anchored cues earliest-wins; bare-clock fallback fires only on a single distinct am/pm time; ranges/multi-time abstain; fills only absent startTime, never overwrites). `scrapers/normalize.py`. Critic adversarially probed 13 hostile inputs (subway lines, prices, years, phones) → all None/abstain. +15 tests. Honestly unblocks the fb-184 fitness startTime gate.

## site/ (ui)
- [x] ui-fb188 (APPROVE): EventModal price-pill parity with FeedCard — numeric-gray + qualitative-sky guards (same regex), "varies"/"TBA"/"unknown" render nothing. `site/app/components/EventModal.tsx`.

## source-curator — no changes (stale-feed moratorium; validation only)
- 12 IG seeds fb-106 + exclusion clean; folk-dance lean-keep (~50% participatory); recommends a residential-IP scrape (Critic ENDORSED).

## Dreams (DREAM-DEFER)
- D1 (Did-you-go past-save calibration) → already tracked as open fb-178; not duplicated.
- D2 (venue alias normalization) → new fb-193.

## Backlog status (for Phase 6)
- fb-189 → addressed: <sha> (this round).
- fb-186 → addressed: <sha> (this round).
- fb-188 → addressed: <sha> (this round).
- fb-190/191/192 already addressed (8d10fc2 / b6a0cf3) by the feedback-collector.
- fb-193 new (open).

## Skipped / rejected
- None. All 3 proposals APPROVED. No new source adds (moratorium). folk-dance kept (fb-187 watch stands).

## ⚠ Standing: 3rd consecutive frozen round — a residential-IP scrape is the single highest-leverage next action (Critic + source-curator concur).
