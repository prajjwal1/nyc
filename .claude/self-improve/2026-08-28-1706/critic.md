# Critic Report — 2026-08-28 1706

## Cross-check results

- sanity_check regression risk: current live counts are Backgammon 1, Reading Rhythms 10, music 199, Williamsburg/Greenpoint/Bushwick 46, and free 116, so none of P1-P8 or the bounded source additions threatens a hard floor. Instagram is only 7 versus the requested >=50 guard; the current code has demoted that check to a warning, and this round does not repair it. P8 may remove a few music rows, but the 199-to-15 cushion is ample. P1 must retain explicit branch-name precedence so neighborhood canonicalization cannot reduce the W/G/B count.
- Duplicate source proposals: no proposed organizer ID or the folk-dance route is already in `LUMA_PAGES` or `GENERIC_URLS`. S6's Book Club Bar organizer is a deliberate content duplicate of the dedicated Bookmanager source (10/11 projected rows already represented), so it is resilience/provenance work, not new breadth. The five S6 organizer URLs are already staged and should be reviewed as proposals, not presumed accepted.
- User-excluded check: source-curator explicitly checked every proposed host against `user_excluded_sources.json::{accounts,hosts,title_hints}`; none collides. Liz's `Speed Dating Book Club` must continue to be removed by the existing `speed dating` hint. After 5 does contain an uncaught AI listing, which is handled in the modified S7 verdict.
- UI preference compliance: ok. U1-U4 add no empty gray image boxes, no left-sidebar widget, and no party-oriented This Weekend hero. U2's export belongs as a compact header action, not an ActivityPanel/sidebar restoration.
- Top-3 directive coverage: addressed conditionally: fb-206 by S1 + modified P5; fb-207 by modified S3-S6, with After 5 withheld; fb-208 by modified P4 + U1/U2. Earlier directives: fb-178 is addressed by modified U1/U2; fb-187 is provisionally addressed by modified S2 but must remain open until landed quality is measured; fb-193 is addressed by P1.
- Silent-failure watch: Eventbrite, Lu.ma, Partiful, and the major dedicated sources still yield. Two previously working literary sources deserve a next-round probe: `mcnallyjackson` was 1 in the 2026-08-21 stats and is 0 live now; the journal recorded 2 `bondandgrace` events in July and the live feed now has 0. This may be calendar exhaustion, but it must not be silently assumed. Instagram also fell from 10 local events to 7 live and remains far below the >=50 guard, though not to zero.
- Feed/build consistency: local `site/public/events.json` has 286 rows while the deployed feed has 537. The SEO build reads the local file in `site/app/lib/server-data.ts:13`; deployment must use a refreshed feed or 251 live events will have no generated detail page/sitemap entry.

## Verdicts

### ingestion-P1: Complete fb-193 by using the canonical venue key for neighborhood lookup
- **Verdict**: APPROVE
- **Metric moved**: high-conviction ratio remains 16.8% (0 pp count change), while location precision improves for at least the confirmed BK Bowl and MoMA alias cases.
- **Reasoning**: Dedup already uses `_normalize_venue_name`; using the same key for neighborhood lookup fixes an inconsistent consumer without changing display names. The explicit-neighborhood Step 0 and longest/specific branch matching must remain ahead of canonical defaults.

### ingestion-P2: Stop numbered avenues from substring-matching the wrong neighborhood
- **Verdict**: MODIFY
- **Metric moved**: high-conviction ratio remains 16.8% (0 pp); one confirmed live contradiction is fixed and the whole 21st/31st Avenue class is protected.
- **Reasoning**: The diagnosis is correct, but special-casing only 1st and 2nd Avenue will recur for other ordinals.
- **If MODIFY**: compile a boundary-safe matcher for every neighborhood keyword shaped like `^\d+(st|nd|rd|th) (ave|avenue|st|street)$`, using `(?<!\d)` before the number and `\b` after the street token. Test 1st Ave, 2nd Ave, 21st Ave, and 31st Ave plus the Astoria regression.

### ingestion-P3: Let shared Bookmanager extraction use an event-specific address
- **Verdict**: MODIFY
- **Metric moved**: high-conviction ratio remains 16.8% (0 pp); up to 13/30 current Book Club Bar cards gain correct address/neighborhood data.
- **Reasoning**: This is the right shared-parser fix, but the address detector must cover alphanumeric NYC street numbers such as `21A Clinton Street` and hyphenated Queens numbers.
- **If MODIFY**: treat `location_text` as the address only when it contains a bounded pattern equivalent to `\b\d{1,5}[A-Za-z]?(?:-\d{1,5})?\s+...\b(St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard)\b`; otherwise retain `default_address`. Add the three real offsite examples and a prose-only negative control.

### ingestion-P4: Make Eventbrite organizer promotion taste-first and survivable
- **Verdict**: MODIFY
- **Metric moved**: high-conviction ratio has 0 pp immediate change, with an expected +~0.5-1 pp over future scrapes if organizer slots stop being consumed by anonymous high-volume calendars.
- **Reasoning**: Eligible unique URLs, user exclusions, and the structured organizer-row shell exception are correct. The proposal misses the already-known organizer frontier: `platform_discovery.py:298-304` flattens every curated organizer to the same `+8`/`via=curated`, so explicit user choices are still tied with inferred additions and sorted lexically.
- **If MODIFY**: (1) count unique events only after both `is_blocked` and `is_user_excluded`; (2) sort promoted organizers by explicit signal, then count of conviction-bearing/personal events, then clean unique yield; (3) preserve curated-host provenance in `platform_frontier` (`curated:user_mentioned`, `curated:engagement_*`, `curated:agent_recommended_vetted`) and rank user-mentioned/engagement-derived hosts ahead of inferred ones; (4) keep organizer catalog rows only with image plus venue/address; (5) add the requested small-explicit-versus-large-anonymous regression in both known-frontier and newly-promoted paths. Do not manufacture `userAffinity` merely to improve the metric.

### ingestion-P5: Guarantee Liz's organizer and preserve structured titles
- **Verdict**: MODIFY
- **Metric moved**: topic coverage stays 4/4, with literary depth +1 current event (14 -> 15 allowed Liz rows); high-conviction ratio is essentially flat (~-0.03 pp if the recovered row carries no conviction flag).
- **Reasoning**: Stable organizer identity, cross-source refs, and recovery of the Patricia Lockwood event are all required. The config edit duplicates S1 ownership, and a structured-title escape must not bypass hard blocks or user exclusions.
- **If MODIFY**: let S1 own the organizer config. P5 should add stable organizer-ID comparison for slugged/slugless URLs, mark titles coming from a dedicated structured `row.title` field, and bypass only the caption-fragment hard-zero for that marker. Preserve `is_blocked`, `is_user_excluded`, title-quality, and score-floor checks. Keep the 26 -> 16 -> 15 end-to-end provenance test.

### ingestion-P6: Treat Eventbrite endTime == startTime as unknown
- **Verdict**: APPROVE
- **Metric moved**: high-conviction ratio remains 16.8% (0 pp); schedule accuracy improves on 25/37 live Eventbrite rows.
- **Reasoning**: A missing end time is more truthful than a fabricated zero-duration event, and the parser-local change has low blast radius.

### ingestion-P7: Drop Substack date-range headings that leak as titles
- **Verdict**: APPROVE
- **Metric moved**: high-conviction ratio rises by ~0.03 pp (90/537 -> 90/536) by removing one non-conviction junk row.
- **Reasoning**: The exact full-title date-range grammar is narrow, and authoritative event links from the post remain available to other adapters.

### ingestion-P8: Reject explicit NJ addresses and the Edmonton leak
- **Verdict**: APPROVE
- **Metric moved**: high-conviction ratio rises by ~0.19 pp (90/537 -> 90/531) if the six confirmed non-conviction rows are removed.
- **Reasoning**: Address-only state matching avoids broad text false positives. Implement neighboring-state checks only as comma/state or state-plus-ZIP tokens in `location.address`; keep `edmonton` in the explicit non-NYC city set.

### source-pool-S1: Add Liz's Book Bar organizer 83466825333
- **Verdict**: APPROVE
- **Metric moved**: topic coverage and high-conviction ratio are unchanged immediately (0 net cards, 0 pp), while up to nine requested literary events gain a deterministic fallback and retained Eventbrite provenance.
- **Reasoning**: This is the user's exact organizer, it is 9/10 exclusion-clean, and the overlap is honestly disclosed. Use `source: user_mentioned`; keep the speed-dating exclusion.

### source-pool-S2: Restore the folk-dance Eventbrite path provisionally
- **Verdict**: MODIFY
- **Metric moved**: topic coverage remains 4/4 but participatory dance depth may add 4-8 incremental rows; absent conviction flags, the ratio could dilute by ~0.1-0.25 pp.
- **Reasoning**: The live 55% strict-participatory result clears the watch threshold, but it should not become an ad-hoc static URL or displace a stronger personal category from the bounded plan.
- **If MODIFY**: represent `folk-dance` as a supplemental slug under the Eventbrite dance vocabulary, schedule it only when dance is in the personal frontier, dedupe it against the broad dance URL, keep normal floor/late-night/exclusion gates, and leave fb-187 open until the next scrape proves landed strict participation >=50% and at least 5 survivors.

### source-pool-S3: Add High Line Programs organizer 46113016283
- **Verdict**: MODIFY
- **Metric moved**: topic coverage stays 4/4 with +7 projected outdoors/art/fitness rows; if none is conviction-tagged, high-conviction ratio would fall ~0.22 pp in isolation.
- **Reasoning**: The calendar is strong, but the claim that the user already follows it is unsupported: `highlinenyc` is recorded as discovered via `fomofeed`, not `user_following` (`discovered_accounts.json:442-445`). It is an inferred-fit source, not an explicit-follow source.
- **If MODIFY**: add it as `source: inferred_from_taste` (not `user_mentioned`), set `floor_bypass: false`, and confirm at least 5 rows still survive the normal floor before landing it.

### source-pool-S4: Add The Ripped Bodice BK organizer 121441877858
- **Verdict**: MODIFY
- **Metric moved**: topic coverage stays 4/4 with +9 projected literary/social rows; untagged inventory alone would lower the high-conviction ratio ~0.28 pp.
- **Reasoning**: The fit and clean yield are excellent, but inferred recommendations should not receive the same permissive floor as explicit user-mentioned organizers.
- **If MODIFY**: add as `source: inferred_from_taste`, `floor_bypass: false`, and require a >=5 survivor recheck under that exact configuration.

### source-pool-S5: Add Strand Bookstore organizer 30058841244
- **Verdict**: MODIFY
- **Metric moved**: topic coverage stays 4/4 with +10 projected literary rows; untagged inventory alone would lower the high-conviction ratio ~0.30 pp.
- **Reasoning**: Strand matches the user's durable bookstore preference and recovers a dead first-party page, but the one family row and sold-out/thin rows justify the normal score floor.
- **If MODIFY**: record provenance as `inferred_from_named_bookstore_preference`, set `floor_bypass: false`, retain the family hard block, and confirm >=5 survivors after the normal floor.

### source-pool-S6: Ship five already-staged organizers
- **Verdict**: MODIFY
- **Metric moved**: topic coverage stays 4/4 with roughly +32 projected net rows; without explicit conviction provenance this batch could lower the ratio by as much as ~0.9 pp.
- **Reasoning**: Caveat, Union Hall, Book Club for the Book Hoes, and National Arts Club are useful bounded additions. Book Club Bar is mostly fallback coverage, not breadth. The staged metadata also overstates user provenance for Caveat.
- **If MODIFY**: ship the four net-new calendars plus the explicitly labeled Book Club Bar fallback only after each still has >=5 survivors with `floor_bypass: false`; use `agent_recommended_vetted`/`inferred_from_taste` rather than `user_mentioned` unless the backlog proves a direct user mention. Keep Book Club Bar's expected net-new count documented as one.

### source-pool-S7: Add an exact AI guard for staged After 5
- **Verdict**: MODIFY
- **Metric moved**: high-conviction ratio improves by at most ~0.03 pp if the one AI row would otherwise land; more importantly, a known negative preference remains enforced.
- **Reasoning**: The exact guard is appropriate, but it must not be used to justify After 5. That organizer has only 5/12 useful rows after city and AI filtering (~42%), far below fb-207's >=80% calendar-quality requirement; an uncommitted staged source is not protected by the additive-only rule.
- **If MODIFY**: add the exact `ai apocalypse` title hint, but remove/withhold `eventbrite.com/o/120724085237` from the staged organizer batch. Reconsider it only through event-level discovery, not a globally curated organizer calendar.

### ui-U1: Preserve final attendance examples without changing attended:v1
- **Verdict**: MODIFY
- **Metric moved**: 0 pp immediately; each response becomes one durable labeled example and can plausibly add ~0.2-1 pp to future high-conviction coverage after sync.
- **Reasoning**: The cache is needed, but the proposed early return can skip caching an old response, and switching yes -> no leaves the prior +8/+5 profile bumps largely intact.
- **If MODIFY**: cache the event stub before idempotence return; expose all raw attendance states; and make answer changes reversible by undoing the previous answer's profile delta before applying the new one. Add tests for repeated same-answer clicks, yes -> no, no -> yes, and reload persistence of `nyc-events:attended:v1`.

### ui-U2: Restore a safe, download-only taste export
- **Verdict**: MODIFY
- **Metric moved**: 0 pp until the file is moved into the repo; thereafter saved/hidden/attendance evidence can reasonably lift the high-conviction ratio by ~1-3 pp over subsequent scrapes.
- **Reasoning**: Download-only is the correct no-backend/no-token design. “Didn't go” is not equivalent to dislike, so merging it into the same semantic negative centroid as an explicit Hide would teach the wrong preference.
- **If MODIFY**: export all attendance IDs/states via a public `loadAttendedStates()`. Keep `negativeTexts` limited to hidden events; add separate `attendedYesTexts` and `attendedNoTexts`, with attended-yes included in positives and attended-no retained as weaker/diagnostic evidence rather than a full negative. The success message must state the manual copy target `scrapers/data/user_engagement.json`. Test saved, hidden, yes, no, old state without stub, download filename, and unchanged `attended:v1` after reload.

### ui-U3: Make SEO event landings personalized and actionable
- **Verdict**: MODIFY
- **Metric moved**: 0 pp server-side immediately; exposing Save/Hide on search landings should add future labeled events and plausibly lift high-conviction coverage by <1 pp per engagement cycle.
- **Reasoning**: Search landings should not be a less capable dead end than the modal. Reusing the current helpers preserves the client-only model and indexable page.
- **If MODIFY**: retain the crawlable detail page and source-ticket link, reuse a shared event-stub builder, and after Hide either navigate back to `/events` or show an immediate Undo state; do not leave the user staring at an event they just removed. Verify mobile/desktop and a followed-account event.

### ui-U4: Show neighborhood fallback and remove repeated day scent
- **Verdict**: APPROVE
- **Metric moved**: high-conviction ratio remains 16.8% (0 pp); required geography becomes visible on 25/537 live cards.
- **Reasoning**: This recovers real decision information with no new chrome and removes redundant date text from an already grouped route. The no-image text-only rule remains intact.

## Notes back to each worker

## Notes back to ingestion-quality
- You missed: P4 changes newly promoted organizers but not the known curated frontier, where `platform_discovery.py:298-304` erases `user_mentioned` versus inferred provenance and gives every organizer the same score.
- You missed: most location/completeness proposals improve event quality but do not numerically move the defined high-conviction ratio; the report should distinguish proxy quality from a numerator change.
- You missed: P5's config step duplicates S1 ownership; one proposal should own each edit.
- Strong work on: the Liz 26 -> 16 -> 15 -> 14 trace, retained organizerRefs/contributingSources analysis, and exact six-row non-NYC evidence.

## Notes back to source-curator
- You missed: After 5 fails the user's own >=80% organizer bar at roughly 42% useful raw inventory. “Already staged” is not a reason to keep an uncommitted proposal.
- You missed: High Line is not evidenced as a direct follow; `discovered_accounts.json:442-445` says it came via `fomofeed`. Label it inferred, not explicit.
- You missed: adding 30+ clean but unflagged rows can reduce the defined high-conviction ratio even when subjective coverage improves; source recommendations need to report that denominator effect.
- Strong work on: live-probing every candidate, explicitly checking exclusions, separating gross yield from projected survivors, and identifying Book Club Bar/Liz overlap rather than claiming false net-new coverage.

## Notes back to ui-agent
- You missed: `markAttended` must reverse the prior profile delta when the user changes an answer; merely blocking duplicate clicks leaves contradictory learned weights.
- You missed: attended-no is “planned but did not make it,” not an explicit dislike. It needs its own export field rather than being merged with Hide in `negativeTexts`.
- You missed: SEO generation currently reads the stale 286-row local feed (`server-data.ts:13`) while production has 537; action parity does not solve missing detail pages for the other 251 events.
- Strong work on: identifying the removed taste-sync regression, preserving the `attended:v1` contract, and respecting the no-sidebar/no-empty-placeholder/no-party-hero preferences.

## Dream proposals

### D1: Report active-feed follow coverage alongside lifetime yield
- **Verdict**: APPROVE-DREAM
- **Metric moved**: follow-graph coverage measurement changes from a misleading historical 50/50 (100%) to an explicitly reported active-feed 6/50 (12%); no inventory change, but an 88 pp blind spot becomes actionable.
- **File**: `scrapers/sanity_check.py`, `scrapers/data/stats_history.jsonl`
- **Change sketch**: keep the existing lifetime `yield_map` metric, add `active_follow_graph_covered` by folding `event.account`/`instagramAccount` for current `userFollowing` rows against `signal_accounts`, persist both values, and print the missing active handles. Do not hard-fail merely because an account has no future event; warn only on a drop from recent active yield.

### D2: Learn an Eventbrite organizer quality score over time
- **Verdict**: DREAM-DEFER
- **Metric moved**: projected high-conviction ratio +~1-3 pp over several scrapes by spending organizer slots on calendars that both land and earn saves/attendance, rather than repeatedly trusting raw calendar size.
- **File**: new `scrapers/data/organizer_quality.json`; `scrapers/sources/eventbrite.py`; `scrapers/utils/platform_discovery.py`
- **Change sketch**: persist per organizer raw count, exclusion-clean count, normalized landed count, current-feed overlap, saves, hides, attended-yes/no, and last-seen date. Rank explicit user-mentioned organizers first, then learned engagement rate with a minimum sample, then clean landed yield. Never auto-remove a user-mentioned organizer; put low-performing inferred organizers on probation and rotate them out of the bounded frontier after repeated poor landed/engagement results.
