# Metrics — before (run 2026-06-22-1501)

Feed source: `site/public/events.json` (live deployed fetch unavailable in sandbox; local mirror = deployed-equivalent). 365 events.

- **Follow-graph coverage:** 15/50 (30.0%)
- **Topic coverage:** all topics ≥1 — ny 88, nyc 54, club 74, run 26, bk 42, book 117, brooklyn 42, ai 76, read 43. No zero topics.
- **High-conviction ratio:** 64/365 (17.5%)

Round-specific context (this session's user feedback = more fitness/run-clubs + Brooklyn Contra):
- **Fitness/wellness/dance events in feed:** 29

## Uncommitted session work entering this run (aligned with North Star)
- Meetup: +4 fitness/run-club search URLs (run club / running / fitness).
- Ranking: removed `"running club"` soft-penalty; bumped `fitness` 1.1→1.3, `wellness` 1.05→1.2.
- IG seed: +10 run-club/fitness accounts.
- New `scrapers/sources/brooklyncontra.py` (dedicated Squarespace-store scraper) + `run_all` + `SOURCE_QUALITY` registration; `normalize.py` `DISTINCT_SCHEDULE_SOURCES` exemption.

Note: these are code changes; the deployed `events.json` is not re-scraped in this loop, so metric deltas land on the next CI scrape (consistent with prior code-only rounds).
