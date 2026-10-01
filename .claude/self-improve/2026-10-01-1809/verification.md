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

The first Linux run (`36906687066`) passed the scraper job but found a pre-existing test mismatch introduced in `4f46a136`: it clicked an index card, which intentionally opens `EventModal`, then waited for the standalone page's back link. `test-ui.mjs` now explicitly checks the index modal on both viewports, closes it, and follows the same event from the calendar to its static detail page. Full description rendering, the original sticky mobile back geometry, and the return to the selected date remain covered. No production interaction was changed to satisfy the test. The corrected Linux run is pending.

## Publication

Two actual platform refreshes completed successfully. The final feed has 848 upcoming events and a timestamp of `2026-10-01T18:23:03.843104+00:00`; both public JSON copies match exactly. Default-day descriptions are now 42/58 (72.4%), clearing fb-220's 60% target. The final pass reused 31 cached descriptions, recovered another 13 in 3.31 seconds, and had no timeouts or rate limits. The rebuilt site contains 930 static pages. The image cache grew by two entries with no prior entries removed.

The initial implementation was published in `d43428ea83ff973ff5e235520fe30e91b859121f`. Pages run `36906687207` succeeded. Independent HTTPS reads confirm that the public `events.json` and `communities.json` exactly match the committed copies. The public static pages for Junk Journal Night (`117f34350d7318b3`) and East of Eden Screening (`7dd726e1bbc7f297`) contain the newly recovered descriptions and the mobile back control. Final browser results will be recorded after the test correction passes CI.
