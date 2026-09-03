# Verification

- Targeted scraper tests: **107 passed, 3 xfailed**.
- Full scraper suite: **395 passed, 3 xfailed**.
- `python -m scrapers.sanity_check`: **0 critical failures**; corrected active upcoming follow coverage is 4/50 rather than the stale all-dates 6/50.
- `npm run lint`: **0 errors**, 7 existing `no-img-element` warnings.
- `npm run build`: **passed**, generating 616 static pages from the checked-in 556-event snapshot.
- `node --check site/scripts/test-ui.mjs`: **passed**.
- Playwright/Chrome visual execution is environment-blocked before page load by macOS Mach-port permission denial. The updated script now checks mobile/desktop action target sizes and persistent Hide behavior when run in CI.
- Freshness gate dry check on the current snapshot: feed age about 148 hours, 199 past rows, completed scrape telemetry present. The new deploy guard correctly makes this payload ineligible for release.
- GitHub/Pages network access is currently blocked from this execution environment. Final freshness, push, CI screenshot, and deployment verification remain release-gate steps, not silently accepted.

No code rollback was required.
