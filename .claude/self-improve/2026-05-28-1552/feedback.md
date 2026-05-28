# Feedback for run 2026-05-28-1552

## Note on the user-ask gate

This is the first invocation. The 7-day throttle is technically open, but I'm deferring the user-ask for this round because:
1. The metrics baseline alone identifies obvious directives (no need to ask).
2. The first run should demonstrate end-to-end loop mechanics; the calibration ask is best timed once we have a `userFollowing`-tagged event to show.
3. The deferred ask becomes a backlog item: `fb-100 — Run calibration ask next round`.

The next `/self-improve` invocation should ask the user a calibration question grounded in real events from `account ∈ signal_accounts`.

## Top 3 directives (workers MUST address or justify deferral)

### 1. Close the follow-graph 0-yield gap
- backlog item: derived from metrics-before (42/54 signal_accounts at 0-yield)
- best agent: **ingestion-quality**
- "addressed" criterion: at least 5 of the named 0-yield `signal_accounts` move to yield > 0 within ~3 runs. This round, focus on the highest-leverage ones the user has explicitly named in README §480–533:
  - `vitalrunclub` — named run club
  - `silentbookclub.nyc` — implied via book-clubs naming
  - `nycbackgammonclub` — `sanity_check.py` already requires this to surface; the fact it's 0-yield is a regression alarm
  - `reading_rhythms` — `sanity_check.py` requires this; same alarm
  - `bookclubbar` — named bookstore
  - `crownheightscraftclub`, `midnightrunnersnewyork`, `philosophy.nyc` — second-tier

### 2. Raise IG share of feed + surface follow-graph provenance in event records
- backlog item: derived from metrics-before (IG = 21/246 = 8.5% of feed; should be dominant per README §40–45)
- best agent: **ingestion-quality** (raise share) + **ui-agent** (surface provenance)
- "addressed" criterion: events from IG scraper carry an `account` field that the deployed-feed metric can read (currently 0/246 — likely a serialization bug or the field is called something else); high-conviction ratio rises from 3.3% toward 15%+.

### 3. Fix the `bk` topic gap
- backlog item: derived from metrics-before (`bk` interest count = 4 but only 2 events surface; vs `brooklyn` = 3 surfacing 14 events)
- best agent: **source-curator** (look for accounts/URLs that use BK shorthand) + **ingestion-quality** (text-matching for the shorthand on existing events)
- "addressed" criterion: `bk` topic count rises from 2 to ≥ 8 within 2 runs.

## Questions to ask the user this round

None — throttle deferred per above. Logged as a backlog item.

## Backlog mutations applied

- Added `fb-100 — Run calibration ask next round`: open
- Re-ranked: top 3 open items are now the three derived directives above (will become formal `fb-101`/`fb-102`/`fb-103` once written into the backlog)
- Closed (with sha): none yet
