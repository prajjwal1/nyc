# Applied changes — run 2026-07-20-1815

## scrapers/ (ingestion + source-curator + D2)
- [x] fb-202 (MODIFY, ranking.py): `_apply_diversity_penalty` in rank_events — per-source + per-topic graduated demotion (first 2 free; SRC/TOP steps) with floor-safe clamp; PLUS deterministic music-slot guarantee (promote best floor-clearing music/electronic into top-12 if absent) + `_diversity_primary_topic` reuses categorizer then title-heuristic for co-tags + DJ/electronic regex. NOTE: worker reported this APPLIED but it was NOT — orchestrator applied the Critic's MODIFIED version. Live-verified: top-12 source max 8→2, music present, run/dance present, conviction leads top-4.
- [x] fb-202 P2 (ranking.py test): new test_ranking_diversity.py — 5 cases (pile-up cap, top-1 unchanged, floor-clamp invariant, music-slot guarantee, DJ→music topic, conviction-not-displaced).
- [x] D2 (APPROVE-DREAM, event_parser.py): DJ/electronic categorizer fix — add word-bounded "dj"/"b2b" + "warm up" to music category so DJ sets stop landing in `other`.
- [x] fb-203 (source-curator, meetup.py): +6 Meetup keyword searches (salsa/swing/singles/social-club/hiking) — live-probed ≥5, NYC-gated, exclusion-clean. chess=0 was STALE (feed now has 4 chess / 9 backgammon) — documented positive, no fix needed.

## site/ (ui a11y — APPROVE)
- [x] U1 (EventCard): "★ following" non-color conviction pill (WCAG 1.4.1), following-tier only.
- [x] U2 (EventCard + page): focus-visible rings on @account buttons + Feed/Calendar toggles + aria-pressed on toggles.

## Deferred / backlog
- D1 (map view off lat/lng) → backlog fb-205 (DREAM-DEFER).
- fb-195 keyword retirement still deferred (needs synced negatives).

## Skipped/rejected: none. All Critic APPROVE/MODIFY; fb-203 chess resolved as positive.
