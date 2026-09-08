# Ingestion Quality Report — 2026-09-08 1754

North Star: **Surface events the user would actually attend in NYC.**

## Metrics observed

- Deployed-feed probe: unavailable from this runner. `curl` to `https://prajjwal1.github.io/nyc/events.json` failed with connection error 7 before any HTTP response. This is a connectivity failure, not a zero-yield result.
- Audit feed: `data/events.json` and `site/public/events.json` are byte-identical (SHA-256 `97018d12be55f30513e999cf5ab3197054097c809930956f6eb57f41b8e7e8c9`), with 645 events and `lastUpdated=2026-09-04T15:06:43.095421+00:00`. On September 8, 132/645 rows are already before today, so deployment freshness cannot be verified from this snapshot.
- signal_accounts with `yield_map > 0`: **50 / 50 (100.0%)**.
- 0-yield accounts in `IG_ACCOUNTS` but no events emitted: **none**.
- 0-yield accounts NOT in `IG_ACCOUNTS`: **none**.
- All 50 signal accounts are already in `IG_ACCOUNTS`; no additive IG-account change is warranted. `account_quality.json` has no signal account with at least 5 posts and zero emitted events (aggregate: 4,569 posts / 4,168 events).
- `dead_accounts.json` contains ledger entries for all 50 signal accounts, but 49 are transient-only `feedback_required` records and one (`explorenycfree`) is a transient 429; only `brooklynbotanic` still carries `reason=repeated_failure`, and its `last_reason` is also transient. Current scraper logic revives these rather than treating them as true dead accounts. Do not call these zero yield.
- Topic coverage (the run's existing synonym-aware metric): **9 / 9** entries with `topic_counts >= 2` are represented: `ny=117`, `nyc=70`, `club=69`, `run=23`, `book=117`, `bk=60`, `brooklyn=60`, `read=42`, `ai=103`.
- Topic caveat: `ai` is not a valid expansion target despite appearing in the follow-derived token map; the user-exclusion policy says no AI-themed events. Two explicit AI events remain in the snapshot: `The Fragility of Borrowed Intelligence: Subtle Risks of AI Dependence` and `The Frontier of Enterprise AI in Production`. This conflict should be resolved by the Critic without adding a broad `ai` keyword, which the exclusion data explicitly cautions against.
- High-conviction event ratio (`userFollowing || userSaved || userAffinity`): **49 / 645 (7.6%)**. Flags are 49 `userFollowing`, 1 overlapping `userAffinity`, and 0 `userSaved`. Only four followed handles are represented in the snapshot (`bookclubbar`, `readingrhythms`, `onefinedaynyc`, `explorenycfree`) even though historical `yield_map` coverage is 100%.

## 0-yield investigation

There are no current 0.0 values among `signal_accounts`, so there is no per-account add/deadlist/extraction proposal. Four excluded personal accounts (`alvinzx`, `j_palmer_7`, `leahcanel`, `sophiareed5`) remain at 0.0 in `yield_map` but are not signal accounts and are explicitly off-limits under fb-106/fb-153.

The important distinction is historical coverage versus current-feed conviction: `yield_map` says every signal account has produced an event at some point, while only four followed handles have an event in the September 4 snapshot. The 7.6% high-conviction ratio is therefore the useful active constraint this round.

## Live-feed audit

### Source distribution

| Source | Events | Source | Events |
|---|---:|---|---:|
| eventbrite | 121 | songkick | 108 |
| partiful | 85 | luma | 79 |
| newyorkcomedyclub | 46 | brooklyncomedy | 41 |
| allevents | 35 | bookclubbar | 29 |
| powerhousearena | 21 | eastvillecomedy | 18 |
| thebellhouseny | 15 | lizsbookbar | 15 |
| dice | 14 | instagram | 5 |
| brooklyncontra | 5 | greenwoodcemetery | 3 |
| smorgasburg | 2 | nypl | 2 |
| substack | 1 |  |  |

### Filter and title checks

- Late-night regex matches: **1** — `oomfRAVE Labor Day Weekend Extravaganza` (Partiful). Its description says `9pm-4am`, but `4am` begins at character 247 and `_likely_past_midnight` scans only the first 200 description characters.
- Professional-networking regex matches: **0**.
- Exact normalized title+date duplicate groups: **0**.
- Events after 2026-12-31: **0**.
- Caption-fragment detector matches: **1** — `Celebrate Patricia Lockwood, winner of the 2026 Gabe Hudson Prize`; it has `structuredTitle=true` and is a legitimate titled bookstore event, so the existing structured-title exception is correct.
- Narrative-starter matches: **0**.
- Hype-opener matches: **0**.
- Additional malformed title: `Running fromatProspect Park’ LeFrak Center at Lakeside. Free reservations are encouraged` (Substack). The missing space is consistent with `heading.get_text(strip=True)` joining nested inline elements in `substack.py:420`, but the source XML/HTML could not be fetched. Capture a fixture before changing title segmentation.

## High-quality non-IG source audit

Deterministic random seed: `20260908`.

| Source | Count | Missing time | Missing location | Missing image | Samples inspected |
|---|---:|---:|---:|---:|---|
| Lu.ma | 79 | 0 | 0 | 0 | `The Ethereal Show NYFW`; `Afrikrea NYFW POP-UP: Created by Africa and the African Diaspora`; `OutRun CO2 Club 👟🗽` |
| Eventbrite | 121 | 0 | 0 | 2 | `Nick Naney’s Big Secret Project Reveal`; `FICTION Book Club`; `Science & Society: The Ocean Frontier` |
| Substack | 1 | 0 | 1 | 0 | Only one available: malformed `Running fromatProspect Park…` title above |
| Partiful | 85 | 0 | 8 | 0 | `Cordial Creative Club: September`; `The Great Brooklyn Beer Mile`; `Summer Send Off: Labor Day Hike!` |

The Luma and Eventbrite samples have usable times, venues, canonical links, and clean titles. Missing Eventbrite images are limited to `Chess Night at La Fonda` and `Chess Night at The Fox Harlem - September 23rd`; both otherwise have complete time/location data. Partiful's eight hidden/missing locations are not themselves grounds for rejection, but its NYC gate admits four explicit non-NYC New York State ZIPs (P3).

## Source-expansion survival audit

No candidate could be live-probed because outbound network access failed. Therefore none is certified or proposed for addition. The unverified queue is:

- `https://theworldsboroughbookshop.com/events/list/upcoming-events` (literary)
- `https://www.brooklynrunningco.com/blogs/news/events-calendar/` (run/social fitness)
- `https://NYCRuns.com/races` (running)
- `https://www.eventbrite.com/cc/writing-community-4261073` (literary collection)

The first three would enter through the generic JSON-LD/OpenGraph/iCal path. They must be re-probed with the project parser for at least 5 future events and at least 80% exclusion-clean/on-taste inventory. If the blog/races pages are JS shells or use non-event article paths, do not add per-site code; capture HTML and implement a source-agnostic calendar-card or one-hop discovery strategy.

The Eventbrite candidate exposes a concrete ingestion bug independent of its unverified quality: `platform_discovery._classify` correctly returns kind `collection` for `/cc/`, but `eventbrite.scrape()` schedules only `organizer` and `event`. Two already-discovered collections are silently unscheduled today. Historical `url_health` shows they previously worked through the old generic route (`last_event_count` 29 and 14, zero failures), while the current generic scraper deliberately skips dedicated-platform URLs.

## Proposals

### P1: Schedule the Eventbrite collection frontier

- **Metric moved**: topic coverage
- **File**: `scrapers/sources/eventbrite.py:119`; tests in `scrapers/tests/`
- **Change**: add a small, bounded `platform_frontier("eventbrite", kinds={"collection"})` lane before broad searches; fetch with `_fetch_with_backoff`, parse with `_parse_search_page`, stamp `discoveryLane`/`discoveryVia`, dedupe, and require the existing >=5 clean events / >=80% clean-ratio gate before admission. Suggested budget: 2 collections in quick mode, 6 in full mode. Add a regression test proving a `/cc/` item is scheduled; classification itself already exists at `scrapers/utils/platform_discovery.py:194-201`.
- **Example title(s) this catches/excludes**: no candidate title is claimed because the network probe failed. Concrete dormant inputs are `ironstrength-2026-one-community-for-all` (historical last yield 29) and `edfest-2026` (historical last yield 14); the new `writing-community-4261073` candidate remains unverified.
- **Risk**: collection pages can be mixed-quality or duplicate organizer/search inventory. Keep the strict usefulness gate, bounded fetch count, canonical URL dedup, and normal exclusions; do not add the Writing Community collection until a connected probe passes.

### P2: Credit structured organizer references before shell filtering

- **Metric moved**: high-conviction event ratio
- **File**: `scrapers/normalize.py:1476`, `scrapers/normalize.py:1714`, `scrapers/normalize.py:2218`
- **Change**: extend `_enrich_provenance_from_url` to inspect `organizerUrl` and every `organizerRefs[].handle|url|name` through the existing `_handle_candidates`/excluded-follow normalization. Run enrichment before `_is_shell_event`, and let exact `userFollowing` matches receive the same shell exception and lower score floor already promised by `_min_score_floor`. Preserve the later category derivation after enrichment.
- **Example title(s) this catches/excludes**: `Garden Rest and Read` exposes `organizerRefs.handle=litclub.nyc`; `Philosophy at the Museum: Ottoman Art vs. Orientalist Fantasy` exposes `organizerRefs.handle=philosophy.nyc`. Both are followed accounts but currently have `userFollowing=false`. Snapshot replay changes 49/645 to 51/645 (7.9%); as of September 8, the Philosophy event is the still-upcoming gain.
- **Risk**: sparse events from genuinely followed organizers can survive the shell gate. This is deliberately bounded to exact normalized follow matches, with excluded accounts removed by `_user_following_normalized`; hard blocks, user exclusions, late-night filtering, and score floors still run.

### P3: Reject explicit non-NYC New York ZIP codes in Partiful

- **Metric moved**: high-conviction event ratio
- **File**: `scrapers/sources/partiful.py:420-438`
- **Change**: after the existing NJ/CT/PA and nearby-city checks, parse an explicit `NY 12345` ZIP. Keep known NYC ZIP families (100xx-104xx, 11004-11005, 111xx-116xx); return `non-nyc` for any other explicit New York ZIP. Preserve events with hidden/no ZIP locations.
- **Example title(s) this catches/excludes**: `Summer Send Off: Labor Day Hike!` (12446), `All Day Margaritas at Montaukila` (11954), `Nine Lives Social Club Presents: The Richie Hart Trio - SEASON FINALE` (10921), and `The Great Jack O'Lantern Blaze` (10520). Tested against all 85 Partiful rows: exactly these four match; all 63 explicit NYC ZIP rows remain.
- **Risk**: excludes destination events outside the five boroughs, which is consistent with the NYC-only product scope. Hidden-location events remain untouched.

### P4: Align the late-night filter window with the audit window

- **Metric moved**: high-conviction event ratio
- **File**: `scrapers/normalize.py:1189-1194`
- **Change**: expand the existing late-night text scan from the first 200 to the first 300 description characters. No new regex or threshold is needed.
- **Example title(s) this catches/excludes**: `oomfRAVE Labor Day Weekend Extravaganza`; its explicit `9pm-4am` marker is at character 247. Tested over all 645 titles/descriptions: 200 characters catches 0; 300 catches exactly this 1; 500 also catches only this 1.
- **Risk**: a deeper description can mention venue trivia, the reason for the original bound. The tested 300-character bound is still narrow and produced zero additional false-positive candidates in the snapshot.

## Directives addressed

- **fb-216**: evidence-based deferral. No new source is recommended because all live probes failed at the network layer, so the required >=5 future-event and >=80% clean/on-taste criteria cannot be certified. P1 removes the ingestion-side zero-yield trap for `/cc/` sources before a connected re-probe.
- **fb-213**: P2 has an immediately measurable snapshot gain (two followed-organizer events correctly become high conviction); P3/P4 remove five demonstrably off-scope rows from the audited snapshot. The orchestrator/Critic must approve and apply before claiming a shipped delta.
- **fb-214**: deferred to the orchestrator after approved changes, scrape, sanity check, build, deployment, and public verification. This runner cannot verify the public host while connectivity is unavailable.

## Open questions for the Critic

- Should `ai` be removed from the *measurement vocabulary* or simply marked non-actionable? It is follow-handle-derived but conflicts with explicit no-AI taste. Do not broaden the hard block without a policy decision; the two live AI titles above need manual classification.
- Should P1 ship before a connected probe because two existing `/cc/` records have strong historical yield, or remain gated with fb-216 until their current inventory is revalidated?
- The Substack `fromat` defect is real, but without the source HTML it is unclear whether spacing alone or event-title segmentation is broken. Capture the feed item as a fixture before patching `heading.get_text(strip=True)`.
- Follow-graph coverage is saturated historically while only four handles are represented in the current snapshot. Should a future metric add a rolling/current-feed coverage window so 100% historical yield cannot mask a present-day conviction collapse?
