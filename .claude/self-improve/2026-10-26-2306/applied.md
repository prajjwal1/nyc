# Applied changes

- [x] ingestion-P1: verified Eventbrite recurring-occurrence descriptions — `scrapers/utils/descriptions.py:88`; reduced public source fixtures plus identity/date/time/privacy/metadata/request-budget regressions.
- [x] ingestion-P2 (MODIFY): distinct successful source snapshots, current-snapshot exclusion, bounded median, and persisted run health — `scrapers/sanity_check.py:493`; failed/partial/timeout/duplicate/legacy/malformed and warning-output regressions.
- [x] source-pool-S1: retained configured discovery after auditing current coverage and Open Book Club. No speculative source additions.
- [ ] ui-U1: visual redesign deferred; no local browser could initialize. fb-212 remains open.
- Deferred dream D1: failure-reason telemetry added as fb-224.

No threshold, exclusion, ranking weight, source list, storage key, or deployed data file was modified by this commit. A fresh CI scrape will publish the actual enriched inventory after the push.
