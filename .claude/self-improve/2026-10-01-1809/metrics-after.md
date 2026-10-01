# Metrics after — 2026-10-01-1809

Validated public snapshot: `2026-10-01T18:23:03.843104+00:00`. Pages run `36906687207` succeeded; independent HTTPS reads of both public JSON files match the committed copies exactly.

| Signal | Before | After |
|---|---:|---:|
| Upcoming events | 788 | 848 |
| Historical follow-graph coverage | 50/50 (100.0%) | 50/50 (100.0%) |
| Active-feed follow coverage | 8/50 (16.0%) | 8/50 (16.0%) |
| Tracked topic coverage | 8/8 | 8/8 |
| Meaningful topic coverage | 4/4 | 4/4 |
| High-conviction events | 70/788 (8.88%) | 70/848 (8.25%) |
| Today's feed with useful descriptions | 26/55 (47.3%) | 42/58 (72.4%) |
| Luma useful descriptions | 0/69 | 15/70 |
| Eventbrite useful descriptions | 15/157 | 85/220 |
| Feature-ready upcoming events | 467 | 534 |
| Past events / exact title-date duplicates | 0 / 0 | 0 / 0 |

Useful descriptions contain at least 40 characters. Thirty pre-existing listings gained descriptions. The 60 net additional events came from the existing platform refresh/discovery machinery, not new hardcoded source URLs. The conviction numerator remains 70; its percentage falls because the allowed inventory grew.

The daily metric includes every October 1 row, before the browser hides events that started over three hours ago. Applying that same cutoff to both snapshots at 14:23 New York time gives 26/51 (51.0%) before and 40/54 (74.1%) after. These are description availability metrics, not claims that every card prints the full body; full text is shown on the detail page or quick view.

Final tracked topic counts: ny=168, nyc=101, club=90, run=42, book=149, bk=88, brooklyn=88, read=61.

The final description pass reused 31 cached event descriptions and requested 24 pages, recovering 13 more descriptions in 3.31 seconds. There were no source timeouts, request timeouts, HTTP 429s, or deadline hits. The prior actual refresh recovered 15 descriptions in 3.70 seconds. Two completed runs demonstrate persistence across real catalog refreshes.

Luma captured 58/58 advertised city events with no missing graphics; the Partiful refresh captured 289 raw events with no missing graphics. All six sanity critical checks pass. Current exclusion checks return zero leaks. Newly exposed text removed the consumer-industry dinner and speed-dating listing through existing filters.
