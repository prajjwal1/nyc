# Ingestion Quality Report — 2026-07-02 1735

Scope: scrape-INDEPENDENT, test/build-verifiable only (feed frozen at 2026-06-15, 3rd code-only round). All changes are normalizer/data fixes measured on the frozen `site/public/events.json` + unit tests. No source-pool, threshold, or scrape-gated work.

## Metrics observed (frozen feed, 365 events)
- Follow-graph coverage: 15/50 (30.0%) — unchanged (no scrape; not a code-fixable metric this round)
- Topic coverage: 4/4 meaningful topics present
- High-conviction ratio: 64/365 (17.5%)
- Name/neighborhood contradictions: **10 → 0** after fix
- Events missing startTime recoverable from body text: 1/5 with strengthened inference

## Proposals (all IMPLEMENTED + verified in this session)

### P1: Explicit neighborhood token in venue name/address wins over the venue-table default (fb-189)
- **Metric moved**: neighborhood-badge correctness (North-Star filter accuracy) — the user relies on the neighborhood badge; 10/365 were lying.
- **Files**: `scrapers/normalize.py` (`_backfill_neighborhood_from_venue`, new `_explicit_hood_in_text` helper) + `scrapers/utils/event_parser.py:840` (`infer_neighborhood` short-keyword word-boundary matching + `_re_neighborhood_word`).
- **Root causes found** (3, intertwined):
  1. `_VENUE_NAME_TO_NEIGHBORHOOD` step-1 substring match applied a chain venue's flagship default over a more-specific branch token in the same name. "New York Comedy Club **Upper West Side**" → mapped to `east village`; "**Book Club Bar Bushwick**, 380 Troutman St" → `east village`; "**McNally Jackson Williamsburg**" → `soho`.
  2. The 3-char `"les"` (Lower East Side abbrev) keyword substring-matched inside `"fiddles`ticks`"`, tagging two Astoria run events as `lower east side`.
  3. `infer_neighborhood` returns the FIRST dict-order hood that matches, so LES (earlier in dict) beat Astoria.
- **Change**: New Step 0 — if the venue name/address contains a word-boundaried explicit neighborhood NAME token, that self-declaration wins outright (longest-match) before the venue table or address inference. Short (≤3 char) keywords in `infer_neighborhood` now match with `\b` boundaries.
- **Events this fixes** (real, from frozen feed): "New York Comedy Club Upper West Side" ×6 (east village → upper west side); "Book Club Bar Bushwick, 380 Troutman Street" (east village → bushwick); "McNally Jackson Williamsburg" (soho → williamsburg); "Astoria Park" run events ×2 (lower east side → astoria).
- **Verification**: ran `_backfill_neighborhood_from_venue` over the live 365-event feed — conflict count **10 → 0**, every named case resolves correctly, no correct case regressed. 5 new unit tests in `scrapers/tests/test_normalize.py::TestBackfillNeighborhood` (incl. a regression guard that bare "Book Club Bar" with no branch token still resolves to the `east village` table default). Full suite: 289 passed, 3 xfailed.
- **Risk**: A venue name that incidentally contains a neighborhood word it isn't actually in would now trust that word. Mitigated: matching is on explicit hood *names* only (not street keywords) with word boundaries, longest-match wins, and the regression test locks the table-default path for name-only venues. No conflict introduced across the full frozen feed.

### P2: Strengthen body-text start-time inference (fb-186)
- **Metric moved**: event completeness → unblocks the fb-184 fitness score-recovery gate (hard-gated on parsed `startTime`). Honest completeness lift, not a floor override.
- **File**: `scrapers/normalize.py` (`_infer_time_from_text`, `_TIME_IN_TEXT_RE`, new `_BARE_TIME_RE` + `_to_minutes`).
- **Gaps found in the existing (2026-06-04) implementation**: bare "7pm"/"7:30pm" NOT caught; "doors open at 7:30pm" NOT caught; no `begins`/`show at` cue.
- **Change**: two-tier inference — (1) keyword-anchored cues (doors/starts/begins/kicks off/show, with optional `open`/`at` and minutes), earliest match wins; (2) bare-clock fallback ("7pm", "7:30pm") fired ONLY when the text has exactly ONE distinct plausible 06:00–23:59 time, so ranges ("2pm to 5pm") and multi-time captions ("7pm ... afterparty 11pm") are left unfilled. Still only fills an ABSENT startTime (caller gate at `process()` unchanged), never overwrites.
- **Call ordering verified**: inference runs at `process()` line ~1832, `rank_events` at ~2080 → scoring sees the inferred time. Confirmed.
- **Verification**: 15 new unit tests in `TestInferTimeFromText` (all listed directive cases: "doors at 7pm", "show starts 8pm", "7:30pm", bare "7pm", never-overwrite-when-present via caller, ambiguous multi-time → None). All pass. On the frozen feed: 1/5 startTime-less events recovered ("SUPERGIRL World Premiere" → 19:00); sample small because the frozen feed is IG-light — real payoff is on future fitness/run/dance Eventbrite scrapes.
- **Risk**: Low. Bare-time fallback is gated on single-distinct-time; keyword tier is anchored. Range/multi-time cases explicitly abstain.

## Directive 3 — scrape-independent feed quality audit
- Source distribution: eventbrite 100, mcnallyjackson 30, partiful 30, meetup 28, luma 24, nycforfree 20, allevents 18, bookclubbar 17, songkick 16, newyorkcomedyclub 15, others small; instagram only 8 (frozen/scrape-starved).
- Late-night leaks (`[1-5]am|nightclub|afterhours`): **0**.
- Far-future misparses (>2026-12): **0**.
- Title+date dupes: **0**.
- Narrative-starter / trailing-fragment titles: **0**. Lowercase-start: 3, all benign stylizations ("commUNITY Run Club", "barnacle boi", "writing party!").
- Pro-networking regex probe: 1 hit — **false positive**, "Wall Street banker" appears in the plot summary of Ali Hazelwood's novel "Games" (a McNally Jackson author event). Correctly kept & categorized; **no fix** (blocking it would drop legitimate literary events).
- **Conclusion**: frozen feed is clean of the fixable leak classes. No P3 warranted — proposing filter/clean_title changes for the benign cases would risk regressing legitimate content with no measurable gain.

## Directives addressed
- fb-189 (PRIMARY): **ADDRESSED** — P1. Conflict count 10→0 on frozen feed, name-token wins, 5 unit tests incl. the exact "Bushwick, 380 Troutman St → bushwick" case + 2 more (UWS, Williamsburg) + LES-substring root-cause case + regression guard.
- fb-186: **ADDRESSED** — P2. Bare-Npm/Npm:MM coverage added, single-time gating, never-overwrite preserved, call-order-before-scoring verified, 15 unit tests.
- Directive 3 (feed quality audit): **ADDRESSED** — no fixable scrape-independent leak found; documented the one false-positive so the Critic can confirm no action.

## Open questions for the Critic
- P1 Step-0 uses an explicit-hood-NAME list (`_EXPLICIT_HOOD_NAMES`) separate from `NYC_NEIGHBORHOODS`. It intentionally EXCLUDES ambiguous single words that double as common nouns (none currently). If you'd prefer a single source of truth, I can derive it from the `NYC_NEIGHBORHOODS` keys instead of a parallel list — but the keys include some I'd want to keep out of name-matching. Flagging for your call; current form is verified-correct on the full feed.
- fb-186 bare-time fallback fires on ANY source (source-agnostic, as the docstring states). If you want it gated to specific completeness-hungry sources (eventbrite fitness/dance), say so — I kept it general because it never overwrites and abstains on ambiguity.
