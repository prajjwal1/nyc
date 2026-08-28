# Verification

- `venv/bin/python -m pytest -q`: **387 passed, 3 xfailed**.
- Targeted scraper regressions: **294 passed, 3 xfailed**.
- `venv/bin/python -m scrapers.sanity_check`: **0 critical failures** on the post-rebase 539-event feed. Follow-graph coverage remains 50/50; active-feed coverage is now explicitly reported as 6/50.
- `npm run lint`: **passed with 7 existing `no-img-element` warnings and 0 errors**.
- `npm run build`: **passed**, producing 595 static pages, including 539 event pages, 22 category pages, community pages, `robots.txt`, `sitemap.xml`, and social preview images.
- Generated-output spot check: `site/out/robots.txt` allows crawling and points to `https://prajjwal1.github.io/nyc/sitemap.xml`; the sitemap contains 587 canonical URLs. The export contains 539 event pages and 22 category pages, and a sampled event page includes its title, canonical tag, Event JSON-LD, category links, and original-source link.
- `npm run test:ui`: **environment-blocked** before application startup because macOS denied Chromium's Mach-port registration (`KERN_SUCCESS ... Permission denied`). No product assertion ran or failed; build-time TypeScript and static generation succeeded.
- `git diff --check`: **passed**.

No scraper or site rollback was required.
