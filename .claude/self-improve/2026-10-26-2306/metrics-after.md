# Metrics after publication — verified 2026-10-27

Code: `5e8b926b`; published feed: `a4719653`. Public event/community JSON exactly matches the repository. Feed timestamp: 2026-10-27T21:39:40.636347+00:00.

- Historical follow-graph coverage: 50/50 (100.00%) -> 50/50 (100.00%).
- Topic coverage: 8/8 workflow tokens -> 8/8; 4/4 meaningful topics -> 4/4.
- High-conviction ratio: 87/764 (11.39%) -> 94/807 (11.65%).
- Current-feed follow coverage: 17/50 (34.00%) -> 17/50 (34.00%).
- Past-date rows: 0 -> 0. Exact title/date duplicate groups: 0 -> 0.
- Final topic counts: {"bk": 65, "book": 179, "brooklyn": 65, "club": 115, "ny": 157, "nyc": 90, "read": 87, "run": 43}.

The public delta includes the intervening 31 automated data commits and the fresh scrape. It is not an estimate of causal effect from this code alone.

## Controlled live trial, October 26

A 24-request pass took 8.36 seconds, with no timeouts, rate limits, or deadline hits. On exactly the same pages, strict identity/date matching recovered 0 descriptions and verified series-session matching recovered 13. Only descriptions changed. Normalizing both snapshots retained all 764 events and all 87 personalized events; useful descriptions (>=40 characters) increased 503 -> 516. All 13 recovered rows survived unchanged quality filters.

## Production refresh, October 27

The fresh 24-request pass recovered eight descriptions in 3.79 seconds and restored 26 from cache. All eight newly filled rows survived normalization, and the public yoga/book-club detail pages contain their recovered prose. Feed normalization also removed three unrelated carried-over rows (two New York Comedy Club listings and an NBD afterparty); none of the eight enriched rows was removed. Final useful descriptions: 558/807.

Both new history rows identify the same feed snapshot and record run_completed=true, partial_run=false, timed_out_sources=[]. Repeated checks now count once in future medians.
