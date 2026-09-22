# Verification

- `PYTHONPATH=. venv/bin/pytest -q scrapers/tests`: 452 passed, 3 expected xfails.
- Focused quality regression suite: 131 passed, 3 expected xfails.
- `PYTHONPATH=. venv/bin/python -m scrapers.sanity_check`: zero critical failures; all six runtime critical checks pass. Existing warnings remain for Instagram volume and Brooklyn Museum; Open Book Club has no future-dated post.
- `site/npm run lint`: zero errors, seven existing `<img>` performance warnings.
- `site/npm run build`: Next.js 16.2.4 production build completed and generated 770 static pages.
- `git diff --check`: clean.
- Current-snapshot replay: exactly six rows newly rejected; no zero-yield signal accounts, exact title/date duplicates, critical-source losses, or UI changes.
- Deployment verification: pending push, feed refresh, Pages run, and live endpoint check.

