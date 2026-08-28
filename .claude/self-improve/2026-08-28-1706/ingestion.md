# Ingestion Quality Report — 2026-08-28 1321 EDT

## Metrics observed

- Deployed feed audited: `2026-08-28T17:07:01.189383+00:00`, 537 events.
- `signal_accounts` with `yield_map > 0`: **50 / 50 (100.0%)**.
- 0-yield signal accounts in `IG_ACCOUNTS` but no events emitted: **none**.
- 0-yield signal accounts NOT in `IG_ACCOUNTS`: **none**.
- All 50 signal accounts are currently in `IG_ACCOUNTS`. The four zero-valued entries still present outside `signal_accounts` (`alvinzx`, `sophiareed5`, `j_palmer_7`, `leahcanel`) are intentionally excluded personal accounts under fb-106/fb-153; do not re-add them.
- `account_quality.json` has no signal account with `posts_scraped > 0` and `events_emitted == 0`; there is no current high-post/zero-event extraction failure to repair.
- Topic coverage: `ny=112`, `nyc=68`, `club=42`, `run=23`, `book=93`, `bk=41`, `brooklyn=41`, `read=38`, `ai=92`; no tracked topic with count >= 2 is absent. (`ai` remains a measurement artifact, not an acquisition target, because AI events are explicitly excluded.)
- High-conviction event ratio: **90 / 537 (16.8%)** — 87 `userFollowing` only and 3 `userFollowing + userAffinity`; no current `userSaved` event.
- Important metric caveat: the profile says 50/50 historical yield, but only **6/50** signal accounts are represented by current live-feed provenance (`nyc_forfree`, `explorenycfree`, `reading_rhythms`, `bookclubbar`, `nycbackgammonclub`, `onefinedaynyc`). The 100% metric is lifetime/stale coverage, not active-feed breadth.
- Local comparison: both `data/events.json` and `site/public/events.json` are identical, last updated 2026-08-21, and contain 286 events versus 537 deployed. Any local-only QA or SEO generation currently sees a feed that is 251 events behind production.

## Live-feed audit

### Source distribution

| Source | Events |
|---|---:|
| songkick | 79 |
| partiful | 74 |
| luma | 60 |
| allevents | 44 |
| nycforfree | 40 |
| brooklyncomedy | 40 |
| eventbrite | 37 |
| newyorkcomedyclub | 30 |
| bookclubbar | 30 |
| thebellhouseny | 21 |
| powerhousearena | 19 |
| eastvillecomedy | 17 |
| dice | 15 |
| lizsbookbar | 14 |
| instagram | 7 |
| brooklyncontra | 5 |
| smorgasburg | 2 |
| greenwoodcemetery | 2 |
| substack | 1 |

### Required checks

- Late-night regex leaks: **0**.
- Professional-networking regex leaks: **0**.
- Exact title+date duplicate groups: **0**.
- Events after 2026-12-01: **1**, `Son Lux (Night #1)` on 2026-12-18 at Pioneer Works. This is a legitimate explicitly dated listing, not a misparse.
- Caption/narrative/hype scan:
  - Bad date-range fragment: `September 5 through 27` (Substack), with no venue and the malformed description `Running fromatProspect Park...`.
  - `WE ARE BACK! 'The House OF VIBES' FALL SEASON! w\\ Mr. V and FRIENDS` is noisy aggregator copy but still names the event; no broad `we are back` block is proposed.
  - `IT'S MURPH @ Under the K Bridge Park` is an artist title, demonstrating that a broad `^it's` narrative rule would false-positive.
- Definite non-NYC leaks: **6 non-conviction events** — `Bleachers @ Stone Pony Summer Stage`, `Chris Botti @ Hackensack Meridian Health Theatre, Count Basie Center`, `Big Bad Voodoo Daddy @ The Vogel, Count Basie Center for the Arts`, `I Set My Friends On Fire @ House of Independents`, `10th Anniversary Ocean County Irish Festival` (all NJ addresses), and `Great Outdoors Comedy Festival - Matt Rife - Saturday (Evening) - Edmonton`.

## High-quality non-IG source audit

| Source | Count | Completeness / sampled quality |
|---|---:|---|
| Lu.ma | 60 | 0 missing start time, venue name, address, or image; all 60 descriptions are empty and 17 prices are unknown. Samples `Worldbuilders Special @ Recess Grove`, `Pages in the Park`, and `Cycol Gallery Presents: Biz Markie x Bisco Smith...` have clean titles/times/venues. |
| Eventbrite | 37 | 0 missing start time/name/address; 24 missing descriptions, 27 unknown prices, and **25 have `endTime == startTime`**. Samples `Sylvan Esso Road Trip...`, `Second Sundays: September 2026`, and `A Winged Victory for the Sullen...` are otherwise clean. |
| Substack | 1 | The sole event is the malformed `September 5 through 27`: date-only title, no venue/address, malformed description. |
| Partiful | 74 | 0 missing start time/description/image; 33 missing end time, 26 missing venue name, 4 missing address, 57 unknown prices. Samples `US Open Block Party - Fan Week`, `Marigold: Pre-launch Reading`, and `Exhibition: Contemporary Photography at Gallery 71` are readable. One current contradiction needs human/source verification: `Astoria Gay Book Club Sep.26 Meetup...` is dated 2026-09-08 and its description also says September 8. |

## Liz's Book Bar end-to-end audit

- Canonical Eventbrite organizer: `https://www.eventbrite.com/o/lizs-book-bar-83466825333`.
- The current Eventbrite parser extracts **10 future events** from it and `_organizer_calendar_is_useful` returns true.
- The dedicated Bookmanager scraper extracts **16 future events**. The deployed site contains **14** `lizsbookbar` events.
- All 10 Eventbrite events also exist in the 16-event Bookmanager result. Combining both sets yields 26 raw rows -> **16 after dedup**, so venue/title dedup is working.
- `Speed Dating Book Club` is then correctly removed by `user_excluded_sources.json::title_hints`.
- `Celebrate Patricia Lockwood, winner of the 2026 Gabe Hudson Prize` is incorrectly removed: the live Bookmanager scrape returns it, but `_is_caption_fragment` treats every title starting `Celebrate ` as noise and `compute_score` returns 0.0. This explains the remaining 16 -> 14 difference exactly.
- The nine allowed Eventbrite listings are therefore already represented on the website under the higher-quality `lizsbookbar` source. What is missing is deterministic Eventbrite organizer discovery and cross-source provenance (`organizerRefs` / `contributingSources`), not the nine event cards themselves.
- The Eventbrite organizer ID is absent from both `discovered_urls.json` and `user_curated_sources.json`; the existing generic key `lizsbookbar` does not match `eventbrite.com/o/lizs-book-bar-83466825333`.
- Organizer-page rows have images, times, and locations but empty descriptions. Unless the organizer matches a curated host, `_is_shell_event` drops them before dedup. That makes the new automatic organizer-promotion lane largely inert for newly discovered (not-yet-curated) organizers.
- The organizer is clean under exclusions: 9/10 allowed; the one disallowed speed-dating event is dropped downstream. It is not present in `user_excluded_sources.json` accounts/hosts.

## Proposals

### P1: Complete fb-193 by using the existing canonical venue key for neighborhood lookup

- **Metric moved**: high-conviction ratio (precision of surfaced event location) and topic coverage (reliable neighborhood browsing).
- **File**: `scrapers/normalize.py:369`, `scrapers/normalize.py:803`, `scrapers/normalize.py:876`; tests in `scrapers/tests/test_normalize.py:361`.
- **Change**: Keep `_normalize_venue_name` as the single canonicalization path. Dedup already uses it and already proves `BK Bowl == Brooklyn Bowl` and `MoMA == Museum of Modern Art`. Build the venue-to-neighborhood lookup from canonicalized keys and canonicalize the candidate venue before lookup. Do not rewrite the user-facing venue string. Add regression assertions for those two alias pairs plus `MoMA PS1 -> long island city` and `New York Comedy Club Upper West Side -> upper west side`.
- **Current evidence / test**: `_normalize_venue_name('BK Bowl') == _normalize_venue_name('Brooklyn Bowl') == 'brooklyn bowl'`, and the same is true for `MoMA`/`Museum of Modern Art`; synthetic same-title/date pairs already dedup 2 -> 1. But neighborhood inference currently returns `None` for both `BK Bowl` and `Museum of Modern Art`, while their long/canonical counterparts return `williamsburg` and `midtown`. The deployed feed has `Warm Up...` at `MoMA PS1` and `Mad Caddies @ Brooklyn Bowl`; both are regression guards.
- **Expected user impact**: alternate venue spellings stop producing blank/contradictory neighborhoods while existing dedup behavior remains stable.
- **Risk**: `_normalize_venue_name` strips neighborhood suffixes, so explicit branch detection must stay first. Otherwise `New York Comedy Club Upper West Side` or `Book Club Bar Bushwick` could collapse to the flagship neighborhood. Preserve the current Step-0 explicit-neighborhood precedence.

### P2: Stop numbered avenues from substring-matching the wrong neighborhood

- **Metric moved**: high-conviction ratio (location precision; numerator unchanged, but event recommendations become trustworthy).
- **File**: `scrapers/utils/event_parser.py:881`; tests in `scrapers/tests/test_event_parser.py` and `scrapers/tests/test_normalize.py:426`.
- **Change**: word-boundary the ordinal-street keywords in `NYC_NEIGHBORHOODS`, not only keywords of length <= 3. At minimum, compile patterns such as `(?<!\\d)1st\\s+ave\\b` and `(?<!\\d)2nd\\s+ave\\b` so `1st Ave` cannot match inside `31st Ave`.
- **Example title(s) this catches/excludes**: `Astoria Gay Book Club Sep.26 Meetup - Fruit Fly by Josh Silver` at `37-14 31st Ave, Queens, NY 11103` is currently tagged `east village` because `1st ave` substring-matches `31st Ave`; after the change it resolves to `astoria` via the title/ZIP.
- **Test**: assert `infer_neighborhood('37-14 31st Ave, Queens, NY 11103', 'Heart of Gold', 'Astoria Gay Book Club...') == 'astoria'`, while a real `1st Ave` address remains `east village`.
- **Expected user impact**: fixes one current neighborhood contradiction and prevents the same failure for 21st/31st Avenue Queens venues.
- **Risk**: low if limited to ordinal-street tokens; do not globally reorder the neighborhood table.

### P3: Let shared Bookmanager extraction use an event-specific address

- **Metric moved**: high-conviction ratio (location precision for a followed/curated literary source).
- **File**: `scrapers/utils/bookmanager.py:132`, especially `location_text` at lines 159-160 and `address=default_address` at line 184; tests in a shared Bookmanager test module.
- **Change**: when `location_text` contains an address-like token (street number plus `St/Street/Ave/Avenue/Rd/Road/Blvd`), pass that location text as the event address; use `default_address` only when the event row has no address-like override. This is protocol-level Bookmanager behavior, not Book Club Bar-specific code.
- **Example title(s) this catches/excludes**: 13/30 current Book Club Bar cards name a non-default venue while still displaying `197 E 3rd St`. Examples: `Stage Dive: Creative Writing Workshop` names `Book Club Bar Bushwick, 380 Troutman Street`; `OFFSITE EVENT: Books & Burlesque` names `Caveat, 21A Clinton Street`; `Offsite Event: "Poking the Squid"...` names `Tompkins Square Library, 331 East 10th Street`. `Sweet Nothings Literary Salon` is also mis-tagged `east village` despite a `380 Troutman St, Brooklyn` venue string.
- **Test**: feed `_row_to_event` each of those real `location_text` shapes and assert its address/neighborhood reflect the event venue, while a blank/generic location continues to use the store default.
- **Expected user impact**: accurate map/directions and neighborhood filters for high-affinity bookstore events.
- **Risk**: some `location_text` values may be prose; gate the override on an address-shaped match rather than blindly copying every value.

### P4: Make Eventbrite organizer promotion taste-first and survivable

- **Metric moved**: high-conviction event ratio.
- **File**: `scrapers/sources/eventbrite.py:177-272`, `scrapers/normalize.py:1709`; tests in `scrapers/tests/test_platform_discovery.py:105` and `scrapers/tests/test_normalize.py`.
- **Change**: in `_promoted_organizers`, count unique **eligible** event URLs (`not is_blocked` and `not is_user_excluded`), track the number from `personal` lanes, and sort explicit user signals first, then personal-event count, then clean recurring yield. Raw event count should only break ties inside the same taste tier. Apply the same exclusion-aware definition of clean to `_organizer_calendar_is_useful`. Stamp parsed organizer-calendar rows as structured Eventbrite catalog records and let `_is_shell_event` keep them when they have an image plus a venue/address, mirroring the existing Lu.ma catalog exception; hard blocks and user exclusions still run first.
- **Example / proof**: current code ranks a generic 10-event search organizer at score 10 above an explicit one-event Liz's Book Bar organizer at score 8. The desired order is the reverse. The Liz calendar itself remains eligible at 9/10 exclusion-clean events; `Speed Dating Book Club` must not contribute clean yield.
- **Test**: add a regression where an explicit/user-affinity organizer with one event outranks a 10-event anonymous organizer, where excluded events do not satisfy the recurring-yield minimum, and where a structured organizer row with image+location but no description survives while an unstructured Eventbrite shell does not.
- **Expected user impact**: limited organizer crawl slots follow demonstrated interests rather than generic Eventbrite popularity, increasing the chance that fetched events carry real user conviction.
- **Risk**: narrow but highly relevant organizers can displace broad inventory; the existing minimum-yield and >=80% clean-calendar gate still bounds this.

### P5: Guarantee Liz's Book Bar's Eventbrite organizer and preserve its structured titles

- **Metric moved**: topic coverage (`book`/`read`) and high-conviction event ratio (taste-aligned inventory selected from an explicitly requested organizer).
- **File**: `scrapers/data/user_curated_sources.json:69`, `scrapers/utils/bookmanager.py:178`, `scrapers/ranking.py:33`; tests in `scrapers/tests/test_platform_discovery.py` plus a ranking regression.
- **Change**:
  1. Add `eventbrite.com/o/83466825333` as a `user_mentioned` curated host. This exact organizer is not excluded and live-probes at 10 future events.
  2. Canonicalize Eventbrite `/o/<slug>-<id>` and `/o/<id>` URLs to the same organizer ID when `_is_curated_host` / `_user_curated_boost` compare them. The normal frontier currently rewrites to slugless form, but direct URLs and fixtures can retain the slugged form.
  3. Mark titles delivered in a structured Bookmanager `row.title` field as structured/authoritative metadata, and exempt only that explicit marker from the social-caption **fragment hard-zero** in `compute_score`. Hard blocks and `is_user_excluded` still run first.
  4. Add an end-to-end fixture proving: 16 direct + 10 Eventbrite rows -> 16 after dedup; `Speed Dating Book Club` is removed; the Patricia Lockwood event survives; the nine allowed Eventbrite rows retain Eventbrite `organizerRefs` after merging.
- **Example title(s) this catches/excludes**: recover `Celebrate Patricia Lockwood, winner of the 2026 Gabe Hudson Prize`; continue excluding `Speed Dating Book Club`.
- **Expected user impact**: the requested organizer is deterministic instead of depending on search-result discovery, cross-source confirmation is retained, and the one desirable current Liz event lost to a generic caption heuristic appears on the site (14 -> 15 allowed Liz events in the current live snapshot).
- **Risk**: trusted structured feeds can still publish promotional wording. Limit the bypass to titles that arrived in a dedicated structured title field; never bypass hard blocks or user exclusions.

### P6: Treat Eventbrite `endTime == startTime` as unknown

- **Metric moved**: high-conviction ratio (decision-quality of surfaced events; no expected inventory-count change).
- **File**: `scrapers/sources/eventbrite.py:391-394` and `scrapers/sources/eventbrite.py:547-582`; tests in `scrapers/tests/test_platform_discovery.py:195`.
- **Change**: after parsing, if a non-empty Eventbrite `end_time` exactly equals `start_time`, set `endTime=None`. Preserve genuinely different end times.
- **Example title(s) this catches/excludes**: 25/37 live Eventbrite events currently claim zero duration, including `Second Sundays: September 2026` (`12:00-12:00`), `Sylvan Esso Road Trip...` (`19:00-19:00`), and all 10 live-probed Liz organizer rows.
- **Expected user impact**: cards stop presenting a false zero-length schedule; missing end time is more honest than incorrect precision.
- **Risk**: a truly instantaneous listing would lose its end time, but that is materially less likely than Eventbrite using start time as a placeholder.

### P7: Drop Substack date-range headings that leak as event titles

- **Metric moved**: high-conviction event ratio (precision; removes a non-conviction junk denominator) and topic coverage quality.
- **File**: `scrapers/sources/substack.py:681`; tests in `scrapers/tests/test_substack.py`.
- **Change**: extend the existing date-only range recognizer to accept `through` as a range separator. This is additive to the existing `to|-|–|—` alternatives.
- **Example title(s) this catches/excludes**: the exact proposed pattern matches the sole deployed Substack event, `September 5 through 27`; it has no venue and a malformed `Running fromatProspect Park...` description.
- **Test**: `_is_date_only_title('September 5 through 27') is True`; retain a negative control for a legitimate title containing a date.
- **Expected user impact**: removes the only current Substack card, which is not an actionable event record; authoritative links harvested from the post remain available to other scrapers.
- **Risk**: low; the rule is restricted to a month/day range occupying the entire title.

### P8: Reject explicit NJ addresses and the current Edmonton leak

- **Metric moved**: high-conviction event ratio (precision; removing six non-conviction rows changes 90/537 = 16.8% to 90/531 = 16.9%).
- **File**: `scrapers/quality.py:1001-1131`; tests in `scrapers/tests/test_quality.py`.
- **Change**: add an address-only state check for `NJ`/`New Jersey` (and equivalently guarded neighboring-state abbreviations) before the current city-marker logic, and add `edmonton` to the explicit non-NYC city set. Address state must take precedence over an aggregator's fabricated NYC marker elsewhere in the record.
- **Example title(s) this catches/excludes**: the five NJ-address rows listed above plus `Great Outdoors Comedy Festival - Matt Rife - Saturday (Evening) - Edmonton`. The proposed patterns were tested against the live feed and match exactly those six rows.
- **Expected user impact**: removes plainly out-of-market inventory from the NYC feed.
- **Risk**: low when state abbreviations are checked only in `location.address`; do not substring-match `NJ` across title/description.

## Directives addressed

- **fb-193**: addressed by P1 with the exact remaining defect isolated. Alias canonicalization already exists and works in dedup; neighborhood inference is the inconsistent consumer that still needs the canonical key and regression tests.
- **fb-178**: deferred to the UI worker. This ingestion audit did not modify the browser-to-pipeline taste sync.
- **fb-187**: deferred to the source-curator worker, who owns the fresh folk-dance probe and participatory-share decision.
- **2026-08-28 user addition — Liz's Book Bar Eventbrite**: investigated end to end in P4/P5. Nine allowed Eventbrite events already survive through the dedicated source; the exact organizer ID should be persisted for deterministic provenance, and one additional desirable direct event is blocked by a false caption-fragment classification.
- **2026-08-28 user preference — infer appreciation, not popularity**: addressed by P4's taste-first organizer ordering and exclusion-aware clean-yield accounting.

## Verification performed

- Live feed audit against `https://prajjwal1.github.io/nyc/events.json` downloaded at 2026-08-28 13:07 EDT.
- Live Eventbrite organizer parse for ID `83466825333`: 10 future events, useful-calendar gate passes.
- Live Bookmanager scrape for Liz's Book Bar: 16 future events.
- Combined Liz dedup: 26 raw -> 16 unique; user exclusion -> 15; current caption-fragment rule -> 14, exactly matching the deployed `lizsbookbar` count.
- Existing targeted tests: `python -m pytest -q scrapers/tests/test_platform_discovery.py scrapers/tests/test_normalize.py scrapers/tests/test_substack.py` -> **79 passed**.

## Open questions for the Critic

- Should `user_interest_profile.yield_map` remain a lifetime/historical metric? It reports 50/50 while current-feed provenance represents only 6/50 signal accounts. A separate rolling/current-feed coverage metric may be more honest without reopening fb-101 source expansion.
- For `Astoria Gay Book Club Sep.26 Meetup - Fruit Fly by Josh Silver`, Partiful's structured date and description both say September 8 while the title says Sep.26. The neighborhood is certainly wrong and fixed by P2; the authoritative event date needs a live Partiful page check before changing it.
- P1 produces no current target-alias duplicate count reduction because the deployed feed has no same-date `BK Bowl`/`Brooklyn Bowl` or `MoMA`/`Museum of Modern Art` pair. The tested defect is real (dedup canonicalizes while neighborhood inference does not), but the Critic should not claim a current duplicate delta.
