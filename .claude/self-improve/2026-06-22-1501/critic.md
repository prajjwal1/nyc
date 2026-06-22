# Critic Report — 2026-06-22 1501

## Cross-check results
- **sanity_check regression risk**: NONE. No proposal removes a source, keyword, or scraper. P1 is an additive scoped skip (keywords still present for non-fitness). P2 narrows a single title-hint match — narrowing exclusion is *recovery*, never suppression of a CRITICAL_CHECK item. P3 only un-merges within one curated source. S1–S6 are additive URLs. Backgammon / Reading Rhythms / music≥15 / W-G-B≥3 / free≥20 / IG-dominant≥50 all untouched. The fitness boost (already landed) carries a WARNING_CHECK ("Run clubs / fitness", min 1) — P1+S1+S6 strengthen it.
- **Duplicate source proposals**: NONE. Verified the 6 proposed slugs against `scrapers/sources/generic.py:200-226`. Existing slugs are `running`, `yoga`, `sports-and-fitness`, `fitness`, `dance`, `wellness`. Proposed `run-club`, `contra-dance`, `swing-dance`, `folk-dance`, `salsa`, `pilates` are all NET-NEW distinct slugs. No collision.
- **User-excluded check (fb-153)**: PASS. Source-curator explicitly cited the check for all 6 URLs (0 title_hint hits, no host/account in `user_excluded_sources.json`). Confirmed independently: none of the 6 slug strings appears in the exclusion `hosts`/`accounts`/`title_hints`. The +10 IG seeds (already landed) were re-verified by both Ingestion and Source-curator against fb-106 personal-shape filter and the exclusion list — all clubs/orgs, none excluded. CHECK-FIRST satisfied.
- **UI preference compliance (§513–516)**: PASS. U1 adds a price pill to the existing flex-wrap badge row — no new widget, no left-sidebar, no empty gray box (badge is conditional), no parties in This Weekend. UI agent independently confirmed §516 hero exclusion intact.
- **Additive-only rule**: PASS for all 11 proposals. The 6 inert legacy fitness slugs (0-yield) are NOT proposed for removal (correctly flagged for human review only).
- **Top-3 directive coverage**: fb-179 ADDRESSED (P1 + S1 + S6, plus already-landed seeds/boosts verified). fb-180 ADDRESSED (P3 recovers the merged Harvest Ball session; DISTINCT_SCHEDULE_SOURCES exemption verified load-bearing; S2–S5 broaden the net). fb-181 ADDRESSED (P2 word-boundary fix). Deferred-REJECTED: none. No silent passes.
- **Silent-failure watch**: FLAGGED for next round (not blocking). Source-curator's url_health audit found 6 legacy fitness/dance category slugs with 500+ successes and **0 events_yielded** (`running`, `yoga`, `fitness`, `dance`, `sports-and-fitness` Eventbrite + `allevents.in/.../{running,yoga,fitness}`). This is a classic silent-failure signature — these slugs likely changed their JSON-LD shape or now 200-with-empty-list. ingestion-quality should investigate WHY they parse to 0 next round (the fix may recover yield without needing the net-new slugs to carry the whole load). Also: `newyorkroad.com`, `northbrooklynrunners.org`, `nyrr.org`, `brooklyntrack.club` all dead/JS-only — own-site run-club paths are structurally unscrapeable via generic; do not retry without a dedicated parser.

## Verdicts

### ingestion-P1: Scope-skip "every <weekday>" recurring soft-penalty for fitness/wellness text
- **Verdict**: APPROVE
- **Metric moved**: high-conviction ratio (+~1–2% — run-club events stop carrying a soft-penalty that suppresses their rank) + directly satisfies the fb-179 "no run-club event carries a soft-penalty" criterion.
- **Reasoning**: Verified the bug is real (`quality.py:716-718` carries `every monday/tuesday/wednesday`; a recurring run club describing "every Tuesday 7pm" takes `soft_penalty_hits=1`). The fix is additive (keywords stay for generic "weekly meeting" admin events) and tightly scoped to `{fitness,wellness,outdoors}` categories or run/yoga/workout text markers. Low blast radius. Note the list is Mon/Tue/Wed-only (inconsistent), but the scoped skip makes that moot for the fitness path — leave the inconsistency per additive-only.

### ingestion-P2: Word-boundary `\brave\b` for short single-word title-hints (fb-181)
- **Verdict**: MODIFY
- **Metric moved**: topic coverage (recovers user-requested Oct-4 "Raven & Goose" contra dance, +1 dance event) + conviction (stops FP-dropping legit "travel"/"gravel"/"brave" titles).
- **Reasoning**: The `len(hint) <= 6 and " " not in hint and hint.isalpha()` heuristic is the right *general* approach — but Ingestion implemented it as "only `rave` currently qualifies." That's correct today, but the heuristic is the durable fix and SHOULD generalize so any future short single-word hint (e.g. a future "edm", "afters") gets boundary-matching automatically without re-discovering this bug. Approve the generalized heuristic exactly as written. On the "rave reviews" edge case: I AGREE with Ingestion — do NOT special-case it. `\brave\b` correctly fires on a standalone "Rave Reviews Book Club" (the word "Rave" IS standalone there), but no such event exists in the feed and over-engineering the regex to whitelist a phrase is worse than the rare FP. If a real "Rave Reviews" event ever appears, add it to `user_curated_sources.json` as an allow-exception (Ingestion's recommended path), not to the exclusion regex.
- **If MODIFY**: Apply Ingestion's `\b<hint>\b` regex for ALL hints passing `len(hint)<=6 and " " not in hint and hint.isalpha()` (the general heuristic), not a `rave`-only hardcode. Precompile the per-hint pattern inside `_load_user_excluded_sources` and cache it on the cfg dict so `is_user_excluded` (`ranking.py:734-739`) doesn't recompile per event. Keep plain substring matching for all multi-word / longer / non-alpha hints. Verification target unchanged: "Raven & Goose"/"travel"/"gravel"/"brave" survive; "warehouse rave"/"Friday Night Rave"/"Saturday rave party"/standalone "RAVE" still blocked.

### ingestion-P3: Exempt brooklyncontra from `_dedup_fuzzy_title` so same-night distinct sessions survive
- **Verdict**: APPROVE
- **Metric moved**: topic coverage (dance) — recovers the 2nd Sep-26 Harvest Ball session, contra reaches the full 10 (with P2). Directly serves fb-180.
- **Reasoning**: Traced the merge path. The two Harvest Ball products are SAME source (brooklyncontra), so they hit the `jacc>=0.55 and len(a&b)>=2` branch at `normalize.py:441` via shared tokens {harvest,ball,dance} — not the cross-source branch. Bypassing `DISTINCT_SCHEDULE_SOURCES` events to `out` *before bucketing* (mirroring `_dedup_same_account_recurring`) is correct and does NOT reopen any duplicate leak: brooklyncontra dedupes exact `(date, title.lower())` internally (`brooklyncontra.py:158-161`, verified), so only genuinely-distinct titles reach normalize. No real dup risk. On the open question (shared helper vs two call-sites): KEEP TWO EXPLICIT GUARDS this round. A `_is_distinct_schedule_source(ev)` helper is cleaner but is a refactor touching two working passes for one curated source — not worth the regression surface in a round whose priority is landing user-explicit features. Defer the helper to a maintenance round (see D2).

### source-pool-S1: Add `eventbrite.com/d/ny--new-york/run-club--events/`
- **Verdict**: APPROVE
- **Metric moved**: topic coverage (run=26, reinforces) + high-conviction (recurring run clubs the user follows surface and expand via detect_recurring_weekday). Directly serves fb-179.
- **Reasoning**: 20/20 future-dated, exclusion-clean, distinct from the inert `running--events/` slug. Eventbrite parse path proven, volume-capped at 100 (`config.py:401`). The key insight — that `run-club` returns real listings where `running` returns 0 — is well-evidenced.

### source-pool-S2: Add `eventbrite.com/d/ny--new-york/contra-dance--events/`
- **Verdict**: APPROVE
- **Metric moved**: topic coverage (dance) — broadens fb-180 beyond the single brooklyncontra venue (NYC English-country / other contra).
- **Reasoning**: 20/20 future-dated, clean, net-new slug. Complements the dedicated scraper without overlapping it (that scraper is brooklyncontra.org-only).

### source-pool-S3: Add `eventbrite.com/d/ny--new-york/swing-dance--events/`
- **Verdict**: APPROVE
- **Metric moved**: topic coverage (dance) — social partner dance, fb-180-adjacent, high meet-people fit.
- **Reasoning**: 20/20, clean, net-new. Partner dance is strongly on the user's meet-people vector.

### source-pool-S4: Add `eventbrite.com/d/ny--new-york/folk-dance--events/`
- **Verdict**: MODIFY
- **Metric moved**: topic coverage (dance) — but the SAMPLES are weaker than S2/S3/S5.
- **Reasoning**: The probe samples ("No Lights No Lycra", "Ayazamana: Traditional Music & Dances from Ecuador", "ĀVARTAN GHAR/BA: Pride Edition") skew toward performances/showcases rather than the participatory social-dance the user asked for — folk-dance is the noisiest of the six. It's still 20/20 future-dated and exclusion-clean so it's not a reject, but I want a guard before it ships as a permanent slug.
- **If MODIFY**: Approve the add, but the orchestrator should have ingestion-quality add `folk-dance` to next round's silent-failure / quality watch and re-probe its *landed* yield after the next scrape — if >50% of its surfaced events are performances (not participatory) or it bleeds non-NYC, retire it. Ship it this round (additive, capped) but tag it provisional in the commit message.

### source-pool-S5: Add `eventbrite.com/d/ny--new-york/salsa--events/`
- **Verdict**: APPROVE
- **Metric moved**: topic coverage (dance) — social partner dance, high meet-people fit.
- **Reasoning**: 20/20 future-dated, clean, net-new. Salsa socials are squarely meet-people events. Strong fit.

### source-pool-S6: Add `eventbrite.com/d/ny--new-york/pilates--events/`
- **Verdict**: APPROVE
- **Metric moved**: topic coverage (fitness/wellness) — fb-179 "more fitness-based events." Many are outdoor/park (high outdoor-vector fit).
- **Reasoning**: 20/20 future-dated, clean, net-new, capped. Note: pilates classes can skew transactional/studio-drop-in rather than social — but the `wellness` boost is now 1.2 (not over-boosted) and the samples include social park sessions. Acceptable. Watch landed yield for studio-spam next round.

### ui-U1: Show non-free price pill on the FeedCard
- **Verdict**: APPROVE
- **Metric moved**: required-detail surfacing (not a North-Star metric directly, but improves the "would actually attend" decision for the paid fitness/dance events this round adds — supports conviction by reducing bounce on paid events).
- **Reasoning**: Clean, scoped to the existing badge row, reuses the modal's guard predicate (`EventModal.tsx:172`). The `/\d/.test()` + `!== unknown/varies` guards prevent junk pills. On the open question (suppress "donation"/"pay what you can"?): I lean SHOW qualitative price words rather than suppress — "donation" / "pay what you can" / "PWYC" are POSITIVE signals (often = free-ish, low-commitment) the user would want at a glance, and the card already wraps. But the digit-only filter is the safer default and acceptable for this round. KEEP the digit-only guard as proposed; queue the qualitative-price-word rendering as a follow-up (D1).

## Notes back to each worker

## Notes back to ingestion-quality
- **You missed**: P2 as-implemented is a `rave`-only hardcode dressed up as a heuristic. The heuristic IS the right fix — generalize it (any hint passing `len<=6 and no-space and isalpha`) so the next short single-word exclusion gets boundary-matching for free. I've made that the MODIFY. You almost left durable value on the table by scoping to "only rave qualifies today."
- **You missed**: the 6 inert legacy fitness/dance Eventbrite slugs (0-yield, 500+ successes) flagged by source-curator are a *silent-failure signature* squarely in your lane — they likely had a JSON-LD shape change. You verified the NEW slugs but didn't ask why the OLD ones died. That investigation could recover yield more cheaply than relying on net-new slugs. Pick it up next round.
- **Strong work on**: tracing brooklyncontra to exactly 8-vs-10 and correctly attributing the −2 (one to the rave bug, one to fuzzy-title merge) with the precise line numbers and the internal-dedup safety argument. That made P3 trivially verifiable. Also good restraint flagging "rave reviews" as not-worth-special-casing.

## Notes back to source-curator
- **You missed**: nothing on diligence — every URL live-probed, exclusion-checked, dup-checked, fb-106 re-verified. But `folk-dance` (S4) has materially noisier samples (performances, not participatory social dance) than your other five; you graded all six as uniformly "low risk" when S4 is the weak one. Call out sample-quality differences, not just yield counts. I've MODIFY-gated S4 to provisional.
- **You missed**: you correctly did NOT propose the IG BFS candidates (outopia.run, eastriverpilates, danceparadenyc, barcontranyc) because the IG sweep is blocked (fb-174) — good restraint. But these are on-vector and fb-106-clean by name; you should have written them into the backlog as a `source: agent-proposal` queued-for-IG-refresh entry so they aren't lost when fb-174 clears. (I'm queuing them via D-defer below so they don't evaporate.)
- **Strong work on**: the url_health audit that proved the existing fitness slugs are inert — that reframed the whole round from "add more fitness" to "the fitness URLs we have are dead, add ones that actually parse." That's the highest-leverage finding in the report.

## Notes back to ui-agent
- **You missed**: you suppress qualitative price words ("donation", "pay what you can") via the digit-only guard, but those are POSITIVE low-commitment signals the user would want surfaced — not junk to hide. Acceptable for this round, but it's a real (small) loss of useful info, not a pure safety win. Queued as D1.
- **You missed**: you asserted "no recurring/weekly hint needed on run-club cards" and you're right that the date header disambiguates — but you didn't check whether `collapseRecurring` keeping only the SOONEST occurrence loses the user's ability to see "this is weekly, I can go any Tuesday." For a recurring run club, a tiny `weekly` affordance is arguably the ONE piece of recurring metadata that helps planning. You recommended against it; I agree for this round but flag that you dismissed it without testing the user-planning angle.
- **Strong work on**: the end-to-end trace proving contra (full schedule, no `recurring`) vs run-clubs (`recurring=true` → collapse to soonest) is a deliberate, correct split. That saved a pointless grouping-widget proposal. Correct minimal-round call.

## Dream proposals

### D1: Render qualitative price words ("donation", "pay what you can", "PWYC") as a positive pill
- **Verdict**: DREAM-DEFER
- **Metric moved**: high-conviction / attend-rate — low-commitment "donation"/"PWYC" events are high-yes-probability for a meet-people user; surfacing them at a glance nudges attendance. Small but real.
- **File**: `site/app/components/EventCard.tsx` (the same badge row U1 touches).
- **Change sketch**: after U1's numeric-price pill, add a branch: if `event.price` matches `/donation|pay what|pwyc|sliding scale|suggested/i`, render a distinct subtle pill (e.g. `bg-sky-50 text-sky-700` "donation"). Keep it visually lighter than FREE so it reads as "cheap/flexible," not "free." Backlog entry: `source: agent-proposal`, "Surface qualitative/low-commitment price words on the card instead of suppressing them; they're positive attend signals."

### D2: Refactor DISTINCT_SCHEDULE_SOURCES into a shared `_is_distinct_schedule_source(ev)` helper + add Story Highlights / time-inference to the dream queue
- **Verdict**: DREAM-DEFER
- **Metric moved**: maintainability (not a North-Star metric directly) — but it de-risks the THIRD+ time someone adds a distinct-schedule source (after brooklyncontra, the next venue with individually-ticketed repeated-title nights will need the same two-call-site edit and someone will forget one). Consolidating now prevents a future silent merge-back regression that would QUIETLY drop user-requested dated events.
- **File**: `scrapers/normalize.py` — extract `DISTINCT_SCHEDULE_SOURCES` membership check (`:176` and the new `_dedup_fuzzy_title` guard from P3) into one helper called from both passes.
- **Change sketch**: `def _is_distinct_schedule_source(ev): return ev.get("source") in DISTINCT_SCHEDULE_SOURCES`, called at both dedup passes. Pure refactor, behavior-identical, add a unit test asserting a 2nd source added to the set bypasses BOTH passes. Backlog entry: `source: agent-proposal`, "Consolidate the two brooklyncontra dedup-exemption call-sites so future distinct-schedule sources can't be half-exempted." NOT this round (priority is landing fb-179/180/181); queue for a maintenance round. Also queue from source-curator: the fb-106-clean IG BFS candidates (outopia.run, eastriverpilates, danceparadenyc, barcontranyc, residentrunners, danceherenownyc) as `source: agent-proposal` "probe + add when fb-174 IG sweep is restored."
