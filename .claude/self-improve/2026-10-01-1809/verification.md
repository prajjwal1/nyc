# Verification — 2026-10-01-1809

## Local checks

- Scraper suite: **460 passed, 3 expected xfails**.
- Production build: successful, 930 static pages from the final refreshed feed.
- ESLint: zero errors; seven existing image-component warnings.
- Sanity on baseline and enriched trial: all six critical checks pass. Existing Brooklyn Museum/Open Book Club warnings remain.
- `git diff --check`: clean.

## Live detail trial on a frozen snapshot

The input is the independently verified public 788-event snapshot, copied to a temporary directory. No trial changed the production feed or learned state. The control and enriched arms run the same normalizer with persistence mocked out.

- 24 requests; 14 successful descriptions (9 Luma, 5 Eventbrite); 11.43 seconds.
- Zero HTTP 429s and no pass deadline. One individual detail request timed out; its original listing survived.
- Default-day completeness: 26/55 (47.3%) -> 32/55 (58.2%).
- The unchanged normalizer removes four duplicate posts in both arms: 788 -> 784 control events. Enrichment exposes one extra user-excluded speed-dating event (`Looking for Love? Your Dog Can Help`), leaving 783. No source or exclusion rule was weakened.
- Follow-account and meaningful topic coverage remain stable; conviction is 70/783 after the trial.
- Follow-up probes explain several skipped details: two real jazz pages provide only 4/10-character descriptions; three recurring Eventbrite pages return their series' original date, which the strict occurrence guard correctly refuses to attach. These are not counted as successful enrichments.

## Browser verification

Local Chromium cannot launch: macOS denies `MachPortRendezvousServer` registration before a page assertion runs. The retry outside the sandbox has the same OS failure. This is not a product-test failure. The repository's existing `Tests` workflow runs the complete desktop/mobile UI suite on Linux; that result must be recorded before final handoff.

## Publication

Two actual platform refreshes completed successfully. The final feed has 848 upcoming events and a timestamp of `2026-10-01T18:23:03.843104+00:00`; both public JSON copies match exactly. Default-day descriptions are now 42/58 (72.4%), clearing fb-220's 60% target. The final pass reused 31 cached descriptions, recovered another 13 in 3.31 seconds, and had no timeouts or rate limits. The rebuilt site contains 930 static pages. The image cache grew by two entries with no prior entries removed.

Public metrics and workflow results will be added after publication, not inferred from these local runs.
