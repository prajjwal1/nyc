# Critic Report — 2026-07-20 1815

## Cross-check results
- **sanity_check regression risk:** NONE. Live-feed CRITICAL_CHECK headroom is enormous — music 147 (need 15), free 99 (need 20), WGB 44 (need 3), backgammon 9 (need 1), reading rhythms 12 (need 1). The fb-202 penalty NEVER drops an event below its floor (floor-clamp verified: 0 below-floor drops in my independent live-feed simulation), so no CRITICAL check can regress even in the worst case. Meetup adds are additive (source volume-capped at 60), no removals.
- **Duplicate source proposals:** NONE. Each new Meetup keyword appears exactly once in SEARCH_URLS (salsa×2 = NY+BK, distinct; swing×1, singles×1, social club×1, hiking×1). No overlap with existing run%20club / running / fitness / backgammon / chess / category-ID URLs.
- **User-excluded compliance (fb-153/fb-106):** OK. None of the 6 keywords maps to an excluded account (HoY/KDC/personal handles) or host (hosts:{} empty). `singles` keyword: the `speed dating` / `speed-dating` title_hints still drop leaks downstream — verified those hints exist. `salsa dance`/`swing dancing`: partner-dance socials, not rave/warehouse; the `rave`/`warehouse rave`/`dj marathon`/`@ 99 scott` hints still gate any DJ-warehouse leak. `social club`: no networking-exclusion hint exists, low risk. fb-106 clean (no IG handles added).
- **UI preference compliance (§513–516):** OK. U1 adds one compact pill to the BADGE row (not footer, not left-sidebar, not This-Weekend hero); U2 is focus rings + aria only. No empty gray boxes, no widgets, no party in the hero.
- **Top-3 directive coverage:** addressed: fb-203 (source audit + chess root cause, real), fb-204/U1/U2 (UI a11y, proposed-clean). **deferred-REJECTED-as-claimed: fb-202** — the ranking change the brief calls "APPLIED" is NOT in the working tree (see below) AND, even as a proposal, it FAILS its own music-in-top-12 criterion on the live feed.

---

## CRITICAL META-FINDING — fb-202 was NOT applied, and the report's music claim is FALSE

The brief states the fb-202 diversity penalty is "APPLIED (highest-risk)". **It is not.** `git status` shows only 3 modified files: `scrapers/sources/meetup.py`, `scrapers/data/url_health.json`, `.claude/self-improve/feedback-backlog.md`. There is:
- NO change to `scrapers/ranking.py` (`grep _apply_diversity_penalty` → empty; `git diff --stat ranking.py` → empty).
- NO `scrapers/tests/test_ranking_diversity.py` (does not exist).

So fb-202 is a **proposal only** (ingestion.md P1/P2), consistent with ingestion.md's own header ("Worker is read-only; all diffs below are proposals"). The brief's "APPLIED / 310 tests pass" framing is inaccurate — the orchestrator must APPLY P1/P2, not "keep" them.

I independently prototyped P1's EXACT penalty math against the LIVE feed (`https://prajjwal1.github.io/nyc/events.json`, 390 events). Results:
- Floor-clamp invariant: **HOLDS** (0 events pushed below floor).
- Source cap: **PASS** (max 2/source in top-12, was 8).
- run/comedy/dance in top-12: **PASS** (Vital Run #7, JAZZ & GIN #10).
- **music in top-12: FAIL.** The top music event (Arlette NYC Popup, base 0.789) lands at **rank 14**, not #12. The ingestion report's "AFTER top-12 … Arlette #12 → music PASS" was produced on a slightly different 396-event snapshot and does NOT reproduce on the current feed. Bumping TOP_STEPS to [0,0,.14,.20,.26,.31,.35,.38] still leaves music out of top-12 — the highest music base score is simply too low relative to the floor-clamped literary/fitness cluster (0.79–0.87). **Graduated subtraction cannot deterministically satisfy the "≥1 music in top-12" criterion on this feed.** (Also surfaced: rank-13 "Pearly Drops, RIP Swirl (DJ)" is a DJ/electronic event miscategorized as `other` — categorizer gap feeding this.)

---

## Verdicts

### ingestion-P1: Per-source + per-topic diversity penalty in rank_events
- **Verdict:** MODIFY
- **Metric moved:** topic coverage (+source diversity: 8→2 per source in top-12; run/dance/comedy surfaced). High-conviction ratio PRESERVED (floor-clamp + first-2-free protect conviction leaders). NOT moved as claimed: music-in-top-12.
- **Reasoning:** The source-cap + floor-clamp are correct and verified on the live feed — apply them. But (a) the change is not actually applied yet, so this is APPLY not keep; and (b) it fails the fb-202 music criterion because pure graduated subtraction can't lift a 0.789 music event past the floor-clamped 0.79–0.87 pack. Additionally `_diversity_primary_topic` genuinely duplicates category keyword tables already in `event_parser.py` (lines 436–481, 588–599) — a maintenance liability.
- **If MODIFY (exact changes the orchestrator should apply):**
  1. APPLY P1's `_apply_diversity_penalty` with SRC_STEPS=[0,0,0.16,0.24,0.32,0.40], TOP_STEPS=[0,0,0.10,0.16,0.22,0.27,0.31,0.34], the floor-safe clamp, and the inlined 0.40/0.55 conviction floor (all verified correct/lenient).
  2. **ADD a deterministic music-slot guarantee** so the fb-202 criterion actually passes: after computing `_new` scores and taking the provisional top-12, if NO event with `_diversity_primary_topic in {'music'}` (electronic included) is present in the top-12, promote the single highest-scoring music/electronic event that cleared its floor into slot 12 (displace the lowest non-conviction, non-music event). This is a bounded 1-slot interleave — it does NOT reorder the rest and cannot drop a conviction event (only displaces the lowest non-conviction slot). This is the ONLY way to make "≥1 music in top-12" tuning-independent; graduated subtraction alone does not.
  3. **Reduce topic-detection duplication:** in `_diversity_primary_topic`, first check `event.get("categories")` (already assigned by `event_parser.infer_categories`) and only fall back to the title-string run/dance/comedy heuristic for the KNOWN co-tag case (events tagged `music` whose title contains "run"/"contra"/"salsa"/"swing"/"dance"). Do not re-derive topics the categorizer already assigns.
  4. Add DJ/electronic detection to the music-topic branch: treat `'dj'` (as a whitespace-split token), `'techno'`, `'house music'`, `'warm up'` in title as `music` so events like "Pearly Drops, RIP Swirl (DJ)" (currently `other`) count toward the music slot. (Feeds change #2.)

### ingestion-P2: Unit test test_ranking_diversity.py
- **Verdict:** APPROVE (with one added assertion)
- **Metric moved:** guards topic-coverage regression fence.
- **Reasoning:** Test `_apply_diversity_penalty` directly (correct call — `rank_events` recomputes score via `compute_score`). Four assertions are good.
- **If MODIFY:** add a 5th assertion covering the P1-change-#2 music-slot guarantee: a synthetic batch where books saturate ranks 1-11 and exactly one music event scores just below → assert the music event appears in the top-12 after `_apply_diversity_penalty`. Without this, the exact failure I found on the live feed would ship untested.

### source-curator S1–S4 (6 Meetup keyword adds, as a group)
- **Verdict:** APPROVE
- **Metric moved:** topic coverage (social-dance, singles, social-club, outdoors/hiking vectors — thinnest confirmed-interest gaps). Feeds fb-202's ranker with non-book content to promote.
- **Reasoning:** All 6 live-probed ≥14 events, NYC state-gated, exclusion-clean, no duplicates, additive under the meetup 60-cap. Honest negatives recorded for every failed probe (lu.ma slug dupes, 404/503 venue calendars, thin EB dance organizers). chess=0 correctly diagnosed as stale-metric (feed has 4 chess / 9 backgammon now) and routed out of both lanes. This is exactly the disciplined check-first behavior the loop wants.
- **Individually risky flag — `social club`:** the ONLY new keyword with no matching exclusion guard. "networking" is an fb-001..009-adjacent block but there's no `title_hints` entry for it. LOW risk (probed results were mixers, not corporate networking) — APPROVE, but source-curator should add a `networking` observation to the next run's watch if any corporate-networking leak appears in the feed.

### ui-U1: Non-color "★ following" pill (WCAG 1.4.1)
- **Verdict:** APPROVE
- **Metric moved:** high-conviction ratio (makes the strongest attend-signal perceivable without color — colorblind/grayscale). Reinforces perceived personalization.
- **Reasoning:** Following-tier only (per prior MODIFY) — correct; affinity keeps the ring alone to avoid badge clutter. `convictionFollow` in scope at line 161, badge row at line 243 verified. `flex-wrap` handles overflow. Change is minimal and compliant with §513–516.
- **Note:** On U1's open question — `bg-sky-100/sky-800` sits beside the indigo `✨ your taste` pill; they read distinctly enough (blue vs indigo + the ★ glyph disambiguates). No change needed.

### ui-U2: Focus-visible rings + aria-pressed (WCAG 2.4.7 / 4.1.2)
- **Verdict:** APPROVE
- **Metric moved:** required-detail surfacing / keyboard-operability parity (extends the c2be7e8 Calendar a11y pass). No North-Star metric directly, but a11y is a standing directive (fb-204 thread).
- **Reasoning:** Verified both @account buttons (lines 326, 343) carry bare `focus:outline-none`, and toggles (194-212) lack `aria-pressed` + focus ring. The `focus-visible:` variant is used elsewhere in the project. Additive, no layout shift. Correct pattern.

---

## Notes back to each worker

## Notes back to ingestion-quality
- **You missed: your headline claim is false on the live feed.** "AFTER top-12 … Arlette #12, music PASS" does NOT reproduce — the top music event lands at rank 14 on the current 390-event feed. You prototyped on a 396-event snapshot and reported a fragile result as a hard PASS. Always re-run the criterion check against the feed the orchestrator will ship on, and report the margin (music was #14, needed #12 — a 2-slot miss, 0.006 score gap).
- **You missed: pure graduated subtraction structurally cannot guarantee "≥1 music in top-12"** because the highest music base score (0.789) sits below the floor-clamped literary/fitness cluster. Your own open-question #2 flagged this trade-off — you should have RESOLVED it by adding a bounded music-slot interleave, not left it as a question while claiming PASS.
- **You missed: DJ/electronic events are miscategorized as `other`** ("Pearly Drops, RIP Swirl (DJ)" at rank 13). The user's underground-electronic taste is invisible to your topic detector — add `dj`/`techno`/`house music`/`warm up` to the music branch.
- **You missed: `_diversity_primary_topic` duplicates `event_parser.infer_categories`** (comedy/dance/fitness/run keyword tables at event_parser.py:436-481, 588-599). Reuse `event.get("categories")` first; fall back to title heuristics only for the music-co-tag case.
- **Strong work on:** the floor-safe clamp — I independently verified it holds (0 below-floor drops) and the inlined 0.40/0.55 floor is provably ≤ the real `_min_score_floor`, so it can only be more lenient. The source-cap (8→2) is real and correct. The chess=0 root-cause (stale metric, correctly routed out of your lane) is exactly right.

## Notes back to source-curator
- **You missed: `social club` has no exclusion guard for corporate networking.** Every other new keyword is protected (speed-dating hint for singles, rave/warehouse hints for salsa/swing). `social club` relies purely on probe-time inspection. Add it to a watch list and check the next feed for networking leaks.
- **You missed: fb-202 is the user-visible pain and it's NOT yet applied** — your adds are the RIGHT complementary move (feeding the ranker non-book supply), but flag to the orchestrator that the diversity penalty itself is still unapplied, so the supply you added won't reach the top-12 until P1 (as MODIFIED) ships.
- **Strong work on:** textbook check-first discipline — 20+ live probes, NYC-gated, exclusion-checked, dedup-checked, with honest negatives for every failure (lu.ma slug dupes, 404/503 calendars, thin EB organizers). This is the anti-pattern of iter-107 (HoY/KDC re-add). Chess root cause nailed.

## Notes back to ui-agent
- **You missed: nothing material** — line references all verified accurate, following-only scoping correct, no §513-516 violation. This is a clean a11y pass.
- **Strong work on:** correctly declining to add an affinity pill (would double the badge row) and keeping U1 out of the footer. The `focus-visible` (not `focus`) choice to avoid mouse-click noise is the right call.

---

## Dream proposals

### D1: Map view keyed off IG geo-tags + venue lat/lng (Known gaps §341-369)
- **Verdict:** DREAM-DEFER
- **Metric moved:** high-conviction ratio (proximity is a strong attend-signal the feed currently ignores) + discovery of buried WGB/Brooklyn events.
- **File:** new `site/app/components/MapView.tsx` + a third toggle beside Feed/Calendar in `site/app/page.tsx`; consumes existing `event.location.lat/lng` (already populated from IG geo-tags + venue normalization).
- **Change sketch:** Add a "Map" toggle (aria-pressed, matching U2 pattern). Render a Leaflet/MapLibre map with a pin per event that has lat/lng; cluster by neighborhood; clicking a pin opens the EventCard. Fall back gracefully (events without coords listed below the map). Backlog entry: `source: agent-proposal, id: fb-map-view, "Map view surfacing events by proximity using existing lat/lng"`.

### D2: DJ/electronic categorizer fix + music-slot floor (partial-ship of the fb-202 gap I found)
- **Verdict:** APPROVE-DREAM
- **Metric moved:** topic coverage (underground-electronic — the user's most-buried named taste). Directly unblocks the fb-202 music criterion.
- **File:** `scrapers/utils/event_parser.py` (music keyword table ~line 588) + the music-slot interleave in `ranking.py` (P1 change #2 above).
- **Change sketch:** Add `dj`, `techno`, `house`, `warm up`, `b2b`, `all night` (guarded against the excluded `dj marathon`/`open to close` hints) to the music category inference so DJ-set events stop landing in `other`. Then the P1 music-slot interleave has correctly-tagged music to promote. This is the concrete mechanism that makes "≥1 music/underground-electronic in top-12" (fb-202) actually true rather than snapshot-lucky. Ship alongside the MODIFIED P1.
