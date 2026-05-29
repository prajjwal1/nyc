# NYC Events — Knowledge Base for Future Agents

This is a personal NYC events aggregator for **prajjwal1** (lives in Williamsburg, Brooklyn). The site lives at https://prajjwal1.github.io/nyc/.

This document captures what we've learned so future agents can keep iterating.

---

## North Star

**Be the best NYC events discovery engine ever built.** Surface events the user would actually want to attend — across music, parties, art, food, comedy, books, dance, fitness, exploration. The user is single, in their 20s/30s, lives in Williamsburg, loves discovering NYC, wants to meet people.

Three guiding principles:
1. **Quality > quantity.** Every event must justify its place. No caption fragments, no recurring kids' programs, no "Just Announced" hype.
2. **Mimic Instagram, but better.** The home view is "For You" — chronologically per-day, top events first.
3. **Self-improving and autonomous.** Discovery should keep finding new accounts and event sources without manual config.

---

## Architecture (high level)

```
┌─ GitHub Actions (every 2h) ─────────────────────────────────────┐
│  scrapers/run_all.py                                            │
│    ├── async scrapers: luma, eventbrite, museums, music_venues, │
│    │    nypl, generic, partiful, substack, theskint, ...        │
│    └── sync scrapers: instagram (instaloader + image OCR)       │
│  → normalize.process(): block, dedupe, rank, filter score≥0.5   │
│  → data/events.json + site/public/events.json                   │
│  → git commit + push                                            │
└─────────────────────────────────────────────────────────────────┘

┌─ GitHub Actions (daily) ────────────────────────────────────────┐
│  scrapers/run_discovery.py                                      │
│    ├── harvest_following_list() — score user's IG follows       │
│    └── discover_accounts() — BFS through @mentions in captions  │
│  → scrapers/data/discovered_accounts.json                       │
│  → scrapers/data/discovered_urls.json (Linktree expansion)      │
└─────────────────────────────────────────────────────────────────┘

┌─ GitHub Actions (on push) ──────────────────────────────────────┐
│  Next.js build → static export → GitHub Pages                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## What works

| Scraper          | Status | Notes                                              |
|------------------|--------|----------------------------------------------------|
| **instagram**    | ✅      | Authenticated via session file. Most events.       |
| **eventbrite**   | ✅      | JSON-LD ItemList walker. 200+ events per run.      |
| **luma**         | ✅      | Organization schema with nested events array.      |
| **substack**     | ✅      | RSS feed → parse `content:encoded` HTML headings.  |
| **partiful**     | ✅      | `__NEXT_DATA__` JSON, NYC trending section.        |
| **meetup**       | ✅      | JSON-LD on search pages. Some duds.                |
| **nypl**         | ✅      | Refinery API at refinery.nypl.org. Mostly garbage. |
| **music_venues** | ⚠️      | Some 403 (Rough Trade). JSON-LD where available.   |
| **museums**      | ⚠️      | Met blocks via Vercel Security Checkpoint. Others. |
| **generic**      | ✅      | Universal JSON-LD/OG/iCal scraper.                 |
| **theskint**     | ✗      | HTML scrape didn't work. Use IG @theskint instead. |
| **bookclubbar**  | ✗      | React SPA, JS-required. Use IG @bookclubbar.       |
| **dice**         | ✗      | URL changes. Try harder.                           |
| **nycforfree**   | ✅      | Squarespace eventlist on /events. 126 events / 83 future surviving filters. Free events by definition (curator), price="free" stamped. Use 90s timeout — page is ~2MB. (Restored iter 100.) |
| **parks**        | ✅      | nycgovparks.org/events: 50 events, 22 surviving filters (yoga/dance/movies/theater in parks). Most yield is fitness + cultural programming. Kids events auto-blocked. (Re-verified iter 99.) |

---

## Bot-blocked sites (need alternative strategies)

These sites return 403 / Vercel checkpoint / Incapsula / require browser:

- **Met Museum** (Vercel Security Checkpoint)
- **NYPL events page** (Incapsula) — but `refinery.nypl.org` API works!
- **Book Club Bar** (Bookmanager React SPA)
- **Luma single events** (often 403 for direct event pages)

**Workarounds:**
1. Use the venue's Instagram account instead (most have one)
2. Look for an underlying API (NYPL → Refinery, ticketing platforms)
3. Look for RSS/iCal feeds on Squarespace sites

---

## Instagram details (most important source)

### Auth
- Session file at `~/.config/instaloader/session-prajfb`
- In CI: stored as `IG_SESSION_B64` GitHub secret, base64-decoded into the session path

### Caption parsing
- See `scrapers/sources/instagram.py`
- `_looks_like_event_post()` gates: needs 2 event signals (1 if image present)
- Multi-event detection: if 4+ sections have explicit dates, treat as roundup
- Caption fragment detection in `scrapers/quality.py`:
  - "Tomorrow night...", "Just Announced:", "PSA", "[London]", numbered lists
  - All-caps hype, narrative phrases, mid-sentence punctuation

### Image OCR
- `scrapers/utils/image_analyzer.py` uses Tesseract via `pytesseract`
- Installed in CI: `apt-get install -y tesseract-ocr`
- Carousel posts: ALL images extracted via `post.get_sidecar_nodes()`
- OCR extracts: dates (regex), times (regex), location heuristics, title

### Discovery (BFS)
- `scrapers/discover.py`
- **Primary seed: user's own IG following list** (`harvest_following_list()`)
- BFS: 1 level deep, max 30 new accounts per run
- Score threshold: 0.45 (NYC keywords + event keywords + bio links to Luma/Partiful)
- Linktree/Beacons bio links → harvested into `discovered_urls.json` for generic scraper

---

## Examples of posts we want to handle

The user has flagged these specific patterns we should handle perfectly:

1. **@sipsandstoriesnyc** "Sips & Stories NYC presents: The Social Room at @rodeo.bk"
   - Single event post, caption has all details (date "Sunday, May 17th 4–8 PM", location)
   - Status: ✅ should be caught

2. **@morningsinmotionnyc** "May calendar 🩵"
   - Image-based: dates ARE in the calendar flyer image, not the caption
   - Status: ⚠️ requires OCR — make sure Tesseract installed in CI

3. **@em_poweredpilates** bio has Linktree → events page
   - Bio link expansion needed
   - Status: ✅ existing flow via `extract_bio_links()`

4. Carousel posts where each image has a different event flyer
   - Status: ✅ now extracts ALL sidecar images

---

## Ranking (`scrapers/ranking.py`)

Multi-signal score 0.0–1.0. Below 0.5 = dropped.

| Signal              | Weight | Source                                       |
|---------------------|--------|----------------------------------------------|
| Source quality      | 20%    | `config.SOURCE_QUALITY` — IG=1.0, etc.       |
| Category match      | 22%    | User interests × boost multipliers           |
| Proximity           | 16%    | Williamsburg=1.0, Brooklyn=0.7, Mid=0.5      |
| Title quality       | 12%    | Action verbs > caption fragments             |
| Time of day         | 8%     | Weekend evenings best                        |
| Popularity          | 7%     | RSVP counts in description                   |
| Description quality | 5%     | Length + content                             |
| Completeness        | 6%     | Has image + time + location?                 |
| Price               | 4%     | Free=1, <$20=0.85, etc.                      |
| Boosts              | +30%   | High-value keywords (rooftop, opening, jazz) |
| Social boost        | +20%   | Singles/mixer/meet-people keywords           |
| Soft penalties      | −40%   | Language exchange, dance class, etc.         |

User-priority categories (from `config.USER_INTERESTS.boost_categories`):
- `singles` 1.5×, `music` 1.4×, `parties` 1.35×, `games` 1.3×
- `exploration` 1.25×, `art/food/books` 1.15×

---

## Quality filtering (`scrapers/quality.py`)

Two levels:

1. **Hard blocks** (event removed entirely) via `is_blocked()`:
   - HARD_BLOCK_KEYWORDS: storytime, ESL, knitting circle, citizenship study, AA meeting, family Saturday, etc.
   - `_is_non_nyc()` — drops events with LA/SF/London/etc. that lack NYC markers

2. **Caption fragment detection** via `_is_caption_fragment()`:
   - Narrative starters ("Throughout his career", "We're loving")
   - Hype openers ("Tomorrow night...", "PSA", "Just Announced")
   - Numbered lists ("3. Harley Spiller...")
   - Mid-sentence titles, stylized unicode, etc.

3. **Title quality** — events with title_quality < 0.3 score zero.

---

## Sanity check (`scrapers/sanity_check.py`)

Run after every pipeline. Verifies critical sources are present:
- NYC Backgammon Club
- Reading Rhythms
- Williamsburg/Greenpoint/Bushwick events
- Free events
- Music events ≥ 15

---

## Common pitfalls / gotchas

1. **`asyncio` mixing**: instagram scraper is sync (instaloader is sync). Don't try to await it.
2. **Git rebase conflicts on events.json**: Use `git checkout --ours data/events.json` (we always trust local fresh data).
3. **Rate limits**: instaloader gets blocked if you fetch too fast. We sleep 1s between profiles.
4. **HTTP cache**: httpx caches responses in-process. Long pipelines can hit stale 403s.
5. **Date parsing**: Always convert relative dates ("Thursday") to absolute dates before saving.
6. **Today vs Tomorrow**: System uses local date. The IG `post.date_utc` may differ — convert.
7. **Caption splitting**: Most IG posts are NOT multi-event roundups. Only split when 4+ sections have dates.

---

## What to improve next

Open work items (in rough priority order):

1. **Make image OCR run on all images in carousels** — currently only first image
2. **Bio link expansion → generic scraper integration** — works but URLs not always re-scraped
3. **Recurring event handling** — "Smorgasburg every Saturday" should generate weekly events
4. **Better duplicate detection** — same event from IG + Substack often slips through
5. **Per-user preference tuning** — "I went to X, I liked Y" feedback loop (no UI yet)
6. **Email digest** — "Here are 5 things to do this weekend"
7. **Map view** — show events geographically, especially walking distance
8. **TimeOut/DoNYC scraping** — high-quality curated content but JS-rendered

---

## File map

| Path                                | Purpose                              |
|-------------------------------------|--------------------------------------|
| `scrapers/run_all.py`               | Orchestrator — runs all scrapers     |
| `scrapers/run_discovery.py`         | Daily IG BFS discovery               |
| `scrapers/discover.py`              | BFS engine + bio link harvesting     |
| `scrapers/normalize.py`             | Dedupe, rank, filter, sort           |
| `scrapers/ranking.py`               | Multi-signal score computation       |
| `scrapers/quality.py`               | Hard blocks + caption-fragment check |
| `scrapers/config.py`                | IG accounts, user interests, sources |
| `scrapers/sanity_check.py`          | QA — fail CI if critical sources gone|
| `scrapers/sources/*.py`             | Per-source scrapers                  |
| `scrapers/utils/event_parser.py`    | Build event, infer category, dates   |
| `scrapers/utils/image_analyzer.py`  | Tesseract OCR                        |
| `scrapers/utils/http.py`            | Browser-like async HTTP client       |
| `site/app/page.tsx`                 | Main page (For You / Calendar)       |
| `site/app/components/TopPicks.tsx`  | "For You" feed (8/day for 30 days)   |
| `site/app/components/EventCard.tsx` | Compact card (image + meta)          |
| `site/app/lib/types.ts`             | Event type + category configs        |
| `.github/workflows/scrape.yml`      | Cron every 2h                        |
| `.github/workflows/discover.yml`    | Cron daily                           |
| `.github/workflows/deploy.yml`      | Build + deploy on push               |

---

## When the user says "expand search"

The lever order to pull (in approximate impact):

1. **Run discovery** — `python -m scrapers.run_discovery` finds new accounts/URLs
2. **Add categorical Eventbrite URLs** — comedy, music, dating, nightlife per category
3. **Add IG seeds** — add to `IG_ACCOUNTS` if they don't get auto-discovered
4. **Add generic URLs** — venue/calendar sites with JSON-LD
5. **Improve category inference** — add keywords to `event_parser.CATEGORY_KEYWORDS`

---

## When the user says "too many useless results"

The lever order:

1. **Tighten `_is_caption_fragment()`** — add new patterns to the rejection list
2. **Lower min score threshold** in `normalize.process` (currently 0.5)
3. **Tighten `_looks_like_event_post()`** — require more signals
4. **Add new HARD_BLOCK_KEYWORDS** — for content categories user doesn't want

Run `python -m scrapers.sanity_check` to make sure you didn't kill critical events.
