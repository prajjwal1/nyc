# Source Pool Report — 2026-05-28-1552

## Probe summary
- Lu.ma topics probed: 11 | recommended: **0** (see Critical Finding below)
- Brooklyn / AllEvents URLs probed: 14 | recommended: **9** (yield ≥ 5)
- URLs promoted from discovered_urls: 0 (the 2 non-individual-event candidates were national / dead)
- Accounts recommended: **2** (the 2 unmissed priority-8 accounts)
- Dead-URL retests: **0** — no dead URL is older than the 7-day threshold (max age = 6 days, retest deferred)

## Critical Finding (read first — affects existing seed list)

All probed Lu.ma category URLs (`lu.ma/nyc/books`, `lu.ma/nyc/ai`, `lu.ma/nyc/brooklyn`, `lu.ma/nyc/run-club`, `lu.ma/nyc/founders`, `lu.ma/nyc/tech`, `lu.ma/nyc/startups`, `lu.ma/nyc/clubs`, `lu.ma/nyc/book-club`, `lu.ma/nyc/reading`) returned the **exact same 20 events** as the bare `https://lu.ma/nyc` discover page. I then spot-checked existing LUMA_PAGES entries (`/nyc/literary`, `/nyc/running`, `/nyc/run-clubs`, `/nyc/social`, `/nyc/dating`) and found **overlap=10/10 of top-10 titles** vs the `/nyc` baseline for every one of them.

Implication: Lu.ma's path-suffix routing is not filtering by topic — every "category" URL serves the same generic NYC discover list. The 60+ LUMA_PAGES entries are scraping the same content over and over. This is a major issue for the Critic/Dreamer phase. **No new Lu.ma topic URLs are worth adding until this is investigated** (likely needs the explicit `?topic=…` query param, or a different endpoint). Not adding speculative Lu.ma URLs satisfies the hard rule "yield ≥ 5 of unique content."

Action: flag for Critic — consider de-duping LUMA_PAGES down to a small handful (`/nyc` + the curator calendars at the bottom of `luma.py:85-90` which DO yield distinct content).

## Proposals

### S1: Add 9 Brooklyn-focused AllEvents + Eventbrite URLs to `GENERIC_URLS`
Directly closes feedback directive #3 (the `bk` topic shortfall): existing GENERIC_URLS contains `/brooklyn/yoga`, `/brooklyn/fitness`, `/brooklyn/books` but is missing the rest of the AllEvents borough taxonomy.

- **Metric moved**: topic coverage (`bk`/`brooklyn`); volume of borough-attributed events.
- **File**: `scrapers/sources/generic.py:17` — append to `GENERIC_URLS` list.
- **Probe results** (live, just now):
  | URL | yield | sample title |
  |---|---:|---|
  | `https://allevents.in/brooklyn/free` | 15 | 15th Annual Bushwick Collective ROOFTOP LAUNCH PARTY |
  | `https://allevents.in/brooklyn/dating` | 15 | Sapphic Speed Dating at Good Judy |
  | `https://allevents.in/brooklyn/comedy` | 8 | Jenny Hagel Gives Advice Book Launch |
  | `https://allevents.in/brooklyn/literature` | 9 | Author Talk: Sara Youngblood Gregory & Dan Kraines |
  | `https://allevents.in/brooklyn/running` | 12 | Bandit Grand Prix |
  | `https://allevents.in/brooklyn/coffee` | 9 | (note: contains some city-wide concert noise; still passes 5+) |
  | `https://allevents.in/brooklyn/poetry` | 14 | RUPI KAUR: UNCUT – A RESIDENCY |
  | `https://www.eventbrite.com/d/ny--brooklyn/parties--events/` | 20 | BROOKLYN CARNIVAL |
  | `https://www.eventbrite.com/d/ny--brooklyn/comedy--events/` | 20 | Girlparty: Sketch Comedy |
- **Risk**: AllEvents is `SOURCE_QUALITY=0.35` aggregator — these will be capped by the existing `SOURCE_VOLUME_CAPS["allevents"]=40` so net feed impact is bounded. Brooklyn-tagged events should help the `bk`/`brooklyn` topic count rise without crowding out high-conviction content.

### S2: Add `silentbookclub.nyc` and `crownheightscraftclub` to `IG_ACCOUNTS`
Two of the 8 named-priority 0-yield accounts from feedback directive #1 are NOT currently in `IG_ACCOUNTS`. Adding them lets the IG scraper actually attempt them (they're currently being polled only via the discovery path, which apparently isn't reaching them).

- **Metric moved**: follow-graph coverage (5 of 8 priority accounts already in list but 0-yield = an ingestion-quality concern, not source-pool; the remaining 2 are an actual gap I can close here).
- **File**: `scrapers/config.py:14` — append to `IG_ACCOUNTS` list.
- **Probe result**: cannot live-probe IG without credentials in this read-only env. Both accounts appear in `signal_accounts` (verified — derived from user's IG following), so the rule "only signal_accounts not yet in IG_ACCOUNTS" applies.
- **Verification of presence**:
  - `silentbookclub.nyc` ✅ in signal_accounts, ❌ not in `IG_ACCOUNTS`
  - `crownheightscraftclub` ✅ in signal_accounts, ❌ not in `IG_ACCOUNTS`
  - Other 6 priority accounts (`vitalrunclub`, `nycbackgammonclub`, `reading_rhythms`, `bookclubbar`, `midnightrunnersnewyork`, `philosophy.nyc`) are ALREADY in `IG_ACCOUNTS` — their 0-yield is an ingestion-quality issue (handled by ingestion-quality agent), not a source-pool issue.
- **Risk**: very low. Both accounts are user-signal. If they're stale/private the IG scraper will silently skip per `config.py:12-13` note.

## Directives addressed
- **fb-101** (close follow-graph 0-yield gap): partially addressed. Adding the 2 missing priority accounts to IG_ACCOUNTS so they can be scraped at all. The 6 already-present priority accounts are 0-yield despite being in the seed list — that's an ingestion-quality problem (likely the IG session/throttle or post recency filter), not a source-pool problem; **deferred to ingestion-quality agent**.
- **fb-102** (raise IG share of feed + surface provenance): **deferred — out of source-pool scope.** This is an ingestion + UI concern (per the directive itself naming "ingestion-quality + ui-agent" as best agents). Source-pool can only help by adding accounts.
- **fb-103** (`bk` topic gap, 4 → ≥ 8): addressed via S1. 9 new Brooklyn-tagged URLs feeding the borough-attributed event stream. Combined with the text-matching work expected from ingestion-quality, the topic count should rise.

## Probes that failed (don't add)
- All `lu.ma/nyc/<topic>` candidate URLs — yield 20 events each but the events are *identical* to `lu.ma/nyc` (no actual category filtering). See Critical Finding.
- `https://lu.ma/brooklyn` — yield 1 (a 2022 event). Dead path.
- `https://allevents.in/brooklyn/music` — yield 5 (just barely passes), but the top 2 results are Ariana Grande arena concerts that match `manhattan/music` and `new-york/music` results. High duplicate risk; **excluded** from S1 to preserve quality.
- `https://allevents.in/brooklyn/parties` — yield 1 (Kwanzaa Crawl only). Below threshold.
- `https://allevents.in/brooklyn/art` — yield 5 (just barely), top results overlap with `brooklyn/free`. Below quality bar.
- `https://allevents.in/brooklyn/business` — yield 15 but content is John Summit + Summercon (not the `bk` interest profile). Off-target; excluded.
- `https://www.eventbrite.com/d/ny--brooklyn/music--events/` — yield 8 (above threshold) but the same Brooklyn Carnival / Stafford Room titles repeat in the already-promoted `…/parties--events` and `…/comedy--events`. Net-new content is < 5. Excluded to avoid dedupe waste.
- `https://allevents.in/events/car-shows-in-usa` — high `events_yielded_total` in `url_health.json` (15361) but it's a US-national feed of car shows. Off-target.
- `https://allevents.in/events/memorial-day-in-the-usa` — 500 Internal Server Error now. Dead.

## Open questions for the Critic
1. **Lu.ma category routing is non-functional** (see Critical Finding). Should LUMA_PAGES be aggressively pruned, or should we investigate the actual Luma category API/endpoint? This is a > 60-URL waste in the current rotation. The 6 curator calendars at the bottom (`luma.com/nycbackgammonclub`, `…/readingrhythms-manhattan`, etc.) DO appear distinct and should be kept.
2. **6 priority IG accounts are already in IG_ACCOUNTS but still 0-yield.** This is a known-gap, but source-pool can't fix it. Likely causes: (a) instaloader session expired / hitting throttle, (b) account posts not matching the date-required filter, (c) account is in IG_SPOTS_ACCOUNTS or otherwise downgraded. Asking ingestion-quality to investigate.
3. **Dead URLs at 6-day age** — directive says retest at > 7 days, so deferred. Next run (within a day) several will cross the threshold; should source-pool retest then, or rely on the auto-prune logic?
4. **Discovered URL promotion was empty** — every high-emit non-seed URL in `url_health.json` is either an individual event page (1 event = 251 "yields" because it succeeded 251 times for 1 event) or off-target (US-national car shows). The promotion rule should probably weight by *per-call yield* not cumulative `events_emitted_total`.
