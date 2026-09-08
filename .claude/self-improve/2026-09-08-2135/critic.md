# Critic Report — 2026-09-08 2135

North Star: **Surface events the user would actually attend in NYC.**

## Cross-check results

- **sanity_check regression risk:** no approved/modified proposal would newly break a threshold. On the 645-row snapshot, the checks are Backgammon **0** (already below 1), Reading Rhythms **11**, music **235**, Williamsburg/Greenpoint/Bushwick **50**, free **109**, and Instagram **5** (below the reviewer checklist's 50; the current code treats this as a warning because of fb-174). P3 removes two music rows and P4 one, leaving **232**, so they remain safely above 15. The existing Backgammon and IG failures must not be attributed to these changes, but a fresh scrape must re-run every check before deployment.
- **Duplicate source proposals:** none. Source Curator proposed no additions. C1-C4 are absent from `LUMA_PAGES` / `GENERIC_URLS` and remain an unverified queue, not proposals. P1's `edfest-2026` and `ironstrength-2026-one-community-for-all` collections are not net-new: both already exist in `discovered_urls.json`; `url_health.json` records 226 successes / last yield 14 and 815 successes / last yield 29 respectively.
- **User-excluded check:** no IG or `GENERIC_URLS` add is proposed. Source Curator explicitly checked C1-C4 against `user_excluded_sources.json`; full title-hint checks remain impossible without inventory, so all four must remain unshipped. P1 must continue to apply both `is_blocked` and `is_user_excluded`; the unverified Writing Community collection must not be inserted into discovery/config state this round.
- **UI preference compliance:** ok. U1/U2 add no UI, and the audited homepage has no empty gray image boxes, left-sidebar widgets, or This Weekend hero. Removed Communities/Saved/Events/Calendar navigation remains absent.
- **Top-3 directive coverage:** **fb-216 deferred-acceptable** — 0/4 candidates could be connectedly probed, so shipping none is the only compliant result; P1 is enabling infrastructure and does not count as one of the required three source additions. **fb-213 addressed conditionally** — modified P2 has a reproducible snapshot gain from 49/645 to 51/645 high-conviction events (7.6% to 7.9%); the loop is not closed until apply/verify/journal. **fb-214 deferred-acceptable only as phase sequencing** — the orchestrator must still test, push, confirm the deployment workflow, and verify the public timestamp/assets after apply; this is not a deferral to a later run.
- **Silent-failure watch:** flagged. `stats_history.jsonl:4423-4424` shows `nycforfree` falling **53 -> 0** between 01:22 and 04:36 UTC on Sep 4 and it never returns in the final snapshot. Backgammon also passed sanity on Aug 28 (`stats_history.jsonl:4224-4228`) but is **0** throughout Sep 4. Ingestion Quality must investigate both on the next connected run; neither is explained by today's network failure.

## Verdicts

### ingestion-P1: Schedule the Eventbrite collection frontier
- **Verdict**: MODIFY
- **Metric moved**: topic coverage, **+0 percentage points immediately** (already 9/9); potentially restores up to 43 historically observed collection rows, but no source or metric gain may be claimed until a current probe passes.
- **Reasoning**: This is an adapter scheduling fix, not approval of an unverified source. The current frontier returns only the two historically productive dormant collections, while the Writing Community URL is not in discovery state. However, the proposed “existing gate” at `eventbrite.py:211-230` checks neither today-onwards dates nor demonstrated-interest fit, so it is weaker than fb-216's admission bar.
- **If MODIFY**: Add the bounded collection lane (2 quick / 6 full) before broad search, but admit a collection's rows only after canonical dedup and a current-page gate over future rows: at least 5 unique `date >= today` events and at least 80% that are both `not is_blocked`, `not is_user_excluded`, and category-aligned with the personal topics from `ranked_topics()`. Stamp `discoveryLane` / `discoveryVia` only after the gate. Add tests for `/cc/` scheduling, past-only rejection, sub-80% rejection, and canonical dedup. Do not add `writing-community-4261073` anywhere this round.

### ingestion-P2: Credit structured organizer references before shell filtering
- **Verdict**: MODIFY
- **Metric moved**: high-conviction event ratio, **49/645 (7.6%) -> 51/645 (7.9%), +0.31 pp** on the frozen snapshot; today-onwards, **47/513 -> 48/513, +0.20 pp** because `Garden Rest and Read` is now past.
- **Reasoning**: The two claimed misses are real and exact: `organizerRefs.handle` is `litclub.nyc` and `philosophy.nyc`, both signal accounts. But moving the entire current enrichment routine before `_is_shell_event` would also let its looser organizer/location suffix-add heuristics rescue shell rows; the proof only supports early bypass for structured exact matches.
- **If MODIFY**: Add a pre-shell structured-organizer pass that checks `organizerUrl` plus each `organizerRefs[].handle|url|name` against `_user_following_normalized()` via exact normalized candidates, sets `account`/`userFollowing`, and allows that exact signal through the shell exception. Keep the existing broader source-URL/organizer/location enrichment after shell filtering. Preserve hard blocks and `is_user_excluded` ahead of shell handling. Test both named events, an excluded-handle negative, an unrelated cohost negative, and a fuzzy location-name shell that must still drop.

### ingestion-P3: Reject explicit non-NYC New York ZIP codes in Partiful
- **Verdict**: APPROVE
- **Metric moved**: high-conviction event ratio, **49/645 -> 49/641 (7.60% -> 7.64%), +0.05 pp** by removing four non-conviction rows; today-onwards only two remain, yielding about **+0.04 pp**.
- **Reasoning**: Snapshot replay identifies exactly four explicit out-of-city ZIP rows and preserves all 63 explicit NYC-ZIP rows. The rule is narrowly anchored to `NY` plus a ZIP and leaves hidden locations alone. Music remains 233 after this change, far above the 15-event guardrail.

### ingestion-P4: Align the late-night filter window with the audit window
- **Verdict**: APPROVE
- **Metric moved**: high-conviction event ratio, **49/645 -> 49/644, about +0.01 pp** in the snapshot denominator; no today-onwards delta because the identified event is now past.
- **Reasoning**: The explicit `9pm-4am` marker at character 247 violates fb-002, and the 300-character replay catches exactly that row while 500 characters finds no additional candidate. It removes one music row but leaves the music check far above threshold.

### ui-U1: Defer source-expansion UI changes
- **Verdict**: APPROVE
- **Metric moved**: high-conviction event ratio, **0 pp directly**; it preserves display of existing conviction/organizer provenance without adding clutter.
- **Reasoning**: `OrganizerLink.tsx:7-24` already provides organizer -> Instagram -> source fallback through `eventOrganizerDetails`, and no source addition is approved today. A source-specific widget would not improve any North-Star metric.

### ui-U2: Defer an exact-distance badge until the feed owns the data
- **Verdict**: APPROVE
- **Metric moved**: high-conviction event ratio, **0 pp** this round.
- **Reasoning**: No trusted distance field exists, and synthesizing one from neighborhood strings would reduce decision quality. This deferral also avoids the forbidden mostly-empty placeholder treatment; the existing coarse `nearby` signal is sufficient for this source-focused run.

Source Pool made no source-add proposal, so there is no Source Pool proposal to approve. C1-C4 remain explicitly unverified and must not ship.

## Notes back to each worker

## Notes back to ingestion-quality

- You missed: `nycforfree` silently collapsed from 53 rows to 0 at `scrapers/data/stats_history.jsonl:4423-4424`. This is the exact recurring failure class the review requires; investigate `scrapers/sources/nycforfree.py` with a connected fixture capture next round.
- You missed: Backgammon passed on Aug 28 (`stats_history.jsonl:4224-4228`) but is 0 in every Sep 4 snapshot and violates `scrapers/sanity_check.py:15-20`. Historical `yield_map > 0` does not clear a current-source regression.
- You missed: P1's reused usefulness helper (`scrapers/sources/eventbrite.py:211-230`) has no future-date or on-taste test, so it cannot by itself satisfy fb-216's source-admission gate.
- Strong work on: separating historical yield from current-feed conviction, proving the two organizer-ref misses, and replaying P3/P4 against all 645 snapshot rows.

## Notes back to source-curator

- You missed: the dead-URL/source audit focused on one old Eventbrite organizer while the much larger `nycforfree` 53 -> 0 collapse was visible in `stats_history.jsonl:4423-4424`.
- You missed: C4 is blocked not merely on a probe but on the collection adapter path at `platform_discovery.py:194-202` versus `eventbrite.py:127-150`; record P1 as a hard dependency before any later promotion.
- Strong work on: refusing to convert search-index visibility into a source proposal, checking exclusions before every candidate, and distinguishing dynamic-frontier duplicates from static-list absence.

## Notes back to ui-agent

- You missed: both proposal headers cite “required-detail/clutter” rather than one of the three North-Star metrics. The honest impact is 0 pp; state that explicitly instead of inventing a fourth metric.
- You missed: `ActivityPanel.tsx` being unmounted is not enough reason to keep auditing its removed export/saved UI each round; the source-expansion contract should instead be asserted at `OrganizerLink.tsx:7-24` with a fallback test.
- Strong work on: verifying the minimalist homepage against every durable UI constraint and recognizing that organizer-link completeness is primarily a normalization contract, not a new widget.

## Dream proposals

### D1: Remove the false `ai` topic inferred from usernames
- **Verdict**: APPROVE-DREAM
- **Metric moved**: topic coverage becomes a truthful **8/8 instead of a misleading 9/9 (0 pp, one false topic removed)**; if the two AI rows currently sitting exactly at score 0.35 lose the spurious +0.03 interest boost and fall below the floor, high-conviction ratio rises roughly **49/645 -> 49/643 (+0.02 pp)** through precision.
- **File**: `scrapers/utils/interest_profile.py:110,116-119`; tests in `scrapers/tests/`; regenerate `scrapers/data/user_interest_profile.json`.
- **Change sketch**: remove `ai` from `_USERNAME_TOPIC_HINTS` and add a regression proving `anaiswinebk` and `likeafriendsaid.nyc` do not infer AI. Those are the only two signal handles containing the substring `ai`; neither expresses AI interest. Do not add a broad AI hard block—the existing exact user exclusions remain authoritative.

### D2: Detect source-yield cliffs before they become stale-feed mysteries
- **Verdict**: DREAM-DEFER
- **Metric moved**: topic coverage **0 pp immediately**, but protects all represented topics and could recover the **53-row** `nycforfree` loss; high-conviction impact is unknown until source provenance is replayed.
- **File**: `scrapers/sanity_check.py`; `scrapers/data/stats_history.jsonl` reader/helper.
- **Change sketch**: add a warning-only source-survival check comparing current source counts with the rolling median of the last five successful snapshots. Warn when the median is at least 5 and current count is 0, printing the source and last non-zero timestamp. Cover a 53->0 failure and a legitimately low/seasonal 1->0 source. Queue this as `source: agent-proposal`; do not make it deployment-fatal until false-positive behavior is observed.
