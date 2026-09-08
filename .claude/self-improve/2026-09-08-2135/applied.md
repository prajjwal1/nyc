# Applied changes

- [x] ingestion-P1 (MODIFY): schedule the bounded Eventbrite collection frontier and admit only canonical-deduplicated calendars with at least five future rows and at least 80% exclusion-clean, personal-topic-aligned inventory — `scrapers/sources/eventbrite.py`.
- [x] ingestion-P2 (MODIFY): credit exact structured organizer URLs/references before shell filtering while leaving loose provenance matching later — `scrapers/normalize.py`.
- [x] ingestion-P3: reject explicit New York ZIP codes outside NYC while preserving hidden locations — `scrapers/sources/partiful.py`.
- [x] ingestion-P4: extend the late-night description audit window from 200 to 300 characters — `scrapers/normalize.py`.
- [x] dream-D1: remove false `ai` interest inferred from username letter substrings and rebuild the interest profile — `scrapers/utils/interest_profile.py`, `scrapers/data/user_interest_profile.json`.
- [x] ui-U1/U2: Critic-approved no-code deferrals; existing organizer/source links already support broader sources, and exact distance remains unavailable upstream.
- [ ] source-pool C1-C4: not added because outbound access failed before an HTTP response, so none could satisfy the live >=5 future / >=80% clean-and-on-taste gate.
- Deferred to backlog: dream-D2 as fb-217 (warning-only source-yield cliff detection).

