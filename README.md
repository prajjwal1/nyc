# NYC Events — IG-replacement event discovery

> **Goal**: be the central place for New Yorkers to **discover cool spots, see which places/events are trending, find events to socialize and meet people, and have fun experiences**. Replace scrolling Instagram entirely. The user is single, lives in Williamsburg, is in their 20s/30s. Hosted at `github.com/prajjwal1/nyc`, deployed to GitHub Pages.

**Two content kinds, one feed**:
- **Dated events** — concerts, parties, classes, run clubs, etc. (most content)
- **Cool spots** — evergreen place picks from `IG_SPOTS_ACCOUNTS` (`@wherethefuckdowego`, `@infatuation`, etc.). Always-current; render with teal "🗺 Spot" pill instead of date pill.

This README is the **complete knowledge handoff**. Everything an agent needs to keep building is documented here. Read it end-to-end before making changes.

---

## Why this exists

The user explicitly does NOT want to scroll Instagram. They want to open this site instead and see promising NYC events to attend. Every design decision is in service of:

1. **Replacing IG scrolling** — every IG behavior (home feed, profile tap, explore, save, send to friend, hashtags, location tags) has a mirror or equivalent here
2. **Surfacing events worth attending to meet people** — singles/social/parties tier weighted heavily
3. **Self-improving without manual curation** — the system gets better every run via 8+ self-improvement loops
4. **Transparency over IG's opaque algorithm** — every ranking signal is explained, every personalization is reset-able

Build on top of these principles. Don't break them.

---

## High-level architecture

```
┌─────────────┐   ┌────────────┐   ┌──────────────┐   ┌────────┐
│  scrapers/  │──▶│  data/     │──▶│  site/       │──▶│ GitHub │
│  (Python)   │   │ events.json│   │  (Next.js)   │   │ Pages  │
└─────────────┘   └────────────┘   └──────────────┘   └────────┘
       ▲                                  │
       │   self-improvement loops         │   localStorage
       │   (URL discovery, account-yield, │   (saves, hides,
       │    interest profile)             │    interest profile)
       └──────────────────────────────────┘
```

- **GitHub Actions** runs the Python scrapers on schedule (full sweep + every-30min quick scrape)
- Output is `data/events.json` (and `site/public/events.json`)
- **Next.js** static site reads events.json and renders
- All **personalization is client-side** (localStorage) — no backend, fully private
- Multiple **self-improvement loops** persist state in `scrapers/data/*.json` between runs

---

## Source pool — 17+ source files, 200+ URLs

### Confirmed-live sources

| Source | File | Pattern | Notes |
|---|---|---|---|
| **Instagram** | `scrapers/sources/instagram.py` | Authenticated via instaloader session | Most curated; user's saves/tags/follows drive ranking |
| **Lu.ma** | `scrapers/sources/luma.py` | `lu.ma/nyc/<category>` + curator calendars | ~80 URLs. Every `/nyc/<topic>` returns ~20 events |
| **Eventbrite** | `scrapers/sources/eventbrite.py` + `generic.py` | Categorical pages + organizer auto-discovery | ~30 categorical URLs |
| **AllEvents.in** | `generic.py` (URLs) | `/new-york?page=N`, `/<borough>/<category>` | Pagination through page 5 |
| **Songkick** | `generic.py` (URLs) | `/metro-areas/7644-us-new-york` + venue pages | Live music focus |
| **Substack** | `scrapers/sources/substack.py` | RSS feeds — onefinedaynyc, theskint, hyperallergic, etc. | Body URLs harvested from each post |
| **Reddit** | `scrapers/sources/reddit.py` | r/AskNYC, r/nyc, r/Brooklyn, r/Queens | URL harvest from selftext + comments |
| **Meetup** | `sources/meetup.py` + URL search | Search-result + topic pages | NYC location filter |
| **NYPL / Bookclubbar / NYC4Free / Museums / Music venues / Parks / The Skint / Partiful** | per-source files | Direct API/HTML | Lower volume |

### Sources tried and blocked (don't waste time re-probing)

- **Bandsintown** — 403s consistently with browser-like headers
- **Resident Advisor (ra.co)** — 403s
- **Time Out NY** — 404s on most calendar URLs
- **Tixr** — 403s
- **Twitter/X via Nitter** — never tried (user rejected probe; instances unreliable)
- **Discord** — too complex to scrape public servers without sustained engineering
- **Most NYC venue own-sites** — JS-rendered with no extractable structure (Met Museum, Brooklyn Museum, MoMA, Carnegie Hall, Lincoln Center, BAM, Apollo, etc.). The iter-98 audit confirmed these systematically. Per-venue alternatives that DO work documented below.

### Sources that turned out to work (formerly thought blocked)

- **DICE.fm browse page** — `dice.fm/browse?location=new-york` ships events in `__NEXT_DATA__.props.pageProps.events` (Iter 101: ~25 future events). The JSON-LD path only has site-metadata; never look there.
- **Reddit** — `.json` API now 403s (cracked down 2026); `.rss` Atom fallback yields a few URLs (Iter 97). Full restore needs OAuth/PRAW.
- **Atom feeds (eaterny etc.)** — Iter 96 added Atom support alongside RSS in `substack._parse_feed`.
- **Eventbrite venue-search** — `eventbrite.com/d/ny--<borough>/<slug>/` works for venues with **unique** slugs (`elsewhere`, `littlefield`, `caveat`, `pioneer-works` → 17-20/20). Generic slugs (`blue-note`, `brooklyn-bowl`, `comedy-cellar`) substring-match across the whole NYC corpus → 0 venue events. Iter 113 documented the trap; iter 107/108/110 had to roll back ~11 false-positive URLs.
- **Squarespace eventlist sites** — `article.eventlist-event` markup with `a.eventlist-title-link` + `time.event-time-24hr-start[datetime]`. Pattern works for: brooklyncomedycollective, nycforfree.co, mcnallyjackson, lizsbookbar/bookclubbar (via bookmanager API).
- **Squarespace month-paginated calendars** — `/calendar/YYYY-MM` (NYCC + East Ville Comedy) or `/events/YYYY/MM` (mcnallyjackson). Iter 91/102 added `_dynamic_calendar_urls()` per source for next-3-months coverage.

### URL audit tooling

- `scrapers/maintenance/audit_urls.py` (iter 115) — probes every URL in `GENERIC_URLS` + `substack.FEEDS`, classifies HEALTHY/WARN/STALE/EMPTY/ERROR. Run it before adding new URLs or as part of a routine cleanup pass.

### Source extraction strategies (in `generic.py`)

For ANY URL, the generic scraper tries in order:
1. **JSON-LD `Event` schema** (preferred — structured, reliable)
2. **Open Graph metadata** (fallback for single-event pages, with `<title>` fallback for bot-stripped HTML)
3. **iCal feed detection** (auto-discovers `<link rel="alternate" type="text/calendar">`, plus `/events.ics`/`/calendar.ics`)
4. **Sitemap mining** (after success, tries `/sitemap.xml`/`/sitemap_index.xml`/`/events-sitemap.xml`, harvests up to 50 event-marker URLs)

---

## Self-improvement — 8 discovery loops

The system grows its source pool every run without manual input. Each loop **harvests URLs into `discovered_urls.json`**; the generic scraper picks them up next run for full structured extraction.

| Loop | Trigger | What it harvests |
|---|---|---|
| **IG caption URLs** | Every IG post scraped | `lu.ma`/`eventbrite`/`partiful`/`posh`/`ra.co`/`dice.fm`/`tixr`/`shotgun`/`meetup` URLs in caption text |
| **IG comments mining** | Saved + tagged posts only | URLs from top 8 comments (rate-limit-safe scope) |
| **IG geo-tags** | Every post with `post.location` | Extracts venue name + lat/lng for ranking |
| **IG hashtag discovery** | Full sweep only (gated by `IG_HASHTAG_DISCOVERY=1`) | Posts from 10 NYC hashtags + user-derived hashtags from saves |
| **IG account auto-discovery** | BFS from @-mentions in event posts | Adds to `discovered_accounts.json` |
| **IG affinity co-mention** | When affinity-author posts mention other accounts | Bumps counters in `account_quality.json` |
| **Reddit URL harvest** | Listings + comments on high-comment posts | Event-platform URLs from r/AskNYC etc. |
| **Substack body URLs** | Every RSS post body (`content:encoded`) | Newsletter posts often link to lu.ma/eventbrite directly |
| **Sitemap mining** | After successful generic-scraper hits | One-shot per host, caps at 50 URLs |
| **Linktree/Beacons fan-out** | When discovered URL is a link aggregator | Outbound URLs to event platforms |
| **Eventbrite organizer auto-discovery** | Every Eventbrite event scrape | Organizer's own page (often hosts dozens of events) |
| **Lu.ma curator auto-discovery** | Every Lu.ma event scrape | `organizer.url` extracted from JSON-LD; calendar slugs added |
| **Dead URL retest** | After 7-day cooldown | Re-tries up to 5 dead URLs per run |

**Critical insight**: each scraper produces both events AND URLs. The URLs grow the search pool. The pool grows the verification density. Verification density sharpens the cross-source-boost signal in ranking. The system gets better every run.

---

## Ranking — 17+ signal types

`scrapers/ranking.py::compute_score` produces a 0-1 score per event. Final formula stacks ~17 boosts/penalties.

### Base weighted score (sums to 1.0)

| Signal | Weight | Source |
|---|---|---|
| Source curation | 0.20 | `SOURCE_QUALITY` lookup in `config.py` |
| Category match | 0.22 | Overlap with `USER_INTERESTS["preferred_categories"]` × `boost_categories` multipliers |
| Proximity (text-based) | 0.16 | `NEIGHBORHOOD_PROXIMITY` lookup; Williamsburg=1.0 |
| Title quality | 0.12 | From `quality_signals` (zeros out caption fragments) |
| Time score | 0.08 | Post-work weekday vs all-day weekend fit |
| Popularity | 0.07 | IG likes + 5×comments, or RSVP/attending count from desc |
| Completeness | 0.06 | Has image / desc>30 / startTime / location.name |
| Description quality | 0.05 | From `quality_signals` |
| Price | 0.04 | free=1.0, low-cost gets boost |

### Stacked boosts/penalties (added/subtracted)

| Signal | Range | When it fires |
|---|---|---|
| `saved_boost` | +0.25 | Event has `userSaved=true` (IG-saved) |
| `tagged_boost` | +0.20 | `userTagged` (someone tagged user in post) |
| `affinity_boost` | +0.10 | `userAffinity` (account user has saved-from before) |
| `following_boost` | +0.08 | `userFollowing` (user follows account directly) |
| `cross_source_boost` | +0.07 / +0.12 / +0.16 | 2 / 3 / 4+ contributingSources |
| `hot_event_boost` | +0.03 to +0.10 | Multi-source AND firstSeenAt < 7 days |
| `yield_boost` | +0.02 to +0.06 | Account event-yield (events_emitted/posts_scraped) |
| `comention_boost` | +0.03 to +0.10 | Affinity co-mentions count |
| `velocity_boost` | +0.02 to +0.10 | Engagement growth since last scrape |
| `quality_boost` | up to +0.05 | Has flyer image + sweet-spot description length |
| `cred_boost` | up to +0.06 | Verified IG account / large follower count |
| `time_relevance` | +0.015 to +0.06 | Closer = higher (today/tomorrow → +0.06) |
| `dow_fit` | -0.03 to +0.05 | Parties on Fri/Sat get +0.05; Mon-Wed -0.03 |
| `tod_fit` | -0.02 to +0.04 | 6-10pm = +0.04; 9am-4pm weekday = -0.02 |
| `geo_proximity` | -0.03 to +0.06 | Distance from Williamsburg (40.7081, -73.9571) when lat/lng present |
| `meet_people_boost` | +0.10 to +0.14 | 2+ social signals AND event in next 21 days |
| `social_boost` | up to +0.28 | `social_hits` count from `quality.py` SOCIAL_KEYWORDS |
| `high_value_boost` | up to +0.30 | `high_value_hits` from HIGH_VALUE_KEYWORDS |
| `soft_penalty` | up to -0.40 | `soft_penalty_hits` from SOFT_BLOCK_KEYWORDS |
| `audience_penalty` | -0.50 | `audience_mismatch` (kids/seniors/etc.) |

**MIN_SCORE filter**: events below 0.5 get dropped from the final feed. This bar keeps quality high.

---

## Dedup — 3 passes

Same event from multiple sources should collapse to one entry with a high `contributingSources` count.

1. **Title-key dedup** (`_dedup_key` in `normalize.py`): MD5 of `(sorted_distinctive_first_6_words, date)` after stopword removal. Catches exact-title events from different sources.

2. **Image-URL dedup** (`_dedup_by_image`): same `imageUrl + date` → merge. Catches cross-source events with subtly different titles but same flyer.

3. **Fuzzy-title dedup** (`_dedup_fuzzy_title`): groups by `(date, venue_key)`, computes Jaccard similarity on title token-sets, merges if ≥ 0.55 with ≥ 2 shared distinctive tokens. Catches "Sips & Stories at Cafe Erzulie" vs "Sips & Stories NYC: The Social Room at Cafe Erzulie".

After dedup: `contributingSources` array tracks every source that contributed → drives `cross_source_boost`.

---

## Quality filters

In order of application in `normalize.process()`:

1. **`filter_future`** — drop past events (date < today)
2. **`filter_far_future_misparsed`** — drop events >180 days out unless title/desc has explicit 4-digit year (most are date misparses)
3. **`is_blocked`** — kids/seniors/utility/services/non-NYC/**nightclubs**/**late-night-only** keywords (`scrapers/quality.py::HARD_BLOCK_KEYWORDS`)
4. **Shell filter** — drop events with no description AND no image AND no location
4b. **`_likely_past_midnight`** — drop events expected to run past midnight (startTime ≥ 23:00, endTime in 00:00-04:59, or text mentions "1am"/"2am"/"after midnight"/etc.). User explicitly excluded these — site is for events worth attending to meet people, not late-night nightlife.
5. **`_is_phantom_recurring`** — drop events whose title mentions a specific date that doesn't match the event date (buggy past expansions)
6. **Recurring expansion** — `detect_recurring_weekday` + `expand_recurring_event` (6 weeks ahead)
7. **`collapse_title_spam`** — when 4+ events share `(title, sourceUrl)` without explicit "every"/"weekly" markers, keep only the earliest (defensive cleanup of bad expansions)
8. **MIN_SCORE = 0.5** — drop low-score events

**IG-specific quality** (`scrapers/sources/instagram.py`):
- `_NON_EVENT_SIGNALS` — past-recap rejection ("thanks for joining", "great pics from", "rained out", "preorders open")
- `_FRAGMENT_TITLE_RE` — drops captions starting with "we", "to", "from" + photo-credit prefixes ("//", "@")
- `_ONE_SHOT_RE` — vetoes weekly recurring expansion when title has "X returns to NYC", "premiere", "opening night", "tour stop", etc.
- Title cleanup in `build_event` — strips emoji clusters, trailing hashtag walls, decodes HTML entities

---

## Personalization — all client-side (localStorage)

Stored under `nyc-events:*` keys. Reset via Activity Panel.

| Key | Content | Purpose |
|---|---|---|
| `nyc-events:interests:v1` | `{accounts, categories, hosts, updatedAt}` | Interest profile from clicks/saves |
| `nyc-events:saved:v1` | Set of event IDs | Locally-saved (★ button) |
| `nyc-events:savedCache:v1` | Map of `id → SavedEventStub` | Past saves persist after pipeline drops them |
| `nyc-events:hidden:v1` | Set of event IDs | × Hide button — excludes from feed |
| `nyc-events:opened:v1` | Set of event IDs | Visited events — fade-out signal |
| `nyc-events:lastVisitedAt:v1` | ISO timestamp | "X new since you last visited" badge |
| `nyc-events:viewMode` | `"detail"` or `"grid"` | Toggle persistence |
| `nyc-events:searchHistory:v1` | Array of last 8 queries | Search dropdown |

### Interest learning weights
- **Account-chip click**: +2 to that account
- **Category-chip toggle**: +1 to that category
- **Card open** (modal/external): +3 to account, +1 each category, +1 host
- **★ Save**: +5 to account, +3 each category, +2 host (strongest signal)
- **× Hide**: excludes from feed (no profile bump; explicit removal)

`interestBoost` adds up to +0.15 to event score on the client side based on profile match.

---

## Frontend architecture (Next.js)

### Components
- `Header.tsx` — title, total count, "X new since you last visited" badge, Share-view button
- `FilterBar.tsx` — search (with history dropdown), quick-filter chips (Today/Weekend/Week/Meet People/Saved/Free), category/source/price chips, sort toggle
- `Calendar.tsx` — date picker with event-density indicators
- `EventList.tsx` — list of events for a selected date
- `EventCard.tsx` — three variants: `MediaFirstCard` (IG events with images), `FeedCard` (text-forward), `GridCard` (square thumbnails for grid mode); each has Save/Hide/Calendar/Share buttons; opened events fade
- `EventModal.tsx` — full-screen tap-to-expand: hero image carousel (multi-image swiper for carousel posts), full description, source attribution, "Recommended by @X" provenance, action buttons, "More from @account" + "More \<Category\> like this" strips
- `TopPicks.tsx` — For You feed with 4 hero sections (Tonight / This Weekend / Just Added / Saved) + per-day grouped feed; Detail/Grid mode toggle
- `TopAccounts.tsx` — sidebar widget split into "From accounts you save" + "Suggested for you"
- `AccountBanner.tsx` — appears when `search` starts with `@`; account stats + "Open on IG" link
- `ActivityPanel.tsx` — surfaces interest profile (top accounts/categories), saved/hidden counts, **bulk Export to calendar**, Past saves collapsible section, reset button

### Hooks/lib
- `lib/types.ts` — TypeScript types (Event, EventsData, TopAccount, etc.)
- `lib/events.ts` — `loadEvents`, `filterEvents`, `getEventDates`
- `lib/interests.ts` — all localStorage helpers (interest profile, saves, hides, opened, search history, saved cache)
- `lib/ics.ts` — single + bulk `.ics` calendar export
- `hooks/useEvents.ts` — loads events, applies interest profile re-rank, exposes filtered events

### URL state
`?date=YYYY-MM-DD&view=for-you|calendar` — shareable bookmarks. `Share view` button in Header copies the URL.

---

## File structure

```
nyc-events/
├── README.md                      ← THIS FILE
├── data/
│   └── events.json                ← scrape output (committed by CI)
├── scrapers/
│   ├── config.py                  ← IG_ACCOUNTS, USER_INTERESTS, SOURCE_QUALITY
│   ├── run_all.py                 ← entrypoint; orchestrates all scrapers
│   ├── normalize.py               ← dedup (3 passes), filters, recurring expansion
│   ├── ranking.py                 ← compute_score with 17+ signal stack
│   ├── quality.py                 ← HARD_BLOCK / SOCIAL / HIGH_VALUE keyword sets
│   ├── discover.py                ← IG following-list crawl (BFS account discovery)
│   ├── sanity_check.py            ← post-run health check
│   ├── sources/
│   │   ├── instagram.py           ← largest file; saved/tagged/curated/hashtag flows
│   │   ├── luma.py                ← ~80 Lu.ma URLs; ItemList JSON-LD support
│   │   ├── generic.py             ← JSON-LD/OG/iCal/sitemap/Linktree/yield-priority
│   │   ├── eventbrite.py
│   │   ├── reddit.py              ← URL harvester (listings + comments)
│   │   ├── substack.py            ← RSS + body URL harvest
│   │   └── … 9 more sources
│   ├── utils/
│   │   ├── event_parser.py        ← build_event, parse_date, parse_time,
│   │   │                            recurring detection, title/desc cleanup
│   │   ├── http.py                ← async fetch_text helper
│   │   └── image_analyzer.py      ← OCR via pytesseract (skipped in CI)
│   └── data/                      ← persistent state across runs
│       ├── account_quality.json   ← per-IG-account event-yield + comentions
│       ├── account_cursors.json   ← incremental scrape cursors
│       ├── dead_accounts.json     ← stale + nonexistent IG accounts
│       ├── discovered_accounts.json ← BFS-discovered IG accounts
│       ├── discovered_urls.json   ← all 8 discovery channels feed here
│       ├── url_health.json        ← per-URL successes/failures + event-yield
│       ├── user_affinity_accounts.json ← accounts user has saved-from
│       ├── user_hashtags.json     ← hashtags user has saved with
│       ├── stats_history.jsonl    ← post-run sanity stats
│       └── following_list_<user>.json ← user's IG follows
└── site/                          ← Next.js 16 app (App Router)
    ├── public/events.json         ← copied from data/events.json
    └── app/
        ├── components/            ← see Frontend section above
        ├── hooks/useEvents.ts
        ├── lib/{types,events,interests,ics}.ts
        ├── layout.tsx
        └── page.tsx               ← root composition
```

---

## GitHub Actions workflows

| Workflow | Schedule | Purpose |
|---|---|---|
| `scrape.yml` | every 4-6h | Full sweep: all sources + IG hashtag discovery + IG account rotation |
| `quick-scrape.yml` | every 30 min | Fast pass: non-IG sources + saved-IG only + freshness for live site |
| `freshness-monitor.yml` | every 15 min | If `events.json` >90 min stale, dispatches quick-scrape |
| `deploy.yml` | on push to main | Builds Next.js + deploys to GitHub Pages |

**Critical secrets**: `IG_SESSION_B64` (base64 of instaloader session file), `IG_USERNAME`. Both required for IG scraping in CI.

**Persistent state files** are git-committed by both workflows so learning compounds across runs:
- `account_quality.json`, `account_cursors.json`, `dead_accounts.json`
- `discovered_accounts.json`, `discovered_urls.json`
- `url_health.json`, `user_affinity_accounts.json`, `user_hashtags.json`
- `stats_history.jsonl`

---

## Dev workflow

```bash
# Initial setup
python3 -m venv venv && source venv/bin/activate && pip install -r scrapers/requirements.txt
cd site && npm install && cd ..

# Run scrapers locally (FAST mode — saved-IG only, no image OCR)
IG_SAVED_ONLY=1 SKIP_IMAGE_ANALYSIS=1 python -m scrapers.run_all

# Run scrapers locally (FULL mode — needs IG session)
python -m scrapers.run_all

# Verify quality
python -m scrapers.sanity_check

# Build frontend
cd site && npx next build

# Develop frontend
cd site && npx next dev
```

The IG session file lives at `~/.config/instaloader/session-<username>`. Create with `instaloader --login <username>` once.

---

## Known gaps + future work

What's NOT done that future agents could ship:

### Discovery
1. **Map view** — geographic browsing with Mapbox/Leaflet. Big lift but transformative. We have `lat/lng` from IG geo-tags ready.
2. **Bandsintown** — keeps 403; would need different access pattern (mobile API? proxy?).
3. **Twitter/X** — Nitter instances unreliable; user explicitly rejected probing once.
4. **Discord** — public NYC servers have events but require sustained engineering.
5. **Geocoding for non-IG sources** — currently only IG events have lat/lng. Adding a venue→coords table or geocoding API would activate distance-ranking for all events.
6. **IG Story Highlights mining** — `Profile.get_highlights()` exists in instaloader; many event venues pin "Events" highlights with persistent flyers. Risk: rate-limit-heavy.

### Refinement
1. **Better venue normalization** — "BK Bowl" vs "Brooklyn Bowl" still don't match in fuzzy dedup. Needs synonym table or fuzzy venue-name matching.
2. **Image quality detection** — distinguish small profile pics from event flyers. Could deboost low-info images.
3. **21+ event detection** — auto-flag age-restricted events.
4. **Time inference from "doors at 7pm"** in description body.
5. **Caption-section pairing** — when carousel splits title and date into separate sections, pair them.

### User value
1. **Per-account dedicated route** — `/account/<username>` with full stats + chronological events. Currently AccountBanner is the closest equivalent.
2. **"Did you go?" feedback** — small thumbs button on past saves that bumps interest profile.
3. **Multi-day URL permalinks** — currently single-date. Range view would help "this weekend" sharing.
4. **Email digest** — out of scope without backend; could ship as RSS instead.
5. **PWA / installable** for mobile.

### Self-improvement
1. **Source-quality auto-tuning beyond URL yield** — could weight `SOURCE_QUALITY` dynamically per-source rather than statically.
2. **Cleanup very-stale account_quality entries** — after N months of no events, drop.

---

## Behavioral guidelines for agents

1. **Don't break existing functionality** — every change should be additive. The user has said this dozens of times. Run pipeline + build before committing.

2. **Confirm builds pass**: `python -m scrapers.run_all` and `cd site && npx next build` should both complete without errors.

3. **Pure additive source URLs are safe to add** when probed live — but probe first via `from scrapers.sources.generic import scrape_url; await scrape_url(url)` to confirm yield ≥ 5 events. Don't add 404s.

4. **Don't add speculative IG accounts** — only ones the user explicitly mentions or those auto-discovered via BFS. Bad accounts = wasted scrape budget.

5. **Compound, don't override** — when adding a new ranking signal, stack it with existing ones; don't replace.

6. **Persist state files via workflows** — any new `scrapers/data/*.json` you introduce must be added to BOTH `scrape.yml` and `quick-scrape.yml` git-add lists or it won't survive across CI runs.

7. **Test fuzzy/regex patterns end-to-end** — many bugs come from regexes that look right but don't match real captions. Print actual matches before committing.

8. **localStorage keys are versioned** — use `:v1` suffix. Bumping versions wipes user state on next visit.

9. **Don't add backend** — the entire system is static + GitHub Pages. Personalization stays in browser localStorage.

10. **The user wants velocity over polish** — they keep saying "expand the search more". Each round, ship something concrete and useful. Avoid endless refactoring.

---

## Decisions made & why (don't undo without good reason)

- **Williamsburg coords** (40.7081, -73.9571) hardcoded in `_distance_proximity_boost` — user lives there. Make configurable in `config.py` if user moves.
- **MIN_SCORE = 0.5** — quality bar that drops the bottom ~20% of events. Lower it cautiously.
- **Lu.ma is highest-yield source** — every `/nyc/<topic>` URL returns 20 events. Adding more category URLs is cheap and boosts cross-source verification density.
- **IG comments mining gated to saved/tagged posts only** — to bound rate-limit risk. Don't extend to curated/hashtag posts.
- **Static neighborhood proximity table over real geocoding** for non-IG events — geocoding everything is overkill given the text matching gets us ~80% of the value.
- **3-pass dedup order matters**: exact-title first (cheap), image-URL second (catches cross-source), fuzzy-title third (most expensive). Don't reorder.
- **Past-event filter applies AFTER everything else** — so we collapse + rank past events too, but only return future ones. This makes the firstSeenAt + engagementDelta logic work correctly.
- **All personalization is in localStorage with reset button** — never sent to a server. The user can wipe and start fresh anytime via Activity Panel.

---

## How the IG-replacement loop is closed

Every IG behavior has a mirror or equivalent here:

| IG behavior | Our equivalent |
|---|---|
| Home feed (followed accounts) | For You feed with `userFollowing` boost |
| Stories at the top | 🔥 Tonight hero |
| Weekly highlights | 🎉 This Weekend hero |
| What's new | ✨ Just Added hero + "X new since last visited" badge |
| Bookmarks | ★ Saved hero + ★ Save button + bulk Export-to-calendar |
| Profile tap | Click @account → Account Banner → "Open on IG" + "More from @account" in modal |
| Explore tab | Top Accounts widget split (Suggested for you) + "More \<Category\> like this" in modal |
| Suggested accounts | "Suggested for you" in TopAccounts (high-yield, NOT user-saved) + affinity comention boost |
| Hashtags | IG hashtag-discovery scrape backend + user-derived hashtag rotation |
| DM share | Share button (Web Share API or clipboard) |
| Save to camera roll | ★ Save (server + local) + .ics calendar export |
| Visited posts dimmed | Opened-event fade (`opacity-60`) |
| "Recommended for you" | "✨ Recommended by @X, @Y" provenance with click-to-verify |

**Plus capabilities IG doesn't have**:
- Cross-source verification (events on 2+ platforms surface to top)
- Distance scoring (Williamsburg-relative)
- Time-of-day fit (evening events boosted for 9-5 worker)
- Day-of-week fit (parties on Fri/Sat)
- Engagement velocity (trending events distinguished from already-saturated)
- Transparent personalization with reset button
- URL permalinks for date views
- In-modal carousel with arrow navigation
- Bulk calendar export

---

## Working with this system

**If the user says "expand the search":**
1. Probe new categorical URLs (Lu.ma `/nyc/<topic>`, Eventbrite category pages, AllEvents tags)
2. Verify yield ≥ 5 events live
3. Add to `LUMA_PAGES` or `GENERIC_URLS`
4. Commit + push

**If the user says "improve IG":**
1. Look at `scrapers/sources/instagram.py` and the IG-specific items in this README
2. Real gaps left: Story Highlights mining, location-tag pages, account-similarity recs
3. Always gate new IG channels by env var to bound rate-limit risk

**If the user says "improve ranking":**
1. Add a new boost in `ranking.py` between existing ones; don't replace
2. Stack additively in the `final = ...` formula
3. Cap each boost so no single signal dominates (most are ≤ 0.10)

**If the user says "improve refinement":**
1. Look at the `process()` order in `normalize.py`
2. New filters/dedup passes go AFTER existing ones
3. Always print a count of what was dropped so we can see impact

**If the user says "improve UX":**
1. The site is functional; small additive features beat big rewrites
2. localStorage is your friend for personalization
3. New components → wire through `page.tsx` props

**If the user gives a specific complaint** (e.g., "no run clubs", "i don't see vital run club"):
1. Check `IG_ACCOUNTS` in `scrapers/config.py` first
2. Add IG accounts they mention
3. Probe Lu.ma `/nyc/<topic>` and Eventbrite categorical for the topic
4. Add Meetup keyword searches if relevant
5. Don't just fix one source — go holistic across all 5+ platforms

---

## User feedback log — durable, never forget

Every concrete preference / requirement the user has stated lives here.
This is the source of truth for "what does the user want?" Future agents
must respect every entry. Add to this list whenever the user gives new
feedback. Do not silently drop entries.

### Excluded content (HARD blocks in `scrapers/quality.py`)
- **Nightclub events**: `nightclub`, `bottle service`, `vip table/booth/section`, `table service`, `bottle minimum`
- **Late-night** (anything running past midnight): `after hours`, `till 4am`, `until 5am`, `all night long`, plus the `_likely_past_midnight` filter in `scrapers/normalize.py` (start ≥ 23:00, end 00:00–04:59, end < start, text matches "1am-5am" / "after midnight" / etc.)
- **Language mixers**: `internationals and language mixer`, `language mixer`, `language exchange`
- **Reggaeton** music genre
- **Professional / finance / corporate networking**: `professional networking/mixer`, `business networking/mixer`, `finance networking/mixer/professionals`, `wall street`, `executive networking/mixer`, `career`, `industry`, `corporate`, `investor`, `founders mixer`, `real estate`, `lawyer`, `consulting`, `banking`, `linkedin`, `b2b`, `sales`. **Tech mixer is fine** (carve-out works because the phrase "tech mixer" doesn't contain any blocked phrase).
- **Kids / seniors / utility / non-NYC** content (longstanding)

### Soft-penalized but not blocked
- **Heavy-drinking emphasis**: `open bar`, `all you can drink`, `free drinks all night`, `unlimited drinks`, `bottomless mimosas`, `pre-game`, `kegger`, `shotgun beer`. Each match contributes to `soft_penalty_hits` (-0.15 per hit, capped -0.40). User: "fine to have some, just downweight."

### Boosted content (positive signals)
- **Alcohol-free events**: `alcohol free`, `sober`, `sober curious`, `non-alcoholic`, `zero proof`, `mocktail`, `no booze`, `tea ceremony`, `matcha`, `specialty coffee`, `kombucha tasting`, `tea tasting` → `alcohol_free_boost` up to +0.10. User: "see more events that are alcohol-free."
- **Meet-people events** (singles, social mixers, run clubs, book clubs, supper clubs) → existing `social_boost` + `meet_people_boost`

### Account-specific user requests
- **Curated IG accounts the user explicitly named** (DO NOT prune — the stale-prune now skips IG_ACCOUNTS entirely):
  - Run clubs: `@vitalrunclub`, `@nobaddays`, `@nobaddaysrunclub`, `@brooklyntrackclub`, `@dashing.whippets`, `@oldmanrunclub`
  - Yoga: `@yogaforthepeople.nyc`, `@modoyoga`, `@humming.puppy`, `@sky_ting`, `@loomyogaclub`
  - Comedy: `@flophousecomedy`, `@greenpointcomedyclub`, `@newyorkcomedyclub`, `@comedycellarnyc`
  - Live music / DJ collectives: `@recessgroove`, `@recess.nyc`, `@718sessions`, `@nowadays.nyc`, `@musichallofwilliamsburg`, `@bowerypresents`
  - Bookstores: `@bookclubbar`, `@books.are.magic`, `@mcnally_jackson`, `@greenlightbookstore`, `@thestrandbooks`
  - NYC city-curators: `@donewyorkcity`, `@secret_nyc`/`@secretnyc`, `@exploringnyc`, `@onefinedaynyc`
  - Alcohol-free nightlife: `@brightnightssocial`, `@thecuriousbar`, `@soberishfun`
  - Spot-curators (`IG_SPOTS_ACCOUNTS`, posts treated as evergreen "🗺 Spot"): `@wherethefuckdowego`, `@thishappensnewyork`, `@newyorkguide`, `@newyorker.eats`, `@tastingny`, `@infatuation`, `@onefinedaynyc`

### UI preferences
- **Left sidebar**: removed TopAccounts and ActivityPanel widgets per user request. Sidebar shows only view-toggle, calendar, and search/filters.
- **Empty placeholders**: when an event has no image, render text-only — DO NOT show empty gray gradient boxes (applied to ActivityPanel past saves, EventModal "More from"/"More like this" strips, GridCard).
- **"This Weekend" hero**: must NOT be parties/nightclub/drinking-heavy. Filters TO low-key social: brunch, books, runs, art, outdoors, comedy, supper-club, workshops. Excludes `parties` cat, `nightlife` highlight, drinking-text patterns. Saturday + Sunday only (not Friday).

### Content kinds + structure
- **Two content kinds**: dated events (most) AND **cool spots** (evergreen, from `IG_SPOTS_ACCOUNTS`). Both render in same For You feed; spots get teal "🗺 Spot" pill, events get date pill.
- **Multi-photo IG carousels matter**: 10-slide roundup posts must produce ~10 events (carousel OCR fan-out runs on saved/tagged/curated/hashtag paths).

### System goals
- **Replace IG scrolling**: the user explicitly does not want to open Instagram. Every IG behavior (home, profile-tap, explore, save, share, hashtags) has a mirror or equivalent here.
- **Be the central NYC events + spots discovery hub**: meet people, find trending spots/events, have fun experiences. SEO-optimized for "things to do nyc / events tonight nyc / events this weekend nyc / brooklyn events" queries.
- **Self-improving loop**: after deployment, audit live `events.json`, find issues, ship surgical fixes, repeat. The `Self-improvement loop` section below shows the audit script.

### Coding principles user stated
- **No custom per-source code**. Generalizable solutions only. Examples: bookclubbar.com event URLs are caught by the **generic** `_EVENT_PLATFORM_RE` venue-events pattern (`*/events/<id>`) → discovered_urls → generic OG fallback. No bookclubbar-specific scraper code.
- **Don't break existing functionality**. Every change additive.
- **Rethink assumptions**. When something looks broken, audit the filters that may be over-pruning (we hit this with the run-club + stale-prune issue).
- **Quality bar**: it's the STACK of filters (shell / recap / fragment / phantom / title-spam / late-night / hard-blocks) plus `MIN_SCORE = 0.50`. Don't add a single high threshold — stack specific filters for what's actually noise.

---

## Self-improvement loop (audit → fix → ship)

The user explicitly asks: "after it gets deployed, scan the website, see what the issues are, ask how can we improve, do it, in a loop." This is the workflow:

```bash
# 1. Audit live data — count by source, check for filter leaks, dupes,
#    far-future events, late-night events, etc.
source venv/bin/activate && python3 <<'PY'
import json, re
from collections import Counter
from datetime import date

with open('site/public/events.json') as f:
    d = json.load(f)
events = d.get('events', [])
print(f'Total: {len(events)}')

sources = Counter(e.get('source', '?') for e in events)
for s, n in sources.most_common(): print(f'  {n:4d}  {s}')

# Check filter leaks
late_re = re.compile(r'\b(?:1|2|3|4|5)\s*am\b|\bnightclub\b|\bafter ?hours?\b', re.IGNORECASE)
lates = [e for e in events if late_re.search(e.get('title','') + ' ' + e.get('description','')[:300])]
print(f'\nLate-night leaks: {len(lates)}')

prof_re = re.compile(r'\b(professional networking|finance mixer|wall street|founders mixer)\b', re.IGNORECASE)
profs = [e for e in events if prof_re.search(e.get('title','') + ' ' + e.get('description','')[:300])]
print(f'Professional-networking leaks: {len(profs)}')

# Same title+date appearing twice = missed dedup
title_dates = Counter()
for e in events:
    key = (e.get('title','').lower().strip()[:60], e.get('date',''))
    if key[0]: title_dates[key] += 1
dupes = [(k,v) for k,v in title_dates.items() if v > 1]
print(f'Title+date dupes (missed dedup): {len(dupes)}')

# Far-future suspects
ff = [e for e in events if e.get('date','') > '2026-12-01']
print(f'Events past 2026-12: {len(ff)}')
PY

# 2. Identify patterns — which filters are leaking? which sources dominate?
#    which titles look junky?

# 3. Ship surgical fixes:
#    - New patterns added to HARD_BLOCK_KEYWORDS in scrapers/quality.py
#    - New text patterns in _likely_past_midnight in scrapers/normalize.py
#    - SOURCE_QUALITY tuning in scrapers/config.py
#    - SOURCE_LABELS additions in site/app/lib/types.ts

# 4. Build + push:
cd site && npx next build && cd ..
git add . && git commit -m "Self-improvement: <what was fixed>"
git push

# 5. Wait for next CI scrape (every 4-6h for full, every 30min for quick).
#    The newly-blocked events are purged on next run; newly-added URLs
#    contribute on the run after.

# 6. Re-audit. Repeat.
```

**Rules of thumb for the audit loop**:
- Filter leaks are easier to fix than dedup misses; do filter leaks first
- Source-quality tuning is risky; only adjust when one source is clearly noisy
- Don't add overly-broad block keywords ("club" alone would block "book club"); use the specific phrase
- Always sanity-test new keywords/patterns against real titles before pushing
- The pipeline state files (account_quality.json, url_health.json) ARE the system's memory; never wipe them



The user's stated goal is unwavering: **find events worth attending to meet people, without scrolling Instagram**. Every commit should serve that. After ~50 rounds of iteration, the IG-replacement loop is essentially complete — the gap between "open IG and scroll" and "open this site" is small and shrinking.

Keep the loop closing. Don't break what works. Self-improve.
