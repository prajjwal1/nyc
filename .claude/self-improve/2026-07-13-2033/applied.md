# Applied changes — run 2026-07-13-2033

## scrapers/ (ingestion + source-curator worker-applied + orchestrator)
- [x] ingestion-fb194 (APPROVE): Queens/LIC neighborhood fix — event_parser.infer_neighborhood borough checks before manhattan fallthrough + LIC/Astoria/Queens hoods; normalize._VENUE_NAME_TO_NEIGHBORHOOD moma ps1→LIC + longest-key-wins. Queens-mistag 14→1, null 15.6%. +11 tests. (worker-applied, critic-verified no regression)
- [~] ingestion-fb195 (DEFER, sound): keyword-list retirement deferred — taste magnitude (0.03 mean) << keyword boosts (0.12-0.15) + zero negative examples; retiring would regress. Concrete unblock plan logged. → backlog fb-199 (D1: retire zero-hit keyword clusters as 0-delta first step).
- [x] source-S1 Chess Place organizer (o/115357260611) → user_curated_sources (chess gap). APPROVE.
- [x] source-S2 backgammon + chess Meetup keyword searches → meetup.py SEARCH_URLS. APPROVE (also feeds NYC-Backgammon CRITICAL).
- [x] source-S3 Harlem Swing Dance organizer (o/10662501681) → curated (non-contra social dance). APPROVE.
- [x] source-S4 Elsewhere organizer (o/105655500371) MODIFY: kept but `floor_bypass:false` (boost-only, not floor-bypass) via new `_is_curated_host(floor_context=True)` mechanism in normalize.py — bounds late-night leak (Critic S4).
- [x] user-directed: openbookclub via Substack (openbookclubnyc.substack.com) → substack.FEEDS + curated host + must_surface updated. Non-roundup posts → pubDate whole-post fallback (no date fabrication — verified). Surfaces on future-dated posts.

## site/ (ui — safe subset; U1+U2 deferred to visual pass)
- [x] ui-U3 (APPROVE): mobile responsive — EventCard image w-20 sm:w-24; EventModal max-h-[90vh] sm:max-h-[95vh].
- [x] ui-U4 (APPROVE): discovery heroes (Just Added, This Weekend) capped 6→4 (Tonight/Following/Saved stay 6) so ranked feed surfaces sooner on mobile. Heroes preserved.
- [ ] ui-U1 (MODIFY, DEFERRED to task #6): non-color conviction chip — clutter/iter-214 tension needs visual review.
- [ ] ui-U2 (APPROVE, DEFERRED to task #6): aria-labels + focus rings — fold into the a11y visual pass (Calendar nav buttons need locating).

## Dreams → backlog
- D1 → fb-199 (retire measured zero-hit keyword clusters, provable 0-delta — the fb-195 first step).
- D2 → fb-200 (ZIP-code-priority tie-break in infer_neighborhood for corrupted-address edge).

## Skipped/rejected: none rejected. fb-195 deferred (sound). U1/U2 deferred to visual pass.
