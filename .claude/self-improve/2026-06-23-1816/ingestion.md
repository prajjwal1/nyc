# Ingestion Quality Report — 2026-06-23 1816

## Metrics observed (feed = site/public/events.json, 365 events; unchanged since last round — no intervening scrape)
- signal_accounts with yield_map > 0: 15 / 50 (30.0%) — unchanged (code-only round)
- High-conviction ratio: 64/365 (17.5%) — unchanged
- eventbrite events in feed: **100 / 100** (exactly at SOURCE_VOLUME_CAPS["eventbrite"]=100 — the binding constraint, see P1)
- fitness/dance/run/yoga-titled events in feed: 23
- Leak audit: late-night 0, real pro-networking 0 (1 false positive "Wall Street" inside a book-event description), AI-themed titles 0, date misparses (>2026-12) 0. **Feed is clean.**

---

## fb-184 (PRIMARY) — ROOT CAUSE: the 6 legacy slugs are NOT broken, NOT empty, and the parse path is intact

I live-probed all 6 legacy slugs through the real `scrapers.sources.generic.scrape_url` on this residential machine. **Every one parses 20 events right now** (JSON-LD shape is unchanged; no drift). The "0-yield despite 500+ fetches" premise is **misattributed to extraction** — the events ARE extracted. url_health corroborates: these slugs show `events_emitted_total` in the dozens-to-hundreds (running NYC 60, dance NYC 420, sports-and-fitness 184) and `last_event_count: 20`/`8`. They never were inert at the source layer.

LIVE PROBE RESULT (events parsed, this machine, 2026-06-23):
```
LEGACY  ny--new-york/running--events/        -> 20   ny--brooklyn/running--events/ -> 20
LEGACY  ny--new-york/yoga--events/           -> 20
LEGACY  ny--new-york/fitness--events/        -> 20
LEGACY  ny--new-york/dance--events/          -> 20
LEGACY  ny--new-york/sports-and-fitness--/   ->  8
WORKING ny--new-york/run-club--events/       -> 20   (the NEW slug from last round)
WORKING ny--new-york/contra-dance--events/   -> 20
```

Where the events actually die — I ran `ranking.compute_score` on each legacy-slug batch:
```
ny--new-york/running--events/   n=20  min=0.00 max=0.80 median=0.51  >=0.55(MIN_SCORE): 8/20
ny--new-york/fitness--events/   n=20  min=0.00 max=0.51 median=0.36  >=0.55:             0/20   <-- ALL dropped
ny--new-york/dance--events/     n=20  min=0.00 max=0.74 median=0.38  >=0.55:             4/20
```
So the legacy fitness slug yields literally **0 survivors of MIN_SCORE 0.55** (its best event scores 0.51); running yields 8 and dance 4, and those survivors then compete for the **100-slot eventbrite volume cap** against ~30 other eventbrite slugs. With the feed already pinned at exactly eventbrite=100, the lower-scoring fitness/dance events lose the cap competition. That is the real, end-to-end cause of the 0-yield — a **scoring + cap bottleneck**, not a parse failure.

Generic Eventbrite-category events score low because they carry no IG signal-account and no curated-host organizer, so they miss the +0.15 interest-profile boost and the IG-curated 0.40 floor — they're judged at the full 0.55 default floor on completeness/category/source signal alone, and short fitness titles with no startTime score poorly on completeness.

REDUNDANCY FINDING (overlap probe, this machine):
```
nyc-running(18) vs bk-running(18):           overlap 18  (100% — Eventbrite IGNORES the borough for this slug)
nyc-running(18) vs run-club NEW(18):         overlap  8  (44% — run-club adds 10 UNIQUE titles)
nyc-dance(20)  vs contra-dance NEW(20):      overlap 12  (60%)
nyc-dance(20)  vs swing-dance NEW(20):       overlap 12  (60%)
nyc-fitness(20) vs sports-and-fitness(8):    overlap  0  (disjoint — both contribute)
```
`ny--brooklyn/running--events/` is a **100% duplicate** of `ny--new-york/running--events/` (Eventbrite's category-search ignores the borough segment for "running"). That is a genuine pure-redundant pair — a prune candidate — but removal is **blocked by additive-only** and needs explicit user opt-in (flagged below, not removed).

CLASSIFICATION (per fb-184 "addressed" criterion):
- `ny--new-york/running--events/` — WORKING (20 parsed, 8 clear MIN_SCORE). Keep.
- `ny--brooklyn/running--events/` — WORKING but 100%-redundant with the NYC running slug → **prune candidate, user opt-in only (blocked)**.
- `ny--new-york/yoga--events/` — WORKING (20 parsed). Keep.
- `ny--new-york/fitness--events/` — WORKING parse but **0/20 clear MIN_SCORE** → addressed by P1 (the bottleneck is scoring, not the slug).
- `ny--new-york/dance--events/` — WORKING (20 parsed, 4 clear). Keep.
- `ny--new-york/sports-and-fitness--events/` — WORKING (8 parsed, disjoint from fitness). Keep.

Net: no slug is dead; nothing to remove for cause. Net fitness/dance count will NOT regress (no removals proposed). The yield recovery is gated on letting these survive the cap+floor, which is P1.

### P1: Give fitness/run/dance Eventbrite-category events a small completeness-independent topic boost so they survive MIN_SCORE and the eventbrite=100 cap
- **Metric moved**: topic coverage (yoga/run topics in topic_counts) + serves user-explicit fb-179 ("more fitness + run clubs")
- **File**: `scrapers/ranking.py:537-539` (the existing fitness/run-club weekday boost block — already added last round) — extend it so the category match for `cats & {"fitness","wellness","outdoors"}` OR title containing `run club`/`yoga`/`pilates`/`contra`/`swing dance` adds a small flat **+0.06–0.08** to the final score (enough to lift the 0.49–0.54 cluster over the 0.55 floor without promoting noise). The boost is justified by a SPECIFIC failure mode: `fitness--events/` yields 0/20 survivors despite being a directly user-requested topic — this is not a blanket MIN_SCORE change, it's a targeted topic-affinity bump on a profile-aligned category.
- **VERIFICATION (ran it)**: `compute_score` on the live `fitness--events/` batch caps at 0.51; the cluster 0.49–0.54 (median 0.36 overall, but ~5 events sit in 0.49–0.54) would cross 0.55 with +0.06. running has 8 already-clearing + ~4 in the 0.49–0.54 band that would join. No late-night/excluded titles appear in these batches (verified against user_excluded_sources title_hints — no rave/open-to-close/dj-marathon/speed-dating matches).
- **Risk**: a +0.08 flat boost could pull in low-completeness fitness events with no time/venue. Mitigate by gating on `event.get("startTime")` present OR a curated-host organizer, and cap the boost at the smaller +0.06. Critic should set the exact magnitude; I recommend +0.06 gated on having either a startTime or a known venue. This is the only lever that actually moves fb-184's yield; the slugs themselves are fine.

### P1b (prune candidate — BLOCKED, flag for user opt-in): `ny--brooklyn/running--events/` is a 100% duplicate of `ny--new-york/running--events/`
- Live overlap = 18/18 identical. Eventbrite ignores the borough segment for "running". Dropping the Brooklyn variant saves one fetch/round with zero event loss.
- **Additive-only rule blocks unilateral removal.** Surface to the user as an opt-in prune (same class as fb-104). Do NOT remove this round.

---

## fb-183 — Extract DISTINCT_SCHEDULE_SOURCES membership into a shared helper

### P2: `def _is_distinct_schedule_source(ev)` shared helper + unit test
- **Metric moved**: none directly — hardens the distinct-schedule lever that fb-179/fb-180 (run-club/contra) depend on; prevents a future single-site edit from silently merge-collapsing user-requested dated events. Behavior-identical refactor.
- **File**: `scrapers/normalize.py:158` (def site), `:180` (`_dedup_same_account_recurring` call-site), `:422` (`_dedup_fuzzy_title` call-site). Add helper:
  ```python
  def _is_distinct_schedule_source(ev: dict) -> bool:
      """True for sources whose listings are individually-scheduled,
      individually-ticketed events that legitimately repeat a near-identical
      title across dates (and sometimes multiple sessions on one date).
      These bypass BOTH dedup passes. See DISTINCT_SCHEDULE_SOURCES."""
      return ev.get("source") in DISTINCT_SCHEDULE_SOURCES
  ```
  Replace `if ev.get("source") in DISTINCT_SCHEDULE_SOURCES:` at both call-sites with `if _is_distinct_schedule_source(ev):`.
- **Unit test** (new, in `scrapers/tests/test_normalize.py`, `TestDeduplicate` class): add a 2nd member to the set at runtime (e.g. via `monkeypatch.setattr` or by appending to a local copy) and assert two same-(source) events with near-identical titles on DIFFERENT dates AND two same-date same-title sessions both SURVIVE `deduplicate` (i.e. bypass both passes). The cleanest form, since `DISTINCT_SCHEDULE_SOURCES` is a module set, is `monkeypatch.setattr(normalize, "DISTINCT_SCHEDULE_SOURCES", {"brooklyncontra", "testsched"})` then feed two `source="testsched"` events and assert `len(result) == 2`, plus a control with `source="othersrc"` that DOES merge to 1.
- **VERIFICATION (ran it)**: baseline `pytest scrapers/tests/ -q` = **253 passed, 3 xfailed**. Confirmed `deduplicate()` (normalize.py:7) calls `_dedup_fuzzy_title` (:30) then `_dedup_same_account_recurring` (:45), and the membership check is currently literally duplicated at :180 and :422. Refactor is mechanical and behavior-identical; the new test asserts the bypass works through the single helper for both passes.
- **Risk**: none — pure extraction, same truthiness. The monkeypatch test is the safest way to prove "a 2nd source bypasses both passes" without permanently widening the production set.

---

## Directives addressed
- **fb-184 (PRIMARY): addressed.** Root-caused live: all 6 slugs parse 20/8 events (no JSON-LD drift, parse path intact). 0-yield is a downstream **MIN_SCORE 0.55 + eventbrite=100 cap** bottleneck (fitness slug: 0/20 clear the floor). Each slug classified (5 WORKING-keep, 1 WORKING-but-redundant prune-candidate). Recovery lever = P1 (targeted topic boost). No slug removed (additive-only); net fitness/dance count cannot regress.
- **fb-183: addressed.** P2 specifies the shared `_is_distinct_schedule_source` helper, both call-site replacements with file:line, and the monkeypatch unit test asserting a 2nd source bypasses BOTH passes. Baseline suite verified green (253 passed).
- **fb-182 (UI): deferred — not my lane** (ui worker). Noted only.

## Open questions for the Critic
1. **P1 boost magnitude/gating.** I recommend +0.06 gated on (has startTime OR known venue) to avoid promoting fitness events with no time. Is +0.06 enough to clear the 0.49–0.54 band reliably, or does the Critic want +0.08 with stricter gating? This is the single load-bearing decision for fb-184's yield.
2. **P1b prune.** `ny--brooklyn/running--events/` is a verified 100% duplicate of the NYC running slug. It's a clean opt-in prune (like fb-104) — should it be surfaced to the user this round or batched with the other blocked-prune items?
3. **folk-dance slug (S4, flagged provisional last round).** Live re-probe confirms it skews toward performances ("Traditional Music & Dances from Ecuador", "Unsung Heroes…Village Folk Scene") rather than participatory social dance. That's a Source Curator concern and additive-only blocks removal — flagging for the Critic to route, not proposing a change.
