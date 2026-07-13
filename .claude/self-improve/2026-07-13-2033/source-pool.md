# Source Pool Report — 2026-07-13 2033 (fb-196: close user-named coverage gaps)

## Probe summary
- Gaps targeted: 3 (games=backgammon/chess, underground-electronic, social-dance-beyond-contra)
- Sources live-probed: 14 (eventbrite organizer pages, eventbrite kw searches, meetup kw searches, lu.ma category pages, venue own-sites, songkick venue pages)
- STRONG-recommend (probed ≥5, vetted, exclusion-clean): 4
- Applied to `user_curated_sources.json` this run: 3 organizer entries
- Recommended for GENERIC_URLS (orchestrator applies): 1 Meetup search URL
- Exclusion check (`user_excluded_sources.json`) run against every proposal: PASS (no accounts/hosts/title_hints match; none are `firstname_lastname` personal per fb-106; none are HoY/KDC/rave/warehouse/AI/speed-dating)

---

## GAP 1 — Games (chess / backgammon)

### STRONG: Chess Place (Eventbrite organizer) — APPLIED to user_curated_sources.json
- **Host key added**: `eventbrite.com/o/115357260611`
- **Parse path**: `eventbrite.py::_parse_organizer_page` (via `_curated_organizer_urls()`) — verified wired
- **Live yield**: 6 upcoming, all genuine recurring social chess nights
- **Samples**: "CHESS NIGHT AT MOXY NYC LOWER EAST SIDE" (2026-07-16), "Chess Night at Cosmic Diner - July 20", "Adult Beginner Chess Workshop at The Fox Harlem" (2026-07-14)
- **Why**: recurring meet-people chess club rotating across NYC bars/venues (Moxy LES, Cosmic Diner, Sugar Mouse, La Fonda, The Fox Harlem). Curation boost/floor-bypass makes these surface. Directly closes the "zero chess events" finding.
- **Exclusion check**: PASS. Not a person, not a club/rave, brand organizer.

### STRONG: NYC Backgammon (Meetup keyword search) — RECOMMEND for GENERIC_URLS
- **URL**: `https://www.meetup.com/find/?keywords=backgammon&location=us--ny--New%20York&source=EVENTS`
- **Parse path**: `generic.py::scrape_url` (Meetup JSON-LD; same pattern as existing `run+club` / `book+club` Meetup search URLs in GENERIC_URLS)
- **Live yield**: 23 total, **13 backgammon-matching, ~9 NYC-relevant**
- **NYC samples**: "Chouette or Match Backgammon Tournament at the Manhattan Gambit" (2026-07-21), "Gotham City Backgammon at Josie Woods" (2026-07-14), "Backgammon Fun on the Upper West Side" (2026-07-16), "Tuesday Cavendish Bridge & Backgammon Club"
- **Why this path (not organizer)**: Eventbrite has ZERO real backgammon events (keyword search returned only substring noise — "BACKENDZ boat bash", "blockchain summit"). lu.ma/nyc/backgammon falls back to the generic NYC feed (0 backgammon-matching). Meetup is the only path with real backgammon supply. `nycbackgammonclub` (the IG chronic-CRITICAL) itself is IG-blocked (fb-174), so Meetup is the non-IG substitute for its content.
- **Note**: ~4 of 13 are Long Island / NJ / virtual — the normalizer's NYC-geo filter should drop those; NYC-relevant floor is ~9 which clears ≥5.
- **Exclusion check**: PASS.
- **Action for orchestrator**: append the URL to `GENERIC_URLS` in `scrapers/sources/generic.py`.

---

## GAP 2 — Underground / experimental electronic (beyond Warm Up)

### STRONG: Elsewhere (Eventbrite organizer) — APPLIED to user_curated_sources.json
- **Host key added**: `eventbrite.com/o/105655500371`
- **Parse path**: `eventbrite.py::_parse_organizer_page` — verified wired
- **Live yield**: 12 upcoming
- **Samples**: "ELSEWORLD RETURNS: Yung Singh, TSVI B2B Surusinghe, 2D0GS…" (2026-07-17), "EUROHEAD, Don-Ri" (2026-07-16), "Wombo, shower curtain" (2026-07-13)
- **Why**: Elsewhere (Bushwick) is a vetted live-music/experimental venue — this is the exact underground-electronic register (ELSEWORLD is its resident DJ/electronic series) the user's taste vector (Carlos Souffront / Dopplereffekt / Detroit-techno) points at. Elsewhere already scrapes via `/d/ny--brooklyn/elsewhere/` + Songkick, but its events were dying downstream at the score floor (why the feed looked thin). Curating the organizer gives them the +0.15 boost + lower floor so they actually surface — moves high-conviction ratio, not just pool size.
- **Distinct from EXCLUDED**: Elsewhere is a permitted, ticketed music venue with seated/standing shows and daytime programming — NOT houseofyesnyc / knockdowncenter warehouse-rave character. Verified none of its 12 titles hit an excluded `title_hint` (no "rave"/"warehouse"/"open to close"/"after party @").
- **Exclusion check**: PASS.

### Public Records — ALREADY COVERED (no action)
- `https://www.songkick.com/venues/4216319-public-records` is already in GENERIC_URLS and live-probed 8 upcoming this run (Cleo Reed, Lomelda, Facetime, Jared Mattson). Listening-room programming already flowing; same score-floor caveat as Elsewhere but no new source needed.

---

## GAP 3 — Social dance beyond contra

### STRONG: The Harlem Swing Dance Society (Eventbrite organizer) — APPLIED to user_curated_sources.json
- **Host key added**: `eventbrite.com/o/10662501681`
- **Parse path**: `eventbrite.py::_parse_organizer_page` — verified wired
- **Live yield**: 7 upcoming
- **Samples**: "TUESDAYS in Harlem: FREE Swinging Lindy Hop Class!" (2026-07-14), "Summer 2026: The Harlem Lindy Hop Experience! July Week 3" (2026-07-20), "…August Week 1" (2026-08-03)
- **Why**: participatory lindy hop / swing socials + weekly classes — non-performance, meet-people, recurring. Adds a swing/lindy register the feed lacked (contra was the only social-dance form present per Critic P7).
- **Exclusion check**: PASS. Org/brand, not a person, no excluded hints.

---

## Directives addressed
- **fb-196 (a) games — chess**: ADDRESSED. Chess Place organizer, 6 upcoming, applied to curated layer.
- **fb-196 (a) games — backgammon**: ADDRESSED (recommend). Meetup backgammon search, 13 matching / ~9 NYC. Only viable path (Eventbrite/lu.ma both empty of real backgammon). Orchestrator must append the one URL to GENERIC_URLS.
- **fb-196 (b) underground-electronic beyond Warm Up**: ADDRESSED. Elsewhere organizer curated (12 upcoming) — the fix was the curation boost so already-scraped events clear the floor. Public Records already covered. HoY/KDC correctly NOT re-added (fb-153).
- **fb-196 (c) social dance beyond contra**: ADDRESSED. Harlem Swing Dance Society organizer curated (7 upcoming), swing/lindy socials.

## Probes that failed (do NOT add) — live-verified negatives
- `eventbrite.com/o/marshall-chess-club`, `/o/nyc-backgammon-club` (name-slug guesses): 404 (organizer URLs need numeric ID).
- `https://www.eventbrite.com/d/ny--new-york/backgammon/`: 20 events, **0 real backgammon** (substring noise). Eventbrite has no backgammon supply.
- `https://lu.ma/nyc/backgammon` and `https://lu.ma/nyc/chess`: 20 events each but these are the generic NYC feed (lu.ma serves the city feed when a category is sparse) — 0 backgammon/chess-matching. Do not add; pure noise.
- `https://www.meetup.com/topics/backgammon/us/ny/new_york/`: 0 events (topic path dead; use the `/find/?keywords=` path instead).
- Nowadays own-site (`nowadays.nyc/calendar`, `/events`): 404. Bossa Nova Civic Club (`bossanovacivicclub.com/events`): 0 (JS-rendered). Market Hotel: no Eventbrite organizer (kw search = noise). These venues list on RA/Dice only (blocked per README). Underground-electronic supply for them is not reachable via a parseable path this round.
- CheckMatesBK (`/o/…121456577037`) 1 upcoming, North Brooklyn Chess (`/o/47462204953`) 1 upcoming, CDNY (`/o/…115478120751`) 5 but contra/English (redundant with existing contra), Prohibition Productions 2 — all below or redundant; not proposed. (The 1-upcoming chess clubs are still caught by the existing `/d/ny--new-york/chess/` GENERIC_URL.)

## Open questions for the Critic
- Elsewhere & Public Records were already SCRAPED but under-surfaced — confirm the score-floor/boost hypothesis holds post-scrape (i.e., electronic count in the feed actually rises). If curation boost alone isn't enough, the electronic taste-cluster weighting (quality.py / ranking.py) may need a nudge — out of scope for source-curator, flag to ingestion.
- The backgammon Meetup search mixes in Long Island / NJ / virtual (~4/13). Confirm the geo-normalizer drops non-NYC so the feed doesn't show "Backgammon On Long Island". If it doesn't, a geo-filter tweak is needed (ingestion).
