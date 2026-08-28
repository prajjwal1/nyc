# Metrics after

- Feed source: refreshed local snapshot matching the latest fetched `origin/main` data
- Feed last updated: `2026-08-28T17:42:31.574514+00:00`
- Feed events: 539
- Follow-graph coverage: 50/50 (100.0%) — unchanged
- Active-feed follow coverage: 6/50 (12.0%) — newly measured
- Topic coverage: `ny=113`, `nyc=68`, `club=42`, `run=23`, `book=93`, `bk=41`, `brooklyn=41`, `read=38`, `ai=92` — all tracked topics remain represented
- High-conviction event ratio: 90/539 (16.7%) — down 0.1 percentage point because two unflagged events arrived in the concurrent automated refresh

The source additions affect subsequent scrapes rather than rewriting the current 539-event snapshot. Their landed yield and conviction impact will be measured on the next refresh; fb-187 remains open until folk-dance lands at least five events with at least 50% strict participatory fit.
