# Applied changes

- [x] ingestion-P1 (MODIFY): shared bounded source-native description pass in `scrapers/utils/descriptions.py`, integrated into `scrapers/run_all.py` before the existing final normalization.
- [x] Cache recovery: previous-feed descriptions survive catalog refreshes, matched by platform identity and date; source URLs, organizer references, user signals, and other metadata remain intact.
- [x] Removed superseded unbounded Luma calendar detail fetching; public inventory collection and learned calendar discovery remain in place.
- [x] Eight behavioral regression tests cover caching, shortlist/request bounds, source scoping, identity/date matching, 429 handling, deadlines, request timeouts, and end-to-end exclusion reapplication.
- [x] README documents the budget and persisted telemetry.
- [x] Final shortlist is 40 recommendations per day; the 24-request cap is unchanged. Two live refreshes preserve cached prose and raise default-day completeness to 72.4%.
- [x] Verification follow-up: corrected the pre-existing UI test's index-modal/calendar-page mismatch, retained the mobile back assertions, and added explicit quick-view and full-description checks on both viewports. Production UI behavior is unchanged.
- [skipped] source-pool-S1: no unverified source additions; meaningful topics are already represented.
- [skipped] ui-U1: existing description surfaces already display the new data; no layout change required.
- Deferred: fb-212 design work, fb-217 source-yield warnings, and fb-222 series-aware Eventbrite descriptions.
