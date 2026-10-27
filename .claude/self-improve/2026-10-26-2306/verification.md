# Verification

- Pulled first: clean main fast-forwarded to 809aa33b.
- Live HTTPS feed fetched via the machine's configured local proxy; byte-identical to the pulled public JSON, timestamp 2026-10-26T21:52:21.031939+00:00.
- Focused regressions: 39 passed.
- Full scraper suite: 487 passed, 3 expected xfails.
- Sanity with --hard-fail: zero critical failures before and after; Brooklyn Museum/art openings and Open Book Club warnings pre-exist.
- Production build: Next.js 16.2.4, 859 static pages, success.
- ESLint: zero errors, seven existing image warnings.
- git diff --check: clean.
- Public description trial: 13/24 recovered in 8.36s; old exact-date matching on those same pages recovered 0/24. No timeout/rate limit/deadline hit. All 13 survive normalization; event and conviction counts unchanged.
- Local browser limitation: Chromium cannot register its macOS Mach port, including the unrestricted attempt. No UI assertion or screenshot ran locally; CI desktop/mobile verification remains pending.
- No code rollback. Normalization replay regenerated the profile timestamp and ordering only; semantic equality was verified and that replay-only churn restored before committing.

## Public trial details

- 2026-10-26: Chef Andrea Belfiore Presents: 75 Murray Dinner Series! — verified series occurrence
- 2026-10-26: Art VS Life Presents: Monday Open Mic & Karaoke @ Starr Bar! — verified series occurrence
- 2026-10-26: Live Stand-Up Comedy Every Night @ The Tiny Cupboard Brooklyn — verified series occurrence
- 2026-10-27: TUESDAYS in Harlem: FREE Swinging Lindy Hop Class! — verified series occurrence
- 2026-10-27: The Rocky Horror Picture Show 360! — verified series occurrence
- 2026-10-28: Time's Up! Fix Your Own Bike Workshop — verified series occurrence
- 2026-10-29: Outdoor Yoga — verified series occurrence
- 2026-10-29: Free Paint & Sip Night (with Free Clay Night after!) — verified series occurrence
- 2026-10-30: 260 Madison Art Exhibition — verified series occurrence
- 2026-10-30: BONE SCULPtING WORKSHOP — verified series occurrence
- 2026-10-30: Brooklyn Book Club: Read your book and then meet some people! BYO Book! — verified series occurrence
- 2026-10-30: Bitches Brew - Free Comedy Stand Up and Variety Show! — verified series occurrence
- 2026-10-31: Comic Book Art Class for Adults — verified series occurrence

## Resume, push, and public verification — 2026-10-27

- Fetched latest main first as requested: 66a6b7d3, 31 newer automated data commits. Rebased cleanly and pushed code 5e8b926b. No code changes arrived from upstream.
- Refreshed pre-push 810-event snapshot passed all six critical checks.
- [Tests 40588496686](https://github.com/prajjwal1/nyc/actions/runs/40588496686) passed: scraper tests plus production lint/build and all desktop/mobile browser checks on Linux. This resolves the functional browser-verification limitation; no visual redesign or screenshot QA is claimed.
- [Quick Scrape 40588561872](https://github.com/prajjwal1/nyc/actions/runs/40588561872) succeeded and committed a4719653. Eight descriptions recovered, 26 restored, no source/request timeout, rate limit, or deadline hit.
- [Pages 40588630671](https://github.com/prajjwal1/nyc/actions/runs/40588630671) passed build, deploy, and timestamp verification.
- Independent HTTPS verification at 2026-10-27T21:42:37.090388+00:00: events and communities are byte-identical to the repository. 807 events, 94 personalized, zero past rows/duplicate groups, all critical source counts above their floors.
- Public static HTML for Outdoor Yoga and Brooklyn Book Club contains the verified source descriptions.
- New persisted history fields were inspected in both appended snapshots; they share snapshot_updated=2026-10-27T21:39:40.636347+00:00 and have complete, nonpartial, timeout-free run metadata.
- fb-222, fb-217, and fb-223 addressed against 5e8b926b. fb-212 remains open; fb-224 is the next diagnostic proposal.
