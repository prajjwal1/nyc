# Verification

- `venv/bin/python -m pytest -q`: **387 passed, 3 xfailed**.
- Targeted scraper regressions: **294 passed, 3 xfailed**.
- `venv/bin/python -m scrapers.sanity_check`: **0 critical failures** on the refreshed 556-event feed. Follow-graph coverage remains 50/50; active-feed coverage is now explicitly reported as 6/50.
- `npm run lint`: **passed with 7 existing `no-img-element` warnings and 0 errors**.
- Local `npm run build`: **passed** after the initial rebase, producing 595 static pages from 539 events.
- The manually triggered Eventbrite/Substack refresh and follow-up GitHub Pages deployment both completed successfully. CI generated **616 static pages** from the refreshed 556-event feed.
- Live-output spot check: `robots.txt` allows crawling and points to `https://prajjwal1.github.io/nyc/sitemap.xml`; the live sitemap contains 608 canonical URLs. A sampled live event page includes its title, canonical tag, and Event JSON-LD.
- `npm run test:ui`: **environment-blocked** before application startup because macOS denied Chromium's Mach-port registration (`KERN_SUCCESS ... Permission denied`). No product assertion ran or failed; build-time TypeScript and static generation succeeded.
- `git diff --check`: **passed**.

No scraper or site rollback was required.
