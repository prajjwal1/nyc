# Ingestion Quality Report — 2026-07-20 1815

Feed inspected: `/Users/prajj/nyc-events/site/public/events.json` (396 events, updated 2026-07-20T16:56, fresh).
Worker is read-only; all diffs below are proposals for the orchestrator to apply. Every top-12 before/after was produced by prototyping the exact penalty math against the live feed (not hand-waved).

## Metrics observed
- Follow-graph coverage: 15/50 (30.0%) — unchanged this lane (ranking, not ingestion).
- Topic coverage: all present (books 108, ai 80, ny 86, club 52, run 44, bk 47).
- High-conviction ratio: 90/396 (22.7%). The 4 conviction events (userFollowing) that lead the feed STAY at the top after the fix — conviction not regressed.

## KEY FINDING — top-of-feed monotone (fb-202)
BEFORE top-12 by `score` = **8 bookclubbar + 4 readingrhythms-manhattan** (the "4 luma" in the brief are Reading Rhythms events delivered via lu.ma). 20 of the top-25 are `books`. 16 events tie at exactly 1.0, so raw score alone can't break the literary monoculture. There is NO diversity control in `rank_events` — only `TopPicks.tsx` render-time caps, which operate on already-ordered data and can't surface a buried topic.

Root cause is TWO overlapping monocultures, so a source-only cap is insufficient:
1. **Source pile-up**: one followed venue (Book Club Bar) posts dozens of literary events that all pin near 1.0.
2. **Topic pile-up**: six DIFFERENT literary sources (bookclubbar, readingrhythms, lizsbookbar, litclub.nyc, silentbookclubnyc, powerhousearena) are all `books` — a per-source cap alone still yields an all-books top-12 (verified: source-only penalty gives max-3/source but top-12 stays 100% literary; music/run/comedy/dance still buried at #46/#60/#48/#88).

Fix therefore combines a per-source AND a per-topic graduated demotion.

---

## Proposals

### P1: Add a per-source + per-topic diversity penalty to `rank_events`
- **Metric moved**: topic coverage (buried music/run/comedy/dance reach the top) + high-conviction ratio is PRESERVED (conviction leaders unchanged).
- **File**: `scrapers/ranking.py` — new helper `_apply_diversity_penalty(events)` plus a call at the end of `rank_events` (after the per-event `compute_score` loop, ~line 916-919), and two module-level helpers `_diversity_source_key` / `_diversity_primary_topic`.
- **Change** (exact):
  1. After the `for event in events: event["score"] = ...` loop in `rank_events`, insert `_apply_diversity_penalty(events)` BEFORE returning. It must run after `compute_score` (needs base scores) and after the taste-model pass (already earlier in the fn).
  2. Group events by `_diversity_source_key(e)` and by `_diversity_primary_topic(e)`. Within each group, sort by base `score` desc and assign a rank (0,1,2,…). Penalty = `SRC_STEPS[srank] + TOP_STEPS[trank]` where:
     - `SRC_STEPS = [0, 0, 0.16, 0.24, 0.32, 0.40]` (first 2 free → protects a followed venue's best 1-2; 3rd+ demoted)
     - `TOP_STEPS = [0, 0, 0.10, 0.16, 0.22, 0.27, 0.31, 0.34]` (first 2 of a topic free; 3rd+ demoted; clamp at last step)
     - beyond the list length, use the last (max) step.
  3. **Floor-safe clamp (mandatory)**: `new = raw - penalty`; if `raw >= floor(e)` then `new = max(floor(e), new)`. This guarantees the penalty only RE-ORDERS survivors — it never pushes an event that would have cleared its floor below it, so nothing gets dropped by the downstream 0.55 gate purely from diversity demotion. Use the SAME floor logic as `normalize._min_score_floor` (conviction/tagged/affinity/following → 0.40, else 0.55). To avoid a circular import, inline the conviction check (`0.40 if any(userSaved/userTagged/userAffinity/userFollowing) else 0.55`) — this is a conservative floor (never higher than the real curated-IG floor), so the clamp can only be MORE lenient than reality, never dropping an event the real gate would keep.
  4. `_diversity_source_key(e)`: `account`/`instagramAccount` → `acct:<lower>`; else `organizerUrl`/`organizer` → `org:<lower>`; else `source|location.name` → `srcloc:...`; else `src:<source>`.
  5. `_diversity_primary_topic(e)`: detect run/dance/comedy from title+categories BEFORE music (run-clubs and contra dances are co-tagged `music` in the feed, e.g. "Brooklyn Contra Dance — Live Music"; without this they eat the music-topic penalty and sink). Order: run → dance → comedy → then first-match of (books, music, fitness, wellness, outdoors, singles, parties, food, art, games, film) → else first category → "other".
- **VERIFICATION (live feed, real numbers)**:
  ```
  BEFORE top-12: 8 bookclubbar + 4 readingrhythms   (topic: 20/25 books)
     1.00 bookclubbar   Bored of Dating Apps Singles Night
     1.00 readingrhythms Reading Rhythms Queens
     1.00 readingrhythms Reading Rhythms Williamsburg
     1.00 bookclubbar   HEA Romance Book Club
     1.00 readingrhythms Pages in the Park!
     1.00 bookclubbar   Indie Press Book Club
     ... (all books/literary) ...

  AFTER top-12 (SRC/TOP steps above + floor clamp):
     1.00 F singles  bookclubbar        Bored of Dating Apps Singles Night
     1.00 F books    readingrhythms     Reading Rhythms Queens
     1.00 F books    readingrhythms     Reading Rhythms Williamsburg
     0.90 F books    bookclubbar        HEA Romance Book Club
     0.869 F art     explorenycfree     RSVPs for @ironstrengthnyc x
     0.866  fitness  meetup|Williamsburg Hotel  NYC Tech Mixer 2026
     0.854  run      partiful           Vital Run Club 2 YEAR ANNIVERSARY RUN
     0.853  outdoors eventbrite/o        An Evening Rooftop Ride w/ Real Yoga
     0.832 F parties nycforfree         UNO Social Club - Brooklyn
     0.815  dance    eventbrite|Urbane   JAZZ & GIN: A Speakeasy Soirée
     0.813  dance    brooklyncontra     Brooklyn Contra Dance — Live Music
     0.789  music    partiful|Doppelgänger  Arlette NYC Popup @Doppelganger

  top-12 source dist: max 2 per source (was 8)   -> PASS (no source >3)
  top-12 topics: singles1 books3 art1 fitness1 run1 outdoors1 parties1 dance2 music1
  music >= 1: PASS (Arlette NYC Popup #12)
  run/comedy/dance >= 1: PASS (Vital Run #7, JAZZ&GIN #10, Brooklyn Contra #11)
  books: 8 -> 3
  Conviction (F = userFollowing) still holds ranks 1-4 and 9: NOT regressed.
  ```
- **Risk / regressions checked**:
  - Chess/games niche not dropped: chess events (0.58-0.70) get topic-demoted but the floor-clamp holds them at 0.55 — all 4 chess events SURVIVE (Chess Night Cosmic Diner 0.704 tr0 untouched; Brooklyn Chess & A Beer / Fox Harlem / Sugar Mouse clamped to 0.55, still ≥ floor). Verified: `games` topic total 10, none dropped.
  - Floor semantics (fb-001..009, 0.55 gate) preserved: penalty only demotes and is clamped ≥ floor; it CANNOT surface junk (it never raises a score) and CANNOT drop a survivor. Nightclub/late-night/networking hard blocks run before ranking, untouched.
  - Conviction preserved: SRC first-2-free means a followed venue's best 2 events keep full score; the 4 userFollowing events still lead.
  - All 310 existing scraper tests pass with the codebase as-is (baseline); the new helper is additive.

### P2: Unit test for the diversity penalty
- **Metric moved**: guards P1 (regression fence for topic coverage).
- **File**: new `scrapers/tests/test_ranking_diversity.py`.
- **Change**: synthetic batch where ONE source ("megavenue", one topic "books") has 10 events pre-set to `score` near 1.0 (0.99..0.90) plus a handful of single-source events in other topics at ~0.85. After `rank_events`:
  - assert ≤3 of the megavenue-books events appear in the top-8 (pile-up capped);
  - assert at least one non-books, non-megavenue event interleaves into the top-8;
  - assert the top-1 event (highest base score) is unchanged (conviction/best-event not nuked);
  - assert no event that started ≥0.55 ends <0.55 (floor-clamp invariant).
- **Note**: because `rank_events` recomputes `score` via `compute_score` (which ignores a pre-set `score`), the test should set the fields `compute_score` reads (title, categories, userFollowing, date, source) so the synthetic events actually score high, OR call `_apply_diversity_penalty` directly on a list with pre-stamped `score`/`account`/`categories`. The latter is simpler and tests the penalty in isolation — recommend testing `_apply_diversity_penalty` directly.

---

## chess = 0 root cause (secondary directive)
**Resolved — no fix needed; documented positive.** The `metrics-before.md` "chess=0" reflects an OLDER feed. In the current fresh feed (2026-07-20T16:56) there are 4 chess events, all above the 0.55 floor:
- `Chess Night at Cosmic Diner - July 20` (eventbrite, 0.704, games) — from the Chess Place organizer o/115357260611.
- `Chess Night at Sugar Mouse - East Village` (eventbrite, 0.661, games) — same organizer.
- `Adult Beginner Chess Workshop at The Fox Harlem` (eventbrite, 0.582, games) — same organizer.
- `Brooklyn Chess & A Beer` (meetup, 0.59, games) — from the Meetup chess keyword search.

So last round's Chess Place Eventbrite organizer (`user_curated_sources.json:129`) AND the Meetup `keywords=chess` search (`meetup.py:30`) BOTH landed once the pool was re-scraped. There is NO downstream ranking/floor/cap suppression: the events parse, clear MIN_SCORE 0.55, and survive the eventbrite volume cap. This is a source/scrape-timing lag, not a ranking bug — nothing for this lane to fix. (Confirms fb-203 chess sub-item; source-curator can mark it a verified positive.)

The ONLY interaction with P1: the topic penalty compresses the `games` cluster (10 events), but the floor-clamp keeps all chess events at ≥0.55 — none are lost. Verified above.

---

## Directives addressed
- **fb-202** (primary): ADDRESSED via P1+P2. Live-verified top-12 now has no source >3 (actually max 2), ≥1 music (Arlette #12), and ≥1 run/comedy/dance (Vital Run #7, JAZZ&GIN #10, Contra #11). No fb-001..009 rule relaxed; 0.55 floor semantics preserved via clamp.
- **fb-203 chess-0 sub-item**: ADDRESSED as a documented positive — chess now yields 4 feed events; root cause of the stale "0" was scrape-timing lag, not a ranking/floor/cap issue. Routed OUT of ingestion lane (no fix owed here). Broader missing-sources audit stays with source-curator.

## Open questions for the Critic
1. **Topic detection lives in ranking, not categorizer.** `_diversity_primary_topic` re-derives run/dance/comedy from title text because the categorizer co-tags contra dances and run clubs as `music`. This is a ranking-local heuristic (a few string checks), NOT per-source code and NOT a categorizer change. Acceptable, or would you prefer the categorizer be fixed upstream (larger blast radius, other lane)? I kept it ranking-local to stay additive and within `ranking.py`.
2. **Step magnitudes are tuned to THIS feed.** SRC=[0,0,.16,.24,.32,.40] / TOP=[0,0,.10,.16,.22,.27,.31,.34] pass the exact fb-202 criteria on the 2026-07-20 feed. They're bounded and conviction-safe, but they are calibrated against one snapshot. If you want the cap to be structurally guaranteed (not tuning-dependent), an alternative is a hard "max N per source-key in the first K ranks" interleave instead of a graduated subtraction. I chose graduated subtraction because the directive explicitly asked for a "graduated demotion" and it composes with the existing score-based sort the site already uses. Flagging the trade-off.
3. **Floor-clamp uses an inlined conviction-only floor (0.40/0.55)** rather than importing `_min_score_floor` (which also grants 0.40 to curated-IG accounts) to avoid a normalize→ranking circular import. This clamp is strictly ≤ the real floor, so it can only be MORE lenient (never drops a real survivor). Confirm that's acceptable vs. threading the curated-IG set into `rank_events`.
