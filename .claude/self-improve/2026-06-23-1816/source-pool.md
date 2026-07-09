# Source Pool Report — 2026-06-23 1816

## Probe summary
- Lu.ma topics probed: 3 (pickleball/tennis/board-games) | added: 0 (all fell back to generic NYC discover feed — redundant + off-vector founder/AI events)
- Eventbrite slugs probed: 9 | proposed: 4 (hiking, board-games, walking-tour, chess)
- Eventbrite slugs probed but held: 2 (trivia, climbing — clear ≥5 but deferred to stay conservative/non-redundant per directive)
- URLs promoted from discovered_urls: 0 (no entry both ≥3 successes AND not already in config that wasn't already seeded)
- Accounts promoted: 0 (IG sweep blocked — fb-174; no probe-able candidate)
- Dead-URL retests: 0 actionable

## Key finding (corrects fb-184 premise)
fb-184 asserts "6 inert legacy Eventbrite fitness/dance slugs, 0-yield despite 500+ fetches."
`url_health.json` (snapshot after the 18:20 scrape that DID land last round's slugs) contradicts this:
- `running--events/` (NY) 80 emitted_total / 20 last; (BK) 180 / 20 last
- `yoga--events/` (NY) 140 / 20; (BK) 120 / 20 (5 fail)
- `fitness--events/` 140 / 20 last
- `dance--events/` 440 / 20 last
- `sports-and-fitness--events/` (NY) 192 / 8 last; (BK) 184 / 8 last
These slugs ARE yielding. The new narrow slugs also landed: `run-club--events/` and `contra-dance--events/` = 20 each, 1 success (this scrape). swing-dance/folk-dance/salsa/pilates have NO health record yet (the 18:20 scrape was partial). So there is no "6 inert slug" parse failure visible in the data — the ingestion-side investigation should confirm against fresher health data; this curator found no inert-slug evidence to compensate for. I focused instead on NEW non-redundant on-vector sources.

## Directive 2: folk-dance slug participatory-vs-performance assessment
Live probe `eventbrite.com/d/ny--new-york/folk-dance--events/` -> 20 events. Sample:
- "Ayazamana: Traditional Music & Dances from Ecuador" (PERFORMANCE)
- "No Lights No Lycra NYC - Dance Session" (PARTICIPATORY)
- "Unsung Heroes...Village Folk Scene" (TALK/PERFORMANCE)
- "POP-UP DANCE!" (PARTICIPATORY)
- "LET'S DANCE (BOWIE DANCE PARTY)" (PARTY, off-folk)
- "Dark Tease: Sexy Goth & Alt Dance Class" (PARTICIPATORY class)
- "The Witch's Dance - Ritual Movement Workshop" (PARTICIPATORY)
Ratio ~ 4-5/8 participatory; the rest are performances/parties/talks mis-bucketed under "folk-dance".
**Recommendation: KEEP but do not expand.** It is not majority-noise (clears the participatory bar at ~55%) and is additive-only, but it is the weakest of the dance slugs. If next round's ranking shows its events under-engaging, retire it — but do not remove this round (additive-only rule + it does surface real participatory dance the user-vector wants). No action needed from me; flagging for the Critic.

## Proposals

### S1: Add `https://www.eventbrite.com/d/ny--new-york/hiking--events/` to GENERIC_URLS
- **Metric moved**: topic coverage (outdoors vector — currently thin in feed)
- **Probe result**: 20 events. Samples: "Sunday Hike: Breakneck Ridge" (2026-06-28), "Saturday Hike: Stairway to Heaven [Transportation Included]" (2026-06-27), "New Paltz Hike, Winery & Farm Stand" (2026-06-27)
- **Parse path**: generic.py JSON-LD (Eventbrite `/d/` search). Same parser the verified run-club slug uses.
- **Participatory-vs-performance**: ~20/20 participatory group hikes / outdoor meetups. Clean — no performances.
- **Exclusion check**: not in accounts; hosts empty; no title_hints match. Clean.
- **File**: `scrapers/config.py` is NOT where these live — `scrapers/sources/generic.py` GENERIC_URLS list (append near the run-club block ~line 233). Volume-capped by `eventbrite=100`.
- **Risk**: low — additive, not redundant (no hiking slug present).

### S2: Add `https://www.eventbrite.com/d/ny--new-york/walking-tour--events/` to GENERIC_URLS
- **Metric moved**: topic coverage (exploration vector — user's confirmed "discover the city" interest, boost 1.25)
- **Probe result**: 20 events. Samples: "Gay History Walking Tour of the West Village - GAY PRIDE WEEKEND" (2026-06-27), "Battle of Brooklyn Walking Tour" (2026-07-03), "Brooklyn Scavenger Hunt Walking Tour & Game" (2026-06-24)
- **Parse path**: generic.py Eventbrite JSON-LD.
- **Participatory-vs-performance**: ~20/20 participatory guided walks/tours. Clean.
- **Exclusion check**: clean (no accounts/hosts/title_hints match).
- **File**: `scrapers/sources/generic.py` GENERIC_URLS (~line 233).
- **Risk**: low — additive, non-redundant.

### S3: Add `https://www.eventbrite.com/d/ny--new-york/board-games--events/` to GENERIC_URLS
- **Metric moved**: topic coverage (games vector — user follows backgammon/games clubs; boost 1.3)
- **Probe result**: 19 events. Samples: "Board Game Night at Hive Mind Books" (2026-07-11), "Board Game Wednesdays" (2026-06-24), "Board Game Speed Dating - Threes Brewing Greenpoint (Ages 25-39)" (2026-08-05)
- **Parse path**: generic.py Eventbrite JSON-LD.
- **Participatory-vs-performance**: ~19/19 participatory game nights. Note: a few "Board Game Speed Dating" titles appear — these are auto-handled by the existing `speed dating`/`speed-dating` title_hints exclusion penalty at rank time (NOT a reason to drop the slug; the non-speed-dating majority is clean).
- **Exclusion check**: slug clean; the speed-dating sub-events are already penalized by ranking.py via title_hints.
- **File**: `scrapers/sources/generic.py` GENERIC_URLS (~line 233).
- **Risk**: low — additive, non-redundant.

### S4: Add `https://www.eventbrite.com/d/ny--new-york/chess--events/` to GENERIC_URLS
- **Metric moved**: topic coverage (games vector; meet-people via recurring community chess clubs — exactly the social-fitness-style recurring format the user wants)
- **Probe result**: 20 events. Samples: "North Brooklyn Chess at McCarren Parkhouse" (2026-06-25), "Bushwick Chess Club Night" (2026-06-23), "Chess Club with Bad BishopBK" (2026-07-02)
- **Parse path**: generic.py Eventbrite JSON-LD.
- **Participatory-vs-performance**: ~20/20 participatory community chess clubs (mostly recurring weekly — high meet-people value). Clean.
- **Exclusion check**: clean.
- **File**: `scrapers/sources/generic.py` GENERIC_URLS (~line 233).
- **Risk**: low — additive, non-redundant.

## Probed and HELD (clear >=5 but deferred for conservatism — Critic may promote)
- `eventbrite.com/d/ny--new-york/trivia--events/` -> 20, participatory ("Pokemon Trivia", "Taylor Swift Trivia", "Twilight Trivia: New Moon"). On-vector (games/social). HELD only to keep the add-count conservative and avoid eventbrite-cap dilution; safe to add if Critic wants more games coverage.
- `eventbrite.com/d/ny--new-york/climbing--events/` -> 20, strongly participatory community climbs ("Climb & Connect Night", "CRUX Trans/Nonbinary Climbing", "Latino Outdoors NYC PRIDE Climb"). On-vector (outdoors/fitness, meet-people). HELD for the same conservatism reason; safe to add.

## Probes that failed / not added
- `lu.ma/nyc/pickleball`, `lu.ma/nyc/tennis`, `lu.ma/nyc/board-games`: each returned 20 events but ALL identical to the generic `lu.ma/nyc` discover feed (tech/founder/comedy events — e.g. "Replit x J.P.Morgan Finance Hack Lab"). These category slugs do not exist on Lu.ma; they silently fall back to the discover page. Adding them = pure redundancy + would inject AI/founder events the user excludes. DO NOT ADD.

## Directives addressed
- fb-184 (source angle): Investigated. Found the "6 inert legacy slugs" premise is NOT supported by current url_health (running/yoga/fitness/dance/sports-and-fitness all show 80-440 emitted_total). No inert-slug yield to compensate for. Compensated for the directive's INTENT (more fitness/run/dance/outdoors/games) with 4 new live-verified ≥19-yield participatory slugs (S1-S4) + 2 held candidates. Ingestion should re-confirm against fresher health data.
- Directive 2 (folk-dance): assessed live, ~55% participatory, KEEP-but-watch recommendation (additive-only forbids removal this round).
- Directive 3 (other on-vector): S1-S4 cover outdoors/exploration/games; all clear ≥19 live yield via the verified generic.py JSON-LD path.

## Open questions for the Critic
- Should trivia + climbing (the 2 HELD candidates) be promoted now? Both clear 20 live, both clean — I held them only to respect the "conservative / non-redundant" directive and the eventbrite=100 cap. Net effect of adding 4 vs 6 slugs is marginal given the cap; Critic's call.
- fb-184 should be re-scoped or closed: its core claim (6 inert slugs) is not visible in url_health post-18:20-scrape. Recommend ingestion verify against a fresh scrape before spending effort on a parse fix that may not be needed.
