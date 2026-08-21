# Metrics before

- Feed: local checkout fallback, `lastUpdated=2026-08-21T16:21:07.066045+00:00` (Python's local CA configuration rejected the live TLS certificate).
- Follow-graph coverage: 50/50 (100.0%).
- Topic coverage: ny=68, nyc=44, club=25, run=21, book=38, bk=21, brooklyn=21, read=25, ai=49. Zero covered topics: 0.
- High-conviction ratio: 36/286 (12.6%).

## Ranking baseline

- Top-12 mean taste score: 0.0582.
- Top-12 events with an explicit follow/save/affinity signal: 8/12.
- Top-30 mean taste score: 0.0395.
- Top-30 events with an explicit follow/save/affinity signal: 11/30.
- Top-30: 24 organizers, 15 categories, max organizer share 6.7%, max repeated series 1.

## Keyword audit

The semantic taste model is active through follow-graph cold start, but no `user_engagement.json` snapshot exists, so it has no explicit negative examples yet.

| Cluster | Keywords | Events hit | Mean taste when hit | Mean taste when not hit | Decision |
|---|---:|---:|---:|---:|---|
| Hard blocks | 588 | n/a | n/a | n/a | Keep: explicit safety and user exclusions. |
| Soft penalties | 33 | 4 | 0.0390 | 0.0226 | Keep: explicit drinking/low-value policy; negative taste data is absent. |
| Social | 39 | 18 | 0.0178 | 0.0232 | Keep as a product-goal prior, but remove unreachable hard-block overlap. |
| Alcohol-free | 24 | 7 | 0.0298 | 0.0227 | Keep: explicit user preference and positive agreement with taste. |
| High value | 90 | 80 | 0.0162 | 0.0254 | Narrow: remove source-specific and hard-blocked terms; prevent phrase stacking. |

High-value phrases matched two or more times on 19 events, allowing one concept such as `live performance`/`performance` to consume the full +0.30 boost before taste and other signals were considered.
