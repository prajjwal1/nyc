# Source Pool Report — 2026-06-15 1724

## Probe summary
- lu.ma curator-handle probes (zero-yield signal accounts): 50+ handle/slug variants | added: 0 (all 404 or 0-yield)
- Own-site calendar probes (bbg, wordbookstores, northbrooklynrunners): 8 | added: 0
- Eventbrite organizer-ID discovery: blocked (search HTML is JS-rendered from this IP — no `/o/<id>` recoverable)
- Non-signal literary/social lu.ma calendars (Bond & Grace-style): 15 | added: 0
- Re-probe of CI-failing literary URLs (greenlight, booksaremagic, caveat, strand): 6 | added: 0 (JS-gated or already dedicated-scraper-handled)
- **Net new sources proposed this round: 0** (conservative — nothing cleared the ≥5 live-yield bar)

## Headline finding
The existing non-IG enrichment lever WORKS and is healthy: a live re-probe confirmed
`lu.ma/readingrhythms-manhattan` (16), `lu.ma/litclub.nyc` (12), `lu.ma/philosophy` (7),
`lu.ma/nycbackgammonclub` (4) all still yielding. The problem this session is that the
**remaining ~38 zero-yield signal accounts have no parseable public non-IG calendar** — they
are genuinely IG-only or sit behind JS-rendered platforms the generic scraper cannot read
server-side. This is documented honestly below rather than padded with speculative adds.

## Proposals
**None.** No candidate produced a live yield ≥ 5 through a path the existing scrapers can parse.
Adding any of the probed URLs would ship a 0-yield source (against the hard rule + additive-only
discipline). SOURCE_VOLUME_CAPS: no implication — nothing added.

## Probes that failed (don't add) — evidence

### lu.ma curator handles for zero-yield signal accounts — all 404 / 0
Probed bare-handle + common slug variants for: reading_rhythms, zoomiesrunclub, franklinparkbk,
nyucreativewriting, crownheightscraftclub, brightlightorg, yogaspace.nyc, open.bookclub,
omgreenpoint, nyplyounglions, queerfeetnyc, thenewyorkgames, northbrooklynrunners,
silentbookclub.nyc, asianfoundersclub, vitalrunclub, wnrr_nyc, anaiswinebk, greenpointtrashclub,
secondsrunclub, midnightrunnersnewyork, richardsgamesnyc, nook_bklyn, fortheplotnyc,
quietreading.club, nycsprintcollective, brooklynbotanic, strangersorfriendsbk, wordbookstores,
likeafriendsaid.nyc, rummikubers, brooklynheightsassociation + slug variants
(strangersorfriends, fortheplot, quietreading, sprintcollective, readingrhythms-brooklyn, etc.).
**Result: every one returned 404 or 0 events.** These accounts do not expose a public lu.ma
curator calendar under any guessed slug. (The ones that DO — readingrhythms-manhattan,
litclub.nyc, philosophy, nycbackgammonclub — are already in LUMA_PAGES.)

### Own-site calendars — live HTML but not generic-parseable
- `https://www.bbg.org/calendar` — HTTP 200, 27 events in custom `event-date`/`event-tag` HTML
  with NO JSON-LD. Generic scraper yields 0. Content is mostly long-running seasonal *exhibits*
  ("May 23–October 25, 2026"), not discrete dated social events. Low attend-value + would need a
  dedicated scraper. NOT WORTH a custom scraper.
- `https://www.wordbookstores.com` (covers signal account `wordbookstores`) — events live on
  `https://withfriends.co/word/events`. withfriends.co is fully JS-rendered (no server-side
  JSON-LD / API returns the SPA shell). Generic + direct `/api/organization/word/events` both
  yield 0. Would need a Playwright-class scraper — out of scope for an additive generic add.
- `https://www.northbrooklynrunners.org/nbr-schedule` — static recurring-run schedule page,
  no dated discrete events. 0 yield. (Run club is IG/Strava/Facebook-group driven.)

### Eventbrite organizer discovery — IP-blocked / JS-rendered
Eventbrite `/d/ny--new-york/<query>/` search pages return only the JS shell from this IP
(no `/o/<id>` organizer links in server HTML). Could not recover organizer IDs for
reading-rhythms / strangers-or-friends / for-the-plot / quiet-reading / sprint-collective /
zoomies. The eventbrite.py organizer-page parser is solid (litclub's `/o/14861961557` works),
but without a discoverable org ID there's nothing to add. Per fb-155 the location.name match-rate
check could not be run (no candidate venue-search URL produced a parseable result set).

### CI-failing literary URLs re-probed (per fb-173 — verify residential vs CI)
greenlight (0), booksaremagic (0), caveat.nyc (0), strandbooks (0), mcnallyjackson (0 via
generic — has its own dedicated scraper), powerhousearena (1, dedicated scraper). All are either
JS-gated or already covered by dedicated scrapers. None is a clean generic GENERIC_URLS add.

### Non-signal literary/social lu.ma calendars (Bond & Grace-style hunt)
Probed offline(club), timeleft(nyc), catapult, thinkolio, founderscoffee, cinemaclub,
dinnerwithstrangers, thelongtable, phonefreebookclub, nycbookclub, greatbooksnyc, lizsbookbar.
Best was `timeleft` (2 events) and `nycbookclub` (1) — both below the ≥5 bar. No new
high-value literary/social source found this round.

## Directive addressed
- **fb-177 / feedback directive (lift follow-graph via non-IG paths):** Executed the full
  non-IG sweep (lu.ma curator handles, own-site JSON-LD/HTML, Eventbrite organizer pages,
  withfriends platform, residential re-probe of CI-failing literary URLs). Honest result:
  the productive non-IG paths for the user's literary/run/social signal accounts are ALREADY
  in the config (readingrhythms-manhattan, litclub.nyc, philosophy, nycbackgammonclub,
  bondandgrace, bookclubbar, lizsbookbar). The remaining ~38 zero-yield accounts are genuinely
  IG-only or JS-platform-gated. No pad-adds made.
- **fb-155 (Eventbrite location.name match-rate):** honored — no venue-search URL proposed
  because none produced a parseable result set to compute a match rate on.
- **fb-106 (no individual-person accounts) + user_excluded_sources check:** N/A — zero adds.

## Open questions / flag for the Critic (likely-higher-value than any source add)
1. **Possible enrichment-fold bug (ingestion, not source):** `lu.ma/readingrhythms-manhattan`
   yields 16 live events, yet signal account `reading_rhythms` still shows **yield 0.0** in
   `user_interest_profile.json`. The curator slug `readingrhythms-manhattan` is not folding to
   the `reading_rhythms` signal handle (underscore-vs-hyphen / location-suffix normalization gap,
   cf. the `philosophy`→`philosophy.nyc` fold shipped in 2026-06-04). If the fold were fixed,
   `reading_rhythms` would move 0→>0 with ZERO new sources. This is the single highest-leverage
   follow-graph win available and should be routed to the **ingestion** agent. Same class of
   issue may apply to `nycbackgammonclub` (lu.ma yields 4 but profile shows 0).
2. **withfriends.co** powers `wordbookstores` (and likely other indie bookstores). If a future
   round wants `word` coverage, it needs a JS-capable scraper or the withfriends GraphQL/JSON
   endpoint (not reachable from this IP). Logging as a known-but-deferred path.
3. Honest coverage ceiling: with the IG account-sweep user-blocked (fb-174) AND the remaining
   zero-yield accounts being IG-only, follow-graph coverage cannot be meaningfully lifted by
   source-adds this round. The lever that CAN move it is the fold-bug fix in (1).
