# Verification

- `PYTHONPATH=. ./venv/bin/pytest -q scrapers/tests`: 414 passed, 3 expected xfails.
- Focused scraper regressions: 122 passed.
- `git diff --check`: clean.
- `site/npm run build`: Next.js 16.2.4 production build completed successfully and generated all static routes.
- `PYTHONPATH=. ./venv/bin/python -m scrapers.sanity_check`: command completed; four of five critical inventory checks pass. NYC Backgammon Club remains at 0, a pre-existing feed condition present before these code-only edits. Warnings remain for Instagram share (5) and Brooklyn Museum (0).
- The checked-in feed is unchanged at 645 events with `lastUpdated=2026-09-04T15:06:43.095421+00:00`; code-only changes do not justify a freshness claim.
- Snapshot replay: exact structured organizer matching recovers two followed-organizer rows (`Garden Rest and Read`, `Philosophy at the Museum...`); the 300-character late-night scan catches exactly the documented `oomfRAVE` row; the explicit New York ZIP rule catches four non-NYC Partiful rows and preserves all tested NYC ZIP families.
- Remote/source verification: configured the repository to use the machine's managed local proxy for GitHub, rebased over 138 automated refresh commits, and pushed successfully. Quick Scrape run `34385054295` and Pages deployment run `34385104225` both completed successfully. The public feed matches commit `1404a998`, has 663 events, zero past rows, `runCompleted=true`, and `lastUpdated=2026-09-09T17:47:45.950224+00:00`; the homepage serves Next.js assets with none of the requested removed copy present.
