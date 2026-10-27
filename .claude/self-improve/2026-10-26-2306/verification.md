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
