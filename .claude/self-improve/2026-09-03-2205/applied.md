# Applied changes

- [x] ingestion-P1 / source-S4: made a fresh, completed, today-onwards feed a release gate; operational scrape and deploy remain required before closure.
- [ ] ingestion-P2 / source-S1: full organizer-quality ledger rejected for this round; retained as fb-209 with the critic's single-writer, distinct-day sampling requirements.
- [x] ingestion-P3 / source-S2: explicit user-mentioned organizer provenance now outranks inferred organizer volume — `scrapers/utils/platform_discovery.py`.
- [ ] ingestion-P4: organizer-ID hydration expansion deferred with fb-209 to avoid extra Eventbrite calls during freshness recovery.
- [x] ingestion-P5: pure month/day-range titles are rejected during normalization as well as source extraction — `scrapers/quality.py`.
- [x] ingestion-M1: active follow coverage counts only today-or-future events in New York time — `scrapers/sanity_check.py`.
- [x] ui-U1: removed the duplicate homepage calendar introduction and compacted mobile calendar spacing — `site/app/page.tsx`, `site/app/components/Calendar.tsx`, `site/app/components/EventList.tsx`.
- [x] ui-U2: consolidated saved/follow/affinity provenance into one explicit, optionally filterable chip — `site/app/components/EventCard.tsx`.
- [ ] ui-U3: time/proximity badge expansion rejected to keep this visual pass focused.
- [x] ui-U4: enlarged mobile card actions and made hidden events disappear immediately and remain hidden after reload — `site/app/components/EventCard.tsx`, `site/app/hooks/useEvents.ts`, `site/app/lib/interests.ts`.
- [x] dream-D1: deployments now refuse feeds older than six hours, past-dated rows, or incomplete scrape telemetry — `.github/workflows/deploy.yml`.
- Deferred to backlog: dream-D2 as fb-215 (external freshness heartbeat outside GitHub Actions).

