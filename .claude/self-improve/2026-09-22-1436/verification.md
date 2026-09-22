# Verification

- `PYTHONPATH=. venv/bin/pytest -q scrapers/tests`: 452 passed, 3 expected xfails.
- Focused quality regression suite: 131 passed, 3 expected xfails.
- `PYTHONPATH=. venv/bin/python -m scrapers.sanity_check`: zero critical failures; all six runtime critical checks pass. Existing warnings remain for Instagram volume and Brooklyn Museum; Open Book Club has no future-dated post.
- `site/npm run lint`: zero errors, seven existing `<img>` performance warnings.
- `site/npm run build`: Next.js 16.2.4 production build completed and generated 770 static pages.
- `git diff --check`: clean.
- Current-snapshot replay: exactly six rows newly rejected; no zero-yield signal accounts, exact title/date duplicates, critical-source losses, or UI changes.
- Code commit `e5bfe876` pushed to `main`.
- Quick Scrape run `35742348048` succeeded and committed refreshed feed `04177ad1` with zero critical failures.
- Pages run `35742435596` succeeded; build, deploy, and repository-snapshot verification all passed.
- Independent public check: 686 events, `lastUpdated=2026-09-22T14:44:31.173314+00:00`, `runCompleted=true`, no timed-out sources, and zero titles matching the new AI/private-event guards.
