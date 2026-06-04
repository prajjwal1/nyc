SOURCE: local site/public/events.json (no scrape ran this round)
FOLLOW_GRAPH_COVERAGE: 12/50 (24.0%)
TOPIC_COVERAGE: {'ny': 99, 'nyc': 68, 'club': 52, 'run': 16, 'book': 79, 'bk': 1, 'brooklyn': 38, 'ai': 80, 'read': 27}
HIGH_CONVICTION_RATIO: 105/347 (30.3%)
TOTAL_EVENTS: 347

NOTE: identical to metrics-before by design - this round shipped CODE only;
the stored events.json was not re-scraped. Expected deltas on next CI scrape:
  follow-graph: +philosophy.nyc (S1+fold), +nycbackgammonclub (P4), +silentbookclub.nyc (P3)
               + reading_rhythms/nyc_forfree register on profile rebuild => ~12/50 -> ~17/50
  high-conviction precision: P1+P2 purge 12 OCR/caption-garbage IG titles from top of feed
  startTime coverage: D1 fills missing times from "doors at 7pm" body text
