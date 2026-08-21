# Verification

- `PYTHONPATH=. python -m pytest -q`: 367 passed, 3 expected xfails.
- `python -m scrapers.sanity_check`: 0 critical failures; all five critical checks pass.
- `npm run build` in `site/`: clean Next.js production build; 35 static pages generated.
- `git diff --check`: clean.

Pre-existing/non-regression warnings remain: low Instagram inventory (fb-174), no current Brooklyn Museum/Smorgasburg/art-opening events, and no future Open Book Club post. None is caused by this ranking-only change.
