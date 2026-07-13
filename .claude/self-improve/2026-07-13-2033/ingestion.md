# Ingestion Quality Report — 2026-07-13 2033

Feed inspected: `/Users/prajj/nyc-events/site/public/events.json` (423 events, frozen).
Python: `/Users/prajj/nyc-events/venv/bin/python`. Full suite green before/after.

## Metrics observed
- Follow-graph coverage: 15/50 (30.0%) — unchanged (fb-194/195 are ranking/normalizer, not coverage levers).
- Null neighborhood share (committed feed): 66/423 = **15.6%** (baseline 19%, target ≤15%). Already below the 19% baseline (feed was rescraped since the Critic review).
- Neighborhood conflicts (Queens venue tokens tagged as a Manhattan neighborhood), BEFORE fix: **14** including all 3 MoMA PS1 "Warm Up" events tagged `midtown`.
- Neighborhood conflicts AFTER fix (frozen feed, re-running `_backfill_neighborhood_from_venue`): **1** (a single malformed doubled-address artifact — see P1 risk).
- taste-active events: 423/423 (cold-start from follow-graph). tasteScore range **0.0022 .. 0.1090**, mean **0.033**, never reaches MAX_BOOST 0.15. **Zero negative examples** (no `user_engagement.json`) → taste currently cannot penalize anything.

## Proposals

### P1 (fb-194): Fix Queens/LIC neighborhood mistags — borough fallback + Queens hoods + MoMA PS1 venue fix — APPLIED
- **Metric moved**: topic/geo correctness (neighborhood filter accuracy). Directly closes Critic P3.
- **Files**:
  - `scrapers/utils/event_parser.py` — `NYC_NEIGHBORHOODS` (LIC/Astoria expanded + `ridgewood`/`flushing`/`rockaway`/`forest hills`/`jamaica`/`corona`/`woodside`/`sunnyside` added), and `infer_neighborhood` borough fallback (new `\bqueens\b` / `\bbronx\b` / `\bstaten island\b` checks placed BEFORE the `new york`/`ny` → `manhattan` fallthrough).
  - `scrapers/normalize.py` — `_VENUE_NAME_TO_NEIGHBORHOOD` gains `"moma ps1": "long island city"` + `"ps1 contemporary"`; the Step-1 venue lookup in `_backfill_neighborhood_from_venue` now picks the **longest** matching venue key (most-specific-wins) so `"moma ps1"` beats the generic `"moma"`→`midtown`.
- **Root cause**: (a) Queens addresses ("22-25 Jackson Ave, Queens, NY 11101") also contain "New York/NY", so `infer_neighborhood` fell through to `manhattan` (Queens was never checked). (b) `"moma"` is a substring of `"moma ps1"` and the venue table used first-substring-match, so MoMA PS1 (LIC, Queens) inherited MoMA's `midtown`.
- **Verification RUN**:
  - Full suite: `310 passed, 3 xfailed`. Added 8 `infer_neighborhood` Queens cases + 3 backfill cases (MoMA PS1→LIC, bare MoMA still→midtown, Queens beer garden→astoria not manhattan). 153 pass in the two touched files.
  - Frozen-feed dry-run of `_backfill_neighborhood_from_venue`: Queens-mistagged-as-Manhattan **14 → 1**; all 3 MoMA PS1 → `long island city`; 12 more correct reassignments (Forest Hills Stadium→forest hills, Rockaway Hotel/Brewery→rockaway, Bohemian Beer Garden→astoria, Trans-Pecos/Lichen→ridgewood, Summerstage/Colden/Seaver Way→flushing, Rufus King Park/Jamaica Ave→jamaica, Hush Lounge→queens).
  - No previously-correct case regressed: bare "MoMA"→midtown preserved; "Brooklyn"→brooklyn preserved; existing 142 parser/normalize tests all pass.
- **Example titles this corrects**: "Warm Up: BADSISTA/TOCCORORO @ MoMA PS1" (midtown→long island city); "Djo @ Forest Hills Stadium" (manhattan→forest hills); "Elsewhere Presents: Otto Benson @ Trans-Pecos" (manhattan→ridgewood); "Dionne Warwick @ Colden Auditorium" (manhattan→flushing).
- **Risk**: LOW. Additive keyword/borough logic; longest-match is a strict refinement. One residual conflict: "5th St & 46th Rd, **Queens, NE**, Queens, NE 11101" — the *doubled/corrupted* address makes "ne 5th" substring-match the East Village keyword "e 5th" (which fires before the Queens fallback). This is upstream address-corruption, not a normalizer-logic bug; the LIC ZIP `11101` is present but shadowed by the earlier-iterating EV keyword. Fixing it safely (word-boundarying numbered-street keywords) risks the 142-test baseline, so I left it and documented it. See Open Questions.

### P2 (fb-195): Retire quality.py keyword lists against taste — DEFER (non-regression NOT demonstrable yet)
- **Metric it would move**: ranking generalization (fewer hand-keywords). Phase C part 2.
- **Finding (data-driven, run on the frozen feed)**: The taste model is *active* on all 423 events but its contribution is **an order of magnitude weaker** than the keyword boosts it would replace:
  - tasteScore max **0.109**, mean **0.033**; keyword boosts contribute **0.12–0.15 per hit** (`social_boost` 0.12/hit cap 0.28; `high_value_boost` 0.15/hit cap 0.30).
  - **Zero negative examples** (no synced `user_engagement.json`; pure follow-graph cold-start), so taste **cannot penalize** — it cannot subsume `SOFT_PENALTY_KEYWORDS` at all.
- **Before/after ranking experiment** (retired a hand-picked, lowest-risk batch of 10 music-genre HIGH_VALUE kws — `live jazz`, `jazz night/club/set`, `techno`, `house music`, `indie band`, `lo-fi`, `live band`, `live set` — all nominally subsumed by the `music` category signal + the user's followed music venues):
  - 5 events lost score, **max drop 0.150**, hitting genuinely relevant events: "Omar Sosa @ Blue Note Jazz Club" (−0.148), "Mingus Big Band @ The Pocket Jazz Club" (−0.105), "Tinned Fish & Jazz" (−0.121). Their taste scores (0.02–0.03) came nowhere near compensating the lost 0.15.
  - Top-40 didn't churn (these weren't top-ranked), but the regression on relevant music events is real and unbounded by taste.
- **Why defer, not proceed**: the directive requires proving taste subsumes the retired keywords with non-regression; the experiment shows the opposite at current taste magnitude/coverage. Per the directive's own escape hatch and the honest-negative precedent (2026-06-15-1724), DEFER with a concrete plan.
- **Concrete unblocking plan** (for a future run):
  1. Land a synced `user_engagement.json` with real `positiveTexts`/`negativeTexts` (needs the taste export loop / user saves) so the model has *negatives* — without them SOFT_PENALTY retirement is impossible.
  2. Raise taste's `MAX_BOOST`/`_SCALE` (taste.py: currently 0.15 / 0.35) OR feed it more positive examples, until median liked-event tasteScore ≥ ~0.12 (matching one keyword hit). Re-run the before/after harness (script in this run's notes): retirement is safe only when max per-event score drop from removing a keyword cluster is < taste's compensating lift on those same events.
  3. Start with **zero-hit-on-feed keywords** as a pure no-op cleanup (measured: HIGH_VALUE has 51/90 zero-hit, SOCIAL 26/39, SOFT_PENALTY 30/33 on the current feed) — these can retire with provable 0 ranking delta, but that's cosmetic (no behavior change) so I did not ship it this round to avoid churn without a ranking win.
- **HARD-RULE PRESERVED**: no change proposed to `HARD_BLOCK_KEYWORDS` (fb-001..009) or `MIN_SCORE`.

## Directives addressed
- **fb-194 (PRIMARY): ADDRESSED** — P1. MoMA PS1 → long island city (all 3); Queens conflicts 14→1; unit tests added (MoMA PS1 + 2 more Queens cases: LIC ZIP, forest hills, rockaway, flushing, queens borough fallback, bronx); null 15.6% (< 19% baseline). Built on the existing `_explicit_hood_in_text` Step-0 (fb-189) and `_VENUE_NAME_TO_NEIGHBORHOOD` (fb-193) as instructed.
- **fb-195 (SECONDARY): DEFERRED** — P2, with a live before/after ranking experiment proving current non-subsumption (taste max 0.109 vs keyword 0.15/hit; zero negatives) and a concrete staged unblocking plan. Conservative per directive ("propose, don't mass-delete"; "if you can't show non-regression, DEFER").

## Open questions for the Critic
1. **fb-194 residual (1 event)**: "5th St & 46th Rd, **Queens, NE**, Queens, NE 11101" stays `east village` because the corrupted doubled address makes "ne 5th" hit the EV keyword "e 5th" before the Queens fallback. Fix options: (a) accept as upstream data corruption (my choice); (b) word-boundary the numbered-street keywords in `NYC_NEIGHBORHOODS` (regression risk to the 142-test baseline); (c) prioritize ZIP-code keywords over street keywords in `infer_neighborhood`. Which do you want?
2. **fb-195**: is landing a real `user_engagement.json` (negatives) in scope for a future ingestion run, or is it gated on the frontend taste-export loop shipping first? The retirement is blocked on it either way.
3. New Queens hoods (`queens`, `bronx`, `staten island` as borough-level tags) will appear in the neighborhood filter UI — confirm the frontend renders unknown neighborhood values gracefully (they're new enum values).
