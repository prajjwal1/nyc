# Source Pool Report — 2026-07-02 1735 (VALIDATION-ONLY)

STALE-FEED gate active: 3rd consecutive code-only round, feed frozen since 2026-06-15.
**No new source-add proposals this round.** This is a validation pass only.

## Probe summary
- Lu.ma topics probed: 0 (moratorium)
- URLs promoted: 0 (moratorium)
- Accounts promoted: 0 (moratorium)
- fb-106 / exclusion sanity-checks on recent IG seeds: 12 handles swept
- Live re-probe: 1 provisional slug (folk-dance)

## V1: fb-106 + exclusion sanity-check on recently-added IG seeds (no network)

Checked against user_excluded_sources.json `accounts` (houseofyesnyc, knockdowncenter,
leahcanel, alvinzx, j_palmer_7, sophiareed5) and against the fb-106 personal-account
heuristic (firstname_lastname / firstname<digits> = person → drop).

All 12 seeds confirmed present in config.py (lines 102-112, 191, 211-212).

| Handle | In config | Excluded-list hit | Personal-account (fb-106) | Verdict |
|---|---|---|---|---|
| harlemrun | yes | no | no — run org/brand | CLEAN |
| frontrunnersnewyork | yes | no | no — run club | CLEAN |
| we_run_uptown | yes | no | no — "we_run" collective | CLEAN |
| orchardstreetrunners | yes | no | no — run club (venue token) | CLEAN |
| prospectparktrackclub | yes | no | no — track club (park token) | CLEAN |
| endorphinsrun | yes | no | no — run brand | CLEAN |
| runclubnyc | yes | no | no — run club (nyc token) | CLEAN |
| thebridgerunners | yes | no | no — run crew | CLEAN |
| thenovemberproject | yes | no | no — fitness org/movement | CLEAN |
| chelseapiersfitness | yes | no | no — fitness venue | CLEAN |
| openbookclub | yes | no | no — book club org | CLEAN |
| open.bookclub | yes | no | no — book club org (dotted) | CLEAN |

Result: **all 12 clean** — no fb-106 personal-account violations, none appear in the
exclusion list. No problems flagged. (Note: cannot probe IG yield — sweep blocked per fb-174.)

## V2: Live re-probe of PROVISIONAL folk-dance slug

URL: https://www.eventbrite.com/d/ny--new-york/folk-dance--events/
Fetch: LIVE, 20 events returned (residential path). First 8 titles:

1. Ayazamana: Traditional Music & Dances from Ecuador — PERFORMANCE (show)
2. No Lights No Lycra NYC - Dance Session (WED AUG 5, 7PM) — PARTICIPATORY (dance session)
3. POP-UP DANCE! — AMBIGUOUS (likely performance/showcase)
4. Another Side of the Village: Deep Cuts That Shaped the Folk Scene — PERFORMANCE (music talk/set)
5. The Witch's Dance - Ritual Movement Workshop (In-Person) — PARTICIPATORY (workshop)
6. Daya Dance — AMBIGUOUS (leans performance)
7. Classical Indian Dance and Contemporary Dance Classes at Modega LIC — PARTICIPATORY (classes)
8. Saturday Night Social Dance — PARTICIPATORY (social dance)

Ratio (first 8): **participatory 4 / performance 3 / ambiguous 1**.
Participatory ~50% (4/8), performance ~38%.

**Verdict: KEEP (provisional → lean-keep).** Slug is live and yields a healthy mix; the
participatory share (social dance, workshops, classes, no-lights-no-lycra) matches the
"events the user would actually attend" North Star better than a pure-performance slug.
Not a prune candidate. Recommend it stay provisional until a scrape validates in-feed
survival + downstream ranking (some performance/ambiguous titles may get filtered).

## V3: Unvalidated-in-feed note (no action)

The following sources added over the last ~3 rounds remain **UNVALIDATED IN FEED** —
committed to config but never exercised by a scrape (feed frozen since 2026-06-15):
- ~12 Eventbrite category slugs (incl. this folk-dance slug + fitness/dance/run slugs)
- Meetup fitness searches
- brooklyncontra

**Recommendation to orchestrator: run a scrape (residential IP per fb-173/fb-174).**
A scrape is the single highest-leverage action — it would validate the entire unlanded
source stack and unfreeze the feed. Until then these sources are theoretical yield only.

## Directives addressed
- Standing STALE-FEED gate: honored — zero new-add proposals; validation-only.
- fb-106: V1 sweep confirms no personal-account violations among recent seeds.
- fb-153 (exclusion check): V1 confirms no seed collides with user_excluded_sources.json.
- fb-174: IG-yield sweep correctly NOT attempted (blocked infra).

## Probes that failed (don't add)
- none — folk-dance slug returned 20 events live.

## Open questions for the Critic
- folk-dance slug carries ~38% performance titles; in-feed ranking will determine whether
  those survive or get down-ranked. Reassess prune/keep after the next scrape lands.
