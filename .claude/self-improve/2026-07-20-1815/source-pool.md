# Source Pool Report — 2026-07-20 1815

Run id: 2026-07-20-1815 | directive: fb-203 (missing-sources audit + chess=0)

## Probe summary
- Existing coverage inventoried across: config.IG_ACCOUNTS (~150 handles), luma.LUMA_PAGES (~85 slugs + 7 curator calendars), generic.GENERIC_URLS (~80 URLs), eventbrite ORGANIZER_URLS + _curated_organizer_urls (preference-layer), meetup SEARCH_URLS (10→16), substack.FEEDS (5), user_curated_sources.json (30+ hosts/hints), plus dedicated scrapers (bookclubbar, lizsbookbar, brooklyncontra, centerforfiction, powerhousearena, mcnallyjackson, museums, music_venues, parks, smorgasburg, brooklyncomedy, dice, partiful, nycforfree, nypl, bondandgrace).
- Gap candidates live-probed: 20+ (Eventbrite organizers, lu.ma category slugs, venue calendars, Meetup keyword searches).
- ADDED: 6 Meetup keyword-search URLs (social dance, singles, social clubs, hiking) — file `scrapers/sources/meetup.py`.
- chess=0 ROOT CAUSE: RESOLVED as stale-metric / downstream, NOT a source gap. Both chess sources live and landing in the current feed.

## chess=0 investigation (fb-203 part B) — VERDICT: not a source problem

- **Chess Place Eventbrite organizer** `o/115357260611`: live-probed **3 upcoming chess events** ("Chess Night at Cosmic Diner - July 20", "Adult Beginner Chess Workshop at The Fox Harlem", "Chess Night at Sugar Mouse - East Village - July 30"). Still parses via _parse_organizer_page. Healthy.
- **Meetup chess keyword search** (already in SEARCH_URLS): live-probed **14 events** ("Social Chess", "Brooklyn Chess & A Beer", "Zeppelin Knight Chess Social! RSVP TO PLAY!"). Healthy.
- **Current feed check** (site/public/events.json, 396 events): chess is **NOT 0** — 4 chess events present with scores 0.58–0.70 (Chess Night at Cosmic Diner, Brooklyn Chess & A Beer, Adult Beginner Chess Workshop, Chess Night at Sugar Mouse). Backgammon = 9 events.
- **Conclusion:** the metrics-before "chess=0" reflected a prior scrape when Chess Place had 0 upcoming at scrape-time (it runs recurring nights that empty out and refill). Both sources are live, parseable, exclusion-clean, and currently landing. No new chess source needed. This is NOT an ingestion-lane bug either — chess is present now. If chess dips to 0 again it will be organizer-refresh timing, not a floor/cap drop (chess events currently clear the floor at 0.58+).

## Inventory vs gaps (confirmed-interest vector)

| Interest | Existing coverage | Gap? |
|---|---|---|
| Underground/experimental + Detroit-techno/dub electronic | MoMA PS1 Warm Up (o/8184194121), Pioneer Works (o/20002618011), Elsewhere (o/105655500371), elsewherebrooklyn.com, lpr, publicrecords/nowadays IG, lu.ma/nyc/music+jazz | Adequate (vetted non-rave). lu.ma techno/electronic slugs return generic feed (no add). Deeper supply blocked by HoY/KDC exclusion — correct. |
| Run clubs (recurring) | ~20 IG run-club handles + Meetup run club/running/fitness + brooklyntrack/nbr/nyrr venue URLs | Well covered |
| Contra & social dance (swing/lindy/salsa) | brooklyncontra.py (contra only), Harlem Swing Dance Society (o/10662501681), lu.ma swing/salsa/bachata/dance slugs | GAP: salsa/swing socials — FILLED via Meetup |
| Literary/books | Deep: bookclubbar, lizsbookbar, mcnallyjackson, booksaremagic, greenlight, centerforfiction, powerhousearena, litclub, readingrhythms, franklinpark, catapult, Meetup Book Clubs cat | Saturated (this is the fb-202 over-supply) |
| Singles/social/meet-people | brightnightssocial, sipsandstories, buzzkill, timeleft, offlineclub, strangersorfriends, lu.ma social/singles/dating/friends slugs, EB singles/dating URLs | GAP: Meetup singles/social-club lane — FILLED |
| Games (backgammon/chess) | nycbackgammonclub, Meetup backgammon+chess, Chess Place organizer, rummikubers, thenewyorkgames, richardsgamesnyc, Meetup Games cat | Well covered (see chess verdict) |
| Comedy | greenpointcomedy, flophouse, unioncomedyhall, eastville, newyorkcomedyclub, standupny, brooklyncomedy.py, caveat, lu.ma comedy | Well covered |
| Outdoors/hiking | nycparks IG + parks.py, greenwood, highline, brooklynbridgepark, lu.ma hiking/parks | GAP: hiking meetups — FILLED |
| Art/museums | brooklynmuseum, met, whitney, new, moma, morgan, cooperhewitt, museums.py, theshed, thekitchen, pioneerworks, lu.ma art | Well covered |

## Proposals (ADDED this run)

### S1: Add social-dance Meetup keyword searches (salsa + swing) — ADDED
- **Metric moved**: topic coverage (contra/social-dance vector, currently only Brooklyn Contra + Harlem Swing)
- **Probe result**: salsa 27 (NY) / 25 (BK): "New Beginner Salsa Classes in LIC Queens", "Salsa/Bachata Social", "Salsa Classes for Absolute Beginners"; swing 14 (NY) / 15 (BK)
- **File**: `scrapers/sources/meetup.py` — SEARCH_URLS (3 URLs: salsa NY, salsa BK, swing NY)
- **Exclusion-check**: clean (no rave/warehouse/HoY/KDC; partner-dance socials)
- **Risk**: low — additive; meetup source has volume cap 60

### S2: Add singles Meetup keyword search — ADDED
- **Metric moved**: high-conviction (singles is boost_categories 1.5, top priority) + topic coverage
- **Probe result**: 19 (NY) / 18 (BK): "July Mix and Mingle", "Central Park Singles Summer Sunset Stroll"
- **File**: `scrapers/sources/meetup.py` — SEARCH_URLS (1 URL: singles NY)
- **Exclusion-check**: clean — any "speed dating" leak still dropped by the speed-dating title_hint in user_excluded_sources.json
- **Risk**: low — additive

### S3: Add social-club Meetup keyword search — ADDED
- **Metric moved**: topic coverage (social/meet-people)
- **Probe result**: 28 (NY) / 28 (BK): "The Awesomely Awkward Social Club: Connect, Chat & Be Yourself", "Social Club Mixer"
- **File**: `scrapers/sources/meetup.py` — SEARCH_URLS (1 URL: social club NY)
- **Exclusion-check**: clean
- **Risk**: low — additive

### S4: Add hiking Meetup keyword search — ADDED
- **Metric moved**: topic coverage (outdoors, previously no dedicated hiking supply)
- **Probe result**: 32 (NY) / 32 (BK): "Enjoy Summer w/ Janine Beer ~4-5 miles", plus outdoor Governors Island / nature walks
- **File**: `scrapers/sources/meetup.py` — SEARCH_URLS (1 URL: hiking NY)
- **Exclusion-check**: clean
- **Risk**: low — additive; some non-NYC (Long Island) rows get geo-filtered downstream, same as backgammon

## Probes that FAILED / did NOT add (honest negatives)
- `lu.ma/nyc/techno` & `lu.ma/nyc/electronic`: 20 events each BUT identical to the generic lu.ma/nyc default feed (lu.ma ignores unknown category slugs). No incremental content over existing lu.ma/nyc. NOT added.
- `nowadays.nyc/calendar`, `publicrecords.nyc/upcoming`: 404. Venue calendars are JS-rendered; not parseable by generic. (These venues already covered via IG + Eventbrite/lu.ma.)
- `countrydancenewyork.org`, `lafamiliany.com`: 503. `amc-ny.org/events`, `shorewalkers.org/events`: 404. `unionhallny.com`: SSL cert failure. Not parseable by generic — no add.
- Eventbrite dance/salsa organizers probed (o/121563865838, o/30017758665, o/45022666893, o/47017594313, o/115055875581, o/50545890703): all 1–5 events and NOT clean recurring social-dance socials (candle-making, choreography workshops, jazz concert series). No vetted social-dance organizer surfaced — Meetup keyword lane is the correct path instead.

## Directives addressed
- **fb-203(A)**: 6 live-probed, exclusion-clean, parseable Meetup keyword URLs added toward the thinnest confirmed-interest gaps (social dance, singles, social clubs, outdoors/hiking). Honest negatives recorded per failed probe.
- **fb-203(B)**: chess=0 root cause identified as stale-metric — both chess sources (Chess Place organizer o/115357260611, Meetup chess) are live-verified yielding, and chess IS present in the current feed (4 events). No fix needed on source side; not an ingestion drop either (chess clears the floor). Documented.

## Open questions for the Critic
- fb-202 (top-of-feed one-venue wall) is the real user-visible pain and is an INGESTION/ranking fix, not a source fix. This run's adds diversify the supply feeding the ranker (music-adjacent dance, singles, outdoors) so the diversity cap has non-book content to promote into the top-12.
- Electronic depth: the user's excluded HoY/KDC bound how much underground-electronic supply we can ethically add. Warm Up + Pioneer Works + Elsewhere are the vetted ceiling. Flagging that "more electronic" cannot be satisfied by more sources without touching the exclusion — it's a ranking-visibility problem (fb-202), not a supply problem.
