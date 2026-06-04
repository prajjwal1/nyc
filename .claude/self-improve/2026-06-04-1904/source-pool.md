# Source Pool Report — 2026-06-04 1904

## Probe summary
- Non-IG paths probed for 38 zero-yield signal accounts: **~45 candidate URLs**
  (individual lu.ma curator calendars, run-club / literary / games own-sites,
  Eventbrite venue-search slugs, Brooklyn Botanic / Franklin Park own-sites).
- LUMA_PAGES additions proposed: **1** (`lu.ma/philosophy`).
- GENERIC_URLS additions proposed: **0**.
- IG_ACCOUNTS additions proposed: **0** (IG session stale → user-blocked; directive said do not lean on IG adds).
- Eventbrite venue-search candidates: **5 probed, 0 passed** the fb-155 match-rate gate.
- Dead-URL retests: **5** | resurrected: **0**.

## Proposals

### source-pool-S1: Add `https://lu.ma/philosophy` to LUMA_PAGES
- **Source / scraper**: lu.ma individual-host curator calendar → handled by `scrapers/sources/luma.py` (`LUMA_PAGES` list). NOT a `/nyc/<topic>` page, so it is NOT a duplicate of the `/nyc` discover feed (fb-104/105 concern does not apply).
- **Covers signal_account**: `philosophy.nyc` (currently `yield_map` = 0.0).
- **Live-probe yield** (probed 3x, stable): **7 events, all 7 future** (>= 2026-06-04), all verified NYC:
  - "Philosophy at the Museum: Rococo" — 2026-06-06 — The Metropolitan Museum of Art (manhattan)
  - "The New York Philosophy Club: Williamsburg" — 2026-06-10 — McCarren Parkhouse (williamsburg)
  - "Philosophy Club x Sugar Mouse" — 2026-06-10 — Sugar Mouse NYC (manhattan)
  - "Philosophy at the Museum: Unicorns, the Met Cloisters..." — 2026-06-14 — The Met Cloisters
  - "The New York Philosophy Club: Columbus Circle" — 2026-06-24 / 2026-07-01 — NY Society for Ethical Culture
- **Not currently in feed**: 0 philosophy-title events in the deployed 347-event feed. `lu.ma/philosophy` is NOT in `discovered_urls.json`. Genuine net-new content.
- **File**: `scrapers/sources/luma.py` — append to the "Curator calendars (verified live)" block (after line 90, alongside the existing `litclub.nyc`, `readingrhythms-manhattan`, `thinkolio` curator calendars).
- **Exclusion check (fb-153)**: PASS. Not in `user_excluded_sources.json` `accounts`/`hosts`; no `title_hints` match (no rave/club/AI/speed-dating). Content is intellectual/social meet-people events — squarely on the user's vector (philosophy.nyc is a followed signal account; matches `social` topic + the user's "meet people without drinking" goal).
- **Topic vector**: serves the `social` topic and the literary/intellectual cluster; covers a zero-yield signal account → moves **follow-graph coverage** (12/50 → 13/50) if luma-handle provenance enrichment fires (`philosophy` slug ↔ `philosophy.nyc` account — flag for ingestion-quality, see open questions). Even absent attribution, it is high-conviction topical content.
- **SOURCE_VOLUME_CAPS implication**: NONE NEEDED. Source label is `luma` (SOURCE_QUALITY 0.9); +7 events on a 347-event feed. The `luma` source has no volume cap and this is a tiny low-volume curator calendar — no risk of crowding. Do not add a cap.
- **Risk**: low — additive, low-volume, verified-live, on-vector.

## Directives addressed
- **fb-155 (Eventbrite venue-search match-rate gate)**: Honored. Probed 5 unique multi-word slugs and reported real location.name match rates (see "Probes that failed"). All 5 failed the gate; none proposed. No single-word/generic slugs probed.
- **fb-153 (exclusion check before any add)**: Performed for S1 — PASS.
- **fb-106 (no individual-person / publisher / private IG accounts)**: Honored — 0 IG_ACCOUNTS adds proposed this round.
- **fb-105 (lu.ma curator probing already returned 0 net-new)**: Note — `probe_luma_curators.py` apparently did not test the individual-host slug `lu.ma/philosophy`; this run found it by direct slug probing. It is genuinely net-new (not in LUMA_PAGES, not in discovered_urls, 0 in feed).
- **fb-104 (prune redundant /nyc/<topic>)**: Not actioned — additive-only, user-blocked. Unchanged.

## Probes that failed (don't add)

### Eventbrite venue-search slugs — all fail the fb-155 location.name match-rate gate (each would inject ~20 noise events):
- `/d/ny--brooklyn/franklin-park/` — 20 events, **~0/3 at Franklin Park** (FRANKLINS MAKERS, Prospect Park, Maria Hernandez Park). Keyword match on "park". REJECT.
- `/d/ny--brooklyn/brooklyn-botanic-garden/` — 20 events, **~1/3 at BBG** (one Brooklyn Botanic Ballroom; rest Cranford Rose Garden, Brooklyn Bridge Park Pier 6). Low match. REJECT.
- `/d/ny--new-york/reading-rhythms/` — 20 events, **0/3 Reading Rhythms-branded** (generic "Quiet Reading Night", "Accra Literacy", "Candlelit Silent Reading"). Keyword match on "reading". REJECT.
- `/d/ny--new-york/nyc-backgammon-club/` — 20 events, **0/3 at the backgammon club** (R&B event, social club night, Prospect Park). Keyword match on "club/social/NYC". REJECT.
- `/d/ny--new-york/philosophy-club/` — 20 events, **0/3 philosophy** (wine club, rooftop party, Explorers Club). Keyword match on "club". REJECT.

### lu.ma individual-host slugs — 404 / 0 events (account does not use that slug or has no public lu.ma):
- run clubs: `vitalrunclub`, `nycsprintcollective`, `midnightrunners`, `northbrooklynrunners`, `secondsrunclub`, `zoomiesrunclub`, `queerfeet(nyc)`, `wnrr`
- literary: `quietreading`, `quietreadingclub`, `openbookclub`, `open-bookclub`, `reading-rhythms`, `readingrhythms`, `silentbookclubnyc`, `silentbook`, `reading.rhythms`, `readingrhythms-brooklyn/-bk/-nyc`, `rrglobal`, `readingrhythmsglobal`
- games/craft: `richardsgames`, `rummikubers`, `thenewyorkgames`, `nyc-games`, `newyorkgames`, `crownheightscraftclub`
- social/wellness: `yogaspace`, `fortheplot`, `strangersorfriends`, `nyphilosophy`, `nyc-backgammon` variants

### Own-site event feeds — 0 events via generic.py (no JSON-LD/iCal/OG events exposed):
- `vitalrunclub.com(/events)`, `nycsprintcollective.com`, `secondsrunclub.com`, `wnrr.nyc`, `queerfeetnyc.com`
- `silentbookclub.com/nyc`, `quietreading.club`, `openbookclub.nyc`, `thenewyorkgames.com`, `richardsgames.nyc`, `crownheightscraftclub.com`
- `franklinparkbrooklyn.com(/events)` (503), `wordbookstores.com/event(s)`, `fortheplot.nyc`, `anaiswine.com/events`
- `bbg.org/calendar`, `/events`, `/learn/calendar`, `/visit/event` (Brooklyn Botanic — JS-rendered calendar, no server-side events)

### Dead-URL retests (>7 days dead, signal-relevant) — all still 0, no resurrection:
- `northbrooklynrunners.org/events`, `brooklyntrack.club/events`, `greenpointcomedyclub.com/events` (own-sites genuinely dead)
- `mcnallyjackson.com/events`, `caveat.nyc/events` (0 via host, but both already covered by dedicated scrapers — no action)

## Honest assessment
The directive's hypothesis holds: **the overwhelming majority of the 38 zero-yield
signal accounts have no scrapeable non-IG path.** Run clubs (vitalrunclub,
nycsprintcollective, secondsrunclub, zoomiesrunclub, wnrr, midnightrunners,
northbrooklynrunners) live on IG + Strava/RunSignup with no public JSON-LD feed.
Literary/games/craft micro-clubs (quietreading, open.bookclub, silentbookclub.nyc,
richardsgamesnyc, rummikubers, crownheightscraftclub, thenewyorkgames) are
IG-only. These are genuinely **IG-session-blocked** — a clean user-blocked
deferral, not a curation gap. The single exception found is `philosophy.nyc`,
which runs a public lu.ma curator calendar (`lu.ma/philosophy`, 7 live NYC
events) → that is the one proposal.

This is consistent with fb-105 (probe_luma_curators returned 0 net-new for the
*curated-list* path) — the one slug it missed was the bare `philosophy` host slug,
which direct probing surfaced this round.

## Open questions for the Critic
1. **Provenance attribution for S1**: the lu.ma slug is `philosophy` but the signal
   account is `philosophy.nyc`. For S1 to actually move follow-graph coverage
   (not just topic content), `normalize.py::_enrich_provenance_from_url` needs to
   fold the lu.ma handle `philosophy` → `philosophy.nyc`. Recommend handing this
   alias to **ingestion-quality** (it owns the enrichment path per feedback.md
   directive #2). Without it, S1 still adds 7 on-vector events but won't flip the
   yield_map entry. The add is worth it either way; the alias is the multiplier.
2. **Net metrics impact is modest by design**: 1 net-new source, +7 events. The
   real lever for the 38 zero-yield accounts is the stale IG session (user-blocked)
   and enrichment of existing non-IG events (ingestion-quality's directive #2),
   not new source discovery. I found no responsible way to pad this with
   speculative or low-match-rate adds.
