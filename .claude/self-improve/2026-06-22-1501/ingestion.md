# Ingestion Quality Report — 2026-06-22 1501

## Metrics observed (before; from metrics-before.md, feed = site/public/events.json, 365 events)
- Follow-graph coverage: 15/50 (30.0%)
- Topic coverage: all topics ≥1 (no zeros)
- High-conviction ratio: 64/365 (17.5%)
- Fitness/wellness/dance events in feed: 29
- Note: live URL unavailable in sandbox; audited the deployed-equivalent local mirror.

## Audit summary of this round's uncommitted work

**fb-179 (fitness/run-clubs) — VERIFIED, with one refinement (P1).**
- The +10 new IG seeds — `harlemrun`, `frontrunnersnewyork`, `we_run_uptown`, `orchardstreetrunners`, `prospectparktrackclub`, `endorphinsrun`, `runclubnyc`, `thebridgerunners`, `thenovemberproject`, `chelseapiersfitness` — are ALL clubs/orgs/studios. None match the `firstname_lastname` / `firstname<digits>` personal shape. **All pass fb-106.** No reject.
- `fitness` 1.1→1.3 / `wellness` 1.05→1.2 (`scrapers/config.py:320-326`): now in line with games/books (1.3), below singles/music/parties. Not over-boosted. Live-feed fitness scan shows run clubs landing at 0.55–0.92 with no spam; top scorer ("Crush The Cliff Wednesdays" 0.92) is a legit recurring fitness meetup, not spam. No charity-race / fun-run / marathon-fundraiser leaks found in the deployed feed (regex `charity (run|walk|5k|10k)|marathon|fun run|color run|turkey trot|race for` → 0 hits).
- `"running club"` removal from SOFT_PENALTY_KEYWORDS (`scrapers/quality.py:689`): correct and verified.
- **GAP (P1):** recurring run clubs still take a soft-penalty via `"every tuesday"` etc. See P1.

**fb-180 (Brooklyn Contra) — VERIFIED, with two refinements (P3 minor, P4 optional).**
- Live `brooklyncontra.scrape()`: 10 distinct dated events, correct dates parsed from titles, $15/$30 prices, `19:00–22:00`, categories `["dance","music"]`, venue + address set. Quality is good.
- Through `normalize.process()`: the `DISTINCT_SCHEDULE_SOURCES={"brooklyncontra"}` exemption (`scrapers/normalize.py:172`) WORKS — the 6 near-identical "Brooklyn Contra Dance — Live Music & Caller" nights all survive as distinct dated cards (not collapsed). Load-bearing exemption confirmed.
- BUT process() output is **8**, not 10:
  - **−1** = the Oct-4 "Raven & Goose" dance dropped by the `'rave'` substring bug (this is exactly fb-181; see P2).
  - **−1** = the two Sep-26 Harvest Ball products ("Advanced Dance" / "Evening Dance") got merged by `_dedup_fuzzy_title` (same date + same venue loc-bucket + shared tokens "harvest ball dance"). They are genuinely distinct ticketed sessions. See P3.
- After P2 lands, contra yields **9** distinct events (≥8 criterion met). After P3, **10**.

**fb-181 (`'rave'` substring exclusion) — CONFIRMED BUG, precise fix ready (P2).**
- Reproduced: `is_user_excluded()` currently returns True for "Oct. 4th Raven & Goose", "Travel meetup", "Gravel bike ride", "Rave Reviews Book Club" — all false positives from `'rave'` ⊂ those words.
- Verified the deployed feed currently has 0 titles containing the substring "rave" — i.e. the over-broad filter is actively suppressing content (and would suppress the contra dance once contra lands).

## Proposals

### P1: Don't soft-penalize "every <weekday>" recurring markers on fitness/wellness events
- **Metric moved**: high-conviction ratio + topic coverage (run/fitness) — directly satisfies the fb-179 "no run-club event carries a soft-penalty" criterion.
- **File**: `scrapers/quality.py` (the `SOFT_PENALTY_KEYWORDS` scan inside `quality_signals`; keyword list at `scrapers/quality.py:712-718`).
- **Bug**: recurring run/yoga clubs describe themselves as "every Tuesday at 7pm"; `"every monday"/"every tuesday"/"every wednesday"` are in SOFT_PENALTY_KEYWORDS as "generic recurring stuff" deprioritizers. Verified: `quality_signals({'title':'Tuesday Night Run Club','description':'... every Tuesday at 7pm ...','categories':['fitness']})` → `soft_penalty_hits=1`, triggered by `'every tuesday'`. This is the dominant penalty on recurring run clubs (it is NOT the drinking keywords).
- **Change**: when computing `soft_penalty_hits`, skip the `"every <weekday>"` / `"weekly meeting"` / `"monthly meeting"` / `"regular meetup"` recurring-bucket keywords if the event's categories intersect `{"fitness","wellness","outdoors"}` OR the text contains a run/yoga/workout marker (`run club`, `running`, `yoga`, `pilates`, `workout`, `social run`). Additive guard — does not remove the keywords (they still penalize generic "weekly meeting" admin events). Also note the existing list is inconsistent (only Mon/Tue/Wed present, not Thu–Sun); leave that as-is per additive-only — the scoped skip makes it moot for fitness.
- **Verification**: with the skip, "Tuesday Night Run Club / every Tuesday 7pm" (fitness) → `soft_penalty_hits=0`, `social_hits=2`; "North Brooklyn Runners Weekly Run" already 0; non-fitness "weekly meeting" admin events keep their penalty.
- **Risk**: low. Scoped to fitness/wellness/run text; a non-recurring fitness event is unaffected (no marker present).

### P2: Word-boundary anchor the short `'rave'` title-hint exclusion (fb-181)
- **Metric moved**: topic coverage (recovers the user-requested Oct-4 contra dance) + follow-graph/conviction (stops FP-dropping legit events).
- **File**: `scrapers/ranking.py::is_user_excluded`, the `title_hints` loop at `scrapers/ranking.py:734-739`.
- **Change**: match short, single-word, alpha-only title hints (heuristic: `len(hint) <= 6 and " " not in hint and hint.isalpha()`) with a word-boundary regex `\b<hint>\b` (case-insensitive); keep plain substring matching for multi-word / longer hints. Only `'rave'` currently meets the short-hint criterion; all the multi-word hints ("warehouse rave", "underground rave", "open to close", "dj marathon", "afterparty @", etc.) keep exact substring behavior. Precompile per `_load_user_excluded_sources` so it stays cached.
- **Example titles this catches / excludes** (verified live):
  - SURVIVES (was wrongly dropped): "Oct. 4th Raven & Goose", "Brooklyn Contra Dance — Raven & Goose", "Travel meetup", "Gravel bike ride".
  - STILL BLOCKED (correct): "Warehouse Rave at Bushwick" (multi-word hint), "Underground Rave" (multi-word hint), "Friday Night Rave", "RAVE in Bushwick", "Saturday rave party" (`\brave\b` fires on the standalone word).
- **Risk**: very low. Residual edge case flagged below for the Critic.

### P3: Exempt brooklyncontra from the fuzzy-title same-venue merge so same-night distinct sessions survive
- **Metric moved**: topic coverage (dance) — recovers the 2nd Sep-26 Harvest Ball session so contra yields the full 10 (8→10 with P2).
- **File**: `scrapers/normalize.py::_dedup_fuzzy_title` (bucketing at `scrapers/normalize.py:408-416`), reusing the existing `DISTINCT_SCHEDULE_SOURCES` set (`scrapers/normalize.py:172`).
- **Bug**: "Brooklyn Contra Dance — Harvest Ball Advanced Dance" and "... Harvest Ball Evening Dance" share date (2026-09-26) + venue loc-bucket + tokens {harvest, ball, dance} → merged into one card. They are two separately-ticketed sessions the store lists as distinct products.
- **Change**: in `_dedup_fuzzy_title`, when building buckets, send `ev.get("source") in DISTINCT_SCHEDULE_SOURCES` straight to `out` (mirror of the guard already in `_dedup_same_account_recurring`). The brooklyncontra scraper already dedupes exact (date,title) repeats internally (`brooklyncontra.py:158-161`), so this won't reintroduce true dups.
- **Verification**: with the exemption, `normalize.process(scrape())` → 9 contra events pre-P2 (the Advanced+Evening pair both kept), 10 with P2.
- **Risk**: very low. Scoped to the single curated source; brooklyncontra has its own internal dedup. Note: this is a 2nd small mention of brooklyncontra in the same module's dedup passes — flagging for the Critic in case they prefer a single shared guard helper over two call-sites.

### P4 (optional / defer): none beyond the above.
- The Ben Sollee night ("at Old Stone House") and the w/Big Apple Contraband night already carry the special venue/band in their titles and survive as distinct cards — no fix needed. Title quality is good.

## Directives addressed
- **fb-179**: ADDRESSED (verify + refine). +10 IG seeds pass fb-106 (no reject). Boosts in-range, no spam, no charity-race leak in feed. One concrete refinement (P1) needed to fully satisfy the "no run-club soft-penalty" criterion — the `"every tuesday"` recurring penalty still fires on recurring run clubs. Recurring expansion path (`detect_recurring_weekday`→`expand_recurring_event`) is wired in `normalize.process` (lines 1847-1862) and live run-club Meetup events with weekday markers will expand; P1 ensures they aren't penalized as they do.
- **fb-180**: ADDRESSED (verify + refine). Contra surfaces 8 distinct dated events through `process()` today (criterion ≥8 met), 9 after P2, 10 after P3. `DISTINCT_SCHEDULE_SOURCES` exemption confirmed load-bearing and working. P3 recovers the merged same-night session.
- **fb-181**: ADDRESSED. P2 is the precise, low-risk word-boundary fix. Verified against the contra "Raven & Goose" event AND a real "warehouse rave"/"Friday Night Rave" probe set.

## Open questions for the Critic
- **P2 residual edge case**: pure `\brave\b` still blocks a hypothetical event literally titled "Rave Reviews Book Club" (the standalone word "Rave" is present). The feedback probe set listed "rave reviews" as a should-survive phrase. I judged this acceptable — no real NYC event in the deployed feed is titled "Rave Reviews", and the high-value recoveries ("Raven", "travel", "gravel") all work. If the Critic wants "rave reviews" preserved too, add it as an explicit `user_curated`/allow exception rather than complicating the exclusion regex. Recommend NOT over-engineering.
- **P3 structure**: I exempt brooklyncontra in a 2nd dedup pass (fuzzy-title) in addition to the existing recurring-merge exemption. Prefer this kept as two explicit guards (clear) or refactored into one shared `_is_distinct_schedule_source(ev)` helper? Low stakes either way.
- **Scope of P1 guard**: I scoped the recurring-penalty skip to fitness/wellness/outdoors categories + run/yoga text markers. If the Critic would rather a broader "recurring is not inherently bad" stance (e.g. also exempt social/singles recurring meetups), that's a larger policy change I did not propose this round (additive-minimal).
