# Feedback for this run — run-id 2026-06-23-1816

No new user feedback this session. The user re-invoked `/self-improve`; the orchestrator confirms no force-ask and no new input. This is the 2nd consecutive code-only round with **no intervening CI scrape** — last round's fitness / run-club / contra levers (run 2026-06-22-1501) are committed-but-unlanded; their payoff is gated on the next scrape, not on more code.

## Top 3 directives (workers MUST address or justify deferral)

### 1. Investigate & recover the 6 inert legacy Eventbrite fitness/dance slugs (0-yield despite 500+ cumulative fetches)
- backlog item: fb-184 (new this round; agent-proposal, surfaced by the Critic/source-curator in run 2026-06-22-1501 hypothesis #2)
- best agent: ingestion
- why now: directly serves the still-unlanded user request fb-179 ("more fitness + run clubs"). The 6 NEW narrow slugs added last round live-verified at 20/20, proving the pattern works — so the legacy broad slugs are silently broken (likely JSON-LD shape drift or a too-broad slug per the fb-155 pattern). Cheapest high-leverage win toward the North Star this round.
- "addressed" criterion: each of the 6 legacy fitness/dance slugs is classified (working / swapped-to-verified-narrow-slug / removed-as-dead) with a live-probe yield count recorded; net fitness/dance event count does not regress and ideally rises next scrape.

### 2. Consolidate DISTINCT_SCHEDULE_SOURCES into a shared helper (+ queue the fb-106-clean IG fitness/dance candidates)
- backlog item: fb-183 (D2 deferral from run 2026-06-22-1501)
- best agent: ingestion
- why now: `DISTINCT_SCHEDULE_SOURCES` is checked at TWO call-sites in `scrapers/normalize.py` (`_dedup_same_account_recurring` and `_dedup_fuzzy_title`). The next person who adds a distinct-schedule source (e.g. while fixing fb-184) must edit both or silently merge-back user-requested dated events — exactly the contra/run-club events fb-179/fb-180 just fought to surface. A behavior-identical refactor that hardens the lever the last two rounds depended on. Part (2) is queue-only (probe + add the 6 fb-106-clean IG handles when fb-174 clears) — do NOT attempt the IG probes this round.
- "addressed" criterion: `def _is_distinct_schedule_source(ev)` extracted in `normalize.py`, called from both dedup passes, with a unit test asserting a 2nd distinct source bypasses BOTH passes; 253-test suite still green.

### 3. Render qualitative / low-commitment price words as a positive pill
- backlog item: fb-182 (D1 deferral from run 2026-06-22-1501)
- best agent: ui
- why now: a code-only, scrape-independent UI win that compounds last round's U1 numeric price pill. "Donation / pay-what-you-can / PWYC / sliding scale / suggested" are positive low-commitment signals a meet-people user wants at a glance — surfacing them nudges attendance toward the North Star. Single-file, same badge row U1 already touches.
- "addressed" criterion: FeedCard renders a distinct subtle pill (visually lighter than FREE) when `event.price` matches `/donation|pay what|pwyc|sliding scale|suggested/i`; no regression to U1's numeric pill; next build clean.

(Deferred over fb-178 "Did you go? on past saved events": it explicitly needs a storage/ingest design beyond a code-only/no-backend round — lower leverage this round than the three above. Stays open.)

## Questions to ask the user this round

None — **question gate CLOSED**. Argument is empty (no force-ask); ≥3 open backlog items exist (gate requires <3); newest user-explicit feedback (fb-179/fb-180) is from 2026-06-22, one day ago, well inside the 7-day throttle. No calibration question this round.

## Standing constraints (NOT actionable directives — do not surface as work)
- fb-174 — IG GraphQL account-sweep 400-blocked fleet-wide (user/infra). Workers MUST NOT propose IG-account-sweep-dependent fixes as the follow-graph lever; use non-IG enrichment paths only.
- fb-173 — GitHub Actions runner IP broadly 403/429-blocked by publishers (user/infra; mitigated via CARRYOVER_SOURCES). A source at 0 in a CI snapshot may be IP-blocked, not broken.
- fb-139 — Reddit OAuth (requires user GitHub-secret setup).
- fb-104 — prune redundant Lu.ma `/nyc/<topic>` URLs: blocked by the additive-only rule (needs explicit user opt-in); fb-105 confirmed there is no replacement curator list, so the deletion is safe-but-blocked.

## Backlog mutations applied
- Added fb-184: "Investigate the 6 inert legacy Eventbrite fitness/dance slugs (0-yield despite 500+ fetches)" — agent-proposal, status open. Inserted at top-of-open (above the append marker).
- Re-ranked (this run's top-3 surface order): fb-184 → fb-183 → fb-182. No existing entry bodies altered.
- Closed (with sha): none this round — no intervening commits since run 2026-06-22-1501 (last commit d2855de already recorded fb-169/fb-175/fb-176 as addressed). The 2026-06-22 levers (fb-179/fb-180/fb-181) are already marked addressed: d9eb82e in the backlog; no new closures to apply.

## Uncertainty flags
- None on priority. fb-184 ranks #1 because it is the only directive that directly advances an outstanding *user-explicit* request (fb-179) and is cheap; fb-183/fb-182 are the two strongest committed-deferral candidates and are both scrape-independent (correct for a code-only round).
