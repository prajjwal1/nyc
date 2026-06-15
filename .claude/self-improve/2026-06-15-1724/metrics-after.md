SOURCE: local (post-scrape, after D1 + P1 + P2) | total: 365

FOLLOW_GRAPH_COVERAGE: 15/50 (30.0%)
TOPIC_COVERAGE: {'ny': 88, 'nyc': 54, 'club': 74, 'run': 26, 'bk': 42, 'book': 117, 'brooklyn': 42, 'ai': 76, 'read': 43}
ZERO_TOPICS: []
HIGH_CONVICTION_RATIO: 64/365 (17.5%)

DELTAS vs metrics-before:
- Follow-graph coverage: 24.0% (12/50) -> 30.0% (15/50)  [D1 credited reading_rhythms + silentbookclub.nyc + others via non-IG enriched events; independent of the blocked IG sweep]
- Topic coverage: bk 0 -> 42 (no zero topics remaining)  [P1 bk<->brooklyn fold in the metric script — measurement fix]
- High-conviction ratio: 18.3% -> 17.5%  [stable; the prior quality cleanup's 30->18 drop is intentionally preserved, not relaxed; P2 dropped 3 more garbage stories]

NOTE: philosophy.nyc + nycbackgammonclub remain yield 0 — no userFollowing events in the current feed (no upcoming lu.ma events for them right now), so nothing to credit. Correct, not a fold gap.
