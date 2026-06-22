# Source Pool Report — 2026-06-22 1501

Theme this round: FITNESS / RUN CLUBS / DANCE (user-explicit fb-179, fb-180).
Read-only. All proposals are additive. Every URL below was live-probed; yield ≥ 5 required.

## Probe summary
- Lu.ma topics probed: 0 net-new (no run/dance lu.ma category not already covered cleared a parseable path)
- Eventbrite category slugs probed (fitness/run/dance): 14
- URLs proposed (≥5 live future-dated yield, exclusion-clean, not in GENERIC_URLS): 6
- URLs promoted from url_health: 0 (none non-seed with successes≥3 AND events_yielded≥5)
- IG accounts promoted: 0 (see "Why no IG adds")
- Dead-URL / dead-account retests: dead_accounts contains only person-shaped IG handles (IG re-probe blocked per fb-174); url_health run/fitness own-site paths re-probed and still 0/503 (see failures)

## Key finding
The deployed feed's existing fitness coverage is largely **inert**. In `url_health.json`:
- `allevents.in/new-york/{running,yoga,fitness}` and `/brooklyn/{yoga,fitness}`: 550+ successes, **0 events_yielded** each.
- `eventbrite.com/d/.../running--events/`, `/yoga--events/`, `/fitness--events/`, `/dance--events/`, `/sports-and-fitness--events/`: all **0 events_yielded** despite many successes.
- `newyorkroad.com/events`, `northbrooklynrunners.org/events`: 9 failures / 0 success (dead paths).

So the broad "running"/"fitness"/"dance" category slugs the config already carries do NOT parse to events. The fix is **more specific slugs that actually return JSON-LD event lists** — which is what cleared the bar below. This directly serves fb-179 (recurring run clubs surface) and fb-180 (Brooklyn Contra / social dance) by adding paths that produce events where the existing ones produce zero.

## Proposals

### S1: Add `https://www.eventbrite.com/d/ny--new-york/run-club--events/` to GENERIC_URLS
- **Metric moved**: topic coverage (`run`=5) + high-conviction (recurring run clubs the user follows surface here)
- **Probe result**: 20/20 future-dated events. Samples: "Meatpacking run club", "commUNITY Run Club", "Sunday Morning Run Club: lululemon x Cen…"
- **Parse path**: Eventbrite JSON-LD (`_domain_source` → `eventbrite`, capped at SOURCE_VOLUME_CAPS["eventbrite"]=100)
- **Exclusion check**: 0 title_hint hits; no account/host in user_excluded_sources.json
- **Why this and not the existing `running--events/`**: the existing `running--events/` slug yields 0 in url_health; `run-club` is a distinct slug that returns real run-club listings (recurring weekly runs → detect_recurring_weekday → expand_recurring_event).
- **File**: `scrapers/sources/generic.py` — append to GENERIC_URLS
- **Risk**: low — additive; Eventbrite parse path already proven; volume-capped

### S2: Add `https://www.eventbrite.com/d/ny--new-york/contra-dance--events/` to GENERIC_URLS
- **Metric moved**: topic coverage (dance) + directly serves fb-180 (Brooklyn Contra / social dance)
- **Probe result**: 20/20 future-dated. Samples: "SWING and SET Double English and Contra Dance", "Fall Fling Double Dance", "Haitian Dance (Folklore)"
- **Parse path**: Eventbrite JSON-LD
- **Exclusion check**: 0 title_hint hits; clean
- **File**: `scrapers/sources/generic.py` — append to GENERIC_URLS
- **Risk**: low — additive. Complements the dedicated `brooklyncontra` scraper (own-site) with a broader contra/social-dance net; the contra scraper covers brooklyncontra.org specifically, this surfaces other NYC contra/English-country dances.

### S3: Add `https://www.eventbrite.com/d/ny--new-york/swing-dance--events/` to GENERIC_URLS
- **Metric moved**: topic coverage (dance) — social partner dance, fb-180-adjacent
- **Probe result**: 20/20 future-dated. Samples: "Swing Dance Lessons", "Nola Swing with Konstantin & The Konstellation", "Jam session with Kings County Swing"
- **Parse path**: Eventbrite JSON-LD
- **Exclusion check**: 0 title_hint hits; clean
- **File**: `scrapers/sources/generic.py` — append to GENERIC_URLS
- **Risk**: low — additive

### S4: Add `https://www.eventbrite.com/d/ny--new-york/folk-dance--events/` to GENERIC_URLS
- **Metric moved**: topic coverage (dance) — social/folk dance, fb-180-adjacent
- **Probe result**: 20/20 future-dated. Samples: "No Lights No Lycra NYC - Dance Session", "Ayazamana: Traditional Music & Dances from Ecuador", "ĀVARTAN Presents- GHAR/BA: Pride Edition"
- **Parse path**: Eventbrite JSON-LD
- **Exclusion check**: 0 title_hint hits; clean
- **File**: `scrapers/sources/generic.py` — append to GENERIC_URLS
- **Risk**: low — additive

### S5: Add `https://www.eventbrite.com/d/ny--new-york/salsa--events/` to GENERIC_URLS
- **Metric moved**: topic coverage (dance) — social partner dance, high meet-people fit
- **Probe result**: 20/20 future-dated. Samples: "Salsa Mundial", "Intro to Cuban Salsa Dancing (SATURDAYS)", "Beginner Salsa Classes Shines - Cucala…"
- **Parse path**: Eventbrite JSON-LD
- **Exclusion check**: 0 title_hint hits; clean
- **File**: `scrapers/sources/generic.py` — append to GENERIC_URLS
- **Risk**: low — additive

### S6: Add `https://www.eventbrite.com/d/ny--new-york/pilates--events/` to GENERIC_URLS
- **Metric moved**: topic coverage (fitness/wellness) — fb-179 "more fitness-based events"
- **Probe result**: 20/20 future-dated. Samples: "Pilates & Pops", "Sunset Pilates in the Park", "Sunrise Pilates Sculpt", "Pilates on the Lawn at The Battery"
- **Parse path**: Eventbrite JSON-LD
- **Exclusion check**: 0 title_hint hits; clean
- **File**: `scrapers/sources/generic.py` — append to GENERIC_URLS
- **Risk**: low — additive. Many of these are outdoor/park social fitness — high alignment with the user's outdoor + meet-people vector.

(Brooklyn variants `contra-dance`/`swing-dance` also yield 20 each but largely overlap the NY-borough results — defer to Ingestion/Critic whether to add the `--brooklyn/` duplicates; I propose the NY-scoped ones which already include Brooklyn venues.)

## Why no IG adds this round
- The +10 IG seeds added this session (harlemrun, frontrunnersnewyork, we_run_uptown, orchardstreetrunners, prospectparktrackclub, endorphinsrun, runclubnyc, thebridgerunners, thenovemberproject, chelseapiersfitness) **all pass fb-106**: every one is an org / club / venue / collective; none matches the `firstname_lastname` / `firstname<number>` personal-account shapes; none is in user_excluded_sources.json. No flags. (See "Directives addressed → fb-179 guardrail".)
- BFS for net-new fitness/dance IG accounts surfaced candidates with score ≥ 0.45 (outopia.run 0.70, eastriverpilates 0.70, danceparadenyc 0.70, barcontranyc 0.70, residentrunners 0.50, danceherenownyc 0.50) BUT **none is `mentioned_by` a signal account** (BFS criterion fails) and the discovery data is stale (last discovery 2026-05-13). Per fb-174 the IG GraphQL sweep is blocked fleet-wide so I cannot live-probe these handles for yield. Per the round's hard rule I do NOT propose them speculatively — flagged for human review below instead. These would be the natural first IG adds if/when the IG session is refreshed and they can be probed.

## Directives addressed
- **fb-179 (fitness / run clubs)**: ADDRESSED (source-pool scope). (1) Confirmed all +10 IG seeds pass fb-106 — no person handles, no excluded accounts; safe to commit. (2) Found that the existing broad fitness/running category URLs yield **0** events in url_health — and proposed S1 (`run-club--events/`, real recurring-run-club listings) + S6 (`pilates--events/`) which clear 20/20 future yield where the old slugs produced nothing. This is the additive fix that actually raises fitness/run event count next scrape.
- **fb-180 (Brooklyn Contra / social dance)**: ADDRESSED (source-pool scope). Dedicated `brooklyncontra` scraper already added this session covers brooklyncontra.org. Proposed S2–S5 (contra / swing / folk / salsa Eventbrite searches, 20 ea.) to broaden the social-dance net beyond the single venue. Note for Ingestion: ensure the contra scraper's dances survive the DISTINCT_SCHEDULE_SOURCES recurring-merge exemption (load-bearing per feedback.md) — not source-pool scope to verify.
- **fb-181 (`'rave'` substring exclusion → word-boundary)**: DEFER to Ingestion. This is a quality/exclusion-filter fix in `quality.py` / `ranking.py`, not source-pool scope. NOTE: I confirmed the relevance — none of my 6 proposed dance/fitness URLs currently surface a title containing "rave" (0 hits), so my adds don't depend on the fix, but the fix is still needed to recover the dropped Oct-4 contra dance per feedback.md. Recommend Ingestion anchors to `\brave\b`.

## Probes that failed (don't add)
- `https://www.nyrr.org/run/race-calendar` and `/events`: 0 events (JS SPA, no JSON-LD / __NEXT_DATA__ parseable via generic)
- `https://www.brooklyntrack.club/events`: 503 Service Unavailable
- `https://www.northbrooklynrunners.org` + `/events` + `/runs` + `/nbr-schedule`: 0 / 404 (own-site paths dead; already 9 failures in url_health)
- `https://www.dancemanhattan.com/calendar`: SSL cert verify failed (self-signed)
- `https://www.youswing.org/events`, `https://www.bigapplecontra.org`: 503
- `https://cdny.org/dances/`: 404
- `https://www.meetup.com/nyc-contra-dance/events/`: 0 (Meetup group event pages don't parse via generic)
- `eventbrite.com/d/ny--new-york/bouldering--events/`: 20 raw but noisy — networking/festival events bleed in, only ~19 non-Jersey and few climbing-specific. Below quality bar; dropped.
- Existing `allevents.in/.../{running,yoga,fitness}` + `eventbrite .../{running,yoga,fitness,dance,sports-and-fitness}--events/`: re-confirmed 0 events_yielded in url_health (kept, never removed; just noting they're inert).

## Open questions for the Critic
1. Should the Brooklyn-scoped duplicates (`/ny--brooklyn/contra-dance--events/`, `/swing-dance--events/`) be added too? They yield 20 each but heavily overlap the NY-scoped S2/S3. I proposed only the NY-scoped versions to avoid feed-dup churn.
2. The 6 inert existing fitness/running category URLs (0 yield, 500+ successes) are wasting fetches every scrape. Hard rule = never remove. Flagging for human review whether they should be retired in a future round — NOT proposing removal here.
3. IG BFS candidates (outopia.run, eastriverpilates, danceparadenyc, barcontranyc, residentrunners, danceherenownyc) are on-vector and fb-106-clean by name, but unprobeable while the IG sweep is blocked (fb-174). Worth queuing for the next round if the IG session is refreshed.
