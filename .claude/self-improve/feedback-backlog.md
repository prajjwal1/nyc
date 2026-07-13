# Feedback Backlog

Durable, structured log of every piece of user feedback (explicit or inferred). **No item silently drops.** The Feedback Collector reads this first; workers must address the top 3 `open` items or the Critic must approve a deferral.

Each entry has:
- `id` — short stable identifier (`fb-NNN`)
- `created_at` — ISO date
- `source` — `user-explicit` / `user-inferred` / `agent-proposal`
- `status` — `open` / `in-progress` / `addressed: <sha>` / `wont-do: <reason>`
- `body` — the feedback itself
- `resolution` — set when status becomes `addressed` or `wont-do`

Items at the top are highest priority. Re-rank when adding new items.

---

## Seeded from README.md §480–533 (user feedback log)

These are the durable preferences the user has stated. They're marked `addressed: README` because they're already enforced in the codebase (see referenced filters); future agents must not regress them.

### fb-001 — Exclude nightclub events
- created_at: seeded
- source: user-explicit
- status: addressed: README (enforced in `scrapers/quality.py::HARD_BLOCK_KEYWORDS`)
- body: No `nightclub`, `bottle service`, `vip table/booth/section`, `table service`, `bottle minimum`.
- resolution: Keep these in HARD_BLOCK_KEYWORDS. If any leak, fix immediately.

### fb-002 — Exclude late-night-only events (past midnight)
- created_at: seeded
- source: user-explicit
- status: addressed: README (enforced via `_likely_past_midnight` in `scrapers/normalize.py` + HARD_BLOCK list)
- body: Anything running past midnight: `after hours`, `till 4am`, `until 5am`, `all night long`. Plus startTime ≥ 23:00 / endTime 00:00–04:59 / "1am-5am" text.
- resolution: Audit Ingestion runs for leaks; tighten filter if any 1am/2am text slips through.

### fb-003 — Exclude language mixers, reggaeton, professional networking
- created_at: seeded
- source: user-explicit
- status: addressed: README
- body: Blocked: `language mixer`, `language exchange`, `internationals and language mixer`, reggaeton genre, `professional networking/mixer`, `finance networking/mixer`, `business networking/mixer`, `wall street`, `executive networking`, `career`, `industry`, `corporate`, `investor`, `founders mixer`, `real estate`, `lawyer`, `consulting`, `banking`, `linkedin`, `b2b`, `sales`. Tech mixer is OK.
- resolution: Watch for new variations leaking through and add patterns.

### fb-004 — Soft-penalize heavy-drinking emphasis
- created_at: seeded
- source: user-explicit
- status: addressed: README (`soft_penalty_hits` in ranking)
- body: `open bar`, `all you can drink`, `free drinks all night`, `unlimited drinks`, `bottomless mimosas`, `pre-game`, `kegger`, `shotgun beer` → −0.15 per hit, capped −0.40. "Fine to have some, just downweight."

### fb-005 — Boost alcohol-free events
- created_at: seeded
- source: user-explicit
- status: addressed: README (`alcohol_free_boost` up to +0.10)
- body: `alcohol free`, `sober`, `sober curious`, `non-alcoholic`, `zero proof`, `mocktail`, `tea ceremony`, `matcha`, `specialty coffee`, `kombucha tasting`, `tea tasting` — boost.

### fb-006 — Curated IG accounts must not be auto-pruned
- created_at: seeded
- source: user-explicit
- status: addressed: README (stale-prune now skips `IG_ACCOUNTS` entirely)
- body: The accounts in `IG_ACCOUNTS` (run clubs, yoga, comedy, bookstores, music, alcohol-free nightlife, spot curators) — all explicitly user-named. Stale-prune must skip them.

### fb-007 — Left sidebar simplified (TopAccounts + ActivityPanel removed)
- created_at: seeded
- source: user-explicit
- status: addressed: README
- body: Sidebar shows only view-toggle, calendar, and search/filters.
- resolution: Don't reintroduce widgets to the left sidebar without explicit permission.

### fb-008 — No empty gray gradient boxes for events without images
- created_at: seeded
- source: user-explicit
- status: addressed: README
- body: When an event has no image, render text-only. Applies to ActivityPanel past saves, EventModal "More from"/"More like this" strips, GridCard.
- resolution: Any new "card" surface must follow the same rule.

### fb-009 — "This Weekend" hero must not be parties/nightclub/drinking-heavy
- created_at: seeded
- source: user-explicit
- status: addressed: README
- body: Filters to low-key social: brunch, books, runs, art, outdoors, comedy, supper-club, workshops. Excludes `parties` cat, `nightlife` highlight, drinking-text. Saturday + Sunday only (not Friday).

### fb-010 — No backend; personalization stays client-side in localStorage
- created_at: seeded
- source: user-explicit
- status: addressed: README
- body: All personalization in `nyc-events:*:v1` localStorage keys with reset button. Never sent to a server.

### fb-011 — Don't write per-source code; prefer generalizable solutions
- created_at: seeded
- source: user-explicit
- status: addressed: README
- body: bookclubbar.com etc. caught by generic `_EVENT_PLATFORM_RE` venue-events pattern; no per-site scraper code.

---

## Open items (top of list = highest priority)


### fb-194 — Queens/LIC neighborhood mistag (MoMA PS1 → "midtown") + ~19% null neighborhoods
- created_at: 2026-07-13
- source: user-inferred (Critic review of the deployed feed, 2026-07-09; deferred there)
- status: open
- body: The 2026-07-09 Critic review of the live feed (the review incorporated in f81a75f) flagged a Queens/LIC neighborhood-normalizer data bug: MoMA PS1 is tagged "midtown" (it's in Long Island City, Queens), and ~19% of events carry a null `location.neighborhood`. This is scrape-independent (present in the committed events.json), unit-testable, and degrades the neighborhood badge + neighborhood filter the user relies on. Distinct from fb-189 (which handled name/neighborhood CONTRADICTIONS via `_explicit_hood_in_text`) — this is a Queens/LIC-specific venue→neighborhood mapping gap plus a broader null-rate problem. Reuse the fb-189 Step-0 path and fb-193 venue-alias path.
- "addressed" criterion: "MoMA PS1" (and any LIC/Queens venue token) resolves to a Queens neighborhood (long-island-city / queens), never "midtown"; a unit test covers "MoMA PS1 → long island city (not midtown)" + ≥2 more Queens cases; the null-neighborhood share in the committed events.json drops below 19% (target ≤15%).

### fb-195 — Retire/validate the ~600 keyword lists in quality.py against the now-active taste model (Phase C part 2)
- created_at: 2026-07-13
- source: agent-proposal (unblocked follow-on to Phase C, 62a08f9; per orchestrator brief)
- status: open
- body: Phase C (62a08f9) shipped a semantic TF-IDF taste model (`scrapers/utils/taste.py`) that ranks events by similarity to what the user saves/attends; the f81a75f P6 change cold-started it from the follow-graph so the loop is now ACTIVE on all 423 events. Phase C deliberately DEFERRED retiring the ~600 hand-maintained keyword boost/penalty lists in `scrapers/quality.py` until the taste signal was validated on the full feed — that precondition is now met, so this is unblocked. Compare the taste signal against the keyword clusters and classify each (keep / redundant-with-taste / retire). The additive-only rule does NOT block this: it is refactoring a ranking signal, not deleting a source. IMPORTANT: the fb-001..fb-009 README hard rules (nightclub/late-night/networking blocks, drinking penalties, alcohol-free boosts) are user-explicit and must be preserved regardless of what the taste model says.
- "addressed" criterion: taste-vs-keyword agreement recorded per cluster; each keyword cluster classified; at least the clearly-redundant clusters removed OR a documented finding (Critic-approved) explains why the keyword lists must stay; the fb-001..fb-009 hard rules verified still enforced.

### fb-196 — Close user-named coverage gaps: backgammon/chess, underground-electronic, social dance
- created_at: 2026-07-13
- source: user-explicit (gaps the user named) via Critic review, 2026-07-09; deferred there
- status: open
- body: The 2026-07-09 Critic review surfaced three coverage gaps the user explicitly named that the feed still doesn't serve: (a) NO backgammon/chess events surface (nycbackgammonclub is a chronic sanity_check CRITICAL); (b) underground-electronic is thin beyond Warm Up — the user wants Nowadays / Public Records / Elsewhere depth; (c) social dance is contra-only (Brooklyn Contra from fb-180) with no other participatory social-dance source. These target the North Star directly (surface events the user would actually attend). Source-curator lane. Mind the exclusion constraints: HoY/KDC are user-EXCLUDED (fb-153, `user_excluded_sources.json`) — do NOT re-add them for the electronic gap; all IG adds must be fb-106-clean (no personal accounts); and do NOT propose IG-sweep-dependent paths (fb-174 is fleet-blocked).
- "addressed" criterion: at least one live-probed parseable path (≥5 future events, exclusion-clean, fb-106-clean) added toward EACH of the three gaps, OR a live-verified honest negative per gap (path probed, <5 yield, root cause recorded) that defers that sub-item with a Critic-accepted rationale.

### fb-189 — Neighborhood contradicts venue name (normalizer bug, ~8/375 events)
- created_at: 2026-07-02
- source: agent-proposal (ui-agent flag; scrape-independent + unit-testable)
- status: addressed: d39f664 (run 2026-07-02-1735 — `_explicit_hood_in_text` Step-0 + word-boundary short-keyword match; conflicts 10→0 on frozen feed, Critic-verified, +5 tests. Live-feed count re-verifies post-scrape.)
- body: ~8 of 375 events in the frozen feed carry a `location.neighborhood` that CONTRADICTS the venue name — e.g. name "Bushwick, 380 Troutman Street" but `neighborhood` "east village". `infer_neighborhood` / `_reinfer_neighborhood` picked a wrong neighborhood from the address (or a default) while the venue name/title held the true neighborhood token. This is scrape-independent (present in the current committed events.json), unit-testable, and degrades the neighborhood badge + neighborhood filtering the user relies on. IMPORTANT: b6a0cf3 U2 only SUPPRESSES the redundant display suffix when the venue name already contains the neighborhood — it does NOT correct the underlying data; the wrong neighborhood still ships and still misfilters. This is the top directive for this round precisely because it needs no scrape.
- "addressed" criterion: for any event whose venue name (or title) contains an explicit NYC neighborhood token, `location.neighborhood` never contradicts that token (name-token wins the tie); a unit test covers "Bushwick, 380 Troutman St → bushwick (not east village)" plus ≥2 more; the count of name/neighborhood-conflict events in the committed events.json drops from ~8 to 0.

### fb-190 — Fix lu.ma/philosophy (+ all lu.ma curators) silently not surfacing
- created_at: 2026-07-02
- source: user-explicit ("why am I not seeing lu.ma/philosophy events" / "fix" / "fix all the issues you know of", 2026-06-26→06-29)
- status: addressed: 8d10fc2
- body: User asked why lu.ma/philosophy events weren't showing, and to fix that + "all the issues you know of." Root cause (philosophy yielded 10 events live but 0 reached the feed): (1) shell filter — luma is description-required, philosophy events have empty descriptions, and lu.ma/philosophy was never in user_curated_sources hosts (unlike litclub/readingrhythms) → all dropped; (2) score floor — explicit high-conviction signals (userFollowing/Saved/Tagged/Affinity) only granted the 0.40 floor when source==instagram, so a followed lu.ma calendar sat at the 0.55 default and dropped.
- resolution: `_is_curated_host` now auto-treats ANY lu.ma/<handle> curator calendar as curated (no current/future curator can silently lose events again); high-conviction signals now grant the curated floor regardless of source (extracted testable `_min_score_floor`). Result: philosophy 0→7 events survive. Added `scrapers/maintenance/audit_source_survival.py` (flags ZERO-RAW/ZERO-SURV/LOW-SURV silent-filter class), parametrized regression test over EVERY lu.ma curator in LUMA_PAGES + 5 `_min_score_floor` cases, and fixed a date-relative test flake. INVESTIGATION FINDING (recorded for future agents): most OTHER audit-flagged sources are NOT bugs — empty calendars, by-design floor+caps, redundant parse-rot, or JS-blocked museums; do not chase them as source-yield work.

### fb-191 — Add openbookclub IG account
- created_at: 2026-07-02
- source: user-explicit ("add openbookclub from IG", 2026-07-02)
- status: addressed: b6a0cf3
- body: User asked to add `openbookclub` from IG.
- resolution: added `openbookclub` (no-dot handle) to `scrapers/config.py::IG_ACCOUNTS`; the dotted variant `open.bookclub` was kept as well.

### fb-192 — Improve the UI (day scent, cleaner location, distinct heroes, empty-state copy)
- created_at: 2026-07-02
- source: user-explicit ("also improve the UI", 2026-07-02)
- status: addressed: b6a0cf3
- body: User asked to also improve the UI.
- resolution: U1 relative-day pill ("Today"/"Tomorrow"/"Sat"/"Jul 12") on hero cards (Tonight/Weekend/Just-Added/Following/Saved) via a showDay prop, grouped date-lists keep their header (no duplication); U2 suppress redundant neighborhood suffix when the venue name already contains it (kills "…East Village · east village"); U3 repaint Just Added slate so sky consistently = "from your follow graph" (matches conviction ring + Following hero); U4 fix stale empty-state copy referencing the removed FilterBar. 269 tests pass; next build clean.

### fb-179 — Incorporate more fitness-based events + run clubs (recurring ones too)
- created_at: 2026-06-22
- source: user-explicit
- status: addressed: d9eb82e (run 2026-06-22-1501; +P1 scope-skip "every <weekday>" soft-penalty for fitness, +S1/S6 Eventbrite run-club/pilates slugs)
- body: incorporate more fitness based events, more run clubs (recurring ones should show up too)
- resolution (this session, pending commit): Meetup +4 fitness/run-club search URLs; removed the `"running club"` soft-penalty in `scrapers/quality.py`; bumped fitness boost 1.1→1.3 and wellness 1.05→1.2 in `scrapers/config.py`; +10 run-club/fitness IG seed accounts in `scrapers/config.py`. The recurring-run-club path (`detect_recurring_weekday` → `expand_recurring_event`) was verified to work so recurring weekly runs surface as dated occurrences.
- "addressed" criterion: fitness/run-club events increase on the next scrape AND at least one recurring run club surfaces as multiple dated occurrences; no run-club event is soft-penalized.

### fb-180 — Add Brooklyn Contra dancing (brooklyncontra.org)
- created_at: 2026-06-22
- source: user-explicit
- status: addressed: d9eb82e (run 2026-06-22-1501; +P3 fuzzy-title-dedup exemption → 10 dances incl. both Sep-26 sessions; +S2–S5 NYC-wide social-dance slugs)
- body: add contra dancing brooklyn https://www.brooklyncontra.org/tickets
- resolution (this session, pending commit): new dedicated scraper `scrapers/sources/brooklyncontra.py` (parses the Squarespace store; date from title; year inference), registered in `run_all.py` with `SOURCE_QUALITY=0.8`; added a `DISTINCT_SCHEDULE_SOURCES` exemption in `scrapers/normalize.py` so each scheduled dance survives the recurring-merge. Verified 8 dances surface (scores 0.59–0.76).
- known-minor: the Oct-4 "Raven & Goose" dance is dropped by a PRE-EXISTING false positive — the user's `'rave'` title-exclusion substring-matches "Rave"n. Tracked separately as fb-181 (pre-existing exclusion bug, not contra-specific).
- "addressed" criterion: Brooklyn Contra dances surface on the next scrape as distinct dated events (≥ the 8 verified, modulo the fb-181 false positive).

### fb-181 — `'rave'` title-exclusion substring-matches legitimate words ("Raven", "rave reviews", etc.)
- created_at: 2026-06-22
- source: agent-proposal (discovered during fb-180 contra work)
- status: addressed: d9eb82e (run 2026-06-22-1501; P2 — generalized `\b<hint>\b` word-boundary match for short single-word exclusion hints, precompiled+cached. Verified: "Raven & Goose"/"travel"/"gravel" survive; "warehouse rave"/standalone "RAVE" still blocked)
- body: The `'rave'` title-exclusion is matched as a bare substring, so it incorrectly drops legitimate titles that merely contain the letters "rave" — e.g. Brooklyn Contra's Oct-4 "Raven & Goose" dance, and would also catch "rave reviews", "gravel", "travel", "bravery", "grave". The exclusion should be word-boundary anchored (`\brave\b`, optionally also `\braves?\b`) so it still blocks actual rave events without false-positiving on substrings.
- "addressed" criterion: "Raven & Goose" (and a representative set like "rave reviews"/"travel") survive the filter while a literal "Rave" / "warehouse rave" title is still excluded; verified against the contra feed and a small FP probe set.

### fb-106 — IG_ACCOUNTS must only contain socializing-oriented accounts; no individual people
- created_at: 2026-05-28
- source: user-explicit (mid-run-1552 correction)
- status: addressed: 2026-05-28-1552 (initial 4 personal accounts removed)
- body: We must NOT include individual person IG accounts in `scrapers/config.py::IG_ACCOUNTS` (e.g. `alvinzx`, `j_palmer_7`, `leahcanel`, `sophiareed5`, `maggie_onthemove` — anything that looks like a personal account of one human). Only socializing-themed entities: clubs, venues, curators, social brands, orgs, institutions. **Private IG accounts are off the table entirely** (they can't be scraped anyway, but also won't be added).
- resolution: This applies to every future agent. Source Curator and Ingestion Quality must filter individual-person accounts out of any `IG_ACCOUNTS` add-list before proposing. Heuristic: drop handles that look like `firstname_lastname`, `firstinitial_lastname`, `firstname<number>`, or that the user follows but are clearly a personal profile (no event-flyer posts, no "club"/"venue"/"NYC"/"BK"/etc. in handle or bio).

### fb-101 — Close the follow-graph 0-yield gap
- created_at: 2026-05-28
- source: agent-proposal (from metrics-before, run 2026-05-28-1552)
- status: addressed-pending-scrape (root cause fixed; metric will move on next CI scrape)
- body: 42 of 54 `signal_accounts` in `user_interest_profile.json` have `yield_map` = 0.0. Highest-priority subset (user-named in README §480–533 or required by `sanity_check.py`): `vitalrunclub`, `silentbookclub.nyc`, `nycbackgammonclub`, `reading_rhythms`, `bookclubbar`, `crownheightscraftclub`, `midnightrunnersnewyork`, `philosophy.nyc`. Each is a follow that produces no events — either the account isn't in `IG_ACCOUNTS`, the scraper is failing silently, or there's a `dead_accounts.json` blocker.
- "addressed" criterion: ≥ 5 of the named accounts move to `yield_map > 0` within ~3 runs.
- root-cause fix shipped (iter 1 P1): IG `feedback_required` no longer strikes accounts. Iter 1 P3: 15 user_following accounts promoted to IG_ACCOUNTS. Iter 79 purged 54 stale entries. Metric will update on next CI scrape (still bottlenecked on IG session refresh).

### fb-102 — Raise IG share + surface follow-graph provenance
- created_at: 2026-05-28
- source: agent-proposal
- status: addressed (across iter 1 P2 + iter 73-109 + iter 78 + iter 71/75/95)
- body: IG is 21/246 (8.5%) of the deployed feed though README §40–45 says it should be dominant. Separately, 0/246 events have an `account` field whose value matches a `signal_account` — either the field isn't being populated or the metric is reading the wrong key (audit `build_event` in `instagram.py` for the `account` / `creator` / `authorAccount` field name).
- shipped:
  - iter 1 P2: IG events now stamp `account` field (mirrors `instagramAccount`).
  - iter 73-74: enrichment via Lu.ma URL handle + venue-domain hostname → adds ~29 non-IG userFollowing events on the current deployed feed.
  - iter 77: organizer.name extraction from JSON-LD.
  - iter 109: location.name match for venue events.
  - iter 78: 👤 Following hero in TopPicks surfaces these prominently.
  - iter 71/75/95: "Did you go?" prompt + visible ✓ badge + aggregate counter.
- IG share itself bottlenecked on IG-session refresh.

### fb-103 — Fix the `bk` topic gap
- created_at: 2026-05-28
- source: agent-proposal
- status: addressed (iter 1 P6 + iter 70 + iter 1 S1)
- body: `topic_counts.bk = 4` but only 2 events match the shorthand, vs `brooklyn = 3` surfacing 14 events. Likely needs (a) a synonym map (bk ↔ brooklyn) in category inference, (b) Brooklyn-specific accounts in `signal_accounts` that may not have BK in their captions.
- shipped:
  - iter 1 P6: `bk → brooklyn` synonym fold in `interest_profile.py` topic match.
  - iter 70: venue-name synonym expansion (BK Bowl ↔ Brooklyn Bowl etc.).
  - iter 1 S1: 9 Brooklyn AllEvents/Eventbrite URLs added.
- Effective on next scrape.

### fb-105 — Curator-calendar lu.ma path probing for every signal_account
- created_at: 2026-05-28
- source: agent-proposal (dreamer-critic D1, APPROVE-DREAM but deferred this round)
- status: addressed: probe ran iter 76 (rate-limit cleared); zero new candidates found
- body: For every `signal_account` (54 today, 69 after this round's P3 promotions), probe `https://lu.ma/<handle>` once. If yield ≥ 3 distinct events not in `/nyc`, add to `LUMA_PAGES`. Implement as `scrapers/maintenance/probe_luma_curators.py` (one-off, not in hot path). Replaces the broken `/nyc/<topic>` URLs.
- resolution: ran the script against 169 candidates (excluding the 6 handles already covered). Result: **0 net-new lu.ma curator URLs** worth adding. Most signal_accounts don't have public lu.ma calendars (404 on the handle path). The existing 6 curator URLs (`nycbackgammonclub`, `readingrhythms-manhattan`, `litclub.nyc`, `thinkolio`, `founderscoffee`, `cinemaclub`) cover everything available. Also fixed a `_existing_handles` bug that was falsely flagging `nycbackgammonclub` as a candidate (the earlier `startswith("nyc")` filter was too broad).
- implication for fb-104: deferral premise (replacement curator-calendar list before prune) doesn't materialize — there's no replacement list to add. Pruning `/nyc/<topic>` URLs would now be safe (they're redundant) but is still a deletion, which the additive-only rule blocks without explicit user opt-in.

### fb-107 — Lower IG-session staleness threshold from 30 to 25 days
- created_at: 2026-05-28
- source: agent-proposal (iter 68)
- status: addressed (committed in iter 68)
- body: The 2026-05-24 mass-kill of 54 accounts happened while the session was ~23 days old. The 30-day STALE threshold in `sanity_check.py` was too lenient — by the time it fires, the session is fully dead and accounts have already been wrongly struck. New thresholds: ⚠ STALE at 25 days, ⛔ CRITICAL at 28 days, with explicit refresh command in the warning.

### fb-108 — Dedup `bookclubbar` in IG_ACCOUNTS
- created_at: 2026-05-28
- source: agent-proposal (iter 68; Critic flagged in run 2026-05-28-1552)
- status: addressed (committed in iter 68)
- body: `bookclubbar` appeared twice in `scrapers/config.py` IG_ACCOUNTS (lines 54 and 133). `list(dict.fromkeys([...]))` made it harmless functionally but it's noise. Removed line 133.

### fb-109 — Block leaks: corporate AWS meetups, B2B coaching, bar crawls
- created_at: 2026-05-28
- source: agent-proposal (iter 69 audit of deployed feed)
- status: addressed (committed in iter 69)
- body: Three leak patterns found in the live feed by sampling non-IG sources:
  (a) "Amazon Quick - NYC Meetup" — Amazon AWS product demo classified as `food/free/outdoors/parties`. Hard-block added: `amazon quick`, `amazon quicksight`, `aws meetup`, `aws user group`, `google cloud meetup`, `azure meetup`, `salesforce meetup`, `snowflake meetup`.
  (b) "The Career Reset: …" + "The AI Edge: Supercharge Your Startup Vision" — B2B coaching framings. Hard-block added: `career reset`, `career strategy`, `supercharge your startup`, `startup vision`, `your startup growth`.
  (c) 3 "Brooklyn Bar Crawl: <neighborhood>" events at 0.65-0.71 — drinking-centric, same spirit as `open bar`/`unlimited drinks`. Soft-penalty added: `bar crawl`, `pub crawl`.
- "addressed" criterion: ✓ patterns block their target titles; verified no false positives on "throughout her career" or "asianfoundersclub mixer".

### fb-110 — Bake fb-106 into agent system prompts
- created_at: 2026-05-28
- source: agent-proposal (iter 69)
- status: addressed (committed in iter 69)
- body: User correction fb-106 ("socializing entities only in IG_ACCOUNTS — no individual people") added directly to `.claude/agents/source-curator.md` (hard filter + heuristic checks) and `.claude/agents/ingestion-quality.md` (hard rule). Future /self-improve runs will respect this automatically.

### fb-111 — Venue synonym expansion in normalize (BK ↔ Brooklyn, MoMA, BAM, HOY, KDC, BMA)
- created_at: 2026-05-28
- source: agent-proposal (iter 70; README §354 known gap)
- status: addressed (committed in iter 70)
- body: `_normalize_venue_name` now expands NYC venue abbreviations before suffix-stripping. `\bbk\b → brooklyn`, `\bmoma\b → museum of modern art`, `\bbam\b → brooklyn academy of music`, `\bkdc\b → knockdown center`, `\bhoy\b → house of yes`, `\bbma\b → brooklyn museum`, `\bthe met\b → metropolitan museum`. Word-boundary regex avoids false-positives on "Backgammon" / "Botanic". Cross-source dedup now collapses "BK Bowl" + "Brooklyn Bowl" + "Brooklyn Bowl Williamsburg" into one event.

### fb-122 — Top-event audit + purge glued-handle leak at top of feed
- created_at: 2026-05-28
- source: agent-proposal (iter 81)
- status: addressed (committed in iter 81)
- body: Audited top 20 events by score. Found 2 critical issues:
  1. **"Ggretavanfleet gave fans quite"** ranked #2 at score 1.00 — an IG-Stories OCR glued-handle leak that iter 1 P5 was supposed to catch. Inspection revealed the iter 1 regex (`^[A-Z]{1,2}[a-z]{2,}[A-Z][a-z]{2,}$`) requires an *internal* uppercase, but the actual leaks (`Glibertybagelsny`, `Ggretavanfleet`) are 1 capital + long lowercase. The Critic's "verified against live titles" claim was wrong.
  2. **"Glibertybagelsny grand opening"** also leaking, score 0.66.
- fix: added shape-(a) regex `^[A-Z][a-z]{12,}$` (1 capital + 12+ lowercase, min title-word length 14). Now caught in:
  - `scrapers/sources/instagram.py::_looks_like_glued_handle` — checks both shape (a) and shape (b) at extraction time
  - `scrapers/normalize.py::_is_glued_handle_title` — post-filter pass in `process()` so already-stored leaks self-clean without a re-scrape (purges 2 events on the very next normalize run)
- defensive scope: shape (a) checks first word length ≥14 AND all-lowercase-after-first-capital. The deployed feed has 0 legitimate words of this shape; the regex catches exactly the 2 leaks.
- other audit findings (not yet addressed): some events have wrong categories ("Silver Sapphics: Speed Dating" tagged `movies`; "Word and Object by Quine" tagged `fitness`). Categorizer false-positives — separate issue, queued as fb-123.

### fb-127 — Substack venue extraction from title (~+33 events per scrape)
- created_at: 2026-05-28
- source: agent-proposal (iter 86 audit of Substack low yield)
- status: addressed (committed in iter 86)
- body: Audit: live Substack yield is 493 events but only 1 in deployed feed. Most surviving events (237 → "ok") are actually junk product affiliates ("J.Crew Cosmo pant", "Mini Phone Tripod") while 235 *real* events were shell-filtered. Inspected the shell pool: titles like "Pet Adoption Day (@ Elizabeth Street Garden)" had the venue baked into the title string but `location.name=""` — so the shell filter (`no desc + no img + no loc`) dropped them.
- fix: `_extract_from_headings` now matches `\((?:@|at)\s+([^)]+)\)\s*$` on the title, pulls the venue into `location.name`, and strips the parenthetical from the title. Result: shell pool 235 → 202 (+33 real events recovered including Brooklyn Ceramic Arts Tour, Pet Adoption Day, High Line Plant Sale, Pupper West Side Street Fair, Brooklyn Bridge Sunset Yoga).
- known issue (separate, not addressed): substack's 237 surviving events include many product-affiliate noise ("Mini Phone Tripod", "Apple AirTag") that should be filtered out. The "(link)" suffix is a strong tell. Logged as fb-128.
- 2 of the Substack FEEDS URLs return 404 (untappedcities.com/feed/, nycgovparks.org/news.rss). Harmless but wasted budget. Not addressed this iteration.

### fb-136 — Aggregate attended counter in TopPicks header
- created_at: 2026-05-28
- source: agent-proposal (iter 95; completes the iter 71+75 attended thread)
- status: addressed (committed in iter 95)
- body: Iter 71 shipped the "Did you go?" button + iter 75 the on-card ✓ badge. Adding a small `· ✓ N attended` suffix in the "For You" subhead so the user sees their feedback history accumulating at a glance. Only renders when `yes >= 1` — no zero-state clutter. Subtle emerald color matches the badge color.
- new helper: `getAttendedCount()` in `lib/interests.ts` returns `{yes, no}` counts.
- intentionally minimal: no "no" count surfaced (negatives stay invisible per iter 75 spec); no "manage attended" UI. The counter exists to reward engagement, not to drive interaction.

### fb-138 — Reddit harvester broken (`.json` 403) + RSS fallback
- created_at: 2026-05-28
- source: agent-proposal (iter 97 audit)
- status: addressed-partial (committed in iter 97; full fix needs OAuth)
- body: reddit.py harvester was returning "No event-platform URLs found" silently. Probed: Reddit cracked down on `/.json` endpoints — 403s every UA (browser, custom, old.reddit). Their API now requires OAuth (PRAW credentials).
- fix (this round): added `_report_reddit_403()` so the silent failure is now a clear log line about the OAuth requirement. Added `.rss` (Atom) fallback that yields 7 URLs from r/AskNYC/new — comments unavailable but post titles/summaries sometimes contain event-platform links. Mirrors the iter 96 Atom-parsing pattern.
- not addressed: the actual harvest yield is degraded (README says comments are the main URL source; RSS doesn't include them). Full restoration requires PRAW creds + `praw.Reddit(client_id=..., client_secret=...)` configuration. Logged as fb-139 for the user to set up auth out-of-band.
- bonus result: harvester now logs visibly when broken; future iters won't waste time re-investigating "is reddit silently failing?"

### fb-168 — Fix workflow git-add: missing 2 state files
- created_at: 2026-05-29
- source: agent-proposal (iter 127)
- status: addressed (committed in iter 127)
- body: All 3 scrape workflows (scrape.yml, quick-scrape.yml, scrape-priority.yml) had a `git add` step that was missing:
  - `scrapers/data/image_hashes.json` — generated by IG scraper's image-OCR; safe-pull list HAD it but git-add didn't (workflow drift).
  - `scrapers/data/user_interest_profile.json` — regenerated each scrape via `interest_profile.build_profile()` per `normalize.py`. The iter-1 metrics work depends on it being persisted. Wasn't in any workflow's git-add list.
- Without these in git-add, the files get regenerated each CI run but never committed → state is wiped between runs, defeating the persistence README §306 talks about.
- fix: added both to all 3 workflows. user_curated_sources.json / user_excluded_sources.json deliberately NOT added (user-edited, not CI-generated).

### fb-167 — Add SOURCE_VOLUME_CAPS for nycforfree + mcnallyjackson
- created_at: 2026-05-29
- source: agent-proposal (iter 126)
- status: addressed (committed in iter 126)
- body: After iter 100 (`nycforfree.py` rewrite, ~83 future events) and iter 102 (mcnallyjackson dynamic month URLs, ~44 future events), both sources have high yield but no `SOURCE_VOLUME_CAPS` entry. Without caps they could crowd out other content.
- added:
  - `nycforfree: 40` — matches allevents cap; user is interested in free events but doesn't need 80 of them per scrape
  - `mcnallyjackson: 30` — literary events the user follows; 30 is generous
- the cap applies AFTER ranking, so the top-30 best events from each source bubble up. Other sources unaffected.

### fb-166 — Add SOURCE_LABELS for sources missing display names
- created_at: 2026-05-29
- source: agent-proposal (iter 125)
- status: addressed (committed in iter 125)
- body: Audited `site/app/lib/types.ts::SOURCE_LABELS` against per-source scraper `source=` field. 5 sources were missing labels and would render as raw key in cards:
  - `lizsbookbar` → "Liz's Book Bar"
  - `mcnallyjackson` → "McNally Jackson"
  - `brooklyncomedy` → "Brooklyn Comedy Collective"
  - `smorgasburg` → "Smorgasburg" (new from iter 106)
- (Note: `parks` uses `source="nyc_parks"` which was already in the dict.)
- build clean.

### fb-165 — Remove 3 STALE substack feeds (0 future + 0 URL harvest)
- created_at: 2026-05-29
- source: agent-proposal (iter 124; ran iter-123 enhanced audit_urls.py)
- status: addressed (committed in iter 124)
- body: Full audit with the new HARVEST classification surfaced 3 substack feeds that contribute **nothing** — neither future events nor harvested URLs:
  - `thedeli.substack.com` — 4 events, 0 future, 0 harvest. Music venues already covered by Songkick + per-venue scrapers.
  - `nycforfree.substack.com` — 3 events, 0 future, 0 harvest. The .co site is covered by the iter-100 nycforfree.py Squarespace scraper.
  - `brokelyn.com/feed/` — 8 events, 0 future, 0 harvest. Appears to have stopped publishing events.
- contrast: `onefinedaynyc.substack.com` was correctly classified as **HARVEST** (8 events + 21 URLs harvested) — kept.
- `audit_urls.py`'s HARVEST classification (iter 123) is what made these removal decisions safe — without it I might have left STALE feeds that were actually contributing via URL harvest, or removed harvesting feeds that looked dead.

### fb-164 — audit_urls.py: HARVEST classification for substack feeds
- created_at: 2026-05-29
- source: agent-proposal (iter 123)
- status: addressed (committed in iter 123)
- body: Iter 117's classification flagged 4 substack feeds (onefinedaynyc, thedeli, nycforfree.substack, brokelyn) as STALE because direct event yield = 0 future. But those feeds **harvest event-platform URLs** (Lu.ma, Eventbrite, Partiful, etc.) from post bodies that the generic scraper picks up next run. A feed with 0 future events but 21 harvested URLs is still a net contributor.
- fix: `audit_urls.py` now counts URL harvest per substack feed (regex-scan of feed XML for known event-platform hosts). New HARVEST classification for feeds with ≥5 harvested URLs but no future events. Tooltip column added to the per-URL output.
- verified: onefinedaynyc → 0 future + 21 URLs → HARVEST (was STALE). theskint → 84 future + 23 URLs → HEALTHY. Substantially more informative.

### fb-163 — Following hero now also surfaces userAffinity events
- created_at: 2026-05-29
- source: agent-proposal (iter 122; UX-consistency fix)
- status: addressed (committed in iter 122)
- body: Iter 78 added the 👤 Following hero filtering on `event.userFollowing`. But iter-71's card ribbon already showed BOTH `userFollowing` (sky) and `userAffinity` (amber) as conviction signals. The hero's filter was strictly narrower, so affinity events were buried in the per-day feed even with the amber card ribbon visible.
- fix: hero filter now includes `userAffinity` too. Header text grows a `· & save from` suffix when affinity-only events are present, so the user knows the broader scope is engaged. Build clean.

### fb-162 — Prune 7 more EMPTYs (bookstores + niche venues, JS-rendered)
- created_at: 2026-05-29
- source: agent-proposal (iter 120)
- status: addressed (committed in iter 120)
- body: Continued audit_urls cleanup. Removed 7 EMPTY URLs:
  - `strandbooks.com/events`, `greenlightbookstore.com/event`, `booksaremagic.net/event` — JS-rendered bookstore own-sites
  - `bookclubbar.com/events` — covered by `bookclubbar.py` (bookmanager API)
  - `caveat.nyc/events` — covered by Eventbrite venue-search `/d/ny--manhattan/caveat/` (verified iter 113: 20/20 venue matches)
  - `roughtradenyc.com/events/`, `publicrecords.nyc/calendar` — JS-rendered, no working alternative
- Iter 120 saves 7 wasted fetches per scrape. Cumulative cleanup totals over session: 38 dead URLs removed.

### fb-161 — Update README "tried and blocked" with current state
- created_at: 2026-05-29
- source: agent-proposal (iter 119)
- status: addressed (committed in iter 119)
- body: README §64 had stale claims after the audit thread:
  - "DICE.fm city pages — 404s (only individual event URLs work)" — wrong as of iter 101 (`__NEXT_DATA__` path yields 25 events).
  - Missing patterns we DID find that work (Atom feeds, Squarespace eventlist, Squarespace month-pagination, Eventbrite venue-search with unique slugs).
- new section "Sources that turned out to work" documents the recovered patterns + the cautionary cases (iter 113's venue-search false-positive).
- new section "URL audit tooling" points future agents at `audit_urls.py` so they can re-run the audit before adding URLs.

### fb-160 — Prune 8 confirmed-redundant EMPTY URLs
- created_at: 2026-05-29
- source: agent-proposal (iter 118; continues iter-116 cleanup)
- status: addressed (committed in iter 118)
- body: Continued EMPTY cleanup. Removed 8 URLs that are dead/redundant with confidence:
  - `nyc.com/events/` — EMPTY, no public alternate
  - `eventcombo.com/events/new-york` — EMPTY, aggregator that lost coverage
  - `timeout.com/newyork/{events, this-weekend, this-week}` (3 URLs) — TimeOut blocks bots; iter-1 README §70 already documented "Time Out NY — 404s on most calendar URLs"
  - `mcnallyjackson.com/events` — page is Squarespace-eventlist; the dedicated `scrapers/sources/mcnallyjackson.py` parses it correctly via iter-102 dynamic month URLs
  - `bookcourt.com/calendar` — site appears closed/redirected
  - `lizsbookbar.com/events` — already covered by `lizsbookbar.py` (bookmanager API)
- saves 8 wasted fetches per scrape run. 46 EMPTYs remaining; venue own-sites need case-by-case review.

### fb-159 — Prune 3 STALE Songkick venue URLs (covered by metro pages)
- created_at: 2026-05-29
- source: agent-proposal (iter 117; follow-up audit_urls run)
- status: addressed (committed in iter 117)
- body: Audit surfaced 7 STALE URLs (events but all past). 3 are Songkick venue pages: brooklyn-bowl, mercury-lounge, village-vanguard — each returns 3 events, all past. The Songkick metro-areas pages (49 events × 7 pages = 306 events from iter 88) already cover these venues' current shows.
- removed:
  - `songkick.com/venues/22-brooklyn-bowl`
  - `songkick.com/venues/5-mercury-lounge`
  - `songkick.com/venues/10735-village-vanguard`
- the other 4 STALE URLs are substack feeds (onefinedaynyc, thedeli, nycforfree.substack, brokelyn) where 0 future is normal (RSS blog feeds — events are referenced in body text). Kept.

### fb-158 — Full audit_urls run: 60 EMPTY URLs found
- created_at: 2026-05-29
- source: agent-proposal (iter 116; ran iter-115 script over all 204 URLs)
- status: addressed-partial (6 cleanest removed; 54 logged for review)
- body: Ran `audit_urls.py` over all 204 URLs (61.9s with concurrency=8). Classification:
  - HEALTHY (≥3 future events): **142** ✓
  - STALE/WARN/EMPTY/ERROR: **62**
  - In particular, 60 URLs return 0 events — they're either JS-rendered own-venue sites (timeout.com, mcnallyjackson.com, terminal5nyc.com, websterhall.com, brooklynbowl.com, metrograph.com, filmforum.org, lincolncenter.org, carnegiehall.org, etc.) or moved/dead.
- removed this round (6 lowest-risk):
  - `allevents.in/brooklyn/{literature,running,coffee,poetry}`
  - `allevents.in/new-york/{art-exhibition,gallery}`
  - Within an otherwise-healthy AllEvents source, these specific subcategory URLs return 0 — borough-level catch-all already covers their events.
- deferred (54 remaining EMPTYs): most are venue own-sites where the alternate path is either an Eventbrite venue-search URL (per iter 107-110 pattern, only 4 verified to actually filter correctly) or no public alternate. Future iterations should:
  1. Cross-check each EMPTY against `audit_urls.py --json` output
  2. For venues that DO have a verified Eventbrite slug, consider swap
  3. For dead-only-sites, just remove

### fb-157 — Maintenance script: audit_urls.py
- created_at: 2026-05-29
- source: agent-proposal (iter 115)
- status: addressed (committed in iter 115)
- body: Manual URL audits across iter 87, 102, 113, 114 found multiple silently-dead feeds + broken-pagination URLs. Automating that audit pattern as `scrapers/maintenance/audit_urls.py` so future agents can run it instead of probing each URL by hand.
- script behavior: probes every URL in `GENERIC_URLS` + `substack.FEEDS`, classifies as HEALTHY (≥3 future events) / WARN (1-2 future) / STALE (events but all past) / EMPTY (0 events) / ERROR. Flags candidates for review.
- usage: `python -m scrapers.maintenance.audit_urls` (slow — 200+ URLs × ~3s each). `--limit N` for quick sampling. `--json` for piping into a follow-up tool. `--concurrency K` to adjust HTTP parallelism.
- smoke test on first 10 URLs already surfaced 4 EMPTY entries (`92ny.org`, `bricartsmedia.org`, `brooklynbrewery.com`, `lpr.com`) — review candidates for the next audit round.

### fb-156 — bedfordandbowery.com is dead (last post May 2021)
- created_at: 2026-05-29
- source: agent-proposal (iter 114 audit)
- status: addressed (committed in iter 114)
- body: Probed bedfordandbowery substack feed — yields 8 items, all dated **2021** (last post May 2021). The site stopped publishing 4 years ago. Articles like "Reviving the American Chestnut From a New York City Terrace", "For the Showman Behind Film Forum, It's On With the Show" are blog posts about news, not future events anyway — but they're 4 years stale.
- fix: removed `https://bedfordandbowery.com/feed/` from `substack.FEEDS`. Cleans up the wasted fetch and stops the parser from producing junk events that get filtered downstream.
- pattern: substack feed sources can die silently — the feed still returns 200 OK with old content. Without date-staleness checks at the FEEDS list level, dead feeds keep getting scraped.

### fb-155 — Eventbrite venue-search slug is keyword-search, not strict-venue
- created_at: 2026-05-29
- source: agent-proposal (iter 113; verifying iter-109 enrichment)
- status: addressed (committed in iter 113)
- body: Verifying iter-109's location.name enrichment against real venue-search fetches surfaced a much bigger problem: the Eventbrite URL pattern `/d/<location>/<slug>/` is **substring keyword search, not strict venue match**. Audit results from real fetches:
  - ✓ elsewhere: 18/20 events actually at Elsewhere
  - ✓ littlefield: 20/20 ✓
  - ✓ caveat: 20/20 ✓
  - ✓ pioneer-works: 17/20 ✓
  - ✗ comedy-cellar: 0/20 (Eventbrite matched "Whiskey Cellar", "Oak Cellar at Jake's Dilemma", "Grove 34")
  - ✗ blue-note: 0/20 (matched "Books Are Magic Montague", "Casa de Montecristo", "Chelsea Table & Stage")
  - ✗ brooklyn-bowl, mercury-lounge, rockwood-music-hall, small-s-jazz-club, village-vanguard, smoke-jazz-club, public-records, murmrr, qed-astoria: all 0-1/20
- iter 108 was therefore adding **~220 noise events per scrape** from 11 false-positive URLs. Removed them; kept the 4 verified working URLs.
- pattern: generic single-word slugs ("blue-note", "comedy-cellar") fail because they substring-match many other venues. Unique multi-word slugs ("pioneer-works", "littlefield") succeed.
- meta lesson #2 for source-curator agents: probe the actual yield + location.name match rate before adding any Eventbrite venue-search URL. The 20-event count alone is meaningless without venue-name verification.

### fb-154 — Bake iter-111 + iter-83-onward lessons into agent prompts
- created_at: 2026-05-29
- source: agent-proposal (iter 112)
- status: addressed (committed in iter 112)
- body: After iter 111's mistake-correction (added user-excluded venues), the agent prompts didn't have a check for `user_excluded_sources.json`. Updated:
  - `source-curator.md`: new **HARD FILTER #1 — exclusion check** at top of "Account promotion" section; new hard-rule bullet.
  - `ingestion-quality.md`: new hard-rule bullet matching.
  - `dreamer-critic.md`: new cross-check "User-excluded check" requiring REJECT for unverified add proposals; new "Silent-failure watch" cross-check codifying the recurring session pattern (API field rename, schema-subtype drift, broken pagination, Atom-vs-RSS, JS-rendering).
- Future `/self-improve` runs will respect these by default. The lessons compound — every agent run after this gets the iter-83-through-111 learnings without re-discovering them.

### fb-153 — Back out iter-107 HoY/KDC (user-excluded); extend exclusion to venue
- created_at: 2026-05-29
- source: agent-proposal (iter 111; reviewed user_excluded_sources.json)
- status: addressed (committed in iter 111)
- body: **Mistake correction**: iter 107 added `eventbrite.com/d/ny--brooklyn/house-of-yes/` and `.../knockdown-center/` to GENERIC_URLS, but `user_excluded_sources.json::accounts` explicitly lists `houseofyesnyc` and `knockdowncenter` with the note "club / late-night DJ venue" and "warehouse rave venue — user explicitly excluded clubs." Iter 107 was wrong; I should have checked the exclusion file before adding.
- fix:
  1. Removed the 2 venue-search URLs from GENERIC_URLS.
  2. Extended `ranking.is_user_excluded` to also check `event.location.name` against the accounts set via the same alphanumeric-fold + suffix-strip/add used in `_enrich_provenance_from_url`. So cross-source events from excluded venues (e.g. Eventbrite event at "House of Yes" from a different search URL) still get dropped.
- 5/5 tests pass: HoY venue / KDC venue / IG account / random venue / AI title hint.
- meta lesson: future agents proposing IG_ACCOUNTS or GENERIC_URLS adds must check `user_excluded_sources.json` first. Logged the lesson in the next agent prompt iteration.

### fb-152 — Pioneer Works + Murmrr from user_curated_sources
- created_at: 2026-05-29
- source: agent-proposal (iter 110; cross-checked `scrapers/data/user_curated_sources.json`)
- status: addressed (committed in iter 110)
- body: Inspected `user_curated_sources.json` — found 16 hosts the user explicitly curated. 14 are covered through various paths; 2 weren't: **pioneerworks** (Red Hook arts/sci nonprofit per the user's note: "talks, readings, music") and **murmrr** (Crown Heights/Prospect Heights venue: "author talks + indie music"). Both have JS-rendered own sites; both yield 19-20 events via the iter-108 Eventbrite venue-search pattern.
- fix: 2 new URLs in GENERIC_URLS. Sample:
  - Pioneer Works: "Supper Club by Dacha 46", "Second Sundays: June 2026"
  - Murmrr: "Mad East: Muze, Xena & Happy"
- the `user_curated_sources.json` file is now ≥ 99% covered.

### fb-151 — Extend enrichment to event.location.name (venue ⇒ follow match)
- created_at: 2026-05-29
- source: agent-proposal (iter 109; followed iter 107-108 thread)
- status: addressed (committed in iter 109)
- body: Investigated whether iter 77's organizer-name path would fire on the new iter-108 venue-search events. Sampled real Eventbrite events: `organizer.name` is the per-show **promoter** ("@officialdjopapi", "Zoe Levy"), not the venue. The user follows venues, not per-show promoters, so the path doesn't fire. The VENUE is in `location.name`.
- fix: extended `_enrich_provenance_from_url` with a 4th match path: alphanumeric-fold + suffix-strip ({nyc, ny, brooklyn, manhattan, bk}) + **suffix-add** ({nyc, ny, bk}) on `event.location.name`. Suffix-add was a new addition because venues often drop the `nyc`/`bk` suffix in their public name even when the IG handle has it. Verified:
  - "Greenpoint Comedy Club" → `greenpointcomedyclub` ✓
  - "Franklin Park" → `franklinpark` + `franklinparkbk` ✓ (via bk suffix-add)
  - "Anais Wine" → `anaiswinebk` ✓
  - "Random Venue NYC" → no match ✓ (correct rejection)
- expected impact: every event at a venue the user follows now triggers `userFollowing` via location.name even when the per-show organizer is someone else.

### fb-150 — Backfill 13 more venues via Eventbrite venue-search
- created_at: 2026-05-29
- source: agent-proposal (iter 108; extends iter-107 pattern)
- status: addressed (committed in iter 108)
- body: Iter 107 verified the `eventbrite.com/d/ny--<borough>/<slug>/` pattern works for any NYC venue booking through Eventbrite. Batch-probed all venues in user's IG_ACCOUNTS: 14/14 yield 18-20 events each. Added 13 more (HoY + KDC already in from iter 107):
  - Brooklyn: elsewhere, brooklyn-bowl, public-records, littlefield
  - Manhattan: mercury-lounge, rockwood-music-hall, comedy-cellar, caveat, small-s-jazz-club, village-vanguard, blue-note, smoke-jazz-club
  - Queens: qed-astoria
- bounded: SOURCE_VOLUME_CAPS["eventbrite"]=100 keeps the top-100 picks bubbling up from the now ~500-event pool. Same feed size, higher venue diversity, more on-target with user's IG follow graph.
- expected impact on next scrape: every venue the user follows has a dedicated event stream. Music/jazz/comedy depth lifts substantially.

### fb-149 — House of Yes + Knockdown Center via Eventbrite venue-search
- created_at: 2026-05-29
- source: agent-proposal (iter 107)
- status: addressed (committed in iter 107)
- body: `sanity_check.py::WARNING_CHECKS` flags both as required venues. Probed sites: both are Squarespace homepages with no scrapable own-site event structure. HoY /calendar is just an Eventbrite collection link ("Dirty Circus at House of Yes"); knockdown.center has no /events path at all.
- discovered: Eventbrite venue-search URLs (`/d/ny--brooklyn/<venue>/`) work as venue calendars via the existing generic.py JSON-LD parser. 19 events each.
- fix: added both URLs to GENERIC_URLS. Sample:
  - HoY: "HOT & FRESH · Burlesque", "Weapons Of Mass Seduction Preview Concert", "Rock the House 2026"
  - KDC: "DJ Harvey at Ruins at Knockdown Center", "LP Giobbi", "Marten Lou"
- pattern: any NYC venue that books through Eventbrite is reachable via `eventbrite.com/d/ny--<borough>/<slug>/`. Could backfill other under-yielding venue keywords this way if more sanity_check WARNINGs surface.

### fb-148 — Smorgasburg recurring scraper (closes sanity_check WARNING)
- created_at: 2026-05-29
- source: agent-proposal (iter 106; sanity_check WARNING_CHECKS gap)
- status: addressed (committed in iter 106)
- body: `sanity_check.py::WARNING_CHECKS` flags Smorgasburg as a required institution but it's been at 0 events for the entire session. Probed smorgasburg.com — only WebSite + LocalBusiness JSON-LD, no per-event structure. It's a recurring weekly market: Saturdays at East River State Park (Williamsburg), Sundays at Breeze Hill (Prospect Park).
- fix: new `scrapers/sources/smorgasburg.py` generates the next 8 weekends per location (16 events). Each event has full venue + address + neighborhood + lat/lng + categories=`food, outdoors, free`, plus an honest description noting "outdoor; check social for weather updates."
- wired into `run_all.py` ASYNC_SCRAPERS.

### fb-147 — Data freshness color cue in Header
- created_at: 2026-05-29
- source: agent-proposal (iter 105)
- status: addressed (committed in iter 105)
- body: Header already shows "Updated <date>" in gray-400 but doesn't visually warn when data is stale. With the IG session-refresh bottleneck leaving feeds stale for days at a time, the user wasn't getting a clear signal.
- fix: compute `ageHours` from `lastUpdated`. Color the "Updated" line gray when < 8h, amber when 8-48h ("feed is getting stale; the scraper may be blocked"), red + bold + ⚠ when > 48h ("IG session likely expired"). Tooltip explains the exact age.
- result: visible at-a-glance staleness signal. The current deployed feed timestamps as ~21h stale; with this iter the user will see amber + tooltip explanation instead of silently looking at old data.

### fb-146 — Shareable account-filtered URLs via `?account=X` query param
- created_at: 2026-05-29
- source: agent-proposal (iter 104; smaller scope than README §361 dedicated route)
- status: addressed (committed in iter 104)
- body: AccountBanner already renders when `search` starts with `@`. Added URL state sync: `?account=<handle>` is read on mount (with safe-handle regex `^[A-Za-z0-9_.\-]{1,40}$` to keep XSS surface minimal) and written when `search.startsWith("@")`. Makes account-filter views bookmarkable + shareable without needing static-route generation. Cleaner than the README §361 idea (which would require `generateStaticParams` for every known account).
- usage: `https://prajjwal1.github.io/nyc/?account=bookclubbar` → opens with the bookclubbar account filter active. Also chains: `?account=bookclubbar&view=calendar&date=2026-06-15`.

### fb-145 — Green-Wood Cemetery URL update (greenwoodcemetery.org → green-wood.com)
- created_at: 2026-05-29
- source: agent-proposal (iter 103 audit)
- status: addressed (committed in iter 103)
- body: `https://greenwoodcemetery.org/events/` (in GENERIC_URLS) redirects to green-wood.com which 503s on bare host. The direct path `https://www.green-wood.com/events` works and yields 10 events (Green-Wood After Hours evening tours through June+).
- bonus negative finding: bookmanager API helper (powers bookclubbar + lizsbookbar) doesn't need pagination — already returns multi-month data (May through September for bookclubbar). No fix needed there.

### fb-144 — mcnallyjackson month-pagination (3 → 44 future events)
- created_at: 2026-05-29
- source: agent-proposal (iter 102 audit)
- status: addressed (committed in iter 102)
- body: mcnallyjackson.py yielded 33 events but only 3 future — same current-month-only issue as the iter 91 comedy-club fix. Inspected page HTML: found 6 unique `/events` URLs including `/events/2026/06` (35 June events) and `/events/2026/07` (11 July events). The bare `/events` route only ships current-month.
- fix: added `_month_urls()` generating `/events/YYYY/MM` for the current + next 2 months at scrape time (handles year rollover). Dedup by (title, date) so any overlap with the bare /events doesn't double-count.
- result: 33 → 79 events extracted, 3 → 44 future events surviving filters (14× lift). Sample: "Matthew Campbell & Mike Bird" (Jun 1), "New Directions Book Club" (Jun 2) — actual literary programming the user follows.

### fb-143 — dice.py rewritten for __NEXT_DATA__ (0 → 30 events)
- created_at: 2026-05-29
- source: agent-proposal (iter 101 audit)
- status: addressed (committed in iter 101)
- body: README marked dice as `✗ "URL changes. Try harder."`. Live probe: `dice.fm/browse?location=new-york` returns 625KB with 3 JSON-LD blocks (all site-metadata: Brand, WebSite) AND a `__NEXT_DATA__` script containing `pageProps.events` — 30 events with structured fields (name, dates.event_start_date, venues[].name/address/location, images.landscape, perm_name). The iter-84 `EVENT_TYPES` fix was reading from the wrong data shape.
- fix: read events from `__NEXT_DATA__.props.pageProps.events`. Build full event with venue name + address + lat/lng + image URL + ticket URL (`dice.fm/event/<perm_name>`). Kept JSON-LD path as defensive fallback in case DICE flips schemes again. Quirk: `about` is `{description, highlights}` dict (not a string).
- result: 30 events / 25 future surviving filters. Sample: "Horse Meat Disco NY in The Ruins", "T4T LUV NRG Pride: Eris Drew b2b Octo Octa", "Elsewhere Presents: Chanel Beads" — indie DJ + live music programming.
- doc cleanup: KNOWLEDGE.md ✗ entries corrected for **dice** (`✅ __NEXT_DATA__`), **theskint** (`✅ RSS via substack`), **bookclubbar** (`✅ bookmanager API`). All 4 remaining `✗` rows in the source table are now resolved over iter 99-101.

### fb-142 — nycforfree.py rewritten for Squarespace eventlist (+126 events)
- created_at: 2026-05-29
- source: agent-proposal (iter 100 audit)
- status: addressed (committed in iter 100)
- body: README marked nycforfree as `✗ "HTML structure unclear. Use IG @nycforfree.co."`. Live probe: nycforfree.co/events is a standard **Squarespace eventlist** with 129 articles (`article.eventlist-event`), same pattern as brooklyncomedy.py. The old scraper looked at the wrong URL (`/`, no events) and CSS selectors. Rewritten to fetch `/events` with 90s timeout (~2MB page) and parse `a.eventlist-title-link`, `time.event-time-24hr-start[datetime]`, `.eventlist-description`, `.eventlist-column-thumbnail img`.
- result: 0 → 126 events, 83 future surviving filters. All correctly tagged `price="free"`. Sample: "U.S. SailGP Fan Zone", "Last Crumb Grand Opening", "Jung Saem Mool Glass Skin Atelier Pop-Up" — exactly the free/pop-up coverage nycforfree.co specializes in.
- KNOWLEDGE.md status: ✗ → ✅ with yield numbers.

### fb-141 — parks.py is actually working + CANCELED leak
- created_at: 2026-05-28
- source: agent-proposal (iter 99 audit)
- status: addressed (committed in iter 99)
- body: README §66 / KNOWLEDGE.md marked parks scraper as `✗` ("didn't return events. Try API."). Live probe found it's actually working: **50 events from nycgovparks.org/events**. Most are "Kids in Motion" (correctly blocked by existing kids/word-boundary filter), leaving 22 legit events surviving: Bellydance, Yoga, Cardio, Bootcamp, Dance Fitness, "Hudson Classical Theater: Uncle Vanya", "Bryant Park Picnic Performance: Jazzmobile", "World Cinema Nights".
- but: 5 "CANCELED: <event>" entries were leaking through. The leading marker is unambiguous.
- fix:
  1. HARD_BLOCK_KEYWORDS += `canceled:`, `cancelled:` (both spellings)
  2. KNOWLEDGE.md status `✗ parks` → `✅ parks` with the actual yield numbers.
- 5 canceled → 0; 22 legit events continue to surface. Parks events should appear in the next scrape (cultural / fitness programming is high-value for the user).

### fb-140 — Museums.py shipped page-scaffold strings as events
- created_at: 2026-05-28
- source: agent-proposal (iter 98 audit)
- status: addressed (committed in iter 98)
- body: Iter 84 extended museums.py's @type acceptance but didn't probe live yield. Audit found:
  - MoMA returns 403 to every UA (bot block)
  - Guggenheim `/calendar` 404s (URL moved to `/event`)
  - Brooklyn Museum / Whitney / New Museum / The Met all JS-render their event data (no JSON-LD, no `__NEXT_DATA__`)
  - The DOM-card fallback was scraping page-scaffold strings as "events": `"Thursday, May 28"` (calendar header), `"Narrow search"` (filter widget), `"Today's events"` (page heading) — all dated 2027-05-28 or 2031-05-01 from far-future date misparse.
- fix:
  - Removed MoMA from MUSEUMS (bot-blocked).
  - Updated Guggenheim URL `/calendar` → `/event`.
  - `_MUSEUM_TITLE_REJECT_RES`: 7 patterns rejecting page-scaffold titles (weekday-headers, "Today's events" with straight + curly apostrophes, "Narrow search", "view/see all events", bare dates, "Upcoming/Featured events").
  - `_is_museum_card_junk(title)` gate applied in `_from_card`.
- result: 3 garbage events → 0. Honest empty is better than fake events polluting the feed with "Thursday, May 28" at score 0.5+.
- known-broken (no fix this round): museum sites JS-render; full restoration would need a JS-rendering pipeline. README §70-83 already documents this class of source. The Met + Brooklyn Museum are in "tried and blocked".

### fb-139 — Set up Reddit OAuth (PRAW) for full comment-mining
- created_at: 2026-05-28
- source: agent-proposal (iter 97)
- status: open (requires user action)
- body: Reddit's `/.json` API now requires OAuth. To restore comment-mining (the main URL source per README), the user needs to:
  1. Register an app at https://www.reddit.com/prefs/apps (script type)
  2. Set GitHub secrets: `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`
  3. Add a small `praw.Reddit(...)` wrapper to `scrapers/sources/reddit.py`
- once done, the iter 97 RSS fallback can stay as defense-in-depth.

### fb-137 — Substack parser only handled RSS, missed Atom (eaterny 0→8)
- created_at: 2026-05-28
- source: agent-proposal (iter 96 audit of substack feeds)
- status: addressed (committed in iter 96)
- body: Surveyed all 7 substack-style feeds. `eaterny` (Eater NY, food/restaurant openings) was returning 0 events. Root cause: Eater NY uses **Atom XML** (`<feed><entry>` with default Atom xmlns) instead of RSS (`<channel><item>`). The substack parser strictly looked for `<channel>` and bailed otherwise.
- fix: `_parse_feed` now falls back to `root.findall("a:entry", ...)` when no `<channel>` found. `_parse_item` extended to read Atom-namespaced `title`, `published`/`updated`, `summary`/`content`, and `<link rel="alternate" href=...>`.
- result: eaterny 0 → 8 events extracted. Sample: "Taqueria Ramirez's Soccer Bar Opens Just In Time for the World Cup", "A Force Behind Ultra-Lauded Atomix Is Opening Her Own NYC Restaurant" — these are restaurant openings = legit user-attendable food events.
- bonus finding: meetup search-page pagination doesn't actually paginate. Probed 6 param patterns + 20 category IDs — most cats ignored. The 4 SEARCH_URLs yield ~45 events, can't grow via pagination. Logged as "no actionable" so future iters don't re-investigate.

### fb-135 — theskint over-fragmentation: 172 events from 11 RSS posts
- created_at: 2026-05-28
- source: agent-proposal (iter 94 audit)
- status: addressed (committed in iter 94)
- body: theskint substack feed was generating 172 "events" from 11 RSS posts because `_extract_from_headings` treats every body `<h2>/<h3>/<strong>/<b>` as an event title. theskint posts are mixed: weekday-roundup posts ("WEDS-THURS, 5/27-28: MANHATTANHENGE, BUSTA RHYMES, ...") SHOULD be fragmented, but single-event sponsored posts ("CELEBRATE THE MODERN AMERICAN THEATER AT HB STUDIO'S FESTIVAL") were leaking dozens of button-text + paragraph fragments.
- fix: added `_looks_like_roundup(title)` heuristic that matches weekday-pair prefixes (`WEDS-THURS,`, `FRI-TUES,`, `MON, 6/3:`). Single-event posts skip heading fragmentation. Also extended `_is_date_only_title` to drop day-name fragments ("wednesday") and date ranges ("May 30 to June 5") that were leaking from roundup posts.
- result: 172 → 106 extracted events. The real-event count from theskint is small either way (~6 surviving filters) because theskint's HTML doesn't have clean per-event structure, but noise is materially reduced. Single-event posts now contribute 1 event instead of 15-30 fragments each.

### fb-134 — bookclubbar venue-rental "[PRIVATE EVENT" leak
- created_at: 2026-05-28
- source: agent-proposal (iter 93 audit)
- status: addressed (committed in iter 93)
- body: bookclubbar live yield is 34 events, mostly high-quality (Author Event, Galinsky Poetry, etc). Two duplicate "[PRIVATE EVENT - closed from 6pm to 10pm]" entries were leaking — those are venue closures for private rentals, not public events. Added `[private event` (with bracket) to HARD_BLOCK_KEYWORDS. The bracketed form is specifically a Book Club Bar / event-calendar convention so won't false-positive on legit phrases like "host your private event tips". Verified 3/3 test cases.
- bonus finding: lizsbookbar yield is healthy at 19 events all passing filters — no fixes needed there.

### fb-133 — NYPL audit: 79 events surviving filters, "Playdate at the Library" leak
- created_at: 2026-05-28
- source: agent-proposal (iter 92 audit)
- status: addressed (committed in iter 92)
- body: NYPL was 3/246 events in deployed feed. Live yield is 121 events (all future from Refinery API + HTML keyword searches). 42 correctly blocked as kids programming, 79 survive — including "Playdate at the Library" which is clearly a parent/kid event but had no caught keywords.
  - Refinery API doesn't expose an `audience` attribute (confirmed via API inspection — keys are `event-id, name, description-short, image, registration-type` only). Can't filter structurally; must use text patterns.
- fix: added `playdate`, `caregivers`, `caregiver and child` to HARD_BLOCK_KEYWORDS. All 3 are near-exclusively parent/kid terms. 4/4 tests pass including negative cases (Adult Book Club, Author Talk).
- note: the 79 surviving NYPL events are still mostly not surfacing in deployed feed because their score < MIN_SCORE=0.5 (NYPL events have generic titles + DEFAULT_IMAGE + thin descriptions, scoring low). That's working as intended — score floor is the right gate for low-info library events.

### fb-132 — Comedy-club month pagination + dynamic URL injection
- created_at: 2026-05-28
- source: agent-proposal (iter 91 audit)
- status: addressed (committed in iter 91)
- body: Comedy clubs were at 2 + 6 events in deployed feed despite stats_history showing yields of 33 + 60 two weeks ago. Probed: NYCC `/calendar` and East Ville Comedy `/events` return ~267 events combined but **all in May 2026** — only 32 are future after today (2026-05-28). The default calendar page only shows the current month; past-date filter strips most.
- discovery: `/calendar/YYYY-MM` pattern reaches future months. NYCC has 109 June + 22 July events; East Ville has 34 June + 38 July events.
- fix: added `_dynamic_calendar_urls()` that generates URLs for the current + next 2 months for both clubs at scrape time (handles year rollover). Avoids hardcoding dates that would go stale monthly.
- expected impact: ~235 future comedy events available, capped to top-25 by existing SOURCE_VOLUME_CAPS (newyorkcomedyclub=15 + eastvillecomedy=10). The comedy category share rises meaningfully and the events are top-quality picks from a much deeper pool.

### fb-131 — Eventbrite pagination works but only page 1 was scraped
- created_at: 2026-05-28
- source: agent-proposal (iter 90 audit)
- status: addressed (committed in iter 90)
- body: Eventbrite was 111/246 events in deployed feed. Probed `?page=N` query param — it paginates correctly (page 2 returns "OkayAfrica x Elsewhere" vs page 1's "BROOKLYN CARNIVAL"; page 5 of all-events still yielded 20 distinct events for a cumulative 100 unique). All ~30 categorical URLs in `GENERIC_URLS` only fetched page 1, missing ~200+ events per scrape.
- fix: added `?page=2` and `?page=3` for the 3 high-density `all-events` URLs (new-york, brooklyn, queens) and `?page=2` for 5 high-priority categorical URLs (music, comedy, parties, dating, singles) — +9 new fetches total.
- bounded with SOURCE_VOLUME_CAPS["eventbrite"]=100. The user explicitly likes "less is more" per the existing cap comments. 100 events keeps Eventbrite from dominating while letting the top-N bubble up from a much deeper pool — same feed size, higher quality, more diversity.
- expected impact: same eventbrite share (~100/feed_total) but the events are top-quality picks from a ~300-event pool instead of all 111 page-1 hits. Music/comedy/parties/singles depth improves significantly.

### fb-130 — AllEvents.in pagination broken (`?page=N` returns page 1)
- created_at: 2026-05-28
- source: agent-proposal (iter 89 audit, following the Songkick thread)
- status: addressed (committed in iter 89)
- body: AllEvents had 14 events in deployed feed. `GENERIC_URLS` had 6 borough URLs using `?page=2..5` for pagination but live probe showed every `?page=N` returns the same page-1 events as the bare URL — 4-5 wasted fetches per scrape.
- discovery: AllEvents uses time-window paths (`/today`, `/tomorrow`, `/this-weekend`, `/upcoming`, `/all`) which return distinct event slices. Probed against the bare URL: each yields 5-30 net-new events.
- fix: replaced the 6 dead `?page=N` URLs with 7 time-window URLs across the 4 borough pages. Live verified: total unique events 353 from 13 URLs (vs ~65 prior with 12 URLs that included duplicates) — 5.4× lift.

### fb-129 — Songkick pagination broken (path suffix vs query param)
- created_at: 2026-05-28
- source: agent-proposal (iter 88 audit)
- status: addressed (committed in iter 88)
- body: Audit: Songkick listed at 16 events in deployed feed despite README claiming "major live-music coverage." Investigated: `GENERIC_URLS` had 7 metro-area URLs using path-suffix pagination — `/metro-areas/.../2`, `/3`, etc. **All 7 path-suffix URLs returned the same page-1 49 events.** Effectively scraping the same content 7 times, costing 6 wasted fetches and capping yield at ~49 unique titles.
- fix: switched to `?page=N` query-param pagination. Live-verified each `?page=2..7` returns ~48 distinct MusicEvent JSON-LD items. Total yield: 334 events, 306 unique titles (6.2× lift). Many duplicates across pages because Songkick repeats artists across venues/dates — downstream dedup handles cleanly.
- expected impact on next scrape: music category share rises substantially; `Instagram is dominant source` sanity_check threshold becomes easier to satisfy as the overall feed grows.

### fb-128 — Substack product-affiliate noise ("Mini Phone Tripod (link)")
- created_at: 2026-05-28
- source: agent-proposal (iter 86 audit)
- status: addressed (committed in iter 87)
- body: Substack RSS includes product affiliate links as RSS items: "J.Crew Cosmo pant", "Mini Phone Tripod (link)", "Apple Wired Ear Pods (link)". Trailing "(link)" + retail-host sourceUrl = clear non-event.
- fix: `_is_affiliate_noise(title, source_url)` checks: title ends with `(link)`/`[link]` OR sourceUrl host matches a deny-list of retail/social hosts (amazon, jcrew, macys, apple, llbean, shopstyle, ltk, distrokid, mirror.xyz, audius, spotify, variety, gofundme, twitter, x.com). Applied per-heading in `_extract_from_headings` before `build_event`. Audit confirmed 13 noise → 0 remaining post-fix.
- bonus: removed 2 confirmed-404 FEEDS URLs (untappedcities.com/feed/, nycgovparks.org/news.rss) so scrape budget isn't wasted.

### fb-126 — Partiful image-field rename + "ged" substring false-positive
- created_at: 2026-05-28
- source: agent-proposal (iter 85 audit of Partiful low yield)
- status: addressed (committed in iter 85)
- body: Audit: live Partiful yield is 15 events but the deployed feed had 1. Two causes:
  1. **Image-field rename**: the scraper read `event_data["coverPhotoUrl"]` but Partiful's __NEXT_DATA__ now uses a nested `image: {url, upload: {url}}` object. Every event came in with `imageUrl=None`, then `_IMAGE_REQUIRED_SOURCES` (partiful is in that set) dropped them all as shell. Fix: read `coverPhotoUrl` first, fall back to `image.url` or `image.upload.url`. Verified: 15/15 events now carry an image URL.
  2. **"ged " substring false-positive**: `HARD_BLOCK_KEYWORDS` had `"ged "` (with trailing space) to block GED prep classes. It false-fired on "collaged", "encouraged", "aged", "engaged" — substring match doesn't respect word boundaries. Moved `ged` and `tefl` (same shape) into `_WORD_BOUNDARY_KEYWORDS` so they only block on real word boundaries.
- result: surviving partiful events 1 → 8 (+7, of which 7 were image-field, 1 was the GED unblock).

### fb-125 — Same strict-@type bug across luma / music_venues / museums / dice
- created_at: 2026-05-28
- source: agent-proposal (iter 84; followed fb-124's thread)
- status: addressed (committed in iter 84)
- body: Audited every source scraper for the same strict `@type == "Event"` filter that iter 83 fixed in Meetup. Found 4 more affected:
  - `luma.py:212` — strict `@type != "Event"` — dropping all subtypes
  - `music_venues.py:54` — Event|MusicEvent only — dropping ComedyEvent, TheaterEvent, ScreeningEvent, Festival
  - `museums.py:60` — Event only — dropping ExhibitionEvent, VisualArtsEvent, EducationEvent (artist talks), ScreeningEvent (film series)
  - `dice.py:20` — Event|MusicEvent only — dropping ComedyEvent, TheaterEvent
- fix: each now imports `EVENT_TYPES` from `generic.py` (canonical set of 18 subtypes) + uses a small `_is_event(t)` helper supporting str-or-list `@type` values. `meetup.py` DRY'd to use the same import.
- expected impact: more events captured from these sources on next scrape — especially museum talks/screenings + venue comedy/theater shows that were silently invisible.

### fb-124 — Meetup Schema.org Event-subtype acceptance
- created_at: 2026-05-28
- source: agent-proposal (iter 83 trace of the Quine event)
- status: addressed (committed in iter 83)
- body: Traced the iter 81 "Word and Object by Quine Week 4 — TMIRCE brunch desc" anomaly. The Meetup page's JSON-LD correctly carries the right title + the right description ("How does language come to have meaning…") tagged `@type: EducationEvent`. But `_parse_meetup` strictly filtered on `@type == "Event"`, so EducationEvent / MusicEvent / TheaterEvent / etc. were all routed to the empty-description DOM card fallback. Wrong descriptions could then bleed in from sibling cards on search pages.
- fix: extended acceptance to a Schema.org Event-subtype set: `Event, EducationEvent, BusinessEvent, SocialEvent, MusicEvent, SportsEvent, TheaterEvent, DanceEvent, ComedyEvent, FoodEvent, Festival, ScreeningEvent, ExhibitionEvent, VisualArtsEvent, LiteraryEvent`. Mirrors `generic.py::EVENT_TYPES`.
- verified: re-parsed Quine's Meetup page → "Word and Object by Quine Week 4" + the correct philosophy description (no more TMIRCE bleed). All philosophy / language / education Meetup groups will now extract correctly.

### fb-123 — Categorizer false-positives ("movies" on dating, "celebrities" on dog rescue)
- created_at: 2026-05-28
- source: agent-proposal (iter 81 audit)
- status: addressed (committed in iter 82)
- body: Identified two trigger phrases in `event_parser.CATEGORY_KEYWORDS`:
  1. `premiere` was in `movies` — false-fired on "NYC's Premiere Party for lesbians" and "Premiere Brunch Series" (means "best/first", not "movie premiere"). Replaced with disambiguated phrases: `movie premiere`, `film premiere`, `premiere screening`.
  2. `meet & greet` was in `celebrities` — false-fired on "meet & greet shelter dogs" (TMIRCE bRUNch) and "Founders Coffee Meet & Greet". Replaced with `celebrity meet`, `celebrity m&g`.
- Verified: 4 positive tests still pass (real movie nights / celebrity m&g still tag correctly), 4 negative tests pass (no false positives on Sapphics, brunch with dogs, founders coffee).
- separate issue still open: "Word and Object by Quine Week 4" event's title doesn't match its description (description was about TMIRCE bRUNch). That's a data-quality bug, not a categorizer one — likely cross-source title swap during dedup. Tracked separately if it recurs.

### fb-121 — Audit iter 77 organizer-match real-world yield
- created_at: 2026-05-28
- source: agent-proposal (iter 80; validation of iter 77 claim)
- status: addressed (committed in iter 80)
- body: Iter 77 added an organizer-name match path to the enrichment, claiming it would surface Eventbrite events from accounts the user follows. Probed 15 random Eventbrite + 15 random Meetup events live: 0/30 organizer names overlap with user_following. NYC Eventbrite organizers are mostly tour/event companies / one-off promoters / venues ("Crush Wine Experiences", "lululemon Williamsburg", "Mireve for Women") not the indie social/curator IG brands the user follows. Meetup groups have entirely different naming. The match path stays as defensive infrastructure (cheap, harmless, may catch future matches) but is documented as low-yield in practice.
- also fixed: iter 77 was storing the FULL org name ("Vital Run Club") as `event.account`, breaking the UI ribbon's @account link semantics. Now stores the matched IG handle ("vitalrunclub") in `account` and keeps the human org name in `event.organizer` for display.

### fb-120 — Clean stale transient-killed entries from dead_accounts.json
- created_at: 2026-05-28
- source: agent-proposal (iter 79; janitorial follow-up to iter 1 P1)
- status: addressed (committed in iter 79)
- body: Iter 1 P1 added a runtime auto-revive for the 54 accounts mass-killed on 2026-05-24 by transient `feedback_required` errors. The skip-set builder correctly bypasses them, but the JSON file itself still carried the stale entries — misleading for sanity_check + ops readers. New `scrapers/maintenance/clean_dead_accounts.py` is an idempotent purger (dry-run by default, `PURGE=1` to apply). Removed 54 entries; 58 remain (26 legitimate `not_exists` + 32 legitimate `stale_no_recent_posts`).
- side benefit: `sanity_check.py` "Newly-dead accounts in last 7 days" dropped from 54 → 0, killing the "sudden dead-account growth" WARNING signal.

### fb-119 — "From accounts you follow" hero in TopPicks
- created_at: 2026-05-28
- source: agent-proposal (iter 78; surfaces the iter 73-77 enrichment work)
- status: addressed (committed in iter 78)
- body: 5th hero in TopPicks, sky-themed, sandwiched between Just Added and Saved. Filters `upcoming` events where `userFollowing` fires (capped at 6). Hero ordering: Tonight → Weekend → Just Added → Following → Saved → per-day. Follow-graph signal is the highest-conviction predictor of "events the user would attend" — surfacing them as a dedicated hero (instead of buried per-day) directly serves the North Star. Combined with iter 73-74 (URL handle + venue-domain) + iter 77 (organizer name), this hero will populate with up to ~35 events post next-scrape (6 current IG userFollowing + 29 enriched).
- Visual choice: 👤 emoji + sky-50/60 background to match the iter 71 U1 ribbon (sky for follow signal).

### fb-118 — Extract organizer name from JSON-LD + match against IG follows
- created_at: 2026-05-28
- source: agent-proposal (iter 77; extends iter 73-74 enrichment to JSON-LD events)
- status: addressed (committed in iter 77)
- body: Eventbrite/Lu.ma/etc. JSON-LD events include `organizer.name`. The generic JSON-LD parser was discarding this field. Now stamped onto the event as `event.organizer`, then `_enrich_provenance_from_url` matches `event.organizer` against user_following via alphanumeric fold + suffix stripping (`nyc`, `ny`, `brooklyn`, `bk`, `manhattan`). Catches: "Vital Run Club" → `vitalrunclub`, "Reading Rhythms NYC" → `readingrhythms` → `reading_rhythms`, "BookClubBar" → `bookclubbar`. Rejects: generic short names ("AB Productions", "Yoga Studio") via 5-char floor.
- Impact will land on next scrape — current deployed feed has no `organizer` field (only `organizerUrl`); the JSON-LD extraction starts populating it on the next CI scrape.

### fb-117 — Surface attended-yes on cards
- created_at: 2026-05-28
- source: agent-proposal (iter 75; completes the iter 71 UI loop)
- status: addressed (committed in iter 75)
- body: Iter 71 shipped the EventModal "Did you go?" Yes/No prompt + localStorage state, but the user could only see the answer by re-opening the modal. Added at-a-glance badges on past events:
  - GridCard: emerald `✓` circle at bottom-right (5x5), title hover "You marked attended"
  - FeedCard + MediaFirstCard: inline `✓ went` pill next to the title (emerald-100 bg, emerald-800 text, 10px)
- Only renders when `event.date < today AND getAttendedState(event.id) === "yes"`. No render for "no" or unmarked. Build + TypeScript clean.

### fb-116 — Extend follow-graph signal to venue-domain hosts (bookclubbar.com)
- created_at: 2026-05-28
- source: agent-proposal (iter 74)
- status: addressed (committed in iter 74)
- body: Extension of fb-115. Beyond Lu.ma + Partiful, venues that run their own .com (bookclubbar.com, theskint.com, lizsbookbar.com, green-wood.com) have a second-level domain that often is the canonical handle. `_extract_handle_from_url` now falls back to hostname extraction when the URL is not a lu.ma/partiful pattern. An `_AGGREGATOR_HOSTS` deny-list keeps eventbrite/meetup/songkick/allevents/instagram/luma/dice from being misread as handles. Matches against user_following only; lizsbookbar (curated but user doesn't follow on IG) correctly DOES NOT fire userFollowing.
- impact: +13 bookclubbar.com events get userFollowing. Combined with iter 73, non-IG userFollowing events 0 → 29 (Lu.ma 16 + bookclubbar 13). Combined with deployed-feed's existing 6 IG userFollowing events, high-conviction ratio rises from 3.3% to projected 15.0% on next scrape.

### fb-115 — Extend follow-graph signal to Lu.ma via curator-handle URL match
- created_at: 2026-05-28
- source: agent-proposal (iter 73)
- status: addressed (committed in iter 73)
- body: Audit finding: Lu.ma events have the curator handle right in the sourceUrl (`lu.ma/litclub.nyc`, `lu.ma/readingrhythms-manhattan`), and those handles are often signal_accounts the user follows on IG. Currently userFollowing only fires on IG events. New `_enrich_provenance_from_url` in `normalize.py` walks all events post-extraction, extracts handles from Lu.ma + Partiful URLs, and matches them against the user_following set (`discovered_accounts.json::discovered_via==user_following`). Handle normalization: strips `-manhattan/-brooklyn/-nyc` suffixes, swaps `_↔-`, and falls back to alphanumeric-only fold so `readingrhythms-manhattan` ↔ `reading_rhythms` matches.
- impact (against today's deployed feed): non-IG userFollowing events 0 → 16 (+10 Reading Rhythms events all attributable to the user's follows). High-conviction ratio rises from 6/246 (non-IG) → 16/246 by enriching alone.
- next-iter follow-ups: same pattern for Eventbrite organizer slugs, Substack newsletter handles.

### fb-114 — Fold title + location.name into neighborhood inference
- created_at: 2026-05-28
- source: agent-proposal (iter 72 audit; 47% of deployed feed has null neighborhood)
- status: addressed (committed in iter 72)
- body: Audit found 32 of 116 events with `location.neighborhood: null` whose **title** explicitly contained a neighborhood keyword ("Harlem Book Company", "The 9:30 Comedy Show - Williamsburg", "Astoria Speed Dating", "Bushwick Collective"). The address had no neighborhood signal but the title did. `infer_neighborhood` now accepts `*extras` (title + location.name) and the two call sites (`event_parser.build_event` + `normalize._reinfer_neighborhood`) pass them. 8/8 test cases pass including negative tests for "Asian Founders Club" and "Backgammon Club" (no false-positive on "club" or "bk"-inside-Backgammon).
- expected lift: neighborhood coverage rises from 53% to ~66% next scrape; topic-coverage for `bk` / `brooklyn` should also lift since the synonym fold (fb-103/fb-111) now has more events to attach to.

### fb-113 — "Did you go?" feedback on past events (README §362)
- created_at: 2026-05-28
- source: agent-proposal (iter 71; ships the calibration loop the user named as the North Star input)
- status: addressed (committed in iter 71)
- body: Closes the loop between "events the system surfaces" and "events the user actually attends." EventModal now shows a "Did you go? [Yes, I went] [No, I didn't]" block on any event whose `date < today`. Persisted in `nyc-events:attended:v1` localStorage map ({eventId: "yes"|"no"}). Profile bumps: yes = +8 account, +5 category, +3 host (strongest positive signal we have — stronger than save). No = -2 account, -1 category, clamped to 0 to prevent NaN in `interestBoost`'s log2 path. Cap 500 most recent. Shows the previous answer on subsequent opens with a confirmation message.
- next-iteration follow-ups: (a) consider also rendering on FeedCard for past events directly, (b) surface aggregate stats in ActivityPanel ("you've attended N saved events"), (c) feed attended-yes events back into the calibration ask for fb-100.

### fb-112 — WNYC.org is a JS-rendered SPA, no RSS/iCal
- created_at: 2026-05-28
- source: agent-proposal (iter 70)
- status: wont-do: requires JS rendering — not in current scraper toolkit. Out of scope.
- body: Critic suggested probing `wnyc.org/series/wnyc-book-club` (interest_profile `curated_title_hints`). Tested: `/series/wnyc-book-club` and `/series/wnyc-book-club/events` return 404; `/events` is an SPA (the generic scraper SPA-salvage already queues 4 child URLs into `discovered_urls.json` but they're also SPAs with no extractable structure). No `/feeds/events.{rss,atom,ics}` or `/calendar.ics`. WNYC is in the same bucket as Met / Book Club Bar / Time Out — JS-only sites that need a different access pattern.

### fb-104 — Prune redundant `/nyc/<topic>` URLs from LUMA_PAGES (after fb-105)
- created_at: 2026-05-28
- source: agent-proposal (dreamer-critic D2, DREAM-DEFER)
- status: open (blocked-by: fb-105)
- body: Critic verified that 60 of 66 `LUMA_PAGES` entries (`scrapers/sources/luma.py:7-91` `/nyc/<topic>` block) return identical content to `/nyc`. The 6 curator calendars at the bottom DO yield distinct content. Once fb-105 grows the curator-calendar list, drop the redundant 60 URLs (8x scrape budget savings).
- deferred reason: additive-only rule. Removing seed URLs needs explicit user opt-in. The 60 URLs scrape redundant content but don't fail; downstream dedup absorbs it.
- "addressed" criterion: `LUMA_PAGES` contains only `/nyc` + a non-empty list of curator calendars. No `/nyc/<topic>` entries.

### fb-100 — Run calibration ask next round
- created_at: 2026-05-28
- source: agent-proposal
- status: addressed (iter 198 — see calibration response below)
- body: This first invocation deferred the user-ask. Next run should call `AskUserQuestion` with 3 real events from `account ∈ signal_accounts` and ask which the user would actually attend. That answer is the ground-truth signal for whether the loop is improving.
- "addressed" criterion: A `/self-improve` run logs a user response to the calibration question in `<run-dir>/feedback.md`.
- calibration response (iter 198, 2026-06-01):
  - Question: "Of these 3 high-conviction events from accounts you follow, which would you actually attend?"
  - Options:
    1. East Village Wordsmiths Literary Salon @ Book Club Bar
    2. Garden Rest and Read @ litclub.nyc
    3. GonzoFest Social - Happy Hour @ Book Club Bar
  - User answer: **ALL THREE** (3/3 — strongest possible signal that the curated-host enrichment is well-aligned).
  - Calibration takeaway: events from `litclub.nyc`, `bookclubbar`, `readingrhythms-manhattan`, and similar curated literary hosts are the user's actual attend-target. The iter 73/74/77/109 enrichment paths surfacing these events as `userFollowing` are validated. No category-coverage gap implied — books/parties/food/outdoors covered. Continue the current enrichment + ranking strategy; the loop is moving in the right direction.

### fb-169 — Make AccountBanner key on event.account (clickable enriched conviction handles)
- created_at: 2026-06-04
- source: agent-proposal (dreamer-critic D2, DREAM-DEFER, run 2026-06-04-1904)
- status: addressed: 707b444 (ui-U1, run 2026-06-15-1724 — 3-file change incl. the load-bearing lib/events.ts predicate)
- body: ui-U1 (this round) surfaces the followed `@account` on the 68 cross-source-enriched conviction events as PLAIN TEXT, because `AccountBanner` currently filters by `instagramAccount` only and would render an empty "0 upcoming" banner for a `bookclubbar`/`readingrhythms-manhattan`/`nycforfree`/`silentbookclubnyc` click. D2 completes the loop: extend `AccountBanner`'s filter predicate to match `e.instagramAccount === acct || e.account === acct`, then make the ui-U1 plain-text `@account` a clickable filter button like the IG branch — turning these calibration-validated literary follows (iter-198: user said they'd attend ALL of bookclubbar/readingrhythms/litclub) into working per-account browse routes.
- files: `site/app/components/EventCard.tsx` (provenance branch) + `site/app/components/AccountBanner.tsx` (filter predicate).
- deferred reason: touches a second component; ui-U1 (plain text) is the safe minimal step. Ship only after ui-U1 lands and is confirmed clutter-free.

### fb-170 — Feature One Fine Day NYC's curated events well
- created_at: 2026-06-05
- source: user-explicit
- status: addressed: bca6495
- body: User wants a very good job extracting events from https://onefinedaynyc.substack.com — its blog posts contain a highly-curated list of NYC events that the user wants featured on the site.
- resolution: Rewrote the onefinedaynyc handling in `scrapers/sources/substack.py`. The weekly "NYC This Week" posts mark each curated event with a 📍 pin and encode `📍Title (@ Venue)☁️ Date | Time🎟️ Price+Desc` inline. The old heading-fragment heuristic mangled these (duplicate/mis-dated-to-2027/mis-linked fragments) and leaked the shop (🛍️/🍀/☕) and product (👖/📱) sections as fake events. New `_extract_pin_marker_events` parses the structure deterministically: 📍+☁️ as event discriminator, split on 🎟️ then ☁️, dates anchored to the post's publication year (fixes dateparser future-preference 2027 bug), per-event external venue/lu.ma/eventbrite URL, inline time, free/ticketed price, venue, cleaned description. Also suppressed the whole-post fallback for roundup/guide/calendar container titles (kills the "Your June Guide to NYC" promo-card junk). Verified live on the May weeklies (Brooklyn Ceramic Arts Tour, High Line Plant Sale, Well-Read/Best Dressed Literary Salon → score 1.00); theskint/eater unaffected.
- NOTE for future agents: the MONTHLY "Your X Guide to NYC" posts are now PAYWALLED (RSS ships only an intro + "Read more") — we correctly extract nothing from them. The WEEKLY "NYC This Week | <dates>" posts remain full-text and free — that is the high-value content. When the user reports "no One Fine Day events showing", first check whether a NEW weekly has been published (the feed can lag a few days between weeklies); the parser is correct, the feed simply may not have a current-week edition yet.

### fb-176 — Brooklyn `bk` topic-coverage gap: shorthand not matching (0 events)
- created_at: 2026-06-15
- source: agent-proposal (metrics-before, run 2026-06-15-1724)
- status: addressed: 707b444 (ingestion-P1 — bk<->brooklyn fold in the metrics-script topic counter; measurement bug, bk 0->42)
- body: `metrics-before` shows `topic_counts.bk = 0` across a 378-event deployed feed while `brooklyn = 43`. The `bk → brooklyn` synonym fold (fb-103 iter-1-P6 in `interest_profile.py`) and the venue-name expansion (fb-111 `_normalize_venue_name`) should have lifted this above zero. Either the synonym fold isn't being applied during the topic-count pass that produces `topic_counts`, or no surfaced events carry the `bk` token in a field the topic counter reads. With 43 Brooklyn events present, the borough is well-covered — this is a *measurement/tokenization* gap, not a coverage gap. The user explicitly named Brooklyn shorthand as a tracked topic; a tracked topic sitting at 0 while its long-form sibling has 43 is a regression signal worth closing.
- "addressed" criterion: `topic_counts.bk > 0` on the next metrics snapshot (target ≥ 5, proportional to the 43 brooklyn events), OR a documented finding that the `bk` token is intentionally not derivable from these events with a wont-do rationale approved by the Critic.

### fb-175 — 4 residual IG-Story OCR fragments survive the iter-4fee74e filters
- created_at: 2026-06-15
- source: agent-proposal (post-ship audit of commit 4fee74e)
- status: addressed-partial: 707b444 (ingestion-P2 story-scoped floor dropped the 3 LIVE residuals; 2 not-in-feed residuals deferred — no FP-verifiable rule with 0 live instances)
- body: The 2026-06-15 quality cleanup (commit 4fee74e) shipped hard-blocks + IG-Story OCR fragment filters (date-led, ALLCAPS-neighborhood, OCR symbol-runs, caption openers, World Cup schedule spam) and dropped 38 garbage events with 0 legit events affected. 4 borderline IG-Story residuals remain because they could not be filtered without false-positive risk on legitimate titles: "45 minutes of feel Sood", "2 mini lobster rolls", "Great vibe 1010 experience", "Dance your cares away". These are caption-sentence fragments OCR'd from stories, not real event titles. They need a precision-safe filter (e.g. a story-source-scoped title-quality floor: short imperative/fragment titles from `instagram` source with no date/venue/structured fields) rather than a global keyword block.
- "addressed" criterion: the 4 named residuals are dropped from the feed (verify against a fresh feed snapshot) AND 0 legitimate IG events are removed (precision check against the prior-feed legit IG titles).

### fb-174 — IG GraphQL account-sweep broadly blocked (400) fleet-wide; only saved-posts works
- created_at: 2026-06-15
- source: agent-proposal (discovered during the onefinedaynyc IG work, commit 6d50046)
- status: open (user-blocked — infra/platform constraint, no code fix)
- body: Instagram's GraphQL endpoint now returns 400 for the account-sweep path from BOTH CI runner IPs and residential IPs — the IG account-sweep is degraded fleet-wide, not just an IP/session problem. Only the saved-posts endpoint still works. This is the dominant structural cause behind low follow-graph coverage (12/50) and the chronically low IG share of the feed (14/378). It is NOT fixable by an IG-session refresh alone — the GraphQL account-sweep path itself is blocked. Workers MUST NOT propose IG-account-sweep-dependent fixes as the lever for follow-graph coverage; they must use non-IG enrichment paths (Lu.ma curator handles, venue-domain hostnames, organizer/location.name matching) which work independent of this block. While working on onefinedaynyc IG capture, spot-account multi-event roundups were made to surface as dated events (commit 6d50046) — that path still works via saved-posts and is the recommended pattern.
- "addressed" criterion: user-blocked; cannot be closed by a worker. Reduce dependence on it by lifting follow-graph coverage via non-IG paths (see fb-177).

### fb-173 — GitHub Actions runner IP broadly 403/429-blocked by many publishers
- created_at: 2026-06-15
- source: agent-proposal (discovered during the onefinedaynyc + multi-source work)
- status: open (user-blocked — infra constraint; mitigations shipped)
- body: The GitHub Actions runner IP is broadly 403/429-blocked by many publishers: substack (onefinedaynyc), mcnallyjackson, centerforfiction, nycgovparks, museums, instagram. This degrades CI scrape yield independent of any per-source scraper correctness. Mitigations shipped this session: expanded `CARRYOVER_SOURCES` (so a blocked fetch reuses the last-good events instead of dropping the source to 0), a feed-reader-header retry for substack, and the operational practice of running residential-IP scrapes when CI is blocked. This is a durable infra constraint future agents must account for — a source showing 0 in a CI metrics snapshot may be IP-blocked, not broken. Verify against a residential-IP run before concluding a scraper is broken.
- "addressed" criterion: user-blocked; mitigated via CARRYOVER_SOURCES + residential-scrape practice. Future audits must distinguish "0 events from CI IP block" from "0 events from scraper bug."

### fb-172 — Lu.ma curators + Bond & Grace literary-salon scraper
- created_at: 2026-06-15
- source: user-explicit
- status: addressed: c462147
- body: User: "Capture lu.ma curators (litclub.nyc, readingrhythms-manhattan, philosophy) well + add bondandgrace.com lit-society." Lu.ma curators are now yielding well (litclub.nyc 13, readingrhythms 18, philosophy 6). Added a dedicated Bond & Grace literary-salon scraper (NYC-only).
- resolution: shipped in commit c462147. Lu.ma curator coverage verified yielding; new `bondandgrace` source live (2 events on the current deployed feed per metrics-before SOURCE_DIST).

### fb-171 — Partiful rewritten off /explore/nyc (3 → ~40 robust NYC events)
- created_at: 2026-06-15
- source: user-explicit
- status: addressed: 28d14c0
- body: User: "Improve partiful, make it robust, NYC-only" and pointed to partiful.com/explore/nyc. Rewrote the partiful scraper to read from /explore/nyc, lifting it from 3 to ~40 NYC events, robust, capped, with carryover.
- resolution: shipped (commits incl. 28d14c0). Partiful is 40 events on the current deployed feed per metrics-before SOURCE_DIST — matches the ~40 target and the SOURCE_VOLUME_CAPS bound.


### fb-178 — "Did you go?" attend/skip affordance on past saved events
- created_at: 2026-06-15
- source: agent-proposal (dreamer-critic D2, DREAM-DEFER, run 2026-06-15-1724)
- status: open
- body: Convert passive saves into explicit attend/skip ground truth to close the calibration loop (README §341-369). For events whose date is in the past AND were saved (`isSavedLocal`), render a minimal "Did you go? Yes / No" on the FeedCard (no new widget chrome — consistent with the iter-215 simplification). Persist to localStorage `attended:<eventId>`. A later round adds an ingest path (`scrapers/data/user_attendance.json`) that re-weights `userAffinity` + the topic_counts derivation. Deferred because it needs a storage/ingest design beyond a no-backend round.
- files: `site/app/components/EventCard.tsx` (past+saved branch) + `site/app/lib/interests.ts` (localStorage helper).

### fb-182 — Render qualitative/low-commitment price words as a positive pill (D1)
- created_at: 2026-06-22
- source: agent-proposal (dreamer-critic D1, DREAM-DEFER, run 2026-06-22-1501)
- status: addressed: 8699d96 (run 2026-06-23-1816, U1 — qualitative sky pill, numeric-wins precedence; no-op until a qualitative-price source lands)
- body: U1 (run 2026-06-22-1501) added a digit-only non-free price pill on the FeedCard, intentionally suppressing qualitative price words ("donation", "pay what you can", "PWYC", "sliding scale", "suggested"). But those are POSITIVE low-commitment signals a meet-people user wants at a glance — surfacing them nudges attendance. Add a branch after U1's numeric pill: if `event.price` matches `/donation|pay what|pwyc|sliding scale|suggested/i`, render a distinct subtle pill (e.g. `bg-sky-50 text-sky-700`), visually lighter than FREE so it reads "cheap/flexible" not "free".
- files: `site/app/components/EventCard.tsx` (same badge row U1 touches).

### fb-183 — Consolidate DISTINCT_SCHEDULE_SOURCES into a shared helper + queue fb-106-clean IG fitness/dance candidates (D2)
- created_at: 2026-06-22
- source: agent-proposal (dreamer-critic D2, DREAM-DEFER, run 2026-06-22-1501)
- status: addressed-partial: 8699d96 (run 2026-06-23-1816 — part 1 DONE: `_is_distinct_schedule_source` helper extracted + used by both dedup passes + 3 unit tests. Part 2 (queue the 6 fb-106-clean IG fitness/dance handles) remains OPEN, blocked on fb-174 IG-sweep restoration.)
- body: Two parts. (1) MAINTENANCE: `DISTINCT_SCHEDULE_SOURCES` is now checked at TWO call-sites in `scrapers/normalize.py` (`_dedup_same_account_recurring` and `_dedup_fuzzy_title`). The 3rd+ distinct-schedule source someone adds will need both edits and someone will forget one → a silent merge-back that quietly drops user-requested dated events. Extract `def _is_distinct_schedule_source(ev): return ev.get("source") in DISTINCT_SCHEDULE_SOURCES`, call from both passes, add a unit test asserting a 2nd source bypasses BOTH. Pure refactor, behavior-identical. (2) QUEUED-FOR-IG-REFRESH: source-curator's BFS surfaced on-vector, fb-106-clean IG fitness/dance handles that are unprobeable while the IG sweep is blocked (fb-174): `outopia.run`, `eastriverpilates`, `danceparadenyc`, `barcontranyc`, `residentrunners`, `danceherenownyc`. Probe + add when fb-174 clears so they aren't lost.
- files: `scrapers/normalize.py` (helper); `scrapers/config.py::IG_ACCOUNTS` (when fb-174 clears).

### fb-184 — Investigate the 6 inert legacy Eventbrite fitness/dance slugs (0-yield despite 500+ fetches)
- created_at: 2026-06-23
- source: agent-proposal (source-curator finding, run 2026-06-22-1501; surfaced in that run's hypothesis #2)
- status: addressed: 8699d96 (run 2026-06-23-1816) — RE-SCOPED: premise DISPROVEN. Both backend workers live-probed the 6 legacy slugs and found they parse ~20 events EACH (not inert; url_health emitted_total 80-440). The events die DOWNSTREAM at MIN_SCORE 0.55 + the eventbrite=100 cap, not at extraction. Fix shipped is score-recovery (P1: +0.05 fitness/run/dance boost gated on startTime AND venue), not a parse fix. The legacy slugs are KEPT (they work). NEXT-SCRAPE verify: fitness/dance count rises AND music CRITICAL_CHECK (≥15) not regressed by cap-eviction.
- body: The source-curator's run-2026-06-22-1501 probe found that the pre-existing broad running/yoga/fitness/dance Eventbrite slugs in `scrapers/sources/generic.py` are INERT — they yield 0 events despite being fetched every scrape (500+ cumulative fetches across the session). The 6 NEW narrow slugs added that round (run-club/contra/swing/folk/salsa/pilates) all live-verified at 20/20 future, so the pattern works; the legacy broad slugs are silently returning nothing. Most likely a JSON-LD shape change or a too-broad keyword slug that Eventbrite no longer resolves (cf. fb-155: generic single-word slugs substring-match nothing or the wrong venues). This is a cheap, high-leverage recovery: the user explicitly asked for more fitness/run-club coverage (fb-179), so reviving these slugs (or swapping them for the verified narrow-slug pattern) directly serves that request and the North Star. Ingestion lane: probe each legacy slug's live yield + JSON-LD shape, then either fix the parse path, swap to a verified narrow slug, or remove the dead fetch.
- "addressed" criterion: each of the 6 legacy fitness/dance slugs is classified (working / swapped-to-verified-slug / removed-as-dead) with a live-probe yield count recorded; net fitness/dance event count does not regress and ideally rises on the next scrape.

### fb-185 — Prune duplicate `ny--brooklyn/running--events/` (100% dup of NYC slug)
- created_at: 2026-06-23
- source: agent-proposal (ingestion P1b + Critic APPROVE, run 2026-06-23-1816)
- status: open (blocked-on: user opt-in — additive-only rule)
- body: `https://www.eventbrite.com/d/ny--brooklyn/running--events/` (`scrapers/sources/generic.py:212`) is a 100% duplicate of `ny--new-york/running--events/` (:213) — Eventbrite ignores the borough segment for category search (live overlap verified 18/18 identical). Safe to remove with zero event loss; saves one fetch/round. Removal blocked by the additive-only rule (same class as fb-104). Batch with fb-104 prune opt-ins when the user green-lights deletions.
- "addressed" criterion: user opts into source prunes → remove the line; confirm no event-count regression.

### fb-186 — Strengthen body-text time inference ("doors at 7pm") to unblock the fb-184 fitness gate
- created_at: 2026-06-23
- source: agent-proposal (dreamer-critic D2, DREAM-DEFER, run 2026-06-23-1816)
- status: addressed: d39f664 (run 2026-07-02-1735 — rebuilt `_infer_time_from_text`: keyword-anchored cues + guarded bare-clock am/pm fallback, ranges/multi-time abstain, fill-only. Critic adversarially probed 13 hostile inputs; +15 tests.)
- body: The fb-184 P1 fitness/run/dance score-recovery boost (shipped this round) is HARD-GATED on a parsed `startTime` (+ venue) to preserve the 0.55 quality floor. Many user-requested Eventbrite-category fitness/run/dance events carry their time only in body text ("doors at 7pm", "starts 8pm") so they fail that gate even though they're well-formed. A robust body-text time extractor recovers their yield HONESTLY (raises completeness rather than overriding the floor) and improves the feed-wide `time_q` signal. NOTE: a `_infer_time_from_text` pass already exists in `scrapers/normalize.py` (added 2026-06-04) — this item is to AUDIT/STRENGTHEN it (coverage of "doors"/"starts"/bare "Npm", single-unambiguous-match gating, never overwrite a parsed time) and confirm it runs before scoring so the P1 gate sees the inferred time. Compounds directly with fb-184.
- files: `scrapers/normalize.py` (`_infer_time_from_text` + its call ordering in `process`).

### fb-187 — folk-dance Eventbrite slug is provisional (~55% participatory)
- created_at: 2026-06-23
- source: agent-proposal (Critic keep-but-watch, run 2026-06-23-1816)
- status: open (watch)
- body: `https://www.eventbrite.com/d/ny--new-york/folk-dance--events/` (added 2026-06-22, `scrapers/sources/generic.py`) was independently re-probed this round by both ingestion + source-curator at ~55% participatory (the rest are performances/parties/talks mis-bucketed: "Ayazamana", "Bowie Dance Party"). It clears the bar and additive-only forbids unilateral removal, but it's the weakest dance slug. WATCH: if the next scrape's LANDED folk-dance events under-engage or skew >50% performance, surface as a user opt-in prune.
- "addressed" criterion: next-scrape folk-dance landed-yield assessed; kept if ≥50% participatory, else surfaced for opt-in prune.

### fb-188 — EventModal: style non-free price as a pill (cross-surface consistency with U1)
- created_at: 2026-06-23
- source: agent-proposal (Critic nicety, run 2026-06-23-1816)
- status: addressed: d39f664 (run 2026-07-02-1735 — EventModal now uses FeedCard's numeric-gray + qualitative-sky guards; junk strings render nothing)
- body: U1 (run 2026-06-22) + this round's fb-182 give the FeedCard a numeric gray price pill and a qualitative sky price pill. `EventModal.tsx:172` still renders any non-free/non-unknown price as verbatim text (so qualitative words already show there, un-styled). Low-priority cosmetic consistency: give the modal the same numeric-gray / qualitative-sky pill treatment. Cosmetic-only; no behavior change.
- files: `site/app/components/EventModal.tsx` (~line 172).

### fb-193 — Venue alias normalization (BK Bowl ↔ Brooklyn Bowl, etc.) (D2)
- created_at: 2026-07-02
- source: agent-proposal (dreamer-critic D2, DREAM-DEFER, run 2026-07-02-1735)
- status: open
- body: Normalize venue-name aliases so the same venue expressed differently collapses to one canonical form ("BK Bowl" ↔ "Brooklyn Bowl", "MoMA" ↔ "Museum of Modern Art", etc.). Compounds directly with the fb-189 Step-0 explicit-neighborhood matcher (`_explicit_hood_in_text`) and cross-source dedup (`_dedup_fuzzy_title`) — a canonical venue name improves both neighborhood inference and duplicate collapse. Note: fb-111 already added some venue-abbrev expansion in `_normalize_venue_name`; this extends/consolidates it. Deferred because the payoff (fewer dupes / better neighborhood tags in the feed) is only measurable post-scrape.
- files: `scrapers/normalize.py` (`_normalize_venue_name` / venue-key path).

### fb-197 — Big /plan directive: learn from preferences, stop hardcoding, better suggestions, reimagine UI, make IG scraping work
- created_at: 2026-07-09
- source: user-explicit (/plan, 2026-07-09)
- status: addressed: 23128fd, af4c066, 62a08f9, 6862a8b
- body: User: "learn from my preferences, stop hardcoding; better suggestions; reimagine UI; make IG scraping work." Delivered as a 4-phase program, all shipped to main.
- resolution: Phase A (23128fd) — engagement→preference feedback loop (`scrapers/utils/engagement.py`) + IG reframe/runbook. Phase B (af4c066) — client "Sync taste" UI (`tasteExport.ts`), closing the browser→pipeline loop. Phase C (62a08f9) — semantic TF-IDF taste model (`scrapers/utils/taste.py`), rank by similarity to saves/attends; keyword-list retirement deferred until validated (now tracked as fb-195). Phase D (6862a8b) — "✨ your taste" explainability chip + graceful feed-load error state. Note: "make IG scraping work" is structurally bounded by fb-174 (GraphQL account-sweep 400-blocked fleet-wide) — Phase A reframed the IG approach around the still-working saved-posts path rather than the blocked sweep.

### fb-198 — Incorporate Critic review of the deployed feed (2026-07-09)
- created_at: 2026-07-09
- source: user-inferred (Critic review of the live deployed feed)
- status: addressed: f81a75f
- body: Critic review of the deployed feed (2026-07-09) and its incorporation.
- resolution: shipped in f81a75f. P1 — de-saturated ranking (score cap 0.55→0.32; wine 1.0→0.69, Warm Up 0.77→0.88) so a few sources stop dominating. P6 — taste cold-start from the follow-graph, so the Phase-C taste loop is now active on all 423 events (this is what unblocks fb-195). P5 — purged OCR-garbage and "Copy of" titles. Still-open items from the same review are tracked as fb-194 (Queens/LIC neighborhood P3) and fb-196 (coverage gaps P7).

<!-- Append new feedback above this comment as it comes in. Top of list is highest priority. -->


---

## Closed items

<!-- Items move here when status becomes addressed: <sha> or wont-do: <reason>, except for the seeded README rules above which stay near the top as durable references. -->
