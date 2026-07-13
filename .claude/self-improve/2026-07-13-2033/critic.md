# Critic Report — 2026-07-13 2033

## Cross-check results
- **sanity_check regression risk**: NONE — and one CRITICAL actively HELPED. The backgammon
  Meetup URL (source-S4) directly fixes the chronic "NYC Backgammon Club" CRITICAL_CHECK
  (title/sourceUrl match on "backgammon"; live-probed titles like "Gotham City Backgammon at
  Josie Woods" satisfy it). fb-194's new Queens/Bronx/SI neighborhood values do NOT touch the
  Williamsburg/Greenpoint/Bushwick CRITICAL (those hoods keep resolving unchanged — verified
  "456 Bushwick Ave, Brooklyn" → bushwick, "Brooklyn" → brooklyn). Music≥15, free≥20,
  Reading-Rhythms, IG-share warning: untouched.
- **Duplicate source proposals**: NONE. The 3 Eventbrite organizers (o/115357260611,
  o/105655500371, o/10662501681) are new numeric-ID host keys, not present before. Public
  Records songkick URL correctly NOT re-proposed (already in GENERIC_URLS). MoMA PS1 organizer
  o/8184194121 already curated — not duplicated.
- **User-excluded check (fb-153)**: PASS for all adds. Verified against
  user_excluded_sources.json: none of the 3 organizer IDs, "chess place", "elsewhere",
  "harlem swing", "backgammon", or openbookclubnyc appear in accounts/hosts/title_hints.
  source-curator explicitly cited the exclusion check per proposal — no Iter-107-style
  CHECK-FIRST miss. openbookclubnyc host is exclusion-clean.
- **fb-106 (personal-account) check**: PASS. All 4 source adds are brand/org/venue organizers,
  not `firstname_lastname` personal accounts.
- **Additive-only**: PASS. fb-194 is normalizer refinement (not a source prune); fb-195 is
  correctly DEFERRED (no deletion); all source work is additive. No fb-104/fb-185 prune ridden in.
- **fb-001..009 hard blocks / MIN_SCORE**: PRESERVED. No change to HARD_BLOCK_KEYWORDS or the
  0.55 floor. fb-195 explicitly left them alone.
- **UI preference compliance (§513–516)**: OK. No empty gray boxes, no left-sidebar widgets,
  no parties in This Weekend hero, 5 heroes preserved (U4 trims slice counts, not the hero set).
- **Top-3 directive coverage**:
  - addressed: fb-194 (ADDRESSED, APPROVE), fb-196 (ADDRESSED across all 3 sub-gaps, APPROVE w/ 1 MODIFY)
  - deferred-acceptable: fb-195 (DEFER — deferral is SOUND, see verdict)
  - deferred-REJECTED: none

## Adversarial verification of the two highest-risk items

### (a) fb-194 longest-key-wins + borough routing — VERIFIED SAFE
Ran live adversarial cases through `infer_neighborhood`:
- `123 Queens Blvd, Brooklyn, NY 11201` → **brooklyn** (Brooklyn check at line 891 fires
  BEFORE the new Queens check — no misroute of Brooklyn addresses that mention "Queens Blvd").
- `Queensboro Bridge approach, New York, NY` → **manhattan** (`\bqueens\b` correctly does NOT
  match "queensboro" — word boundary holds; no false Queens tag).
- `456 Bushwick Ave, Brooklyn` → **bushwick** (specific-neighborhood keyword loop returns
  before any borough fallback — CRITICAL-check neighborhoods safe).
- `Manhattan, New York, NY 10001` → manhattan; `Bronx/Staten Island` → correct.
- `22-25 Jackson Ave, Queens, NY 11101` → **long island city** (specific > borough).
Ordering is correct: specific-keyword loop → brooklyn → queens/bronx/SI → manhattan
fallthrough. Longest-key-wins in `_backfill_neighborhood_from_venue` is a strict refinement
("moma ps1" beats "moma"); bare "moma" still → midtown (test-covered). 153 tests pass in the
two touched files; reported full suite 310 pass. **No Brooklyn/Manhattan regression.**

### (b) Curating the full Elsewhere organizer — bounded rave-leak risk
Elsewhere books varied programming incl. late DJ nights (ELSEWORLD), unlike the venue-level
HoY/KDC exclusion. Key protection verified in code: `is_user_excluded` is a HARD DROP filter
in normalize.py:1974 (not a soft penalty) and fires on title_hints ("rave", "warehouse rave",
"open to close", "dj marathon", "after party @", "@ 99 scott") for ANY event regardless of
curated-host status. Curation boost only lifts events that survive that drop. Additionally
`_likely_past_midnight` (normalize.py) + HARD blocks ("after hours", "till 4am", "all night
long") catch late-night. Residual gap: a late DJ set with a clean title (e.g. "ELSEWORLD
RETURNS: Yung Singh...") carries no excluded token and WOULD be boosted. That is broader than
the user's stated taste warrants for a floor-BYPASS. MODIFY below adds a safety net without
losing the on-taste supply.

## Verdicts

### ingestion-P1 (fb-194): Queens/LIC neighborhood mistag fix — APPLIED
- **Verdict**: APPROVE
- **Metric moved**: Topic coverage / geo-correctness — Queens mistags 14→1, null-neighborhood
  15.6% (< 19% baseline, at the ≤15% target boundary). ~13 events reassigned to correct Queens
  hoods. Improves neighborhood-filter accuracy (a discovery surface) directly.
- **Reasoning**: Independently verified (see adversarial section). Correct ordering, word-
  boundaried borough tokens, strict longest-match refinement, no cross-borough regression,
  tests green. Textbook additive fix.
- **Residual (Open Q1)**: the single "Queens, NE 11101" doubled-address artifact staying
  east-village is upstream data corruption, not a normalizer-logic bug. Accept as-is (option a).
  Do NOT word-boundary numbered-street keywords this round (regression risk to the 142-test
  baseline for a 1-event edge). Queue as a DREAM-DEFER (D2) instead.
- **Open Q3 (new enum values in UI filter)**: confirmed low-risk — queens/bronx/staten island
  are plain lowercase strings the neighborhood filter renders like any other; no code gate on a
  fixed enum. No action needed, but ui-agent should sanity-check the filter dropdown next round.

### ingestion-P2 (fb-195): Retire quality.py keyword lists vs taste — DEFERRED (no change)
- **Verdict**: APPROVE the deferral (deferral is SOUND)
- **Metric moved**: none this round (correctly — shipping it would have REGRESSED high-conviction
  ratio). The before/after harness showed removing 10 music-genre HIGH_VALUE keywords dropped 5
  relevant events by up to 0.150 (Omar Sosa @ Blue Note −0.148, Mingus Big Band −0.105) with
  taste (max 0.109, mean 0.033, ZERO negatives) unable to compensate.
- **Reasoning**: The directive's own escape hatch ("if you can't show non-regression, DEFER")
  is satisfied with quantitative evidence, not hand-waving. Taste is an order of magnitude too
  weak and has no negative examples, so it cannot subsume keyword boosts OR penalties yet. This
  is the honest-negative precedent (2026-06-15-1724) done right.
- **Nudge (not a reject)**: the zero-hit-on-feed keyword cleanup (51/90 HIGH_VALUE, 26/39 SOCIAL,
  30/33 SOFT_PENALTY are 0-hit on the frozen feed) is a provable 0-delta no-op. I disagree with
  fully skipping it "to avoid churn" — a 0-delta dead-code prune is exactly the low-risk win that
  keeps the lists maintainable and makes the NEXT retirement measurable. Queue as DREAM-DEFER
  (D1): retire only the measured-zero-hit clusters with a test asserting 0 ranking delta.
- **Open Q2**: landing a real user_engagement.json (negatives) IS the true unblock and is gated
  on the frontend taste-export loop. Correct read. Keep fb-195 open, blocked-on-negatives.

### source-curator-S1 (fb-196a chess): Chess Place organizer o/115357260611 — APPLIED
- **Verdict**: APPROVE
- **Metric moved**: Topic coverage — closes the "zero chess events" gap; 6 recurring social
  chess nights (Moxy LES, Cosmic Diner, Fox Harlem). Meet-people register the user named.
- **Reasoning**: Live-probed 6, exclusion-clean, brand organizer not a person, wired via
  `_parse_organizer_page`. Clean add.

### source-curator-S2 (fb-196a backgammon): Meetup keyword-search URL — RECOMMEND, orchestrator to apply
- **Verdict**: APPROVE (orchestrator must append to GENERIC_URLS in scrapers/sources/generic.py)
- **Metric moved**: Topic coverage + fixes the chronic "NYC Backgammon Club" sanity_check
  CRITICAL (13 backgammon-matching, ~9 NYC; titles satisfy the CRITICAL's title/sourceUrl
  match). This is the single highest-value source add this round — it green-lights a check that
  has been red for many runs.
- **Reasoning**: Only viable path (Eventbrite/lu.ma both empty of real backgammon, verified
  negatives). Same JSON-LD pattern as existing run-club/book-club Meetup search URLs. The
  ~4/13 LI/NJ/virtual noise is dropped by the NYC-geo normalizer.
- **Watch (source Open Q2)**: confirm post-scrape that no "Backgammon On Long Island" leaks. If
  the geo-filter passes a non-NYC one, flag to ingestion — but do NOT block this add on it.

### source-curator-S3 (fb-196c social dance): Harlem Swing Dance Society o/10662501681 — APPLIED
- **Verdict**: APPROVE
- **Metric moved**: Topic coverage — adds swing/lindy participatory socials (feed was contra-
  only). 7 upcoming, non-performance, meet-people. Exactly the non-contra gap named.
- **Reasoning**: Clean, on-taste, exclusion-clean, wired. No concerns.

### source-curator-S4 (fb-196b electronic): Elsewhere organizer o/105655500371 — APPLIED
- **Verdict**: MODIFY
- **Metric moved**: High-conviction ratio + topic coverage — 12 already-scraped-but-floored
  electronic events lifted over the score floor. On-taste (Warm Up / Detroit-techno vector).
- **Reasoning**: The venue-level curation with a floor-BYPASS is broader than the user's HoY/KDC
  club exclusion justifies for a venue that also books late DJ nights. The hard title_hint DROP
  filter + `_likely_past_midnight` catch labeled raves, but a clean-titled late set would still
  get the full +0.15 boost AND floor-bypass. Keep the source; tighten the lift.
- **If MODIFY (exact change)**: Keep the o/105655500371 entry in user_curated_sources.json BUT
  demote it from a floor-BYPASS curated host to a curated **boost-only** entry (the +0.15
  ranking boost still fires; the 0.55 MIN_SCORE floor is NOT bypassed). Mechanically: add
  `"floor_bypass": false` to the Elsewhere entry (or the equivalent flag the boost path reads in
  normalize.py `_min_score_floor` / ranking.py `_user_curated_boost`); if no such flag exists,
  set its `"score"` to 0.7 instead of 1.0 so it boosts but does not force-surface below-floor
  events. Net: strong Elsewhere shows still surface via boost+quality; a thin/late one-off must
  still clear the normal quality gate. Update the note to say "boost-only, floor not bypassed
  (Critic S4: bounded late-night leak risk)."

### ui-U1: Non-color conviction cue (★following / ◆your-scene pill) — MODIFY
- **Verdict**: MODIFY (ship following-tier chip only)
- **Metric moved**: High-conviction ratio (perceivability — makes the North-Star signal survive
  colorblindness; WCAG 1.4.1). Real a11y win.
- **Reasoning**: The signal being color-ONLY is a genuine bug worth fixing. But TWO new pills on
  every conviction card (following + affinity) risks re-cluttering the footer the same run U3 is
  trying to de-clutter, and skirts the iter-214 "no verbose provenance" removal. Following is the
  higher-value, higher-precision tier.
- **If MODIFY (exact change)**: Ship the `convictionFollow` "★ following" pill only. Drop the
  `convictionAffinity` "◆ your scene" pill this round (affinity is the fuzzier tier and adds the
  most clutter for the least conviction). Re-evaluate the affinity pill next run once U3's
  footer-wrap is in and we can see density on a 320px card.

### ui-U2: aria-labels + visible focus rings — APPROVE
- **Verdict**: APPROVE
- **Metric moved**: a11y (keyboard + screen-reader access to the account-drilldown, which is how
  AT users explore the follow graph). No direct metric, zero-risk correctness.
- **Reasoning**: Purely additive class strings + aria-labels. `focus-visible:` won't show on
  mouse click (no mouse-user regression). Tailwind v3 ships `focus-visible`. Clean.

### ui-U3: Mobile-first responsive tightening — APPROVE
- **Verdict**: APPROVE
- **Metric moved**: Required-detail surfacing on mobile (the ★/hide/@account controls are the
  personalization surface; they must not clip on a phone — the primary IG-replacement device).
- **Reasoning**: `w-20 sm:w-24` image step-down, footer `flex-wrap`, and modal `max-h-[90vh]`
  are standard responsive fixes with no desktop change. Wrap-to-2nd-line beats truncation.

### ui-U4: Cap Just-Added / This-Weekend heroes 6→4 — APPROVE
- **Verdict**: APPROVE
- **Metric moved**: High-conviction ratio surfaced above the fold — the ranked feed + the
  highest-conviction heroes (Tonight/Following/Saved stay at 6) reach the viewport ~8 cards
  sooner on mobile. Directly serves "get high-conviction events in front of the user faster."
- **Reasoning**: Slice-only change, all 5 heroes preserved (§513 durable pref respected), the
  two trimmed rails are the lowest-conviction discovery rails. Simpler than a CSS collapse with a
  "show more" affordance. Correct trade.

### user-directed: openbookclub via Substack — MODIFY
- **Verdict**: MODIFY
- **Metric moved**: Follow-graph coverage / high-conviction — openbookclub is a user-named
  IG-blocked (fb-174) account already in config.py IG_ACCOUNTS + must_surface; Substack is a
  legitimate non-IG enrichment path (exactly what the fb-174 note asks for). Would surface a
  followed account currently at 0 yield.
- **Reasoning**: Path is sound and exclusion-clean. TWO concerns force a MODIFY, not a plain
  APPROVE: (1) the reported post-titles are informal/first-person ("I'm hosting a karaoke
  night", "I hired a magician") — roundup-y captions, not clean event titles; (2) the substack
  parser uses PREFER_DATES_FROM=future (substack.py ~line 570), so a genuinely PAST one-off
  ("I hired a magician") gets a FABRICATED future date and could surface as a fake upcoming event.
- **If MODIFY (exact change)**:
  1. APPLY: add `https://openbookclubnyc.substack.com/feed` to `substack.FEEDS`; add
     `openbookclubnyc` to user_curated_sources hosts; update the must_surface openbookclub entry
     hint to note the Substack path is now wired.
  2. GUARD the date-fabrication risk: for this feed, require the extracted event to have an
     EXPLICIT future date token in the post body (reuse the existing DATE_PATTERNS match) — do
     NOT emit an event from a bare/first-person title with no in-body date. If the substack
     parser can't scope this per-feed cheaply, then set the must_surface `min` to 0 and rely on
     the quality floor + `_likely_past_midnight`/dateless-garbage filters (substack.py:425) to
     drop the informal past posts, and accept a live 0-yield until a real dated OpenBookClub post
     appears. Either way: no fabricated-future one-off events.
  3. Do NOT floor-bypass this host (same reasoning as Elsewhere): boost-only, let the quality
     gate filter the roundup-y captions.

## Notes back to each worker

## Notes back to ingestion-quality
- You missed: the **zero-hit keyword cleanup is not "cosmetic churn" — it is the safe first
  step the directive explicitly names** ("Start with zero-hit-on-feed keywords as a pure no-op").
  Shipping the measured-0-delta prune (with a test asserting 0 ranking delta) shrinks the lists
  you have to reason about next round and makes the real retirement measurable. You had the data
  (51/90, 26/39, 30/33) and chose not to act on it. Queued as D1.
- You missed: confirming the **new borough enum values render in the UI neighborhood filter**
  yourself (Open Q3) — you flagged it as a question but it's a 2-minute grep of the filter
  component. (I confirmed: they're plain strings, safe. But own the verification next time.)
- Strong work on: the fb-194 fix is exemplary — correct ordering (brooklyn before the new
  queens check), word-boundaried borough tokens (verified "queensboro" does NOT false-match),
  longest-match refinement, 11 new tests, and an HONEST residual write-up of the doubled-address
  edge instead of hiding it. And the fb-195 DEFER is the right call backed by a real before/after
  harness with named regressed events — that is exactly the adversarial evidence a defer needs.

## Notes back to source-curator
- You missed: **the Elsewhere floor-BYPASS is the actual leak vector**, not the title match.
  You correctly checked title_hints, but curation on this venue also grants a MIN_SCORE bypass —
  which means a thin/clean-titled late DJ set surfaces below the normal quality gate. See S4
  MODIFY (demote to boost-only). Your own Open Q1 half-saw this ("if curation boost alone isn't
  enough...") but framed it as under-surfacing; the real risk is over-surfacing.
- You missed: noting that **S2 (backgammon Meetup) fixes a standing sanity_check CRITICAL** —
  this is your highest-impact deliverable and you buried it as a GENERIC_URLS footnote. Lead with
  it; a chronic-red CRITICAL going green is a headline win.
- Strong work on: the negative-probe hygiene. Live-verifying that Eventbrite/lu.ma have ZERO real
  backgammon (substring noise only), documenting the 404 slug-guesses, and correctly NOT re-adding
  HoY/KDC is precisely the fb-153-clean discipline the loop needs. The Public-Records "already
  covered, no action" call also avoided a duplicate.

## Notes back to ui-agent
- You missed: **you're adding U1 pills the same run U3 is de-cluttering the footer** — you noted
  the tension but shipped both pills anyway. Ship the following pill only (U1 MODIFY); the affinity
  pill is clutter-for-low-conviction. Re-add it next run once U3's wrap lands and you can measure
  320px density.
- You missed: the neighborhood filter now gets **new borough values (queens/bronx/staten island)
  from fb-194** — verify the filter dropdown renders them (it does; plain strings) and that
  "queens" as both a borough-level tag AND a filter option doesn't read as a dupe of specific
  Queens hoods. Coordinate with ingestion Open Q3.
- Strong work on: correctly identifying the color-only conviction cue as the North-Star-relevant
  a11y bug (not just generic WCAG box-ticking), and preserving all 5 heroes in U4 (slice, don't
  remove) — you respected the durable hero pref while still solving the "ranked feed buried on
  mobile" complaint.

## Dream proposals

### D1: Retire the measured-zero-hit-on-feed keyword clusters (provable 0-delta cleanup)
- **Verdict**: DREAM-DEFER (source: agent-proposal, backlog)
- **Metric moved**: none directly (0 ranking delta by construction) — enables the fb-195
  retirement to become measurable next round; reduces list-maintenance surface.
- **File**: scrapers/quality.py (HIGH_VALUE / SOCIAL / SOFT_PENALTY keyword lists);
  new test in scrapers/tests/ asserting feed-wide ranking is byte-identical before/after.
- **Change sketch**: For each keyword with 0 hits across the current feed (ingestion measured
  51/90 HIGH_VALUE, 26/39 SOCIAL, 30/33 SOFT_PENALTY), remove it and gate the PR on a test that
  re-scores the frozen feed and asserts identical scores. Preserve all fb-001..009 HARD_BLOCK
  keywords regardless of hit count (they're user-explicit, not taste-derived — a 0-hit hard
  block is still a guardrail, do NOT prune those). This is the directive's own "pure no-op
  cleanup" first step that this run skipped.

### D2: ZIP-code-priority tie-break in infer_neighborhood (kills the corrupted-address edge)
- **Verdict**: DREAM-DEFER (source: agent-proposal, backlog)
- **Metric moved**: Topic/geo correctness — recovers the last ~1 Queens mistag (the
  "Queens, NE 11101" doubled-address artifact currently stuck at east-village because "ne 5th"
  hits the EV "e 5th" keyword before the borough/ZIP check) and hardens against future
  corrupted addresses that carry a valid ZIP.
- **File**: scrapers/utils/event_parser.py `infer_neighborhood`.
- **Change sketch**: Before the general keyword loop, add a ZIP-code fast-path: if the text
  contains a 5-digit token matching a known NYC ZIP → neighborhood map (11101/11109→LIC,
  1110x→Astoria, etc.), return that hood first (ZIP is unambiguous; street-name keywords are
  not). This is ingestion Open-Q1 option (c). Deferred (not shipped this run) because it needs
  its own ZIP→hood table + tests and shouldn't ride on the fb-194 patch. Guardrail: only for ZIPs
  with a 1:1 neighborhood; borough-spanning ZIPs fall through to existing logic.
