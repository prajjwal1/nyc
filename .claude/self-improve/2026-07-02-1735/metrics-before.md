# Metrics — before (run 2026-07-02-1735)

Feed: `site/public/events.json`, 365 events, lastUpdated **2026-06-15** (live fetch unavailable in sandbox). **Identical to runs 2026-06-22-1501 and 2026-06-23-1816** — no CI scrape has landed in ~17 days.

- **Follow-graph coverage:** 15/50 (30.0%)
- **Topic coverage:** all ≥1 — ny 88, nyc 54, club 74, run 26, bk 42, book 117, brooklyn 42, ai 76, read 43. No zero topics.
- **High-conviction ratio:** 64/365 (17.5%)

## ⚠ STALE-FEED GATE — 3rd consecutive code-only round
Committed-but-unlanded levers now span FOUR rounds: Meetup fitness searches, +12 Eventbrite fitness/dance/games slugs, +12 IG seeds (run-clubs, openbookclub), brooklyncontra scraper, fitness score-recovery boost, the lu.ma/philosophy shell+floor fix, and the UI day-scent/location/hero changes. **None are observable until a scrape regenerates events.json.** Per the D1 dream (run 2026-06-23), scrape-dependent work is gated: this round focuses on **scrape-INDEPENDENT, test/build-verifiable** fixes only, and defers anything whose payoff can only be measured post-scrape.

## Known scrape-independent code/data bug (candidate this round)
- **Neighborhood/name conflict** (surfaced by ui-agent, run 2026-07-02): ~8/375 events have a `location.neighborhood` that contradicts the venue name (e.g. name "Bushwick, 380 Troutman Street" but neighborhood "east village"). Normalizer data bug — fixable + unit-testable without a scrape.

Binding constraints (user/infra): fb-174 (IG sweep blocked), fb-173 (CI IP blocked), fb-139 (Reddit OAuth). A scrape must be run on a residential IP.
