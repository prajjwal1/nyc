# Critic Report — 2026-06-04 1904

## Cross-check results
- **sanity_check regression risk**: FLAGGED (not a blocker, but the orchestrator must understand it). The `Instagram is dominant source >= 50` CRITICAL check is ALREADY FAILING on the live feed: IG=46 < 50 (stale 33-day session). P1+P2 drop **12 IG events** (verified: all 12 caught events are `source=instagram`, and `normalize.py` drops sub-MIN_SCORE events from the feed entirely). That pushes IG to ~34. This is CORRECT behavior (the 12 are genuine OCR/caption garbage) and the IG-count failure is user-blocked (session refresh). Do NOT block P1/P2 over the sanity IG count — but log that the check will hard-fail on IG regardless this round. Other CRITICAL checks survive: free 76→73 (>=20 ok), wburg/gp/bushwick 42→41 (>=3 ok), music=125 (>=15 ok), Reading Rhythms ok (8 matches, none caught), NYC Backgammon ok (P4 strengthens it — see below).
- **Backgammon CRITICAL is hanging by a thread**: the ONLY backgammon match in the live feed is the IG OCR false-positive `Brunch is for the gals!!! Let's make some` (sourceUrl contains `nycbackgammonclub`). It does NOT match P1/P2 patterns so it survives — but it's the wrong reason the check passes. P4 fixes this for the right reason (6 real backgammon events). APPROVE P4 partly to harden this.
- **Duplicate source proposals**: none. S1 (`lu.ma/philosophy`) is not in LUMA_PAGES (confirmed: only `philosophy`-free `/nyc/<topic>` + 6 named curator calendars present). `nycbackgammonclub` IS already in LUMA_PAGES — P4 is a parser fix, not a source add. No duplicates.
- **User-excluded check**: PASS. Confirmed `philosophy`, `philosophy.nyc`, `silentbookclub.nyc`, `nycbackgammonclub` are NOT in `user_excluded_sources.json` (accounts/hosts/title_hints). The excluded set is houseofyesnyc, knockdowncenter, 4 fb-106 personal accounts, + rave/club title_hints. Both workers explicitly cited the exclusion check (ingestion §158, source-pool §26). No CHECK-FIRST violation.
- **fb-106 (no individual-person accounts)**: PASS. All touched entities (philosophy.nyc, silentbookclubnyc, nycbackgammonclub) are socializing orgs.
- **UI preference compliance**: PASS. ui-U1 is plain-text `@handle` in the existing provenance slot — NOT the banned "Because you follow @X" prose (that ribbon was a separate construct; this is a bare handle identical to the existing IG-handle typographic treatment). No new sidebar widget, no gray box, no This-Weekend-hero change. iter-215 simplification preserved.
- **Top-3 directive coverage**: addressed — D1 (leak audit → P1/P2), D2 (non-IG follow-graph → P3/P4), D3 (provenance surfacing → ui-U1). deferred-acceptable — the 34 remaining zero-yield accounts documented as genuinely IG-session-blocked (both workers independently probed lu.ma/own-site paths and got the not-found shell). deferred-REJECTED — none.

## Verdicts

### ingestion-P1 — OCR-garbage detector in `_is_caption_fragment` — APPROVE
- **Metric moved**: high-conviction precision + top-of-feed quality. Purges 5 OCR-garbage titles that currently sit at score 0.749–1.0 inflating the followed-account count (~1.4% of the 347-event feed, but they're at the very top, so outsized perceived-quality impact).
- **Reasoning**: I re-ran the exact predicate against all 347 live titles. It matches EXACTLY the 5 claimed garbage titles and ZERO others. The `\b[A-Z]{6,}[a-z]` clause matches 0 titles in the feed (no FP surface). The `noise>=0.45` threshold + glyph signatures are tight. FP claim VERIFIED independently — this is the rigor fb-122 demanded and the worker delivered it.

### ingestion-P2 — 6 fragment starters + leading-quote regex — MODIFY
- **Metric moved**: top-of-feed quality; removes 2 score-1.000 leaks + ~4 more (verified the starters catch 6 events, leading-quote catches exactly 1, all garbage).
- **Reasoning**: Independently verified: the 6 starters match exactly 6 garbage titles (worker undercounted as 5 — harmless, all 6 are genuine garbage incl. `Enter to win a pair of tickets to see @scarymovie!`). Leading-quote regex matches exactly 1 (`' Things making me happy`). ZERO good-title FPs in the current feed. BUT `"throwing "` and `"enter a "` are broad enough to risk future FPs ("Throwing Workshop" pottery, "Enter a New World" art show) once the IG session is refreshed and feed composition changes.
- **If MODIFY**: tighten two starters to reduce future-feed FP risk (the worker themselves leaned this way in their open questions):
  - `"throwing "` → `"throwing a "` (still catches `Throwing a sober Y2K party`)
  - `"enter a "` → `"enter a ballot"` and keep `"enter to win"` (still catches `Enter a ballot for free tickets…`; drops the broad `enter a ` that could hit a real "Enter a [venue]" title)
  - Keep `"not able to"`, `"house of @"`, `"below."`, and the leading-quote regex as-is — all tightly anchored.

### ingestion-P3 — Meetup group-slug enrichment — APPROVE
- **Metric moved**: follow-graph coverage (+1 account: `silentbookclub.nyc` → yield>0 via non-IG path) + high-conviction ratio (the `Booze & Books in Brooklyn` event gains userFollowing).
- **Reasoning**: I extracted all 23 distinct Meetup slugs in the live feed (silentbookclubnyc, thewritinggroup, jcrunners, reading-philosophy, books-and-restaurants, nyctechmixer, etc.). Folded each against the following set: ONLY `silentbookclubnyc` matches. ZERO false positives. The `len(fold)>=5` guard mirrors the existing organizer guard. Purely additive, gated on exact membership. The change correctly uses `_re` (module's import alias). Clean.

### ingestion-P4 — Lu.ma `__NEXT_DATA__` parser — APPROVE
- **Metric moved**: follow-graph coverage (+1: `nycbackgammonclub` → yield>0) + topic coverage (`games`) + high-conviction (6 events enrich via existing normalize.py:1141 handle match) + hardens the backgammon CRITICAL check (currently passing only via an OCR false-positive).
- **Reasoning**: This is exactly the silent-failure class this cross-check exists for (ld+json vs `__NEXT_DATA__` schema drift). The root cause is confirmed against code: `_parse_luma_page` reads only `<script type=application/ld+json>` + a CSS fallback, neither of which fires on the SPA curator calendar. Generalizes to ALL curator calendars (fb-011 source-agnostic), not per-site. Two REQUIRED guardrails the orchestrator must enforce when wiring `_parse_luma_next_data`:
  1. **NYC gate (the curator's open question #3)**: gate each NEXT_DATA event on `geo_address_info.city in {"New York","Brooklyn","Queens","Bronx","Staten Island"}` OR address contains `", NY"` / `"New York"`. Do NOT use the strict `city == "New York"` only — that would drop Brooklyn-city-labeled events. Reject events with no parseable NYC address (prevents pulling a curator's out-of-town events).
  2. **Defensive parse**: wrap `json.loads` + each per-event map in try/except; require `name` + parseable `start_at`; dedupe by `api_id`. Must not throw on the 6 working curator URLs (litclub/thinkolio/cinemaclub currently yield 0 from NEXT_DATA — confirm the new path returns `[]` cleanly, not an exception, for them).
- Run `sanity_check.py` after the next scrape to confirm backgammon passes for the right reason.

### source-pool-S1 — add `lu.ma/philosophy` to LUMA_PAGES — MODIFY (approve the add; it is INERT without two dependencies)
- **Metric moved**: topic coverage (social/intellectual cluster, +7 on-vector events) immediately; follow-graph coverage (+1: `philosophy.nyc`) ONLY IF the two dependencies below ship.
- **Reasoning**: The add is on-vector, exclusion-clear, low-volume (+7 on 347, no cap needed), and net-new (0 philosophy titles in feed, not in discovered_urls). BUT I found TWO blocking dependencies the curator only half-flagged:
  - **Dep 1 (HARD — depends on P4)**: `lu.ma/philosophy` is a curator calendar with the SAME SPA shape as `lu.ma/nycbackgammonclub` — no ld+json, events only in `__NEXT_DATA__`. So S1's 7 events will parse 0 unless P4 ships. **S1 is contingent on P4.** If P4 is dropped, S1 yields nothing.
  - **Dep 2 (attribution — handle-fold gap)**: I traced the enrichment path. `_handle_candidates('philosophy')` produces only `philosophy`-rooted variants; `_user_following_normalized()` adds the fold `philosophynyc` for `philosophy.nyc` but NEVER a `.nyc`-stripped `philosophy`. The two sides never meet → **S1 will NOT flip the yield_map for `philosophy.nyc`** without a fold fix.
- **If MODIFY**: (a) ship S1 ONLY together with P4. (b) Add the location-suffix-stripped fold to the following side so `philosophy.nyc` → `philosophy` matches the slug. In `normalize.py::_user_following_normalized`, after the existing alnum-fold loop add:
  ```python
  for h in list(out):
      stripped = _re.sub(r"(nyc|ny|bk)$", "", h)
      if stripped and stripped != h and len(stripped) >= 4:
          out.add(stripped)
  ```
  Verify after applying that this does NOT over-match: it would also generate `silentbookclub` (from `silentbookclubnyc`) and `nycbackgammonclub`→`nycbackgammonclub` (no trailing nyc) — both harmless. Spot-check the full following set for any handle that becomes a too-generic 4-char stub before shipping. This fix is the multiplier that makes S1 (and any future `.nyc` curator) move the follow-graph metric.

### ui-U1 — render `@account` as plain text on 68 cross-source conviction cards — APPROVE
- **Metric moved**: high-conviction surfacing / correct provenance attribution (fb-102 criterion 3a). Completes the conviction signal on 68/105 conviction events (65% of the high-conviction set) that currently show a generic source label instead of the followed handle.
- **Reasoning**: Scope verified by the worker (account-but-no-instagramAccount = exactly the 68 conviction events, 0 non-conviction). Plain-text (not a button) is the right call — `AccountBanner` keys on `instagramAccount` and would render an empty "0 upcoming" banner for `nycforfree`/`bookclubbar` clicks. It is NOT the banned prose ribbon; it's a bare `@handle` matching the existing IG-handle treatment. No clutter reintroduced. The four live values (`bookclubbar`, `readingrhythms-manhattan`, `nycforfree`, `silentbookclubnyc`) are clean handles. Ship as written; keep `nycforfree` in (it's a genuine follow, org-cap already limits volume).

## Notes back to each worker

## Notes back to ingestion-quality
- **Strong work on**: the FP rigor. You actually ran every predicate against all 347 live titles and reported exact match sets — I re-ran them and your numbers hold (P1=5, P3=1 slug, leading-quote=1). This is the discipline fb-122 was created to enforce after the iter-1 glued-handle regex was falsely claimed verified. Keep doing exactly this.
- **You missed**: P2's starter count is 6, not 5 — `"enter to win"` catches `Enter to win a pair of tickets to see @scarymovie!` which you listed separately. Harmless (all 6 are garbage) but your "drops exactly 5" line is wrong; it's 6.
- **You missed**: the sanity-check IG-count interaction. P1+P2 drop 12 IG-source events, and those are removed from the feed (sub-MIN_SCORE drop at normalize.py:1796), pushing IG from 46 to ~34 against a CRITICAL floor of 50. You correctly purge garbage, but you didn't flag that this deepens an already-failing CRITICAL check. Always cross-reference a purge against `sanity_check.py` CRITICAL_CHECKS counts (it's in your guardrail list).
- **You missed**: that S1 (philosophy) has the IDENTICAL `__NEXT_DATA__` shape as backgammon, so your P4 is a hard prerequisite for the source-curator's S1. You owned the luma parser this round; flagging that synergy would have closed the loop the curator opened in their question #1.
- **You missed**: the `philosophy`→`philosophy.nyc` fold does NOT match under current code (I traced `_handle_candidates` + `_user_following_normalized`). The curator handed you this alias as "ingestion's domain" and you didn't pick it up. I've specified the exact fix (S1 MODIFY, Dep 2). It also future-proofs every `.nyc` curator handle.

## Notes back to source-curator
- **Strong work on**: the honest negative result. Probing ~45 URLs and 5 Eventbrite venue-search slugs against the fb-155 match-rate gate, then REJECTING all 5 (Franklin Park 0/3, BBG 1/3, reading-rhythms 0/3, backgammon 0/3, philosophy-club 0/3) rather than padding the round with noise sources — that is exactly right. The "honest assessment" that the 38 zero-yield accounts are mostly genuinely IG-blocked is well-evidenced.
- **You missed**: S1 is INERT on yield without P4 shipping. You flagged the attribution alias as "ingestion's domain" (correct) but didn't realize the events won't even PARSE without the NEXT_DATA fix — `lu.ma/philosophy` is the same SPA shape as backgammon. Your "+7 on-vector events either way" claim is false if P4 is rejected; it'd be +0.
- **You missed**: you could have verified the parse-shape yourself. You probed and got "7 events, stable 3x" — but if you'd inspected HOW they're embedded (ld+json vs `__NEXT_DATA__`) you'd have seen the same silent-failure mode ingestion found on backgammon, and could have made S1's P4-dependency explicit rather than leaving it as my discovery.

## Notes back to ui-agent
- **Strong work on**: the scope verification (68 conviction-only events, 0 non-conviction) and the AccountBanner empty-state reasoning — you correctly chose plain text over a button BECAUSE the banner keys on instagramAccount. That's the kind of second-order thinking that prevents a regression. Also good: confirming directives 1 & 2 are already correct rather than inventing changes.
- **You missed**: nothing material. One forward note — your open question about making `AccountBanner` also match `event.account` (clickable handles) is a real future improvement, but correctly deferred; it's a second-component change. If you'd raised it as a DREAM-DEFER backlog entry yourself that'd be ideal. I'm capturing it as D2 below.

## Dream proposals

### D1 — Description-body time inference ("doors at 7pm" / "starts at 8") — APPROVE-DREAM
- **Metric moved**: high-conviction ratio quality (not count) — events with a real start time rank/render better; indirectly lifts the perceived-quality of the conviction set. Targets the ~2 Eventbrite events with missing startTime + any IG/Substack event with time only in the body (README §369 known gap).
- **File**: `scrapers/normalize.py` — add a `_infer_time_from_text(title, description)` helper called when `startTime` is empty; regex `\b(?:doors?(?:\s+(?:open|at))?|starts?(?:\s+at)?|kicks?\s+off(?:\s+at)?|show)\s*:?\s*(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?)`, map to local HH:MM, only fill when `startTime` is absent (never overwrite a parsed time).
- **Change sketch**: gate on `not ev.get("startTime")`; pick the EARLIEST plausible match (doors before show); validate 06:00–23:59 to avoid the late-night filter conflict. Source-agnostic, additive, no IG session needed. Verify against the 2 startTime-missing Eventbrite events the ingestion worker found.

### D2 — Make `AccountBanner` match `event.account` so enriched conviction handles are clickable — DREAM-DEFER
- **Verdict**: DREAM-DEFER (queue as backlog `source: agent-proposal`, follows ui-U1).
- **Metric moved**: high-conviction surfacing — turns the 68 plain-text handles from ui-U1 into working filter routes (per-account browsing for `bookclubbar`/`readingrhythms` — the iter-198 calibration-validated follows the user said they'd attend ALL of).
- **File**: `site/app/components/EventCard.tsx` (provenance branch) + `site/app/components/AccountBanner.tsx` (filter predicate).
- **Change sketch**: extend AccountBanner's filter to match `e.instagramAccount === acct || e.account === acct`, then make the ui-U1 plain-text `@account` a clickable button like the IG branch. Deferred because it touches a second component and ui-U1 (plain text) is the safe minimal step this round; ship D2 only after ui-U1 lands and is confirmed clutter-free. Backlog entry: "Per-account filter route for cross-source-enriched conviction handles (bookclubbar, readingrhythms-manhattan, nycforfree, silentbookclubnyc) — make AccountBanner key on event.account in addition to instagramAccount; completes ui-U1 (2026-06-04-1904)."
