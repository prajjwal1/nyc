# Feedback for this run — run-id 2026-07-02-1735

## Standing constraint (read first)
3rd consecutive **code-only** round. Feed frozen at 2026-06-15 (~17 days stale). No CI scrape has landed since then; ~4 rounds of committed levers (fitness/dance/contra/boost/lu.ma-floor) sit UNLANDED. **The single highest-leverage action remains a SCRAPE** (residential IP per fb-173 / fb-174 — both user-blocked infra). All three directives below are therefore deliberately scrape-INDEPENDENT, test/build-verifiable work. Scrape-gated source-yield work and user-blocked items (fb-174 IG-sweep, fb-173 CI-IP block, fb-139 Reddit OAuth) are NOT surfaced as actionable — they are constraints only.

## Top 3 directives (workers MUST address or justify deferral)

### 1. Fix neighborhood-vs-venue-name contradiction in the normalizer
- backlog item: fb-189 (new)
- best agent: ingestion
- what: ~8/375 events carry a `location.neighborhood` that contradicts the venue name (e.g. name "Bushwick, 380 Troutman Street" but neighborhood "east village"). `infer_neighborhood`/`_reinfer_neighborhood` picked a wrong neighborhood from address/default while the venue name held the true one. This is scrape-independent (present in the frozen feed), unit-testable, and directly degrades the neighborhood badge the user relies on. Note: b6a0cf3 U2 only *suppresses the redundant display suffix* — it does NOT correct the underlying data; the wrong neighborhood still ships and still misfilters.
- "addressed" criterion: for events whose venue name (or title) contains an explicit NYC neighborhood token, `location.neighborhood` never contradicts it (name-token wins); a unit test covers the "Bushwick, 380 Troutman St → bushwick (not east village)" case and ≥2 more; count of name/neighborhood-conflict events in the frozen `events.json` drops from ~8 to 0.

### 2. Audit + strengthen body-text time inference (`_infer_time_from_text`)
- backlog item: fb-186
- best agent: ingestion
- what: many well-formed fitness/run/dance Eventbrite-category events carry their time only in body text ("doors at 7pm", "starts 8pm") and so fail the fb-184 P1 score-recovery gate (hard-gated on parsed `startTime`). A `_infer_time_from_text` pass already exists (`scrapers/normalize.py`, added 2026-06-04) — AUDIT and STRENGTHEN it: coverage of "doors"/"starts"/bare "Npm", single-unambiguous-match gating, never overwrite a parsed time, and confirm it runs BEFORE scoring so the P1 gate sees the inferred time. Recovers yield honestly (raises completeness, does not override the 0.55 floor). Fully unit-testable on synthetic descriptions; no scrape needed.
- "addressed" criterion: unit tests show "doors at 7pm"/"show starts 8pm"/"7:30pm" filled into `startTime` when absent, NOT overwritten when present, and no fill on ambiguous/multi-time text; call ordering verified so scoring sees the inferred time.

### 3. EventModal price-pill consistency with FeedCard (U1 + fb-182)
- backlog item: fb-188
- best agent: ui
- what: FeedCard now renders a numeric gray price pill (U1) and a qualitative sky price pill (fb-182). `EventModal.tsx` (~line 172) still renders any non-free price as verbatim un-styled text. Give the modal the same numeric-gray / qualitative-sky pill treatment. Cosmetic-only, no behavior change, build-verifiable — a clean fit for a scrape-frozen round.
- "addressed" criterion: EventModal renders numeric prices as a gray pill and qualitative price words (donation/PWYC/sliding-scale/suggested) as a sky pill, matching FeedCard; next build clean; no regression to the free/unknown states.

## Questions to ask the user this round
none — GATE CLOSED (orchestrator: arg empty, ≥3 open items, newest user-explicit feedback is today 2026-07-02). No user-facing questions produced.

## Backlog mutations applied
- Added fb-189 (open, agent-proposal, TOP directive): neighborhood-vs-venue-name normalizer contradiction (~8/375 events).
- Added fb-190 (addressed: 8d10fc2): lu.ma/philosophy + all lu.ma curators not surfacing — shell-filter curated-host bypass + high-conviction score floor regardless of source (philosophy 0→7); + source-survival audit tool + parametrized curator regression tests + date-relative test-flake fix.
- Added fb-191 (addressed: b6a0cf3): add `openbookclub` to IG_ACCOUNTS (no-dot; dotted `open.bookclub` kept).
- Added fb-192 (addressed: b6a0cf3): UI — U1 relative-day pill on hero cards, U2 de-dup neighborhood/location line, U3 slate Just-Added so sky=conviction, U4 fixed stale empty-state copy.
- Re-ranked open list: fb-189 → top (new, actionable, scrape-independent, targets the neighborhood-badge North-Star signal). fb-186 and fb-188 promoted directly under it (both scrape-independent + test/build-verifiable). fb-174/fb-173/fb-139 kept as constraints-only, not directives.
- Closed (with sha): fb-190 → 8d10fc2; fb-191 → b6a0cf3; fb-192 → b6a0cf3. (These are the three new user-explicit/UI items, already implemented + committed this session.)

## Investigation finding recorded (for the orchestrator, from the 8d10fc2 lu.ma work)
Most OTHER audit-flagged sources are NOT bugs: empty calendars, by-design floor+caps, redundant parse-rot, or JS-blocked museums. Do not chase them as source-yield directives. The lu.ma/philosophy case was a genuine silent-filter bug (curated-host + score-floor) and is now fixed + guarded by the new `audit_source_survival.py` + parametrized curator test.
