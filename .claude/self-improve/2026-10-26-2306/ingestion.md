# Ingestion audit

Single-agent proposal stage; no implementation applied at this point.

## Metrics observed
- Historical follow yield: 50/50; no zero-yield signal accounts to revive.
- Current-feed canonical follow coverage: 17/50; conviction: 87/764 (11.39%). All four meaningful topics and all six critical checks pass.
- Live feed and pulled snapshot match exactly. No past rows or exact title/date duplicates. Existing warnings: Brooklyn Museum, art openings, Open Book Club.
- Last description pass: 0/24 recovered, 20 restored from cache.

## Proposals

### P1: Use explicit Eventbrite occurrence evidence for descriptions
- Metric: useful decision details; expected at least two more descriptions, no inventory or conviction-count change.
- File: `scrapers/utils/descriptions.py:86`.
- Evidence: Outdoor Yoga (1986163951846) lists original April 2 in JSON-LD but `nextAvailableSession=2026-10-29T11:00:00-04`; Brooklyn Book Club (1996345114979) lists original August 7 but `nextAvailableSession=2026-10-30T18:00:00-04`.
- Change: preserve exact-date matching, with a narrowly validated fallback for those explicit series occurrences. Require stable ID, series identity, published/public status, timezone-aware date and matching time when present. Use only that same event's parsed description; change no dates, URLs, organizer fields, or budgets.
- Risk: accidentally transferring series prose to a rescheduled occurrence or unrelated recommendation. Add adversarial fixtures and retain exact-date cache keys.

### P2: Filter failed records out of source-yield history
- Metric: preserve topic supply through warnings; no direct inventory change.
- File: `scrapers/sanity_check.py:492` and `_append_stats:655`.
- Evidence: 1,172/5,000 history records carry critical failures; the last five records include duplicate checks from two scrapes. A five-good/three-failed replay hides a 53-to-zero cliff under the current helper.
- Proposed change: exclude records with critical failures before taking the median.
- Risk/open question: a source can have zero yield in a partial run whose critical checks still pass; repeated checks of one snapshot also skew the median. Critic must specify how to handle these.

## Directives
- fb-222: P1.
- fb-217: P2, with duplicate/completion limitations for critique.
- fb-212: UI audit; no scraper action.
