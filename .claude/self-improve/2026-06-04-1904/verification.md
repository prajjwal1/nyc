# Verification — 2026-06-04-1904

## sanity_check
- **Result: 1 critical failure — "Instagram is dominant source" (IG=46 < 50).**
- **Not a regression.** This critical was ALREADY failing on the live feed before
  any edit this round (IG=46, stale 33-day IG session — flagged in the Critic
  report cross-checks). My edits touch only `scrapers/*.py` and `site/*.tsx`
  source; `sanity_check.py` reads the unchanged `data/events.json` (no scrape
  ran), so the result is identical to a pre-edit run. There is nothing to
  revert — the failure is the user-blocked IG-session-refresh bottleneck, not
  caused by P1/P2/P3/P4/S1/D1/ui-U1.
- The Critic pre-authorized continuing: "Do NOT block P1/P2 over the sanity IG
  count … the IG-count failure is user-blocked (session refresh)."
- North-Star metrics from sanity_check: follow-graph 12/50 (24%), topic 4/4,
  high-conviction 105/347 (30.3%) — unchanged this run (code effects land on the
  next scrape).
- No other CRITICAL or WARNING failures. Reading Rhythms / NYC Backgammon
  assertions still pass (backgammon currently via the OCR false-positive; P4
  will make it pass for the right reason on the next scrape).

## next build
- **Clean.** Next.js 16.2.4 (Turbopack), compiled successfully, TypeScript
  passed, all 4 static pages generated. ui-U1 introduces no type or build error.

## Live-probe verification done during apply
- P1+P2: ran `_is_caption_fragment` over all 347 live titles → caught exactly 12
  IG OCR/caption-garbage titles, 0 false positives.
- P3: `_enrich_provenance_from_url` tags the silentbookclubnyc Meetup event;
  unrelated `jcrunners` Meetup correctly NOT tagged.
- P4: `lu.ma/nycbackgammonclub` now yields 6 NYC events (was 0); `lu.ma/litclub.nyc`
  returns [] cleanly (no exception).
- S1: `lu.ma/philosophy` yields 7 NYC events; the suffix-strip fold makes
  `philosophy` (slug) match `philosophy.nyc` (signal account) → enriched
  userFollowing. Spot-checked the fold's new stubs — no generic-word collisions.
- D1: `_infer_time_from_text` returns earliest plausible 06:00–23:59 time from
  "doors at 7pm / show starts at 8pm" cases; returns None for out-of-range
  (2am) and keyword-less ("join us at 11am") text.

## Nothing rolled back.
