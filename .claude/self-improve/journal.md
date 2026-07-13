# Self-Improvement Journal

Every `/self-improve` run appends one entry here. Entries are append-only — earlier rounds are read for context but never rewritten.

Entry format:

```
## <YYYY-MM-DD HHMM> — run-id <slug>

**Shipped:**
- <one-liner per landed change, with file path and commit SHA>

**Rejected:**
- <proposal> — <reason>

**Deferred (still in backlog):**
- <item id> — <Critic-accepted reason>

**Metric delta:**
- Follow-graph coverage: <before> → <after>
- Topic coverage: <before> → <after>
- High-conviction event ratio: <before> → <after>

**Hypothesis for next round:**
<one or two sentences>
```

---

<!-- Future runs append below this line -->

## 2026-05-28 15:52 — run-id 2026-05-28-1552

**Shipped:**
- ingestion-P1: treat IG `feedback_required` / rate-limit / checkpoint as transient (not a strike) — `scrapers/sources/instagram.py`. Will revive 54 mass-killed accounts on the next scrape.
- ingestion-P2: source-agnostic `account` alias mirror — `scrapers/sources/instagram.py`. Unblocks the high-conviction metric.
- ingestion-P3 (modified): promote 15 socializing-oriented user_following accounts to `IG_ACCOUNTS` (excluded `timeoutnewyork` per Critic; excluded `alvinzx`/`j_palmer_7`/`leahcanel`/`sophiareed5` per user mid-run feedback fb-106) — `scrapers/config.py`.
- ingestion-P5 (modified): `_looks_like_glued_handle` predicate (safer than the camel-case regex) — `scrapers/sources/instagram.py`.
- ingestion-P6: `bk` ↔ `brooklyn` synonym fold in `interest_profile_boost` — `scrapers/utils/interest_profile.py`.
- source-pool-S1: 9 Brooklyn URLs added to `GENERIC_URLS` (all probed live, yield ≥ 8) — `scrapers/sources/generic.py`.
- ui-U1: card-level sky/amber ring + "Because you follow @X" ribbon on FeedCard + MediaFirstCard — `site/app/components/EventCard.tsx`.
- ui-U2 (modified): glyph-only `★`/`♥` conviction pill on GridCard — `site/app/components/EventCard.tsx`.
- ui-U3 (modified): "location in caption" placeholder gated on `!neighborhood` — `site/app/components/EventCard.tsx`.
- ui-U4 (modified): conviction-first sort in `diversifyByCategory` with `score ≥ maxScore − 0.2` floor — `site/app/components/TopPicks.tsx`.
- Event type: `account?: string` added — `site/app/lib/types.ts`.

**Rejected:**
- ingestion-P4 (lu.ma drop-off via normalize.py): rejected by Critic, replaced by D2. The Critic verified that 60 of 66 `LUMA_PAGES` entries return identical content to `/nyc` — a source-list bug, not a dedup bug. Pruning gated on D1 first.

**Deferred (still in backlog):**
- fb-100: run the user calibration ask next round. Critic-accepted (first-run, no real conviction events to anchor the question).
- fb-105 (D1): curator-calendar lu.ma path probing script (`scrapers/maintenance/probe_luma_curators.py`). Critic-accepted (scope of this round was the in-pipeline fixes; one-off maintenance script next round).
- fb-104 (D2): prune redundant `/nyc/<topic>` URLs from `LUMA_PAGES`. Critic-accepted (blocked-by fb-105 + additive-only rule).

**Mid-run user feedback (now durable as fb-106):**
- User: "we should not be including individual person's account from IG ... only the ones geared towards socializing ... private accounts are off the table"
- Applied immediately: removed `alvinzx`, `j_palmer_7`, `leahcanel`, `sophiareed5` from the in-flight P3 add list. Future agents must filter individual-person accounts before proposing IG_ACCOUNTS additions.

**Metric delta:**
- Follow-graph coverage: 22.2% (12/54) → unchanged this run; structural fixes (P1+P3) will move it on the next CI scrape. P1 will revive **54 transient-killed accounts** which include 6 of 8 priority signal_accounts (`vitalrunclub`, `nycbackgammonclub`, `reading_rhythms`, `bookclubbar`, `midnightrunnersnewyork`, `philosophy.nyc`). Expected to jump to ~80%+ once the next scrape lands.
- Topic coverage (`bk`): 2 → unchanged this run; S1 + P6 will move it on the next CI scrape. Expected to rise to 8+ once Brooklyn URLs are scraped.
- High-conviction event ratio: 3.3% (8/246) → unchanged this run; P2 + the un-deading of 54 accounts will surface more IG events from followed accounts. UI changes (U1/U2/U4) will make the existing 8 conviction events visibly distinguished.

**Hypothesis for next round:**
After the next CI scrape (which will pick up P1's auto-revive of the 54 transient-killed accounts), expect a big jump in IG share + follow-graph coverage. Next `/self-improve` should:
1. Actually run the calibration ask (fb-100) — by then there should be real userFollowing events to show.
2. Ship the curator-calendar probing maintenance script (fb-105).
3. Audit whether the un-deading uncovered any new caption-fragment patterns now that more posts flow.


## 2026-06-04 19:04 — run-id 2026-06-04-1904

**Shipped (commit 9eb458e):**
- ingestion-P1: OCR-garbage title detector `_looks_like_ocr_garbage` wired into `quality._is_caption_fragment` — purges glyph-artifact IG-story titles (`6» GOLIVIACRANDALL *ASTaa}`, `AA Mi, ill il th`, etc.).
- ingestion-P2 (MODIFIED by Critic): narrative/CTA fragment starters + leading-stray-quote regex in `quality.py`. Critic tightened `throwing `→`throwing a ` and `enter a `→`enter a ballot` for future-feed FP safety. P1+P2 together caught exactly 12 garbage IG titles across the 347-event feed, 0 false positives (verified live).
- ingestion-P3: Meetup group-slug enrichment in `normalize._enrich_provenance_from_url` — the curator handle lives in the URL path (`meetup.com/<slug>`), not the host SLD; folds + membership-checks it. Moves `silentbookclub.nyc` toward yield>0. Verified `jcrunners` etc. don't false-match.
- ingestion-P4: `luma._parse_luma_next_data` — reads `__NEXT_DATA__` for SPA curator calendars (ld+json yields 0 on them). Broad NYC gate (`_is_nyc_address`) + fully defensive parse. `lu.ma/nycbackgammonclub` recovered 0→6 live events; `litclub.nyc` returns [] cleanly.
- source-pool-S1 (MODIFIED by Critic): added `lu.ma/philosophy` to LUMA_PAGES (7 live NYC events, covers `philosophy.nyc`). Critic found it INERT without two deps: (1) hard-dep on P4 (same SPA shape) — both shipped together; (2) added a location-suffix-strip fold in `_user_following_normalized` so the bare `philosophy` slug matches the `philosophy.nyc` signal handle. Enrichment verified firing.
- ui-U1: plain-text `@account` provenance branch on `EventCard.tsx` FeedCard for the 68 cross-source-enriched conviction events (userFollowing + account but no instagramAccount: bookclubbar, readingrhythms-manhattan, nycforfree, silentbookclubnyc). Not the banned prose ribbon; not clickable (avoids empty AccountBanner). Build clean.
- D1 (APPROVE-DREAM): `_infer_time_from_text` fills absent startTime from "doors at 7pm / show starts at 8" body text (earliest plausible 06:00–23:59, fill-only). Wired into `process()` before the late-night filter.

**Rejected:** none this round (Critic APPROVE/MODIFY on all 6 worker proposals).

**Deferred (added to backlog):**
- fb-169 (D2): make `AccountBanner` key on `event.account` so ui-U1's plain handles become clickable per-account routes. Touches a 2nd component; ship after ui-U1 confirmed clutter-free.

**Feedback gate:** CLOSED (last calibration 2026-06-01, inside 7-day throttle; no force-ask). No user question this round.

**Still user-blocked (no code fix possible):**
- IG session 33 days stale (⛔ CRITICAL) → CI IG account-sweep degraded → 38 zero-yield signal accounts + sanity_check "Instagram dominant" CRITICAL (IG=46<50). The dominant cause of low follow-graph coverage. Needs interactive `instaloader --login` + IG_SESSION_B64 secret refresh.
- fb-139 (Reddit OAuth), fb-104 (prune redundant Lu.ma /nyc/<topic> URLs — additive-only rule).

**Metric delta (code-only round; events.json not re-scraped — deltas land on next CI scrape):**
- Follow-graph coverage: 12/50 (24.0%) → 12/50 (24.0%). Next scrape expected ~17/50 (+philosophy.nyc, +nycbackgammonclub, +silentbookclub.nyc, + reading_rhythms/nyc_forfree registering on profile rebuild).
- Topic coverage: 4/4 → 4/4 (stable).
- High-conviction ratio: 105/347 (30.3%) → 105/347 (30.3%). Next scrape: P1+P2 remove 12 OCR/caption-garbage IG titles (precision up), P3/P4/S1 add genuinely-followed non-IG events.

**Hypothesis for next round:**
After the next CI scrape, follow-graph coverage should tick up from the 3 newly-enriched non-IG accounts (philosophy/backgammon/silentbookclub) even with the IG session still stale — proving the non-IG enrichment lever works independent of the IG bottleneck. The binding constraint remains the IG-session refresh (user-blocked). Next run should re-audit the top-of-feed after the OCR purge lands and consider whether a story-specific title-quality floor is warranted (ingestion open question #4).

## 2026-06-15 17:24 — run-id 2026-06-15-1724

**Shipped:**
- ingestion-P1 (APPROVE): bk↔brooklyn synonym fold in the metrics-script topic counter — `.claude/commands/self-improve.md`. Fixed the `bk`=0 measurement bug (the fb-103 ranker fold never reached the metric, which counted literal `bk` = 0/378). bk topic 0 → 42.
- ingestion-P2 (APPROVE): story-scoped title floor in `scrapers/ranking.py::compute_score` — drops digit-prefix / imperative-prefix `isStory` titles ("2 mini lobster rolls", "45 minutes of feel Sood", "Purchase a @nike kit…"). isStory-gated so non-story digit/imperative titles untouched. Verified 0-FP.
- D1 / APPROVE-DREAM (the corrected source-pool-S1): credit NON-IG enriched (`userFollowing`) events into `yield_map` — `scrapers/utils/interest_profile.py::build_profile` second pass. Critic correctly diagnosed that follow-graph coverage reads yield_map, which was sourced ONLY from account_quality.json (IG-only) — so non-IG signal accounts (reading_rhythms etc.) sat at 0 despite producing events. Added location-suffix folding so "readingrhythms-manhattan" → "reading_rhythms". Coverage 24% → 30%.
- ui-U1 / fb-169 (APPROVE): clickable `@account` filter for cross-source-enriched conviction handles — 3 files (`site/app/lib/events.ts` load-bearing predicate now matches `event.account`; `AccountBanner.tsx` counts account-matches + `isIg` guard suppresses dead "Open on IG" link for non-IG handles; `EventCard.tsx` plain span → clickable button). next build clean.

**Rejected:**
- source-pool-S1 (Critic REJECT of the diagnosis): the reading_rhythms "handle-fold gap" was inert — the conviction fold already matches (userFollowing fires). The real issue was the yield_map data-source architecture → replaced by D1.
- source-curator 0 source-adds: APPROVE (honest negative; nothing cleared ≥5 live yield via a parseable path).

**Deferred (backlog):**
- D2 → fb-178: "Did you go?" attend/skip affordance on past saved events (closes the calibration loop; needs storage/ingest design).
- 2 IG-Story residuals ("Great vibe 1010 experience", "Dance your cares away") — not in current feed, no FP-verifiable rule with 0 live instances (fb-175 stays open).

**Feedback gate:** CLOSED (user gave extensive direct feedback over the prior 11 days; logged it as fb-171–176; no calibration question this round).

**User-blocked (routed around, not fixed):** fb-174 (IG GraphQL sweep 400-blocked fleet-wide), fb-173 (CI runner IP 403/429-blocked by many publishers), fb-139 (Reddit OAuth).

**Metric delta:**
- Follow-graph coverage: 24.0% (12/50) → 30.0% (15/50) [D1]
- Topic coverage: bk 0 → 42; no zero topics remaining [P1]
- High-conviction ratio: 18.3% → 17.5% (intentionally stable — the prior 30→18 quality-cleanup drop is preserved, not relaxed; P2 dropped 3 more garbage stories)

**Verification:** next build clean; 253 tests pass; sanity_check has 2 criticals (backgammon, IG-dominant) — BOTH pre-existing data conditions, NOT caused by this run's code-only edits (events.json unmodified by the edits; confirmed). No revert.

**Hypothesis for next round:** D1 establishes that non-IG enrichment can move follow-graph coverage independent of the IG block — future rounds can push coverage further by enriching more signal accounts' events via non-IG sources (lu.ma curators, venue sites). The IG sweep + CI-IP blocks remain the binding constraints (user-action / infra). Consider implementing fb-178 (attend feedback) to start building calibration ground-truth.

## 2026-06-22 1501 — run-id 2026-06-22-1501

**Theme:** user-explicit (this session) — "more fitness-based events + run clubs (recurring too)" (fb-179) and "add contra dancing brooklyn" (fb-180). Both implemented in-session before the loop ran; the loop audited, hardened, and broadened them.

**Shipped (pre-loop session work + loop edits, all in this run's commit):**
- fb-179 (fitness/run-clubs): Meetup +4 run-club/running/fitness search URLs (`scrapers/sources/meetup.py`); removed `"running club"` from SOFT_PENALTY_KEYWORDS (`scrapers/quality.py`); fitness boost 1.1→1.3, wellness 1.05→1.2, +10 run-club/fitness IG seeds (`scrapers/config.py`). All +10 seeds fb-106-clean (clubs/orgs/studios).
- fb-180 (Brooklyn Contra): new dedicated `scrapers/sources/brooklyncontra.py` (Squarespace-store parser; date-from-title; year inference), registered in `run_all.py` + `SOURCE_QUALITY=0.8`; `DISTINCT_SCHEDULE_SOURCES` exemption in `normalize.py`.
- ingestion-P1 (APPROVE): scope-skip "every <weekday>" soft-penalty for fitness/wellness/outdoors text — `scrapers/quality.py::quality_signals`.
- ingestion-P2 (MODIFY): generalized `\b<hint>\b` word-boundary matching for short single-word exclusion title-hints (len≤6/no-space/alpha), precompiled+cached — `scrapers/ranking.py`. Fixes fb-181 ('rave'→"Raven & Goose").
- ingestion-P3 (APPROVE): DISTINCT_SCHEDULE_SOURCES also bypasses `_dedup_fuzzy_title` — `scrapers/normalize.py`. Contra 8→10 (both Sep-26 sessions recovered).
- source-pool S1–S3,S5,S6 (APPROVE) + S4 (MODIFY/provisional): +6 live-probed Eventbrite slugs (run-club/contra/swing/folk/salsa/pilates), 20/20 future each — `scrapers/sources/generic.py`. Curator finding: existing broad running/yoga/fitness/dance slugs are INERT (0-yield) — flagged for ingestion next round.
- ui-U1 (APPROVE): non-free digit-price pill on FeedCard — `site/app/components/EventCard.tsx`.

**Rejected:** none — Critic APPROVE/MODIFY on all 11 proposals; zero directives deferred-rejected.

**Deferred (added to backlog):** D1→fb-182 (qualitative price-word pills); D2→fb-183 (shared `_is_distinct_schedule_source` helper + queued fb-106-clean IG fitness/dance candidates for when fb-174 clears).

**Feedback gate:** CLOSED (≥3 open items; newest user-explicit feedback is this session). No calibration question. Captured this session's two requests as fb-179/fb-180.

**Metric delta (code-only round; events.json not re-scraped — deltas land on next CI scrape):**
- Follow-graph coverage: 15/50 (30.0%) → 15/50 (30.0%).
- Topic coverage: 0 zero-topics → 0 zero-topics (run=26, bk=42 stable; run-club/dance slugs reinforce run+dance next scrape).
- High-conviction ratio: 64/365 (17.5%) → 64/365 (17.5%).

**Verification:** 253 tests pass; next build clean; sanity_check 2 criticals (backgammon, IG-dominant) — IDENTICAL to pre-run, pre-existing data conditions (fb-174 IG block), NOT regressions (events.json unmodified). No revert. Note: the configured black formatter reflowed long lines across config/normalize/run_all/generic (cosmetic, behavior-preserving; content verified intact — IG_ACCOUNTS 167→176, SOURCE_QUALITY +brooklyncontra). Test-induced state-file churn (url_health/user_interest_profile) reverted to HEAD.

**Hypothesis for next round:** the fitness/run-club/dance levers are now in place but their payoff is gated on the next CI scrape (Meetup live-verified 74 fitness/run events; Brooklyn Contra 10 dated dances verified through normalize). Next round should: (1) re-probe the 6 NEW Eventbrite slugs' LANDED yield (esp. folk-dance/pilates for performance/studio-spam) and the provisional S4; (2) investigate WHY the 6 legacy fitness slugs yield 0 (silent JSON-LD shape change — could recover yield cheaply); (3) measure the fitness/dance event-count lift in the deployed feed.

## 2026-06-23 1816 — run-id 2026-06-23-1816

**⚠ STALE-FEED (D1, headline):** 2nd consecutive code-only round with 0 observable metric movement — no CI scrape has run since ~2026-06-15. ~3 rounds of committed levers are stacked UNLANDED (last round's Meetup/Eventbrite/IG/contra/boost + this round's). The single highest-leverage action now is a SCRAPE (residential IP per fb-173), not more code. Deltas for all of it are unverifiable until `run_all` runs.

**Premise overturned this round:** fb-184 assumed 6 legacy Eventbrite fitness/dance slugs were INERT (0-yield). BOTH backend workers live-disproved it: the slugs parse ~20 events each; events die DOWNSTREAM at MIN_SCORE 0.55 + the eventbrite=100 cap (e.g. fitness 0/20 clear the floor), not at extraction. fb-184 re-scoped from parse-fix → score-recovery.

**Shipped (commit <sha>):**
- ingestion-P1 (MODIFY): fb-184 score-recovery — +0.05 for fitness/wellness/outdoors (+ run-club/yoga/pilates/contra/swing text) HARD-GATED on `startTime AND location.name` so low-info events still floor out (preserves the 0.55 quality gate; self-limited by the existing +0.06 clamp) — `scrapers/ranking.py`. Verified: well-formed 0.637 clears, low-info 0.536 floored. Critic tightened worker's "OR" gate to "AND" + dropped +0.06→+0.05 to shrink cap-eviction footprint on music-category events.
- ingestion-P2 (APPROVE, fb-183): extracted `_is_distinct_schedule_source(ev)` helper used by both dedup passes + 3 unit tests (bypasses BOTH passes; control merges) — `scrapers/normalize.py`, `scrapers/tests/test_normalize.py`.
- source-pool S1–S4 + trivia + climbing (APPROVE/promote): +6 Eventbrite slugs (hiking, walking-tour, board-games, chess, trivia, climbing), all live-probed ≥19 future + exclusion-clean; cap-bound (deepen pool). Corrected the now-false "INERT slugs" comment — `scrapers/sources/generic.py`.
- ui-U1 (APPROVE, fb-182): qualitative low-commitment price pill (donation/PWYC/sliding-scale), sky-50/700, numeric-wins precedence — `site/app/components/EventCard.tsx`. No-op on current feed; lights up when a qualitative-price source lands.

**Rejected:** none — Critic APPROVE/MODIFY on all proposals.

**Deferred (backlog):** D2→fb-186 (strengthen body-text time inference; compounds with P1's startTime gate). P1b→fb-185 (prune dup Brooklyn running slug — additive-only, user opt-in). fb-187 (folk-dance provisional ~55% participatory watch). fb-188 (EventModal price-pill consistency nicety).

**Feedback gate:** CLOSED (no new user feedback; ≥3 open items; newest user-explicit feedback fb-179/180 from yesterday). No question.

**Metric delta (code-only; events.json not re-scraped — deltas land next scrape):**
- Follow-graph coverage: 15/50 (30.0%) → 15/50 (30.0%).
- Topic coverage: 0 zero-topics → 0 zero-topics (stable).
- High-conviction ratio: 64/365 (17.5%) → 64/365 (17.5%).

**Verification:** 256 tests pass (253+3 new); next build clean; sanity_check 2 criticals (backgammon, IG-dominant) IDENTICAL to pre-run — pre-existing data conditions, not regressions (events.json unmodified). No revert. Test/probe-induced `scrapers/data/` churn reverted to HEAD (code+docs-only commit).

**Hypothesis for next round:** STOP grinding code-only rounds — RUN A SCRAPE first to land ~3 rounds of accumulated fitness/dance/contra levers, then measure. Post-scrape, confirm: (1) fitness/run/dance event count rises (P1 + 12 new slugs), (2) the eventbrite=100 cap didn't evict music below its CRITICAL_CHECK floor of 15 (P1 cap-eviction risk), (3) folk-dance landed participatory ratio (fb-187), (4) brooklyncontra 10 dances + recurring run clubs present. If a scrape still can't run (IG/IP blocks), the binding constraint is infra/user-action, not code.

## 2026-07-02 1735 — run-id 2026-07-02-1735

**⚠ STALE-FEED (3rd consecutive frozen round):** feed unchanged since 2026-06-15 (408h). Metrics frozen at 30.0% / 0-zero-topics / 17.5% for the 3rd round running. ~4 rounds of committed levers remain UNLANDED. Between the last self-improve run and this one, direct user requests were handled (committed, unpushed): 8d10fc2 (lu.ma/philosophy shell+floor fix, philosophy 0→7, + source-survival audit tool + test-flake fix — fb-190) and b6a0cf3 (openbookclub IG seed fb-191; UI day-scent/location-dedup/slate-hero/empty-copy fb-192). This round deliberately scoped to scrape-INDEPENDENT verifiable work only (per D1 gate).

**Shipped (commit <sha>):**
- ingestion-fb189 (APPROVE): neighborhood/venue-name contradiction fix — `_explicit_hood_in_text` Step-0 in `_backfill_neighborhood_from_venue` (explicit word-boundaried neighborhood token in name/addr wins over venue-table default + address inference) + word-boundary match for short ≤3-char keywords (les/ues/uws) in `event_parser.infer_neighborhood`. Critic-verified on frozen feed: conflicts 10→0, also fixed "Singles Night"→LES mistag, WGB CRITICAL_CHECK 36→38, no regression. +5 tests.
- ingestion-fb186 (APPROVE): rebuilt `_infer_time_from_text` (keyword-anchored cues earliest-wins + guarded bare-clock am/pm fallback; ranges/multi-time abstain; fill-only, never overwrite). Critic adversarially probed 13 hostile inputs. +15 tests. Unblocks the fb-184 fitness startTime gate.
- ui-fb188 (APPROVE): EventModal price-pill parity with FeedCard (numeric-gray + qualitative-sky; junk strings render nothing).

**Process note:** the ingestion worker APPLIED (not just proposed) its changes via Bash; the Critic reviewed the live diffs (verifying independently, not trusting the report) and APPROVED both to stay. UI proposed→applied by orchestrator. source-curator died mid-response (API error), re-invoked once per operational rule → validation-only pass succeeded (12 IG seeds fb-106/exclusion-clean; folk-dance lean-keep).

**Rejected:** none — Critic APPROVE on all 3.

**Deferred (backlog):** D1 (Did-you-go calibration) → already tracked as open fb-178, not duplicated. D2 (venue alias normalization) → new fb-193 (compounds with fb-189 Step-0).

**Feedback gate:** CLOSED (newest user-explicit feedback is today; ≥3 open items). No question. Captured this session's user requests as fb-190/191/192 (addressed).

**Metric delta (code-only; events.json not re-scraped — frozen):**
- Follow-graph coverage: 15/50 (30.0%) → 15/50 (30.0%).
- Topic coverage: 0 zero-topics → 0 zero-topics.
- High-conviction ratio: 64/365 (17.5%) → 64/365 (17.5%).

**Verification:** 289 tests pass (20 new); next build clean; sanity_check 2 criticals (backgammon, IG-dominant) IDENTICAL to pre-run — pre-existing frozen-feed artifacts, not regressions. No revert. Probe/test-induced `scrapers/data/` churn reverted to HEAD.

**Hypothesis for next round:** The binding constraint is now unambiguous and has held for 3 rounds: **a scrape must run.** Code quality is well ahead of what the frozen feed can demonstrate. Next action should be a residential-IP `run_all` (Critic + source-curator both endorse), then a round that MEASURES: fitness/dance count, philosophy surfacing (0→~7 expected), neighborhood-conflict count (→0), music CRITICAL_CHECK not cap-evicted, brooklyncontra + recurring run clubs present. Absent a scrape, further code-only rounds have sharply diminishing value.

## 2026-07-13 2033 — run-id 2026-07-13-2033

**Context:** first round on a FRESH feed after the /plan program landed (run coverage 26→46, conviction 17.5%→22.5%). Tackled the deferred critic items on real data.

**Shipped (commit f53488a):**
- fb-194 (APPROVE): Queens/LIC neighborhood mistag fix — `infer_neighborhood` borough checks before the manhattan fallthrough + Queens hoods (LIC/Astoria/Ridgewood/Flushing/Rockaway); `_VENUE_NAME_TO_NEIGHBORHOOD` moma ps1→LIC + longest-key-wins. Queens-mistag 14→1, null 15.6%. +11 tests. Critic adversarially verified no Brooklyn/Manhattan regression.
- fb-196 (APPROVE, coverage gaps): Chess Place (o/115357260611) + Harlem Swing Dance (o/10662501681) Eventbrite organizers → curated; backgammon + chess Meetup keyword searches → meetup.py (also feeds NYC-Backgammon CRITICAL); Elsewhere organizer (o/105655500371) added boost-only.
- Elsewhere floor_bypass:false (Critic S4 MODIFY): new `_is_curated_host(floor_context=True)` + `no_floor_hosts` set — boost-only curated hosts get +0.15 but still clear the 0.55 floor (bounds late-night leak). Verified.
- openbookclub via Substack (user-directed, MODIFY): openbookclubnyc.substack.com → FEEDS + curated + must_surface. Non-roundup posts date to pubDate (no fabrication, verified); surfaces on future posts.
- UI U3 (mobile responsive: card image w-20 sm:w-24, modal max-h-90vh sm:95vh) + U4 (discovery heroes 6→4, ranked feed surfaces sooner; heroes preserved).

**Deferred:** fb-195 keyword-retirement (SOUND — taste 0.03 mean << keyword 0.12-0.15, zero negatives; would regress). UI U1 conviction chip + U2 aria/focus → task #6 (visual pass). Dreams D1→fb-199 (retire zero-hit keyword clusters), D2→fb-200 (ZIP-priority tie-break).

**Rejected:** none (Critic APPROVE/MODIFY on all).

**Feedback gate:** CLOSED (newest user-explicit 2026-07-09). Captured the /plan program (fb-197) + critic-incorporation (fb-198) + openbookclub-substack (fb-201).

**Metric delta:** follow-graph 30.0%→30.0%; topic all-present (run 46); conviction 17.5%→22.5% (program landing, not this commit — this commit's source/neighborhood deltas land next scrape).

**Verification:** 310 tests pass; sanity_check Critical failures 0 (IG reframed to warning last round); next build clean. Elsewhere floor_bypass verified (shell-survives, floor-gated, +0.15 boost).

**Hypothesis for next round:** after the next scrape, verify backgammon/chess/swing/Elsewhere counts rise and MoMA→LIC. The keyword→taste retirement (fb-195/199) unblocks once the client syncs real engagement (adds negative taste examples + raises taste magnitude); until then the taste signal is follow-graph-seeded (positive-only). Consider the client-sync onboarding nudge to get real engagement flowing.
