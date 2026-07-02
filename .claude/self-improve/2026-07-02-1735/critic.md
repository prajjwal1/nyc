# Critic Report — 2026-07-02 1735

Reviewing LIVE working-tree changes (ingestion applied + tested) + one UI proposal
+ a validation-only source pass. Verdicts verified against the actual diffs and the
frozen `site/public/events.json` (365 events), not just the worker reports.

## Cross-check results
- **sanity_check regression risk**: NONE — and one CRITICAL_CHECK is *strengthened*.
  The WGB check ("Williamsburg / Greenpoint / Bushwick ≥ 3") goes 36 → 38 after fb-189
  backfill on the frozen feed (Book Club Bar Bushwick + McNally Jackson Williamsburg now
  tag correctly), zero WGB entries lost. Music ≥15, free ≥20, backgammon, Reading Rhythms,
  IG-dominant unaffected (neighborhood/time changes don't touch category/price/source).
  fb-186 time-fill runs before the late-night filter but is am/pm-guarded + abstains on
  multi-time, so it can't spuriously push events past the late-night cut.
- **Duplicate source proposals**: NONE — source-curator proposed zero adds (moratorium).
- **User-excluded check (fb-153)**: N/A for adds (none). V1 sweep of the 12 existing IG
  seeds against user_excluded_sources.json is clean and correctly cited — but this is a
  re-validation of already-landed seeds, not a new add, so the CHECK-FIRST rule isn't
  triggered this round.
- **UI preference compliance**: OK — U1 is a pure additive JSX pill in an existing flex
  row; no empty gray box (§514), no left-sidebar widget (§515), no hero-party issue (§516).
- **Top-3 directive coverage**: addressed: fb-189 (ingestion P1), fb-186 (ingestion P2),
  fb-188 (ui U1 proposed). deferred-acceptable: none. deferred-REJECTED: none.
  All three top directives were addressed this round.
- **Silent-failure watch**: instagram source = 8 events (scrape-starved, frozen feed) —
  known, infra-blocked (fb-174), not a code regression. No NEW previously-working source
  at 0. Forward flag for next scrape carried below (eventbrite cap-eviction interaction).

## Verdicts

### ingestion-fb189: explicit neighborhood token in venue name/address wins over table default
- **Verdict**: APPROVE (keep in tree)
- **Metric moved**: Topic/neighborhood-badge correctness (North-Star filter accuracy).
  10 → 0 contradictions on the frozen feed; 19 events re-tagged, all verified correct;
  net +2 to the WGB CRITICAL_CHECK. Second-order: improves neighborhood-topic coverage.
- **Reasoning**: Verified the diff independently, not the report. Ran the backfill over all
  365 frozen events and inspected every one of the 19 changes. The fix is actually BROADER
  and better than the report claimed: the "les"-substring bug wasn't just "fiddlesticks" —
  it was firing inside "Sing**les** Night" too (Wynn Love / What If We NYC Singles → were
  mis-tagged LES, now correctly manhattan/None). Confirmed every event that KEEPS the
  `lower east side` tag has a genuine LES address token (delancey/ludlow/essex/orchard);
  every event that LOSES it had no real LES token. No correct case regressed. The
  word-boundary change in `infer_neighborhood` affects ONLY 3 keywords — `les`, `ues`,
  `uws` — all abbreviations that *should* be boundaried; this is a strict improvement
  feed-wide (it was a latent substring bug in build_event for every scraper, not just the
  frozen feed). Step-0 correctly reads `name + addr` only (NOT title), so the "Harlem
  Globetrotters at MSG" title-trap does not fire. Full suite 289 passed / 3 xfailed —
  independently reproduced.
- **Residual watch (non-blocking)**: `_EXPLICIT_HOOD_NAMES` is a parallel list to
  `NYC_NEIGHBORHOODS` keys (worker's open Q). Keep the parallel list — deriving from the
  keys would pull in ambiguous common-noun-ish tokens. But it's now a second place to
  maintain when a hood is added; leave a one-line comment pointing at it (already present).
  The only theoretical over-apply is a venue NAME that contains a hood word for a place it
  isn't in (e.g. a "Williamsburg Savings Bank"-style proper noun) — none exist in the feed;
  if one appears post-scrape, ingestion-quality should add it to the venue table as an
  explicit override. Not worth pre-empting now.

### ingestion-fb186: two-tier body-text start-time inference
- **Verdict**: APPROVE (keep in tree)
- **Metric moved**: High-conviction ratio (indirect) — fills absent startTime so the fb-184
  fitness/dance score-recovery gate (hard-gated on parsed startTime) can fire on future
  Eventbrite scrapes. On the frozen feed only 1/5 recovers (IG-light feed); real payoff is
  scrape-gated. Honest completeness lift, not a floor override.
- **Reasoning**: Adversarially probed the bare-clock fallback — the flagged high-risk path —
  with 13 hostile inputs. The `am`/`pm` requirement is the load-bearing guard: "7 train",
  "$20 at 5 spots", "Year 2026", "call 917-555-1234 at 8pm" (phone digits) all correctly
  return None or pick only the am/pm-suffixed time. Ranges ("9am to 9pm") and afterparties
  ("7pm ... 11pm") correctly abstain via the single-distinct-time gate. Caller (line 1913)
  only fills when startTime is empty and never overwrites; runs at 1913, well before
  rank_events at 2160 — call ordering confirmed for the P1 gate. Keyword tier earliest-wins
  is correct (doors precede show). 15 tests, all pass.
- **On the worker's open Q (source-gating)**: do NOT gate to specific sources. It never
  overwrites a real parse and abstains on ambiguity, so a wrong source would have to have
  (a) no parsed time AND (b) exactly one am/pm time in body text that isn't the start. The
  only edge cases I could construct ("20% off before 6pm", "Route 7 pm snacks") fill a
  *plausible evening time* on an otherwise time-less event — a mild, self-limiting error,
  strictly better than shipping no time. Keeping it general maximizes the honest recovery.
- **Residual watch (non-blocking, forward)**: because fb-186 lets MORE eventbrite events
  clear the fb-184 startTime gate, next scrape will push more eventbrite events at the
  eventbrite=100 cap — watch that music doesn't get cap-evicted below its floor of 15
  (this is the standing cap-eviction concern from the 2026-06-23 journal, now with a new
  upstream feeder). Flag for ingestion-quality post-scrape, not a blocker now.

### ui-fb188: EventModal price-pill parity with FeedCard
- **Verdict**: APPROVE (apply as proposed)
- **Metric moved**: High-conviction ratio (perception) — the modal is the attend-decision
  surface; qualitative-sky pills (donation/PWYC/sliding-scale) read as low-commitment =
  higher attend likelihood, and numeric-gray replaces junk verbatim text. No feed-count
  metric moves; this is a required-detail parity fix.
- **Reasoning**: Verified the proposed guards are a faithful copy of FeedCard's two blocks
  (EventCard.tsx:271-279 numeric-gray + 286-292 qualitative-sky), correctly rescaled to the
  modal's `text-[11px] font-medium`. The FREE pill (EventModal.tsx:167-171) is preserved
  directly above. The intentional behavior change — "varies"/"TBA" now render NOTHING in the
  modal — is the CORRECT call: FeedCard already suppresses these (fb-182 junk-pill cleanup),
  and the modal must not disagree with the card the user tapped from. Actionable info
  (date/time pill, Open-original link) is untouched, so no data is lost. Do NOT add the
  worker's alternative "plain-gray fallback for varies" — it would reintroduce the exact
  junk pill fb-182 removed and diverge the two surfaces.
- **If applying**: replace the single pill block at EventModal.tsx:172-176 with the two-guard
  block from ui.md §U1 verbatim. Run `next build` to confirm clean (per AGENTS.md this is a
  modified Next.js; the change is pure JSX with no new imports/state, so build risk is nil).

### source-curator: scrape recommendation + folk-dance lean-keep + V1 sweep
- **Verdict**: ENDORSE the scrape recommendation; APPROVE folk-dance lean-keep (provisional);
  APPROVE V1 sweep (no action, validation only).
- **Metric moved**: ALL THREE North-Star metrics are frozen and will stay frozen until a
  scrape lands. This is the 3rd consecutive code-only round with ~4 rounds of unlanded
  levers (fitness/dance/contra/12 slugs/12 IG seeds/lu.ma-floor/UI). The single
  highest-leverage action remains a scrape on a residential IP (fb-173/fb-174, user-blocked
  infra). Correctly making zero adds under the moratorium is the right call.
- **Reasoning**: folk-dance slug is live (20 events, ~50% participatory) and exclusion-clean;
  keep provisional until a scrape validates in-feed survival — the ~38% performance titles
  may down-rank, reassess post-scrape (fb-187 watch). The V1 12-seed sweep is clean but is
  re-validation of already-landed seeds, not new adds.
- **Qualification**: the scrape is a user/infra action, not something the orchestrator can
  execute in-loop. The correct framing for the orchestrator: this round ships code-only
  (fb-189/186/188), and the recommendation to the USER is "run a residential-IP scrape to
  land the ~4 rounds of stacked levers and unfreeze all three metrics." Do not let a 4th
  code-only round accrue more unlanded work without escalating the scrape blocker louder.

## Notes back to each worker

## Notes back to ingestion-quality
- You missed (undersold, actually): your fb-189 report only cited "fiddlesticks" for the
  "les" substring bug. The real blast radius is bigger — it was also firing inside
  "Sing**les** Night" (Wynn Love Presents, What If We NYC Singles Night both mis-tagged LES).
  Your fix correctly cleans these too; you just didn't credit yourself. Worth noting in the
  commit message so the next auditor understands the LES→None/manhattan changes are intended.
- You missed: the forward interaction between fb-186 and the eventbrite=100 cap. By letting
  more eventbrite events clear the fb-184 startTime gate, you increase pressure at the cap —
  the standing music cap-eviction risk (2026-06-23 journal) now has a new upstream feeder.
  Add a post-scrape check: music-category count stays ≥15 after the fitness/time-fill levers
  land together.
- Strong work on: the two-tier time inference with the single-distinct-time gate is genuinely
  well-designed — I threw 13 adversarial inputs (subway lines, prices, years, phone numbers,
  ranges, afterparties) and it held. The am/pm requirement + abstain-on-ambiguity is exactly
  the right conservatism for a source-agnostic fill. And Step-0 reading name+addr but NOT
  title correctly dodges the "Harlem Globetrotters at MSG" title-trap.

## Notes back to source-curator
- You missed: nothing actionable — the moratorium discipline is correct. But the escalation
  is getting quieter each round while the unlanded stack grows. Next round, if still frozen,
  the report should LEAD with a single blunt line: "N rounds / N levers unlanded, metrics
  cannot move without a scrape" so the orchestrator/user can't miss it. Validation passes are
  fine but they're not moving the North Star and shouldn't read as if they are.
- Strong work on: the live folk-dance re-probe (20 events, participatory-ratio breakdown) is
  the right kind of cheap validation to do under a freeze — it keeps a provisional slug
  honest without adding anything.

## Notes back to ui-agent
- You missed: nothing — you correctly anticipated the one judgment call (varies/TBA
  suppression) and recommended AGAINST the fallback pill, which is the right answer. Clean.
- Strong work on: copying FeedCard's guards verbatim rather than re-deriving them is exactly
  how you keep two surfaces from drifting. Rescaling to the modal's 11px/font-medium while
  keeping the same logic is the correct discipline.

## Dream proposals

### D1: "Did you go?" one-tap feedback on past saved/attended events (calibration loop)
- **Verdict**: DREAM-DEFER
- **Metric moved**: High-conviction ratio (long-run) + calibration accuracy — closes the
  loop between what we surface and what the user actually attends, which is the literal
  North Star ("events the user would ACTUALLY attend"). Every other lever is a proxy; this
  is ground truth.
- **File**: `site/app/components/EventModal.tsx` (button on events whose date has passed
  and are in the saved set) + a new localStorage key `attendedFeedback` (`{eventId: "yes"|"no"}`)
  + an export path so `scrapers/data/user_interest_profile.json` can ingest the signal to
  re-weight account/topic affinities.
- **Change sketch**: for a saved event with `endTime`/`date` in the past, render a
  "Did you go? [Yes] [No]" pill in the modal; store to localStorage; add a manual
  export-to-profile step (no backend, per fb-010). Deferred because it needs a small
  cross-boundary design (client capture → profile ingest) that's more than a scrape-frozen
  round should ship, and its payoff compounds only once real save/attend history exists.
- **Backlog entry**: source: agent-proposal; "Did you go? past-save calibration button —
  captures attend ground-truth to re-weight affinities; localStorage + manual profile export,
  no backend."

### D2: Venue normalization pass ("BK Bowl" vs "Brooklyn Bowl", branch consolidation)
- **Verdict**: DREAM-DEFER
- **Metric moved**: Follow-graph coverage + dedup accuracy — inconsistent venue names split
  what should be one venue's events across variants, weakening dedup and neighborhood
  backfill (which now leans on venue-name tokens per fb-189). A `_VENUE_ALIASES` map feeding
  both the fb-189 Step-0 matcher and the dedup key would compound with this round's work.
- **File**: `scrapers/normalize.py` (new `_VENUE_ALIASES` dict + a normalize step applied
  before `_backfill_neighborhood_from_venue`) and `scrapers/utils/event_parser.py`.
- **Change sketch**: canonicalize known aliases ("BK Bowl"→"Brooklyn Bowl", "MSG"→"Madison
  Square Garden") on `location.name` before neighborhood backfill and dedup key computation;
  seed the map from the top-20 venues in the current feed. Deferred: its payoff is only
  measurable post-scrape (frozen feed already de-duped), and it's adjacent-but-not-identical
  to the fb-189 work just landed — bundle it into the same file's next touch rather than a
  frozen round. Note it directly hardens the fb-189 Step-0 matcher against name-variant misses.
- **Backlog entry**: source: agent-proposal; "Venue alias normalization — canonicalize
  BK Bowl/MSG-style variants before neighborhood-backfill + dedup; seed from top-20 feed
  venues; compounds with fb-189 Step-0."
