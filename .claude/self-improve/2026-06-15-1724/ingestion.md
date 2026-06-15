# Ingestion Quality Report — 2026-06-15 1724

## Metrics observed (against /tmp/si_feed.json, 378 events)
- Follow-graph coverage: 12/50 signal_accounts with yield_map > 0 (24%). Cause is fb-174 (IG sweep blocked) — user-blocked, not addressed here.
- Topic `bk`: literal-substring count = **0** across all 378 events (titles + categories + 300-char desc). `brooklyn` = 43. The borough IS covered; `bk` is a pure measurement artifact.
- isStory events: 7 total. 3 are caption-fragment garbage, 4 are legit.
- Live-feed leak audit: 0 late-night/nightclub leaks, 0 real professional-networking leaks (1 audit-regex false-positive on a legit author event — "Wall Street" appears in the book description, not a finance mixer), 0 events past 2026-12, 0 garbage in top-25.

---

## Proposals

### ingestion-P1: Apply `bk`↔`brooklyn` synonym fold in the metrics-script topic counter (fb-176)
- **Metric moved**: topic coverage (`bk` 0 → 43).
- **Root cause**: The synonym fold added in fb-103 lives in `interest_profile_boost` (`scrapers/utils/interest_profile.py:232-235`) — that's the *ranker*, which only affects score boosts. The *metric* that produces `metrics-before`/`metrics-after` (`.claude/commands/self-improve.md:58-62`) counts the literal substring `bk` in event text, which never appears (verified: 0/378 events contain substring or word-boundary `bk`). So the fold has no path to the topic-coverage number. This is a **measurement bug, not a coverage gap** — exactly as the directive hypothesized.
- **File**: `.claude/commands/self-improve.md:58-62`
- **Change** (diff-level): replace the literal-substring topic loop with a synonym-aware one:
  ```python
  TOPIC_SYNONYMS = {'bk': ('bk', 'brooklyn'), 'brooklyn': ('brooklyn', 'bk')}
  topic_rep = {t: 0 for t, c in topics.items() if c >= 2}
  for e in events:
      txt = (e.get('title','') + ' ' + ' '.join(e.get('categories', []) or []) + ' ' + e.get('description','')[:300]).lower()
      for t in list(topic_rep):
          needles = TOPIC_SYNONYMS.get(t, (t,))
          if any(n in txt for n in needles): topic_rep[t] += 1
  ```
- **Verification**: with the fold applied to /tmp/si_feed.json the topic counter returns `bk: 43` (== `brooklyn`), clearing the ≥5 target. All other topics unchanged.
- **Risk**: none. Additive; the fold only adds `brooklyn` as an alternate needle for `bk` (and vice-versa), mirroring the ranker fold the user already approved (fb-103). Does not touch any source list or threshold.
- **Note (do NOT also "fix" sanity_check.py)**: `scrapers/sanity_check.py:441` deliberately classifies `bk` and `brooklyn` as `location_topics` and excludes them from its "meaningful topics" coverage count. That is a separate, intentional design choice (location topics aren't actionable coverage goals). The directive's addressed-criterion is the metrics snapshot (the self-improve.md script), so P1 alone satisfies fb-176. Leaving sanity_check as-is. Flagged for the Critic in case they want consistency.

### ingestion-P2: Story-scoped title floor — drop digit-led and imperative/CTA-led isStory titles (fb-175)
- **Metric moved**: high-conviction quality (removes 3 garbage followed-IG story events without touching the 18% ratio's legit members).
- **Root cause**: These 3 survive because they are IG-story OCR/caption fragments that the existing `_is_caption_fragment` and `_title_quality` detectors pass (all score `title_q=0.9`, `frag=False`), and `userFollowing` boost floats them above MIN_SCORE. A *global* fragment rule was rejected last session because it FP'd on "Beauty on the Block, a free beauty and cultural experience". The safe lever is a floor **scoped to `isStory` only**.
- **File**: `scrapers/ranking.py`, in `compute_score`, immediately after the existing caption-fragment nuke (after line 53, before "Multi-signal ranking").
- **Change** (diff-level): add a story-scoped guard:
  ```python
  # Story-scoped title floor (fb-175): IG-story OCR/caption fragments that
  # pass the global fragment detector but are not real events. Scoped to
  # isStory so non-story digit-led / imperative titles are untouched.
  if event.get("isStory") or event.get("discoveredVia") == "ig_story":
      import re as _re
      _t = (event.get("title") or "").strip().lower()
      _imperative = ("purchase ", "buy ", "get ", "try ", "grab ", "order ",
                     "shop ", "tap ", "swipe ", "click ", "use code",
                     "dm us", "head to")
      if _re.match(r"^\d", _t) or _t.startswith(_imperative):
          return 0.0
  ```
- **Verification (against ALL 378 events in /tmp/si_feed.json)**:
  - DROP-set (exact, 3 events — all isStory): `"2 mini lobster rolls"` (onefinedaynyc), `"45 minutes of feel Sood"` (omgreenpoint), `"Purchase a @nike federation kit and get a free cheer"` (nyc_forfree).
  - LEGIT isStory events that SURVIVE (4, 0 false drops): `"Reading Rhythms"`, `"A Space For The Work You've"` (venue LIGHTNING SOCIETY), `"Seconds Run Club"`, **`"Block, a free beauty and cultural experience"`** (the directive's must-survive case — survives because it starts with a letter, not a digit or imperative).
  - Scope check: the rule is `isStory`-gated, so the 6 legit non-story digit-led titles (`"100 Page Book Club…"`, `"6th Annual Juneteenth Freedom Festival"`, `"2026 New York Summer Outdoor Street Festival"`, `"718 Sessions PRIDE BOAT PARTY"`, `"4TH OF JULY ROOFTOP PARTY @230 Fifth Rooftop"`, `"4th of July Fireworks Viewing Party…"`) and the 1 non-story imperative title (`"Get the Beauty Scoop with Sally Beauty"`) are all UNTOUCHED.
- **Risk**: low. Strictly additive, strictly story-scoped, returns 0.0 (drop) only on digit-prefix or a closed imperative-verb prefix list. The only conceivable FP would be a legit story titled "5K Fun Run" — mitigated because such events also have an event-word and we could refine later; none exist in the current corpus, so 0 FP today.
- **Partial-coverage caveat (honest)**: 2 of the 4 directive-named residuals (`"Great vibe 1010 experience"`, `"Dance your cares away"`) are NOT in the current feed (already removed by 4fee74e) and are NOT caught by this floor — they start with a letter and a non-imperative verb. I deliberately did NOT add a rule for them: they are sentence-like and any pattern broad enough to catch "Dance your cares away" / "Great vibe…" risks FP'ing on legit story titles, and with 0 live instances I cannot FP-verify such a rule. They are deferred to the existing fragment detector; revisit only if they recur on a future snapshot. The 2 that ARE live both drop precision-safely.

---

## Directives addressed
- **fb-176 (`bk` topic gap)** — addressed by ingestion-P1. Confirmed measurement bug: literal `bk` = 0/378, fold lifts to 43. Fix is in the metric script, not the source pool. Not solved by adding Brooklyn sources (borough already at 43).
- **fb-175 (4 residual IG-story fragments)** — addressed by ingestion-P2 for the 3 live residuals (`"2 mini lobster rolls"`, `"45 minutes of feel Sood"`, `"Purchase a @nike…"`) with verified 0 legit-story loss. The other 2 named residuals are not in the live feed and are deferred (see caveat) — flagged for Critic.
- **Directive 3 (new low-quality leaks)** — none found. Top-25 and full-feed scans clean: 0 late-night, 0 nightclub, 0 real networking leaks, 0 date misparses past 2026-12. The 3 sub-0.5-title-quality survivors (`"barnacle boi @ The Rooftop, Elsewhere"`, `"writing party!"`, `"commUNITY Run Club"`) are all legit. Non-IG sources (luma/eventbrite/partiful) extract cleanly with times/dates/venues; no systemic extraction bug.

## Open questions for the Critic
1. Should `sanity_check.py:441` ALSO get the `bk` treatment (remove `bk` from `location_topics` so it's counted as a meaningful topic), or keep the current intentional exclusion of location topics? P1 satisfies the fb-176 metric criterion either way; this is a consistency call.
2. The 2 not-in-feed residuals (`"Great vibe 1010 experience"`, `"Dance your cares away"`) — accept the deferral (no FP-verifiable rule with 0 live instances), or is there appetite for a riskier pattern?
3. One Lu.ma event ("Reading Rhythms Long Island: June 25th", Northport Books) is on Long Island, not NYC. Single instance from a curated host (reading rhythms) — not flagged as a fix, but noting it in case NYC-strictness on curated hosts matters.
