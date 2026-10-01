# Ingestion Quality Report — 2026-10-01-1809

## Evidence

Historical signal-account yield is 50/50, but only 8/50 are represented now. No historical zero-yield account needs promotion. The known Instagram account-sweep constraint remains; no speculative account additions are proposed.

All 69 Luma rows and 141 of 157 Eventbrite rows lack descriptions. Source detail pages return useful prose through the existing parsers. `luma.scrape()` excludes quick runs from both hydration and cache reuse; its broad city catalog is intentionally not hydrated. `eventbrite._hydrate_shortlist()` is disabled in quick mode and otherwise selects missing organizers, not missing descriptions. These omissions recur after every catalog refresh.

## P1 — Bounded source-native description enrichment

- Metric: default-day description completeness, 26/55 (47.3%) toward at least 60%; preserve meaningful topic and followed-account coverage.
- Files: new shared description utility and `scrapers/run_all.py`; retire duplicate unbounded Luma calendar hydration in favor of the shared pass.
- Change: restore descriptions from the previous feed before normalization. Use normalized survivors to shortlist the highest-ranked 30 events per day over the next seven days. Fetch at most 24 missing descriptions, restricted to platforms refreshed in this run. Only accept descriptions from a matching canonical URL and event date. Fill description fields without replacing event identity, organizer provenance, or user signals. Final normalization applies all existing exclusions to newly exposed text.
- Cache: reuse the already-persisted events payload; no new state-file persistence contract.
- Bounds: one request at a time per platform, no retry, 8-second request timeout, 45-second pass deadline, stop that platform on HTTP 429.
- Telemetry: cache hits, shortlist/missing counts, attempts, successful fills, failures, timeouts, rate limits, elapsed time.
- Risks: sibling-event metadata being attached to the wrong listing; new descriptions exposing excluded content; refreshes erasing previously fetched details. Cover these with behavioral regressions and a frozen-feed live trial.

## Directives

- fb-220: P1 directly addresses the missing information.
- fb-211/fb-210/fb-221: refresh and deployment verification remain required after tests.
