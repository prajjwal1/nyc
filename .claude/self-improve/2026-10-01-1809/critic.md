# Critic Report — 2026-10-01-1809

This is an explicit self-review of the staged proposals, not an independent agent review.

## Cross-checks

- Sanity: six critical checks pass before changes. Final normalization must still enforce all exclusions after enrichment; do not relax a guard to preserve an otherwise invalid event.
- Source duplication/exclusions: no additions or removals of source calendars or curated accounts. `user_excluded_sources.json` remains authoritative.
- UI preferences: no new navigation, search, Hide action, placeholders, backend, or localStorage version changes.
- Top-three coverage: P1 addresses fb-220; feed refresh and public deployment must address fb-211/fb-210/fb-221. Do not claim them from code alone.
- Silent-failure watch: descriptions disappear despite successful catalogs. Historical follow coverage is not current-feed coverage; report both honestly.

## Verdicts

### ingestion-P1 — MODIFY

Approve the bounded shared pass, with explicit safeguards: use already-normalized survivors as candidates; restore cached prose before that preview; propagate successful descriptions to the raw rows so the existing final normalization checks them again; never replace an entire event with a detail response. Canonical event identity must include date, fold Luma's host alias, ignore tracking parameters, and recognize Eventbrite's stable event ID. A detail response for a sibling or rescheduled event is rejected. Only platforms selected by the current scraper workflow may make new requests. Persist telemetry in the public ingestion summary. Remove the superseded unbounded Luma hydration loop so the new description pass has a genuine bound.

Expected measurable improvement: at least seven additional useful descriptions on today's calendar would take 47.3% past 60%; actual improvement must be measured. No forecast is treated as a deployed result.

### source-pool-S1 — APPROVE (no additions)

All four meaningful topics are represented. Current-source completeness has stronger evidence than speculative expansion; expected topic-coverage delta is zero. Repeating the known alias probes would consume requests without adding inventory.

### ui-U1 — APPROVE

Use the existing description surfaces and verify them in a browser. A layout change cannot supply the missing source text. fb-212 remains open with this explicit deferral; no visual improvement is claimed.

## Critique notes

- Ingestion: the old Luma path replaces whole events and can lose discovery/provenance fields. Copy only missing descriptions. Tests must cover identity, caching across quick refreshes, exclusion reapplication, failures, 429 circuit stops, and the deadline.
- Source review: 100% lifetime yield does not imply all follows are served today. Keep Open Book Club and current-feed follow coverage visible as unresolved observations.
- UI review: use the calendar's actual default day as the completeness denominator, not the global top-50 score list, which misleadingly looks 76% complete.

## Dream D1 — Reuse fb-217: source-yield cliff warnings (DREAM-DEFER)

The earlier warning-only rolling-median proposal is still useful for zero-yield calendars. Keep the existing fb-217 open rather than add a duplicate. Its intended metric is recovered topic/follow coverage, but no gain is quantifiable before a cliff is diagnosed. This cycle first establishes the missing-description baseline and recovery telemetry.

## Live-trial review and dream D2 (DREAM-DEFER)

The trial recovered 14 descriptions in 11.43 seconds, with zero 429s, and raised default-day completeness to 58.2%. This is a real improvement, but remains below fb-220's 60% target. Do not close that criterion before checking the newly refreshed public feed.

Three skipped Eventbrite pages describe recurring series whose JSON-LD carries the original date: Outdoor Yoga (April 2), Structural Collabs (September 5), and Brooklyn Book Club (August 7), while the feed lists October occurrences. Preserve the strict date guard. Queue fb-222 to accept series descriptions only after explicit schedule/sub-event evidence validates the selected occurrence; never infer recurrence from a stale page date alone. This could raise literary/fitness description coverage without additional requests, but the delta is unproven.

### Final shortlist modification

The fresh calendar has 59 events today. The initial 30-row window stops just before Junk Journal Night (rank 32), an art opening (36), and Sarah Langan + Victor LaValle (38), all still missing descriptions. Extend the examined window to 40 events per day, preserving the 24-request/45-second limits and all identity guards. This lets the cache progressively cover more of the visible calendar instead of repeatedly spending its remaining requests on only the first 30 rows. Verify a second actual refresh to prove cached descriptions survive and measure the resulting completeness.

### Verification follow-up — MODIFY

The first CI failure revealed a pre-existing test that expected standalone-page navigation from an index card even though the index intentionally opens a modal. Preserve both production behaviors and test them separately; retain the original sticky mobile back-link and return-date assertions. Also verify full descriptions on the standalone page. The corrected suite passed on desktop and mobile in run `36907364504`. Distinguish all-day feed completeness (72.4%) from the time-filtered calendar (74.1% at 14:23 New York time); both exceed the target without claiming every card displays the entire body.
