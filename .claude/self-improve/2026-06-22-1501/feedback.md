# Feedback for this run — 2026-06-22-1501

## Top 3 directives (workers MUST address or formally defer)

### 1. Land + verify the fitness / run-club expansion (recurring runs surface)
- backlog item: fb-179 (user-explicit, implemented this session, uncommitted)
- best agent: ingestion (verify), source-curator (confirm the +10 IG seeds are socializing-oriented per fb-106), ui (no-op)
- "addressed" criterion: on the next scrape, fitness/run-club event count rises vs the prior feed AND at least one recurring run club appears as ≥2 dated occurrences via detect_recurring_weekday → expand_recurring_event; no run-club event carries a soft-penalty. Commit this round; Phase 6 flips fb-179 status to `addressed: <sha>`.
- guardrail: the +10 new IG seed accounts must each pass the fb-106 filter (no individual-person handles — clubs/orgs/curators only). Reject any `firstname_lastname` / `firstname<number>` shapes before commit.

### 2. Land + verify Brooklyn Contra dancing as distinct dated events
- backlog item: fb-180 (user-explicit, implemented this session, uncommitted)
- best agent: ingestion / source-curator
- "addressed" criterion: brooklyncontra source yields its dances as distinct dated events on the next scrape (≥ the 8 verified this session, modulo fb-181), each surviving the DISTINCT_SCHEDULE_SOURCES recurring-merge exemption in normalize.py. Commit this round; Phase 6 flips fb-180 status to `addressed: <sha>`.
- note: do NOT let the recurring-merge collapse the scheduled dances back into one event — the normalize.py exemption is load-bearing.

### 3. Fix the `'rave'` substring exclusion (word-boundary anchor)
- backlog item: fb-181 (agent-proposal, open — surfaced by the contra work)
- best agent: ingestion (quality / exclusion filter)
- "addressed" criterion: anchor the exclusion to `\brave\b` (and `\braves?\b` if needed) so "Raven & Goose", "rave reviews", "travel", "gravel" survive while a literal "Rave" / "warehouse rave" title is still blocked. Verify against the contra feed + a small FP probe set. Recovers the dropped Oct-4 contra dance and prevents future substring false positives.
- if deferred: requires explicit Critic sign-off with a wont-do reason; it is a low-risk, high-precision fix that directly recovers a user-requested event, so deferral should be hard to justify.

## Questions to ask the user this round

none — throttled. QUESTION GATE is CLOSED: argument empty (no force-ask); ≥3 open backlog items (gate requires <3); and the most recent user-explicit feedback is from THIS session (today, 2026-06-22). No user-facing question produced.

## Backlog mutations applied

- Added fb-179: Incorporate more fitness-based events + run clubs (recurring too) — user-explicit, status: in-progress (uncommitted this session).
- Added fb-180: Add Brooklyn Contra dancing (brooklyncontra.org) — user-explicit, status: in-progress (uncommitted this session).
- Added fb-181: `'rave'` title-exclusion substring-matches legitimate words ("Raven", etc.) — agent-proposal, status: open.
- Re-ranked: fb-179, fb-180, fb-181 placed at the TOP of the open-items list (most actionable + most recent + direct North-Star fit: fitness/run-clubs and contra both expand follow-graph/topic coverage of accounts the user explicitly named). All pre-existing open items (fb-106, fb-101, fb-174, fb-173, fb-178, fb-175, fb-176, etc.) retained in prior order below; no body text edited.
- Closed (with sha): none newly closed this round. (Existing addressed items unchanged: fb-169/fb-175(partial)/fb-176 were marked addressed in the prior run 2026-06-15-1724 per the journal; fb-179/fb-180 will move to `addressed: <sha>` in Phase 6 once this run's commit lands.)

## Open-items snapshot (post-mutation, top-down)
1. fb-179 (user-explicit, in-progress) — fitness/run-clubs
2. fb-180 (user-explicit, in-progress) — Brooklyn Contra
3. fb-181 (agent-proposal, open) — `'rave'` substring bug
4. fb-178 (open) — "Did you go?" attend/skip calibration affordance
5. fb-174 (open, user-blocked) — IG GraphQL sweep blocked fleet-wide
6. fb-173 (open, user-blocked) — CI runner IP 403/429-blocked
7. fb-175 (addressed-partial) — 2 not-in-feed IG-Story residuals deferred
(remaining items addressed / addressed-pending-scrape)

## Uncertainty flags
- None on ranking. The two new user-explicit items are unambiguously top priority; fb-181 sits third as the immediate follow-on bug from fb-180's work.
