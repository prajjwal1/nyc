# Metrics — before (run 2026-06-23-1816)

Feed source: `site/public/events.json` (live deployed fetch unavailable in sandbox). 365 events. **Identical to run 2026-06-22-1501** — events.json has NOT been re-scraped since (no CI scrape ran between rounds), so last round's fitness/run-club/contra code changes are not yet reflected in the feed.

- **Follow-graph coverage:** 15/50 (30.0%)
- **Topic coverage:** all topics ≥1 — ny 88, nyc 54, club 74, run 26, bk 42, book 117, brooklyn 42, ai 76, read 43. No zero topics.
- **High-conviction ratio:** 64/365 (17.5%)
- **Fitness/wellness/dance events:** 29

Source distribution: eventbrite 100, mcnallyjackson 30, partiful 30, meetup 28, luma 24, nycforfree 20, allevents 18, bookclubbar 17, songkick 16, newyorkcomedyclub 15, lizsbookbar 11, brooklyncomedy 11.

## Standing context
- This is the SECOND consecutive code-only round with no intervening scrape — last round's levers (Meetup +4 fitness searches, +6 Eventbrite slugs, +10 IG seeds, brooklyncontra, fitness boost) are committed but unlanded. Deltas land on the next CI scrape.
- Open silent-failure flag from last round: 6 legacy Eventbrite fitness/dance slugs (running/yoga/fitness/dance/sports-and-fitness) yield 0 despite 500+ fetches — candidate for ingestion investigation (could recover yield cheaply).
- Binding constraints (user-blocked): fb-174 (IG GraphQL sweep blocked), fb-173 (CI runner IP 403/429), fb-139 (Reddit OAuth).
