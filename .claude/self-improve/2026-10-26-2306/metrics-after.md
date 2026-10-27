# Metrics after local verification (before publication)

The public/checked-in snapshot remains the same verified 764-event feed while the code is prepared for publication.

- Historical follow-graph coverage: 50/50 (100.00%) -> 50/50 (100.00%).
- Topic coverage: 8/8 workflow tokens -> 8/8; 4/4 meaningful topics -> 4/4.
- High-conviction ratio: 87/764 (11.39%) -> 87/764 (11.39%).
- Active-feed follow coverage: 17/50 (34.00%) -> 17/50 (34.00%).

## Controlled live trial — not yet a deployed claim

A single 24-request pass took 8.36 seconds, with no timeouts, rate limits, or deadline hits. On exactly the same fetched pages, strict identity/date matching recovered 0 descriptions and explicit series-session matching recovered 13. The trial only changed descriptions. Normalizing both snapshots retained all 764 events and all 87 personalized events; useful descriptions (>=40 characters) increased 503 -> 516. All 13 recovered rows survived the unchanged quality filters, and all critical counts stayed identical.

The actual post-scrape public metrics will be recorded after deployment.
