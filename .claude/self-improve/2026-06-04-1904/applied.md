# Applied changes — 2026-06-04-1904

- [x] ingestion-P1 (APPROVE): OCR-garbage detector `_looks_like_ocr_garbage` + call in `_is_caption_fragment` — `scrapers/quality.py`
- [x] ingestion-P2 (MODIFY): 6 narrative/CTA fragment starters (tightened to `throwing a `/`enter a ballot` per Critic) + leading-stray-quote regex — `scrapers/quality.py`
- [x] ingestion-P3 (APPROVE): Meetup group-slug enrichment in `_enrich_provenance_from_url` (moves silentbookclub.nyc) — `scrapers/normalize.py`
- [x] ingestion-P4 (APPROVE): Lu.ma `__NEXT_DATA__` parser `_parse_luma_next_data` + broad NYC gate + defensive parse (recovers nycbackgammonclub, 6 events) — `scrapers/sources/luma.py`
- [x] source-pool-S1 (MODIFY): added `https://lu.ma/philosophy` to LUMA_PAGES (7 events; covers philosophy.nyc) + the Critic's Dep-2 location-suffix-strip fold in `_user_following_normalized` so the bare `philosophy` slug matches `philosophy.nyc` — `scrapers/sources/luma.py` + `scrapers/normalize.py`. (Hard-dependent on P4 — both shipped.)
- [x] ui-U1 (APPROVE): plain-text `@account` provenance branch for the 68 cross-source-enriched conviction events (no instagramAccount) — `site/app/components/EventCard.tsx`
- [x] D1 (APPROVE-DREAM): `_infer_time_from_text` helper + wired into `process()` to fill absent startTime from "doors at 7pm" body text — `scrapers/normalize.py`
- Deferred to backlog: D2 (added as fb-169) — make `AccountBanner` key on `event.account` so ui-U1's plain handles become clickable per-account routes.

## Verification
- sanity_check: 1 critical (Instagram dominant, IG=46<50) — PRE-EXISTING, user-blocked (stale 33-day IG session), not a regression. Nothing reverted.
- next build: clean (TypeScript pass, 4 static pages).

## Notes
- All metric improvements (philosophy/backgammon/silentbookclub enrichment → follow-graph coverage; OCR purge → high-conviction precision; time inference) materialize on the **next CI scrape** — the code edits don't mutate the stored events.json this round.
