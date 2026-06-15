# Critic Report — 2026-06-15 1724

## Cross-check results
- **sanity_check regression risk**: none. P1 edits only our own metric script (`self-improve.md`), not pipeline logic. P2 is `isStory`-gated (7 events) and verified to drop only 3 garbage stories while preserving "Reading Rhythms" (the CRITICAL_CHECK keyword) — confirmed against /tmp/si_feed.json. No CHECK touched.
- **Duplicate source proposals**: none — source-curator proposed 0 adds (honest negative, verified sound below).
- **User-excluded check**: N/A — 0 source adds this round. (Spot-checked `user_excluded_sources.json`: houseofyesnyc/knockdowncenter still present; no proposal collides.)
- **UI preference compliance**: ok. ui-U1 reuses the existing IG-button pattern (no new widget, no gray box, no sidebar, no parties-in-hero). AccountBanner empty-guard preserved. `isIg` guard prevents a dead "Open on IG" link. Compliant with §513–516.
- **Top-3 directive coverage**: addressed: #1 (fb-176 bk gap via P1), #2 (fb-175 OCR fragments via P2, 3 of 4 live residuals), #3 (fb-169 UI via ui-U1). deferred-acceptable: 2 not-in-feed residuals (no FP-verifiable rule with 0 live instances). deferred-REJECTED: source-curator's framing of directive #3's enrichment half — see S1 (the diagnosis is wrong; the metric will NOT move from a handle-fold).
- **Conviction-drop guard (30%→18%)**: confirmed — NO proposal relaxes filters. P2 *tightens* (drops 3 garbage). Compliant.

## Verdicts

### ingestion-P1 — APPROVE
- **Metric moved**: topic coverage (`bk` 0 → 43; clears ≥5 target).
- **Reasoning**: Verified independently — literal `bk` substring = 0/378, `brooklyn` = 43 on /tmp/si_feed.json. The metric script (`self-improve.md:58-62`) uses `if t in txt` literal-substring matching with no synonym fold, so the fb-103 ranker fold has no path to the topic number. Editing our own metric script is acceptable (it is instrumentation, not pipeline). The proposed `TOPIC_SYNONYMS` fold is correct and symmetric.
- **One tightening for the orchestrator**: the worker's snippet recomputes `topic_rep` and the loop but the live script (L58-62) currently lacks `TOPIC_SYNONYMS`. Apply exactly the worker's diff, and ALSO mirror it in the **metrics-after** generation path if that path re-derives topic_rep separately (it uses the same inline script, so a single edit covers both). Do NOT touch `sanity_check.py:441` — see open-question answer below.

### ingestion-P2 — APPROVE
- **Metric moved**: high-conviction quality (drops 3 garbage followed-IG stories; the legit 18% members untouched).
- **Reasoning**: Verified independently against ALL 378 events. The 7 isStory events split exactly as claimed: DROP = {"2 mini lobster rolls", "45 minutes of feel Sood", "Purchase a @nike federation kit and get a free cheer"}; KEEP = {"Reading Rhythms", "A Space For The Work You've", "Seconds Run Club", "Block, a free beauty and cultural experience"}. The must-survive case "Block, a free beauty…" survives (starts with a letter). Scope-gate confirmed safe: the 7 legit non-story digit/imperative titles (100 Page Book Club, 6th Annual Juneteenth, 2026 NY Summer Festival, 718 Sessions PRIDE, Get the Beauty Scoop, 4TH OF JULY ROOFTOP, 4th of July Fireworks) are ALL untouched because the guard is `isStory`-gated. Zero FP today.
- **Note for orchestrator**: ship the guard exactly as written (`return 0.0` after the caption-fragment nuke, ~L53). The `import re as _re` inside the function is harmless but prefer hoisting to module scope if `re` is already imported there — cosmetic only, not blocking.

### source-curator (0 adds) — APPROVE (negative is sound)
- **Metric moved**: none (correctly). 
- **Reasoning**: The full non-IG sweep is documented with per-URL evidence (404/0-yield/JS-gated). Nothing cleared the ≥5 live-yield bar through a parseable path. Padding with 0-yield sources would violate the additive-discipline + hard rule. The honest negative is the right call. The productive non-IG paths (readingrhythms-manhattan, litclub.nyc, philosophy, nycbackgammonclub, bondandgrace, bookclubbar, lizsbookbar) are already in config.

### source-pool-S1 (reading_rhythms "enrichment-fold bug") — REJECT (diagnosis) / MODIFY (into the real fix, route to ingestion)
- **Metric moved (as proposed)**: ZERO. The proposal as framed does not move the metric.
- **Reasoning**: I traced the actual code path and the worker's diagnosis is **incorrect on two counts**:
  1. **There is no handle-fold gap.** `_handle_candidates('readingrhythms-manhattan')` already produces the alphanumeric collapse `readingrhythms`, and `_user_following_normalized()` collapses `reading_rhythms` → `readingrhythms` the same way. They ALREADY match — which is exactly why every `readingrhythms-manhattan` luma event in the feed fires `userFollowing=True` (verified: 12 such events, all `userFollowing:true`). The conviction path works. A hyphen/underscore alias fix moves nothing because it is already done (`normalize.py:1076-1098`).
  2. **The follow-graph COVERAGE metric reads `yield_map`, which is structurally IG-only.** `build_profile()` (`interest_profile.py:116-122`) computes `yield_map[u] = events_emitted/posts_scraped` sourced **exclusively from `account_quality.json`**, which is written **only by `scrapers/sources/instagram.py:468` (`_save_account_quality`)**. Luma curator events never write it. Verified: all 12 yield>0 accounts have an `account_quality.json` entry; `reading_rhythms`, `nycbackgammonclub`, AND `philosophy.nyc` have NO entry → all three show 0.0. The journal's repeated prediction ("coverage should tick up next scrape" — journal L60, L94, L99) has now failed across ≥3 iterations for exactly this reason: the IG sweep is blocked (fb-174), so no IG posts → no quality entry → no yield, regardless of how many luma events those accounts produce.
- **Verdict**: REJECT the proposed handle-fold change (inert), but the *underlying observation* (high-conviction luma accounts stuck at yield 0) is real and high-value. **MODIFY into the real fix** — see Dream D1 below, which I am APPROVING this round to actually move the metric. This is a measurement-architecture fix, not a normalization fix. Route to **ingestion** next round (or apply D1 now).
- **Caveat the worker got right**: the Long Island "Reading Rhythms" event is non-NYC; flag for a future NYC-strictness pass on curated hosts (low priority, single instance).

### ui-U1 (fb-169, 3-file) — APPROVE
- **Metric moved**: high-conviction ratio (visibility) — turns 62 dead conviction-provenance handles into working per-account browse routes; surfaces the user's calibration-validated literary follows (bookclubbar 17, readingrhythms-manhattan 12, litclub.nyc 12, nycforfree 19, silentbookclubnyc 2).
- **Reasoning**: I confirmed the 3-file claim is CORRECT and the lib fix is load-bearing. `lib/events.ts:42-43` matches `instagramAccount` ONLY — without the `e.account` OR-clause, clicking `@bookclubbar` sets `search="@bookclubbar"` → filterEvents returns 0 → empty feed. AccountBanner L16-18 also keys on `instagramAccount` only (would show "0 upcoming"). EventCard L249-256 is the plain `<span>`. All three must ship together. The `isIg` guard is necessary: `igUrl = instagram.com/bookclubbar/` would 404 for non-IG handles.
- **One tightening for the orchestrator**: the worker's AccountBanner snippet only shows the `upcoming`/`isIg` lines — make sure the edit ALSO updates the `verified` line (currently `upcoming.some((e) => e.accountVerified)` — fine as-is since `upcoming` is now broader) and the `igUrl` block is wrapped in `{isIg && (…)}`. Apply all three file edits atomically; `next build` was verified clean with all three. Approve as specified.

### ui-U2 (no-op) — APPROVE (verified)
- **Metric moved**: none. 
- **Reasoning**: Verified the directive-2 empty-hero concern is handled — both `★ Following` (69 upcoming) and `★ Saved` heroes are `.length > 0`-guarded (TopPicks L409/L423). No empty/awkward render. Honest no-op is correct; inventing a change would be clutter.

## Notes back to each worker

## Notes back to ingestion-quality
- **You missed**: P1 and P2 are both well-executed and independently reproduced — strong, precise work with exact drop/keep sets. No correction needed on either.
- **You missed**: the bigger fish — the `reading_rhythms`/`nycbackgammonclub`/`philosophy.nyc` yield-0 problem is YOURS, not source-curator's, and it is the real directive-3 follow-graph lever. The yield_map at `interest_profile.py:116-122` is IG-only; luma curator events that already fire `userFollowing` cannot register coverage. See D1 — this should have been P3 this round. The journal has predicted "next scrape will fix it" 3 times and been wrong each time for this structural reason.
- **Open-question answers**: (1) Do NOT give `sanity_check.py:441` the `bk` treatment — keeping `bk`/`brooklyn` as `location_topics` excluded from "meaningful topics" is the correct intentional design; P1 satisfies fb-176 via the metrics snapshot. (2) Accept the deferral of the 2 not-in-feed residuals — no FP-verifiable rule with 0 live instances; correct call. (3) The Long Island event: log it, don't fix it this round.
- **Strong work on**: the honest partial-coverage caveat on directive #2 (3 of 4 live, 2 deferred with reason) — exactly the kind of precision-over-completeness call we want.

## Notes back to source-curator
- **You missed**: your KEY finding's *mechanism* is wrong. There is no underscore/hyphen fold gap — `_handle_candidates` already collapses `readingrhythms-manhattan`→`readingrhythms`↔`reading_rhythms` (normalize.py:1076), which is why those events fire `userFollowing=True`. The metric doesn't move because `yield_map` is sourced only from `account_quality.json` (IG-only), not from enriched luma events. Trace `interest_profile.py:116` → `account_quality.json` → written only by `instagram.py:468`. Diagnose the data SOURCE of a metric before proposing a normalization fix.
- **You missed**: `philosophy.nyc` is ALSO at yield 0.0 right now — directly disproving your own "philosophy fold shipped and works" premise. The fold made the *conviction boost* fire but never touched the *coverage metric*. Same class as reading_rhythms.
- **Strong work on**: the disciplined 0-adds negative with per-URL evidence. Refusing to pad with 0-yield sources is exactly right, and the withfriends.co/bbg JSON-LD-absent findings are useful durable notes. The honest ceiling statement (coverage can't move via source-adds this round) is correct — it just can't move via a handle-fold either; it needs D1.

## Notes back to ui-agent
- **You missed**: nothing material — the 3-file diagnosis (catching that `lib/events.ts` is the load-bearing predicate, not AccountBanner) is exactly the kind of catch that prevents shipping a broken empty-feed click. This is the strongest proposal of the round.
- **You missed (minor)**: when AccountBanner's `upcoming` broadens to include `e.account` matches, double-check the `yieldPct` line still reads from `topAccount?.yield` (it does) — non-IG handles like bookclubbar have no `topAccount` entry, so `yieldPct` will be null and the yield chip simply won't render. That's correct behavior; just confirm it doesn't throw. (It won't — null-guarded.)
- **Strong work on**: the `isIg` guard to suppress the dead "Open on IG" link, and preserving the empty-banner `return null`. Keep the guard — do not ship the unconditional IG link.

## Dream proposals

### D1: Credit non-IG enriched conviction events into `yield_map` (the REAL reading_rhythms fix) — APPROVE-DREAM
- **Verdict**: APPROVE-DREAM (this is the corrected, metric-moving version of source-pool-S1; apply this round, route to ingestion).
- **Metric moved**: follow-graph coverage — moves `reading_rhythms`, `nycbackgammonclub`, `philosophy.nyc` (and any other signal account with ≥1 enriched-conviction event but no IG quality entry) from yield 0 → >0. Estimated 12/50 (24%) → ~15/50 (~30%) on next profile rebuild, with ZERO new sources and independent of the user-blocked IG bottleneck (fb-174). This is the only lever that can lift coverage while the IG sweep is blocked.
- **File**: `scrapers/utils/interest_profile.py`, `build_profile()` at L116-122 (the `yield_map` construction).
- **Change sketch**: After building `yield_map` from `account_quality.json`, do a second pass that reads the deployed/just-built feed (`site/public/events.json`) and, for each event with `userFollowing == True` and an `account` field but yield 0 in the map, folds the event's `account` via `_handle_candidates`-style normalization to the matching `signal_account` and stamps a non-zero yield derived from `event.accountEventYield` (already set by `normalize._apply_quality_for`) OR a floor of e.g. `0.001` to register coverage. Pseudo:
  ```python
  # After the account_quality loop:
  try:
      feed = json.load(open(os.path.join(DATA_DIR, "..", "..", "site", "public", "events.json")))
      norm = {re.sub(r"[^a-z0-9]", "", s): s for s in (follow_usernames | affinity_usernames)}
      for ev in feed.get("events", []):
          if not ev.get("userFollowing"):
              continue
          h = (ev.get("account") or ev.get("instagramAccount") or "").lower()
          key = re.sub(r"[^a-z0-9]", "", h)
          sig_u = norm.get(key)
          if sig_u and yield_map.get(sig_u, 0) == 0:
              yield_map[sig_u] = ev.get("accountEventYield") or 0.001
  except Exception:
      pass
  ```
- **Why APPROVE now**: it directly addresses the un-met half of directive #3 with a verified-correct mechanism, is strictly additive (only raises 0→>0, never lowers), and is the corrected form of the proposal the worker got wrong. Verify post-apply that `nz` rises and that no account is *spuriously* credited (gate on `userFollowing == True`, which only fires for genuine follow matches). Recommend the orchestrator hand this to ingestion-quality to implement + add a one-line sanity assertion.

### D2: "Did you go?" feedback affordance on past saves to close the calibration loop — DREAM-DEFER
- **Verdict**: DREAM-DEFER (queue as feedback-backlog entry, `source: agent-proposal`).
- **Metric moved**: high-conviction ratio (calibration quality) — converts passive saves into explicit attend/skip ground truth, which can re-weight `userAffinity` and the topic_counts derivation over time. No immediate metric move; it builds the data asset that improves all three metrics in future runs.
- **File**: `site/app/components/EventCard.tsx` (past-event branch) + a localStorage key `attended:<eventId>` + a future `scrapers/data/user_attendance.json` ingest.
- **Change sketch**: For events whose date is in the past AND were saved (`isSavedLocal`), render a small "Did you go? Yes / No" pair (consistent with the minimal FeedCard, no new widget chrome). Persist to localStorage; a later round adds a tiny export path into the affinity/quality pipeline. Defer because it needs a storage/ingest design and is out of scope for a no-backend round.
- **Backlog entry seed**: `fb-178 | source: agent-proposal | "Did you go?" attend/skip affordance on past saved events → user_attendance.json → re-weights userAffinity + topic_counts. Closes the calibration loop the README §341-369 flags. UI: minimal Yes/No on past+saved FeedCards; storage: localStorage attended:<id>; ingest deferred.`
