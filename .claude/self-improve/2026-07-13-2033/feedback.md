# Feedback for this run — 2026-07-13-2033

## Top 3 directives (workers MUST address or justify deferral)

All three are scrape-INDEPENDENT and unit-testable (the feed is frozen; the last CI
scrape predates these). Each was raised in the 2026-07-09 Critic review of the deployed
feed and deferred there. They are the highest-value verifiable work this round.

### 1. Fix Queens/LIC neighborhood mistags + ~19% null-neighborhood rate (normalizer data bug)
- backlog item: fb-194
- best agent: ingestion
- "addressed" criterion: "MoMA PS1" (and any LIC/Queens venue token) resolves to a Queens
  neighborhood (long-island-city / queens), never "midtown"; a unit test covers
  "MoMA PS1 → long island city (not midtown)" + ≥2 more Queens cases; null-neighborhood
  share in committed events.json drops below 19% (target ≤15%). Compounds with fb-189
  (`_explicit_hood_in_text` Step-0) and fb-193 (venue alias) — reuse those paths.

### 2. Retire/validate the ~600 keyword lists in quality.py against the now-active taste model
- backlog item: fb-195
- best agent: ingestion
- "addressed" criterion: the TF-IDF taste signal (scrapers/utils/taste.py, active on all
  423 events as of 62a08f9/f81a75f-P6) is compared against the hand-maintained keyword
  boost/penalty lists in quality.py; each keyword cluster is classified
  (keep / redundant-with-taste / retire) with the taste-vs-keyword agreement recorded;
  at least the clearly-redundant clusters are removed OR a documented finding explains why
  keyword lists must stay. This is Phase C part 2 — now UNBLOCKED because the taste loop is
  live on the full feed (was blocked on "validate first"). Additive-only rule does NOT block
  this: it is refactoring a ranking signal, not deleting a source. Preserve the fb-001..fb-009
  README hard rules regardless (those are user-explicit, not taste-derived).

### 3. Close the user-named coverage gaps: backgammon/chess, underground-electronic, social dance
- backlog item: fb-196
- best agent: source-curator
- "addressed" criterion: at least one parseable path added (live-probed ≥5 future events,
  exclusion-clean per fb-153/user_excluded_sources.json, fb-106-clean) toward EACH gap the
  user explicitly named: (a) backgammon/chess — no events currently surface
  (nycbackgammonclub is a chronic sanity_check CRITICAL); (b) underground-electronic beyond
  Warm Up — probe Nowadays / Public Records / Elsewhere sourcing (mind fb-153: HoY/KDC are
  user-EXCLUDED, do not re-add); (c) social dance beyond contra-only — a non-contra
  participatory social-dance source. A live-verified negative (path probed, <5 yield, why) is
  acceptable per the honest-negative precedent (run 2026-06-15-1724) and defers the item.

## Questions to ask the user this round

none — GATE CLOSED. Newest user-explicit feedback is 2026-07-09 (<7 days, inside the
7-day throttle) AND ≥3 open items remain in the backlog. No user-facing question.

## Backlog mutations applied

- Added fb-197 (top of open list): big /plan preference-learning directive (2026-07-09,
  user-explicit) — status addressed across 4 phases: A 23128fd, B af4c066, C 62a08f9,
  D 6862a8b.
- Added fb-198: 2026-07-09 Critic-review incorporation — status addressed: f81a75f
  (P1 de-saturated ranking, P6 follow-graph taste cold-start on all 423 events,
  P5 OCR-garbage/"Copy of" title purge).
- Added fb-194 (open, ranked #1): Queens/LIC neighborhood mistag + ~19% null (Critic P3).
- Added fb-195 (open, ranked #2): retire/validate quality.py keyword lists vs taste model
  (Phase C part 2, now unblocked).
- Added fb-196 (open, ranked #3): user-named coverage gaps — backgammon/chess,
  underground-electronic, social dance (Critic P7).
- Re-ranked: fb-194, fb-195, fb-196 placed at the top of the open list (most actionable +
  recent + North-Star-direct). The prior top open items (fb-104, fb-178, fb-185, fb-187,
  fb-193, fb-139) drop below them; their bodies/status unchanged.
- Closed (with sha): none newly closed from prior-run commits this round (fb-197/fb-198 are
  logged already-addressed with their shipping SHAs). Note: several previously-open program
  items are captured under fb-197/fb-198 rather than duplicated.

## Do-not-surface (user-blocked; not actionable this round)
- fb-174 (IG GraphQL account-sweep 400-blocked fleet-wide), fb-173 (CI-runner IP blocks),
  fb-139 (Reddit OAuth), and the fb-104/fb-185 additive-only prunes (need user opt-in).
  Workers MUST NOT propose IG-sweep-dependent levers for follow-graph coverage; use non-IG
  enrichment paths.

## Metric trajectory (context, not a directive)
- Run coverage 26 → 46 and high-conviction ratio 17.5% → 22.5% both moved off the 4-phase
  program + Critic incorporation landing (first real metric movement after ~4 frozen rounds).
