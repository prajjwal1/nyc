# Critic Report — 2026-06-23 1816

Run id 2026-06-23-1816. Second consecutive code-only round, no intervening CI scrape (feed frozen at 365 events, identical to 2026-06-22-1501). All metric deltas this round are gated on the next scrape.

## Cross-check results
- **sanity_check regression risk**: none from any APPROVED change. P1 (fitness +boost) does NOT touch a CRITICAL_CHECK floor, but it DOES risk eviction-by-cap of music-category eventbrite events (CRITICAL min 15). See P1 verdict — I MODIFY P1 to neutralize that risk. S1-S4 are additive-only and cap-bound; cannot reduce music/free/IG counts on their own.
- **Duplicate source proposals**: none. Verified via `grep` on `scrapers/sources/generic.py` — hiking, walking-tour, board-games, chess, trivia, climbing are all ABSENT from GENERIC_URLS. S1-S4 + held candidates are non-duplicate. (Contrast: P1b's `ny--brooklyn/running--events/` IS a confirmed 100% dup of the NYC slug, already present at generic.py:212-213.)
- **User-excluded check (fb-153 / iter-107 lesson)**: S1-S4 explicitly cited the exclusion-list check (accounts/hosts/title_hints) and are clean. S3 (board-games) correctly noted "Board Game Speed Dating" sub-events are handled by the existing `speed dating`/`speed-dating` title_hints penalty (confirmed present in user_excluded_sources.json:26-27) — not a slug-level block. Held trivia/climbing: curator did NOT explicitly re-cite the exclusion check in the held block — I require it before promotion (see verdict).
- **UI preference compliance**: ok. U1 adds one badge-row pill, no left-sidebar widget, no empty gray box (renders only when price matches), not in the This Weekend hero. Compliant with §513-516.
- **fb-106 (no personal/private IG accounts)**: N/A this round — no IG-account adds proposed (fb-174 blocks the sweep; correctly deferred).
- **Top-3 directive coverage**: addressed: fb-184 (root-caused + P1 lever), fb-183 (P2 refactor), fb-182 (U1 pill). deferred-acceptable: none silently dropped. deferred-REJECTED: none.
- **Silent-failure watch**: the round's headline finding INVERTS the standing silent-failure flag — the "6 inert legacy slugs" were NOT silently broken; they parse 20 events each (live-probed on residential machine, corroborated by url_health emitted_total 80-440). The fb-184 premise was wrong at the extraction layer. Real cause = MIN_SCORE 0.55 + eventbrite=100 cap bottleneck. No NEW silent failure surfaced. One watch item: swing-dance/folk-dance/salsa/pilates have NO url_health record yet (18:20 scrape was partial) — re-confirm their LANDED yield next scrape.

## Verdicts

### ingestion-P1: targeted +0.06 fitness/run/dance topic boost to clear MIN_SCORE + cap
- **Verdict**: MODIFY
- **Metric moved**: topic coverage (fitness/run/yoga topics, +modest) + serves user-explicit fb-179. Magnitude is small and CONTESTED (see reasoning) — at most a handful of fitness events cross 0.55, and the cap makes the net feed gain near-zero unless they outscore incumbent eventbrite events.
- **Reasoning**: Two concerns the worker under-weighted. (1) The cap is zero-sum: eventbrite is pinned at exactly 100/100 and the cap sorts by score descending (normalize.py:2096). Every boosted fitness event that wins a slot EVICTS another eventbrite event — and the lowest-scoring incumbents most at risk are exactly the generic music/comedy/free-category fillers. A blanket +0.06 to a whole topic family could measurably shuffle the eventbrite mix; the worker measured the floor-crossing but NOT the eviction. (2) The journal explicitly establishes the 0.55 floor as the honest quality gate that intentionally floors out low-info NYPL events (journal context + normalize.py:2036-2038 comment "marginal-quality long tail in 0.45-0.55 was 133 events; trimming that"). A flat end-of-pipeline +0.06 is a category-wide exemption from that gate. Note the fitness CATEGORY multiplier already landed last round (1.1→1.3); `_category_score` for a fitness event is already saturated (0.6×1.3=0.78). So the events scoring 0.36-0.51 are NOT losing on category — they lose on COMPLETENESS / TITLE-QUALITY / TIME (short titles, no startTime). A flat boost specifically overrides those quality signals, which is the spam vector.
- **If MODIFY** — apply this tightened version instead of the proposal's "+0.06-0.08 on cats OR title-keyword":
  - At `scrapers/ranking.py:537-542` (the existing fitness/run weekday block), do NOT widen it to a flat post-hoc additive on the final score. Instead add a SEPARATE small recovery boost that is HARD-GATED on completeness so it cannot float low-info events:
    ```python
    # fb-184: profile-aligned fitness/run/dance Eventbrite-category events
    # score 0.36-0.51 on completeness/title alone and miss the 0.55 floor
    # despite being user-requested (fb-179). Recover ONLY well-formed ones:
    # require BOTH a parsed startTime AND a venue name, so a low-info
    # caption-only event still floors out (preserves the 0.55 quality gate).
    if (cats & {"fitness", "wellness", "outdoors"} or any(
            k in text for k in ("run club", "yoga", "pilates", "contra", "swing dance"))):
        if event.get("startTime") and (event.get("location", {}) or {}).get("name"):
            boost += 0.05
    ```
  - Magnitude: **+0.05, not +0.06-0.08**. +0.05 lifts the verified 0.49-0.54 cluster over 0.55 (worker measured fitness max=0.51, running has ~4 in band) while +0.08 would also pull the 0.47-0.49 band which is where the genuinely thin events sit.
  - Keep the existing `max(-0.05, min(0.06, boost))` clamp at line 547 — note this means the new +0.05 COMBINES with the existing weekday +0.03 but is capped at +0.06 total, which is acceptable and self-limiting (a good accident: the clamp already prevents runaway stacking).
  - The dual gate (startTime AND venue name) is the load-bearing safety: it is strictly stronger than the worker's "startTime OR known venue" (OR lets a venue-only, timeless studio drop-in through). AND is correct here — a real fitness event the user would attend has both a time and a place.
- This keeps fb-184 OPEN-but-mitigated: the lever is real but small. Do NOT close fb-184 on this; mark it "addressed — re-scoped from parse-fix to score-recovery; verify lift in next scrape's fitness count and confirm no music-count regression in sanity_check."

### ingestion-P1b: prune `ny--brooklyn/running--events/` (100% dup of NYC running slug)
- **Verdict**: APPROVE (as backlog opt-in surfacing only — do NOT remove this round)
- **Metric moved**: none (pure efficiency — saves one fetch/round, zero event loss since overlap is 18/18).
- **Reasoning**: Live overlap verified 18/18 identical; Eventbrite ignores the borough segment for the running category. Genuine pure-redundant pair (generic.py:212 vs :213). But removal is blocked by additive-only (same class as fb-104). Correct call by the worker.
- **Action for orchestrator**: add a feedback-backlog entry `fb-185` (source: agent-proposal, status: open, blocked-on: user opt-in) — "Prune `ny--brooklyn/running--events/`: 100% duplicate of `ny--new-york/running--events/` (live overlap 18/18; Eventbrite ignores borough for category search). Safe to remove, zero event loss. Batch with fb-104 prune opt-ins." Do not touch generic.py.

### ingestion-P2 (fb-183): extract `_is_distinct_schedule_source(ev)` helper + unit test
- **Verdict**: APPROVE
- **Metric moved**: none directly. Hardens the distinct-schedule lever fb-179/fb-180 (run-club/contra) depend on — prevents a future single-call-site edit from silently merge-collapsing user-requested dated events. Defends high-conviction event integrity.
- **Reasoning**: Verified the duplication is real — `DISTINCT_SCHEDULE_SOURCES` membership is checked at normalize.py:180 (`_dedup_same_account_recurring`) and the worker cites :422 (`_dedup_fuzzy_title`). Pure extraction, same truthiness, behavior-identical. The monkeypatch unit test (assert a 2nd source bypasses BOTH passes + a control that DOES merge) is exactly the right shape and avoids permanently widening the production set. Baseline 253 passed / 3 xfailed confirmed by worker.
- **Note**: ship the helper docstring as written (it correctly documents the "individually-scheduled, individually-ticketed, repeats title across dates" contract that matches the existing comment at normalize.py:151-157).

### source-pool-S1: add `ny--new-york/hiking--events/` to GENERIC_URLS
- **Verdict**: APPROVE
- **Metric moved**: topic coverage (outdoors vector, currently thin). Net feed effect is cap-bound — only helps insofar as these outscore incumbent eventbrite events — but it DEEPENS the pool so the cap is filled with on-vector rather than generic content, and outdoors hikes pair with the morning-fitness time boost (ranking.py:482). 20/20 participatory, exclusion-clean.
- **Reasoning**: Non-duplicate (grep-confirmed absent). Participatory group hikes, no performances, clean exclusion check. Lowest-risk of the four. Insert at generic.py ~line 248 near the existing topical block (NOT line 233 — that's the book-club region; the worker's line estimate is stale, see note to curator).

### source-pool-S2: add `ny--new-york/walking-tour--events/` to GENERIC_URLS
- **Verdict**: APPROVE
- **Metric moved**: topic coverage (exploration / "discover the city" vector, user boost 1.25). Cap-bound, deepens pool. 20/20 participatory guided walks, clean.
- **Reasoning**: Non-duplicate, on a confirmed user-interest vector, exclusion-clean. One sample ("Gay History Walking Tour … GAY PRIDE WEEKEND") is timely and on-vector. Approve.

### source-pool-S3: add `ny--new-york/board-games--events/` to GENERIC_URLS
- **Verdict**: APPROVE
- **Metric moved**: topic coverage (games vector — user follows backgammon/games clubs, boost 1.3; also reinforces the NYC Backgammon CRITICAL_CHECK ecosystem). Cap-bound. 19/19 participatory.
- **Reasoning**: Non-duplicate, strong meet-people vector, exclusion-clean. Board-games at the 1.3 games boost is the one topic family that plausibly outscores incumbent eventbrite events (vs fitness which loses on completeness) — so this is the highest-yield of S1-S4 given the cap. The "Board Game Speed Dating" sub-events are correctly handled by the existing title_hints penalty (verified in user_excluded_sources.json). Approve.

### source-pool-S4: add `ny--new-york/chess--events/` to GENERIC_URLS
- **Verdict**: APPROVE
- **Metric moved**: topic coverage (games vector, recurring community clubs = high meet-people value, exactly the recurring social format fb-179 wants). Cap-bound. 20/20 participatory, mostly recurring weekly.
- **Reasoning**: Non-duplicate, exclusion-clean, samples skew to recurring neighborhood chess clubs (McCarren, Bushwick, Bad Bishop BK) which are precisely the meet-people recurring format. Note: recurring chess clubs that repeat near-identical titles across dates may want a future DISTINCT_SCHEDULE_SOURCES consideration if they merge-collapse — but they arrive via eventbrite source (not a distinct source) and the title_jaccard dedup is per-publisher, so monitor next scrape. Approve as-is.

### source-pool held: trivia, climbing
- **Verdict**: MODIFY (promote trivia + climbing, BUT require the explicit exclusion re-check first)
- **Metric moved**: topic coverage (games/social via trivia; outdoors/fitness via climbing). Both clear 20 live, both on-vector.
- **Reasoning**: The cap argument is symmetric — adding 6 vs 4 slugs is marginal because eventbrite is pinned at 100, so dilution risk is near-zero (you can't exceed the cap; you only change WHICH eventbrite events fill it). Given that, holding them for "conservatism" buys nothing — they're on-vector and the cap protects against overflow. Climbing ("Climb & Connect Night", "CRUX Trans/Nonbinary Climbing") is strongly meet-people and outdoors-vector; trivia ("Pokemon/Taylor Swift Trivia") is games/social. Promote BOTH.
- **If MODIFY**: orchestrator adds `https://www.eventbrite.com/d/ny--new-york/trivia--events/` and `https://www.eventbrite.com/d/ny--new-york/climbing--events/` to GENERIC_URLS alongside S1-S4 — CONDITIONAL on the orchestrator (or curator) confirming neither has a title-family match in user_excluded_sources.json. Trivia is clean (no speed-dating/rave/ai/networking hits in the samples). Climbing is clean. If either surfaces a hit, drop only that one. This is the iter-107 CHECK-FIRST guard applied mechanically.

### source-pool folk-dance: keep-but-watch vs retire
- **Verdict**: APPROVE keep-but-watch (do NOT retire this round)
- **Metric moved**: topic coverage (dance vector, ~55% participatory). Retiring = removal = additive-only blocked anyway.
- **Reasoning**: Both ingestion and curator independently re-probed: ~4-5/8 participatory ("No Lights No Lycra", "POP-UP DANCE!", "Witch's Dance Workshop") vs performances/parties ("Ayazamana", "Bowie Dance Party"). 55% clears the participatory bar, additive-only forbids removal, and it does surface real participatory dance. Keep-but-watch is correct. Add a watch note to fb-backlog: "folk-dance slug provisional — if next scrape's landed folk-dance events under-engage or skew >50% performance, surface as user opt-in prune (additive-only blocks unilateral removal)." Do not touch generic.py.

### ui-U1 (fb-182): qualitative price pill, numeric-wins precedence
- **Verdict**: APPROVE
- **Metric moved**: high-conviction ratio (surfaces low-commitment positive attend signal at a glance) + required-detail surfacing. No-op on current feed (0 qualitative price strings in the 385-event snapshot) — forward-looking hardening that lights up the moment a qualitative-price source lands.
- **Reasoning**: Single-file, additive conditional, no Next.js APIs, `bg-sky-50/text-sky-700` is deliberately lighter than FREE's emerald and distinct from the conviction sky-300 ring (no signal confusion). The regex anchors `/donation|pay what|pwyc|sliding scale|suggested/i` are low-commitment word-fragments. Reachable: eventbrite.py:236 lifts raw price text verbatim, so these strings CAN populate event.price.
- **Precedence decision (the open Q the worker punted to me)**: APPROVE numeric-wins (`!/\d/` guard). Rationale: on "sliding scale $10" the dollar figure is the more actionable at-a-glance fact and one pill per card keeps the badge row clean; "$10" already communicates low-commitment to a meet-people user. Showing both would add chrome for marginal info — and the §513-516 spirit is "remove chrome over adding it." The worker's instinct was right. Ship as written.
- **EventModal**: deferring the matching sky pill is fine (modal already renders the word verbatim at EventModal.tsx:172). Do not add cross-surface consistency this round — but log a one-line fb-backlog nicety so it isn't forgotten.

## Notes back to each worker

## Notes back to ingestion-quality
- **Strong work on**: the live-probe root-cause that OVERTURNED the fb-184 premise. Running `compute_score` on actual legacy-slug batches and showing fitness=0/20, running=8/20, dance=4/20 clearing the floor — then connecting it to the eventbrite=100 cap — is exactly the depth this loop needs. You disproved a directive's own assumption, which is more valuable than executing it.
- **You missed**: the cap is ZERO-SUM and you measured only one side. You verified P1 lifts fitness events OVER the 0.55 floor, but you never measured what they EVICT. normalize.py:2096 sorts eventbrite by score descending and keeps top 100; with the feed pinned at 100/100, every boosted fitness event displaces a lower-scoring incumbent — and the most at-risk incumbents are generic music-category eventbrite events that feed the `music ≥ 15` CRITICAL_CHECK. Your P1 could, in principle, shuffle the eventbrite mix in a way sanity_check would catch. My MODIFY (dual startTime+venue gate, +0.05) shrinks the eviction footprint; next round you must report the post-scrape music count delta.
- **You missed**: the fitness category multiplier already landed last round (1.1→1.3, journal:135). So `_category_score` for a fitness event is already saturated (0.6×1.3=0.78). The events stuck at 0.36-0.51 are losing on COMPLETENESS / TITLE-QUALITY / TIME, not category. Your proposed flat boost specifically overrides those quality signals — which is the exact spam vector the 0.55 floor exists to block (normalize.py:2036-2038, the NYPL-style trim). That's why I gated on startTime AND venue rather than approving the flat additive.

## Notes back to source-curator
- **Strong work on**: the Lu.ma fallback detection — recognizing that `lu.ma/nyc/pickleball|tennis|board-games` all silently return the generic discover feed (and would inject excluded AI/founder events) is precisely the kind of silent-redundancy trap that adds noise. Correctly did NOT add them. Also good: independently corroborating the fb-184 reframe via url_health emitted_total.
- **You missed**: your line estimate "~line 233" for the GENERIC_URLS insertion is stale — line 233 is in the salsa/book-club region; the topical Eventbrite block runs ~212-248. Orchestrator should insert S1-S4 near the existing run-club/topical cluster (~line 229-248), not 233. Minor, but flag it so the add doesn't land mid-book-club.
- **You missed**: in the HELD block (trivia/climbing) you did not explicitly re-state the user_excluded_sources check the way you did for S1-S4. Per the iter-107 lesson, every add candidate must cite the check. I promoted both but made promotion conditional on that re-check — close that gap proactively next time so the Critic doesn't have to add the guard.

## Notes back to ui-agent
- **Strong work on**: the precedence analysis. You surfaced the "sliding scale $10" double-fire risk yourself, chose numeric-wins with a clear rationale, and proved it's a no-op on the current 385-event feed (0 qualitative strings) so there's zero regression risk to U1. That's complete, honest scoping.
- **You missed**: nothing material. One thought for next round — the regex `/suggested/i` is slightly broad (could match "suggested attire" or "suggested for ages 18+" if such strings ever land in `event.price`). It's fine because it only runs on the `event.price` field (not title/desc), and price-field text is short and money-oriented. But if a future source dumps non-price text into `price`, tighten to `/suggested (donation|price|contribution)/i`. Logging only; no change this round.

## Dream proposals

### D1: The loop is starving for a scrape — instrument "unlanded committed levers" and trigger a scrape gate
- **Verdict**: APPROVE-DREAM (observation + lightweight artifact; not a code change to scrapers)
- **Metric moved**: ALL THREE — indirectly but decisively. This is the 2nd consecutive code-only round with 0 metric movement because no CI scrape ran. follow-graph (30%), high-conviction (17.5%), and fitness count (29) are ALL frozen, and TWO rounds of committed levers (Meetup +4 fitness searches, +6 Eventbrite slugs, +10 IG seeds, brooklyncontra, fitness boost 1.3, and now S1-S4 + P1) are stacked unlanded. The single highest-leverage action available is not more code — it's running the scrape that lands ~3 rounds of accumulated work.
- **File**: `/Users/prajj/nyc-events/.claude/self-improve/journal.md` + a check in the orchestrator's pre-run gate (not a scraper edit).
- **Change sketch**: At run start, the orchestrator compares `git log` since the last "Quick scrape" / "Self-improve … scrape landed" commit. If ≥2 self-improve commits have landed with NO intervening scrape, emit a top-of-report banner: "STALE-FEED WARNING: N committed levers unlanded since last scrape (list). Metric deltas this round are unobservable until a scrape runs. Recommend the user trigger a CI/manual scrape before the next code-only round." This stops the loop from grinding out code-only rounds whose payoff is invisible and unverifiable, and gives the user one clear actionable. Optionally: gate the next round to scrape-dependent-only work being deferred until the scrape lands.
- **Why now / why APPROVE not DEFER**: it's a journal+report-banner artifact (read-only-safe, the orchestrator applies the banner), and the cost of NOT doing it is a 3rd blind round. Apply this round as a banner in the run summary.

### D2: Time inference from "doors at 7pm" / "8pm" in description body — directly unblocks P1's gate
- **Verdict**: DREAM-DEFER (backlog as agent-proposal)
- **Metric moved**: topic coverage + high-conviction. The fb-184 finding showed generic Eventbrite fitness events die partly on MISSING startTime (the dual-gate in my P1 MODIFY requires startTime, which many of these lack even though the time is sitting in the body text "doors at 7pm"). A body-text time extractor would let well-formed-but-time-unparsed fitness/run/dance events pass the P1 completeness gate honestly (recovering yield without lowering the quality bar) AND improve the `time_q` signal feed-wide.
- **File**: `scrapers/normalize.py` (a `_infer_time_from_text(ev)` enrichment pass before scoring) or `scrapers/quality.py`.
- **Change sketch**: regex over title+description for `/(doors?(?:\s+open)?(?:\s+at)?|starts?(?:\s+at)?)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)/i` and `/\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b/` as fallback; populate `event.startTime` only when currently empty AND a single unambiguous match exists (skip if multiple conflicting times — avoids guessing). Gate on confidence; never overwrite a parsed startTime. This is listed in README §341-369 "Time inference from doors at 7pm" — it is the most leveraged of the listed gaps because it compounds directly with this round's P1 fitness-recovery lever.
- **Backlog entry**: fb-186, source: agent-proposal, status: open, why: "Many user-requested fitness/run/dance Eventbrite-category events carry their time only in body text ('doors at 7pm') and so fail the startTime completeness gate that the fb-184 P1 recovery boost requires. A body-text time inferer recovers their yield honestly (raises completeness rather than overriding the floor) and improves time_q feed-wide. Compounds with fb-184."
