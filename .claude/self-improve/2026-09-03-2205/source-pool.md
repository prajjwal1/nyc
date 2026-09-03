# Source Pool Report — 2026-09-03 2205

## Probe summary

- Feed freshness: the checked-in/public fallback is dated `2026-08-28T18:04:42Z`, six days stale. It contains 556 events, of which 357 are dated September 3 or later. A fresh full scrape is the prerequisite for judging source changes this round.
- Lu.ma topics probed: 4 (`run`, `books`, `brooklyn`, `clubs`) | added: 0. Every request hit an environment-level connection failure. `ny`/`nyc` are geography tokens rather than interest categories; `ai` was skipped because AI events are explicitly excluded.
- Eventbrite organizers probed: 14 previously curated calendars | added: 0. All 14 failed with `ConnectError: All connection attempts failed`; this is network blockage, not zero yield.
- URLs promoted from `url_health.json`: 0. There are 101 unlisted rows with at least 3 successes and last yield at least 5, but 61 are now owned by dedicated platform adapters and the remaining 40 are dynamic month URLs, duplicate aliases, obsolete pagination, broad US pages, or dedicated-source duplicates.
- Accounts promoted: 0. No account outside `IG_ACCOUNTS` has both `events_emitted >= 5` and discovery score `>= 0.45`; all account observations are also older than the requested ~30-day window.
- Dead-URL retests: 1 (`92ny.org`) | resurrected: 0 | result indeterminate because the same network failure affected a known-working Bell House control.
- Exclusion check: completed before considering additions. No account or URL is proposed. The durable no-club/late-night, no-AI, no-speed-dating, and social-entity-only rules remain intact.

## Current coverage and organizer evidence

- Follow-graph coverage is 50/50 lifetime, but only 4/50 signal accounts appear in the stale upcoming slice (8%). Source work should optimize active coverage, not the already-saturated lifetime metric.
- Every tracked `topic_counts >= 2` token appears in the fallback feed. The `ai` token is profile noise under an explicit negative preference and must not drive source discovery.
- High-conviction ratio is 90/556 (16.2%); upcoming-only it is 62/357 (17.4%).
- Liz's Book Bar remains covered: 14 dedicated-source rows in the snapshot, 13 dated September 3 onward, and 9 rows retain organizer ID `83466825333` provenance.

The August 28 quick refresh only exercised the top eight organizer frontier slots. Therefore a zero below means **not yet observed in a full post-addition scrape**, not evidence that the calendar is bad.

| Organizer | ID | Snapshot rows | Sep-3+ rows | Interpretation |
|---|---:|---:|---:|---|
| Elsewhere | `105655500371` | 11 | 6 | Landed; retain normal floor and exclusions |
| Pioneer Works | `20002618011` | 9 | 8 | Landed strongly |
| The Ripped Bodice Brooklyn | `121441877858` | 9 | 8 | Landed strongly; best evidence from the August literary cohort |
| Liz's Book Bar | `83466825333` | 9 provenance matches | 9 | Explicit-user fallback; dedicated source remains primary |
| Lululemon NYC | `14861961557` | 2 | 2 | Landed, low current inventory |
| MoMA PS1 | `8184194121` | 2 | 1 | Landed, low current inventory |
| Harlem Swing Dance Society | `10662501681` | 2 | 1 | Landed, low current inventory |
| Chess Place | `115357260611` | 1 | 0 | Needs a fresh observation before judging |
| Caveat | `13580085802` | 0 | 0 | Outside the prior quick-refresh evaluation set |
| Union Hall | `17899496497` | 0 | 0 | Outside the prior quick-refresh evaluation set |
| Book Club Bar fallback | `40513431663` | 0 | 0 | Expected heavy overlap with the dedicated source |
| High Line Programs | `46113016283` | 0 | 0 | Outside the prior quick-refresh evaluation set |
| Book Hoes | `52255937823` | 0 | 0 | Outside the prior quick-refresh evaluation set |
| National Arts Club | `6140247955` | 0 | 0 | Outside the prior quick-refresh evaluation set |
| Strand Bookstore | `30058841244` | 0 | 0 | Outside the prior quick-refresh evaluation set |

There is currently no `organizer_quality.json`, no organizer-specific entry in `url_health.json`, and no historical raw/clean/landed record. The pipeline cannot distinguish “not scheduled,” “fetch failed,” “fetched zero,” “filtered,” and “deduplicated against a stronger source.” That is the core fb-209 gap.

## Proposals

### S1: Persist bounded Eventbrite organizer quality history (fb-209)

- **Metric moved**: high-conviction ratio and useful source coverage; weak inferred calendars stop consuming scarce frontier slots while productive organizers remain available.
- **Evidence**: the snapshot proves strong yield for Ripped Bodice (9), Pioneer Works (9), and Elsewhere (11), but seven August additions have no landed rows because the quick refresh never reached them. With no history, those states are indistinguishable.
- **Files**: add `scrapers/data/organizer_quality.json`; update `scrapers/sources/eventbrite.py` at fetch/parse time and the post-normalization pipeline where landed/deduplicated rows are known; consume the history in `scrapers/utils/platform_discovery.py`.
- **Minimum record**: stable organizer ID, provenance tier, attempted/fetch-success flags, raw rows, exclusion-clean rows, normalized landed rows, overlap rows, saves, hides, attended yes/no, last successful observation, and completed-observation count.
- **Selection rule**: explicit user-mentioned organizers first; then organizers with enough engagement samples; then clean landed yield; then a small probation lane. Never score a connection error or an unscheduled organizer as zero yield. Never auto-remove an explicit organizer.
- **Minimum-sample guard**: do not demote an inferred organizer until at least two successful full-scrape observations. Keep the record even when it rotates outside the active bounded frontier.
- **Risk**: medium. State updates must be atomic and normalization-aware, or duplicate-heavy fallback calendars such as Book Club Bar/Liz's could look falsely weak.

### S2: Fix explicit-user precedence in the existing Eventbrite frontier

- **Metric moved**: high-conviction source coverage.
- **Evidence**: discovered URL `https://www.eventbrite.com/o/st-mazie-5803675324` has `discovered_via: user_mentioned`, but receives score 6 and ranks 16th. Every curated inferred organizer receives score 8, so an explicit user request sits below seven untested inferences and is omitted by the quick organizer limit of 8.
- **File**: `scrapers/utils/platform_discovery.py` — use a provenance tier in the sort key rather than relying only on additive scores. `user_mentioned` should rank with curated explicit hosts regardless of whether it arrived through `discovered_urls.json` or `user_curated_sources.json`.
- **Tests**: explicit discovered organizer outranks inferred curated organizer; failed/unattempted organizers do not gain a negative observation; stable numeric organizer IDs collapse slug variants.
- **Risk**: low. This changes crawl priority, not event ranking or any hard filter. St. Mazie is already in the learned frontier, so this is not an unprobed source add.

### S3: Reserve organizer frontier capacity for measured probation

- **Metric moved**: active follow/taste coverage and organizer learning velocity.
- **Evidence**: fixed curated scores occupy nearly the entire quick frontier, while seven newly inferred organizers remained untested after the August refresh. A quality ledger cannot learn if every slot is permanently held by incumbents.
- **Files**: `scrapers/utils/platform_discovery.py` / `scrapers/sources/eventbrite.py` — partition the bounded organizer budget into explicit, learned, and probation lanes. Suggested starting bound: quick `4 explicit + 3 learned + 1 probation`; full `all explicit + learned leaders + at least 3 probation`, within the existing total limits.
- **Guardrails**: probation still requires the existing >=5 clean event and >=80% clean-calendar gate before persistence; `floor_bypass` remains false for inferred organizers; network failures do not consume the two-observation probation count.
- **Risk**: low-medium. The lane split needs tests showing explicit organizers cannot be displaced and exploration remains bounded.

### S4: Run one full scrape before adding another organizer cohort

- **Metric moved**: freshness plus evidence quality for fb-209.
- **Reason**: the deployed fallback is six days old, live probing is blocked in this worker environment, and seven existing additions have never had a full-scrape observation. Adding more hosts now would be speculative and would deepen the unmeasured queue.
- **Acceptance check**: the final feed is dated September 3, all explicit organizer URLs are attempted first, every attempt records success/failure separately, and the seven unobserved August organizers receive a fair full-run slot or an explicit scheduler reason.
- **Risk**: low; this is the required measurement pass, not a source removal.

## Account promotion / co-mention BFS

- Joined `account_quality.json` to `discovered_accounts.json`: zero unconfigured accounts meet `events_emitted >= 5` plus score `>= 0.45`.
- The newest score-qualified signal-account co-mentions include entity-shaped `paulacoopergallery`, `consuladobrnyc`, and `bamfilmbrooklyn`, but all have 0 scraped posts / 0 emitted events and date to May. They are candidates for a future successful IG audit, not promotion evidence.
- `cvall96` was dropped immediately as person-shaped under fb-106.
- No IG account addition is recommended while the session/network path cannot validate current public yield.

## High-yield URL audit

- 101 unlisted `url_health` rows meet `successes >= 3` and `last_event_count >= 5`.
- 61 are Eventbrite/Lu.ma/Partiful URLs now owned by dedicated bounded adapters; restoring them to `GENERIC_URLS` would duplicate requests and fragment quality state.
- The remaining 40 are dominated by generated comedy month pages, old AllEvents/Songkick pagination, broad US seasonal pages, short-link aliases, or calendars already covered by dedicated sources (Book Club Bar, Liz's, Green-Wood).
- No static URL promotion is justified. Stable organizer/calendar identities plus learned quality are the correct promotion unit.

## Probes that failed (do not treat as zero yield)

- Eventbrite: all 14 prior curated organizer URLs returned `ConnectError: All connection attempts failed`. A direct `curl` to Eventbrite failed at TCP connection as well.
- Lu.ma: `/nyc/run`, `/nyc/books`, `/nyc/brooklyn`, and `/nyc/clubs` all logged `fetch failed: All connection attempts failed`; the generic helper then returned an empty list. These are indeterminate probes, not four zero-yield results.
- Dead/control URLs: both `https://www.92ny.org/calendar` (historically dead) and `https://thebellhouseny.com/calendar/` (known productive) failed identically. This confirms environment blockage rather than a source-specific regression.
- DICE, Tixr, RA, Bandsintown, and Time Out were not re-probed, per the documented blocked list.

## Directives addressed

- **fb-209**: S1-S3 provide the concrete persistent quality model, precedence fix, and bounded probation mechanism needed for learned organizer selection.
- **fb-210 / fb-211 / fb-214**: S4 makes a current full scrape and verified September 3 feed an explicit release gate; rebuilding the August 28 data is not “fresh.”
- **fb-208 durable preference rule**: selection recommendations prioritize explicit/user-engaged provenance and measured clean landed yield, not raw organizer popularity. No AI, speed-dating, club/late-night, or personal-account source is proposed.

## Open questions for the Critic

- Approve S1-S3 as one fb-209 unit, or land S2's explicit-precedence bug fix immediately and stage the ledger separately?
- Should a successfully fetched inferred organizer with strong clean yield but 100% overlap remain in the active frontier as resilience, or move behind novel-yield organizers? Explicit-user fallbacks must remain protected either way.
- Is two successful full-scrape observations enough for probation, or should low-frequency literary/game organizers receive a longer three-observation window?
