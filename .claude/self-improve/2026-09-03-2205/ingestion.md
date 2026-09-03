# Ingestion Quality Report — 2026-09-03 2205

## Executive finding

The binding problem is freshness, not a shortage of scraper ideas. `data/events.json` and `site/public/events.json` are byte-identical, but both stop at `2026-08-28T18:04:42.140021+00:00`. The latest repository data commit is also August 28 (`2d0b8f70`), even though quick scrape, platform refresh, priority IG, full scrape, deploy, and freshness-monitor schedules should all have run repeatedly since then. The watchdog shares the same GitHub Actions scheduling failure domain as the producers, so it cannot recover a scheduler-wide outage.

GitHub Actions and the public Pages URL were unreachable from this worker environment, so the exact external cause and current public payload could not be verified. Do not close fb-211/fb-214 until a successful workflow run and the deployed timestamp are observed externally.

## Metrics observed

- Feed: 556 total events; 357 dated September 3 or later; **199 already past**. Snapshot age was 148.1 hours when audited.
- Follow-graph coverage: 50/50 lifetime yield. There are no lifetime zero-yield `signal_accounts` to repair.
- Active upcoming follow coverage: **4/50 (8.0%)** in the September-3+ slice: `nyc_forfree`, `explorenycfree`, `reading_rhythms`, and `bookclubbar`. `sanity_check` reports 6/50 because its “active” calculation at `scrapers/sanity_check.py:520-527` includes the 199 past rows; that metric is misleading precisely when the feed is stale.
- Topic coverage: 4/4 meaningful topics under the repository metric (`club`, `run`, `book`, `read`). Location tokens are excluded; `ai` is correctly excluded because it conflicts with the user's explicit negative preference.
- High-conviction ratio: 90/556 (16.2%); upcoming-only 62/357 (17.4%).
- Upcoming source depth: Luma 43, Partiful 41, Eventbrite 40, Songkick 31, AllEvents 28, Brooklyn Comedy 27, Book Club Bar 27, NYC for Free 22, Powerhouse Arena 19, Bell House 16, NY Comedy Club 14, Dice 13, Liz's Book Bar 13, Eastville Comedy 11, Brooklyn Contra 5, Instagram 4, Green-Wood 2, Substack 1.
- Eventbrite organizer attribution: 32/40 upcoming rows have a stable organizer ID; **8/40 (20%) do not**. Ten rows lack an organizer display name. None of the 40 upcoming Eventbrite rows currently carries `userFollowing`, `userSaved`, or `userAffinity`.
- Liz's Book Bar remains healthy in the stale snapshot: 13 upcoming dedicated-source rows, and 9 retain organizer ID `83466825333` through dedup; all 9 are cross-source overlaps.

## Live/local quality audit

The local feed was used as the public fallback because both GitHub API and Pages network access failed in this environment.

- Late-night leak regex (`\b[1-5]\s*am\b|\bnightclub\b|\bafter ?hours?\b`): 0 matches.
- Professional-networking regex: 0 matches.
- Exact normalized title+date duplicates: 0.
- Dates after 2026: 0.
- User-excluded/blocked rows: 0 under current filters.
- Caption/narrative title scan: one confirmed leak, `September 5 through 27` (Substack). The source parser now rejects this form, but a carried-over row bypasses that extraction-time-only fix.
- Deterministic platform samples had complete dates/times. Luma had 43/43 empty descriptions but complete location/image/organizer data, consistent with the catalog shell exception. Partiful had 14/41 missing venue names and 25/41 missing organizer names. Eventbrite had 29/40 empty descriptions but complete images/locations; organizer identity is the more important gap. The sole Substack row has no location or organizer and a date-range title.
- Current sanity check: 0 critical failures, 3 warnings (Instagram volume 7, Brooklyn Museum 0, art openings 0). The local IG session is missing, but the six-day system-wide workflow gap is broader than the known IG constraint.

## Proposals

### P1: Restore a genuinely current feed before shipping the redesign

- **Metric moved**: follow-graph coverage (active upcoming), topic coverage, and high-conviction ratio; all three are currently measured on an obsolete inventory.
- **Files / operational targets**: `.github/workflows/scrape.yml:48-113`, `.github/workflows/platform-refresh.yml:29-73`, `.github/workflows/quick-scrape.yml:49-96`, `.github/workflows/deploy.yml:38-100`, `.github/workflows/freshness-monitor.yml:25-104`.
- **Change / action**:
  1. Manually dispatch the full scrape, then the platform refresh and quick Eventbrite/Substack refresh if their source lanes did not complete successfully.
  2. Require a new data commit whose feed contains only today-onwards rows and whose `lastUpdated` is September 3 or later.
  3. Run `python -m scrapers.sanity_check`, the approved regression suite, and the production build; only then dispatch deploy.
  4. Verify the public `events.json` timestamp is at least the repository timestamp, using the existing deploy check.
  5. Do not accept a timestamp-only rewrite: inspect source counts and run logs so a carryover-only run is not mislabeled as fresh.
- **Test / acceptance**: repository and public timestamps match; zero past rows; `ingestionStats.run.runCompleted == true`; no critical sanity failures; Luma/Partiful catalog checks pass; Eventbrite has a nonzero fresh result or an explicitly documented platform failure; final deployed SHA matches the release commit.
- **Expected impact**: immediately removes 199 past rows and establishes the real September active-follow and conviction baselines. A direction or size should not be claimed before the scrape lands.
- **Risk**: medium operational risk. GitHub-hosted IP blocking can yield a superficially successful carryover-heavy run. The scheduled freshness monitor cannot diagnose a scheduler-wide outage because it depends on the same scheduler.

### P2: Persist bounded Eventbrite organizer quality and use evidence-based probation (fb-209)

- **Metric moved**: high-conviction ratio, by spending bounded organizer capacity on explicit or demonstrated-taste calendars instead of anonymous volume; also improves useful topic depth without expanding raw source count.
- **Files**: add `scrapers/utils/organizer_quality.py` and `scrapers/data/organizer_quality.json`; instrument `scrapers/sources/eventbrite.py:119-208`; update after normalization in `scrapers/run_all.py:284-314`; consume the state in `scrapers/utils/platform_discovery.py:240-338`; persist the state in `.github/workflows/scrape.yml:73-104` and `.github/workflows/quick-scrape.yml:61-89`.
- **Change**:
  - Key records by canonical numeric Eventbrite organizer ID. Store at most the last 8 **successful** observations: `{observedAt, raw, exclusionClean, landed, overlap}` plus `failedAttempts` and `lastSeenAt`. A network error or an organizer not scheduled in that run must never become a zero-yield observation.
  - After `process()`, compute `landed` from `organizerRefs`; compute `overlap` when `contributingSources` contains Eventbrite plus another source. This correctly credits Liz's and Book Club Bar even when their dedicated source wins dedup.
  - Extend the existing browser taste export at `site/app/lib/tasteExport.ts:10-68` with organizer-ID counters derived from `SavedEventStub.organizerUrl` (`site/app/lib/interests.ts:345-378`): saves, hides, attended yes, attended no. Do not use the generic `eventbrite.com` host because `scrapers/utils/engagement.py:45-51` correctly treats it as too broad.
  - Rank organizer tiers in this order: explicit `user_mentioned`; reliable organizer engagement (minimum 3 actions, smoothed positive rate); proven clean landed yield; bounded probation. An inferred organizer remains probationary until 3 successful observations, keeps the normal floor, and can rotate out of the active crawl without being deleted from configuration. Explicit organizers are never automatically removed or demoted.
  - Suggested initial lane bound within existing limits: quick = 4 explicit + 3 learned/proven + 1 rotating probation; full = all explicit + learned leaders + at least 3 probation slots.
- **Tests**:
  - New `scrapers/tests/test_organizer_quality.py`: history caps at 8; failed fetches do not add zero observations; raw/clean/landed/overlap counts are distinct; a Liz event whose winning source is `lizsbookbar` still records Eventbrite overlap via organizer ID `83466825333`; engagement counts are reversible/idempotent.
  - `scrapers/tests/test_platform_discovery.py:59-87`: explicit user-mentioned organizers always outrank high-volume inferred organizers; inferred organizers need 3 successful samples before graduating; weak inferred organizers rotate rather than being deleted; explicit organizers survive weak/no observations.
- **Expected impact**: converts the current unmeasured organizer list into an adaptive bounded frontier. In the present snapshot, Ripped Bodice (8 upcoming), Pioneer Works (8), and Elsewhere (6) provide initial landed evidence, while seven August additions with zero rows remain “unobserved,” not falsely “bad.”
- **Risk**: medium. Counting carryover as a fresh observation would permanently bias the ledger; only successful current-run organizer fetches may append observations. Overlap-heavy explicit fallbacks must not be punished as useless.

### P3: Fix explicit-user precedence before organizer learning is enabled

- **Metric moved**: high-conviction ratio and taste-aligned source coverage.
- **File**: `scrapers/utils/platform_discovery.py:247-263`, `295-313`, and `335-338`; test at `scrapers/tests/test_platform_discovery.py:59-87`.
- **Change**: add an explicit provenance tier to the aggregate/sort key. A discovered organizer marked `user_mentioned` must share the highest tier with a curated `user_mentioned` host, ahead of every inferred or agent-vetted organizer, regardless of additive raw-yield score.
- **Evidence**: the current frontier ranks user-mentioned St. Mazie organizer `5803675324` **16th with score 6**, below inferred curated hosts with score 8; quick mode fetches only 8 organizers (`scrapers/sources/eventbrite.py:126-129`). Thus a direct user signal is currently omitted while unobserved inference consumes the crawl budget.
- **Tests**: explicit discovered organizer outranks inferred curated organizer; slugged/numeric URLs collapse to one ID; prior raw event volume cannot displace an explicit organizer.
- **Expected impact**: makes organizer discovery obey fb-208 immediately, before enough quality history exists to rank inferred calendars reliably.
- **Risk**: low. This changes fetch priority only; normalization, hard blocks, exclusions, and score floors remain unchanged.

### P4: Complete organizer identity before scoring organizer quality

- **Metric moved**: high-conviction ratio, by making organizer-level saves/hides/attendance attributable instead of falling back to generic Eventbrite.
- **File**: `scrapers/sources/eventbrite.py:306-340` (`_hydrate_shortlist`) and parser merge at `scrapers/sources/eventbrite.py:500-522`; tests in `scrapers/tests/test_platform_discovery.py:126-199`.
- **Change**: treat a missing canonical organizer ID—not merely a missing organizer display name—as a hydration need. Within the existing full-run detail limit, prioritize personal rows first, then organizer-ID-missing explore rows by taste/score. Keep quick mode bounded; do not raise the global request budget until timing is measured.
- **Evidence**: 8/40 upcoming Eventbrite rows have no stable organizer ID, including three `Elsewhere Presents` rows and `Everyday People NYC @ Elsewhere`; 10/40 lack the display name. Those rows cannot contribute reliable organizer raw/landed/engagement evidence.
- **Tests**: an explore-lane event missing `organizerUrl` is selected for hydration; a row with only a name but no numeric ID is selected; a complete organizer row is skipped; hydration merges `organizerUrl` and `organizerRefs` without overwriting better event fields.
- **Expected impact**: target organizer attribution rises from 80% toward 100% on Eventbrite rows, preventing fb-209 from learning from a biased denominator.
- **Risk**: low-medium. Detail calls can encounter Eventbrite rate limits, so preserve the existing cap and organizer-first crawl order.

### P5: Apply date-range-title rejection during normalization, not only fresh Substack extraction

- **Metric moved**: topic coverage quality (removes a non-event without reducing a real topic) and high-conviction precision.
- **File**: `scrapers/quality.py:2323-2347`; regression test beside `scrapers/tests/test_substack.py:32-34` or in `scrapers/tests/test_quality.py`.
- **Change**: extend the generic pure-date title check to reject exact month-day ranges such as `September 5 through 27`, including `to`, hyphen, en dash, and em dash forms. Keep it anchored to the whole title so `A Festival Running September 5 through 27` remains valid.
- **Example title this excludes**: `September 5 through 27` — the only match across all 556 local titles. The existing source-level test already proves the intended valid control.
- **Expected impact**: removes the single confirmed caption/date fragment and prevents extraction-time fixes from being defeated by source carryover.
- **Risk**: low; the tested anchored pattern matched exactly one current title and no legitimate title.

## Measurement correction

`scrapers/sanity_check.py:520-527` should skip rows with `date < today` before labeling an account “active.” On this stale file it reports 6/50, while the actual upcoming slice is 4/50. Add a regression containing one past followed event and one future followed event; only the future account should count. This does not improve inventory, but prevents a stale feed from overstating the North Star.

## Directives addressed

- **fb-210 / fb-211 / fb-214**: P1 defines the non-negotiable fresh scrape, validation, build, deploy, and public timestamp verification. This worker cannot claim completion because GitHub/public network access is blocked and no September data commit exists locally.
- **fb-213 / fb-209**: P2-P4 provide the bounded persisted organizer-quality model, minimum-sample probation, explicit-user precedence, attribution prerequisites, and tests required by the acceptance criterion.
- **fb-208**: P2-P3 rank demonstrated user preference ahead of generic popularity/raw calendar size and preserve all explicit exclusions.
- **fb-212**: deferred to the UI worker; ingestion's release gate is that approved UI changes must be built and deployed only with a fresh feed.

## Verification performed

- `python3 -m scrapers.sanity_check`: 0 critical failures; freshness 148.1h; 3 warnings.
- `PYTHONPATH=. ./venv/bin/pytest -q scrapers/tests/test_platform_discovery.py scrapers/tests/test_substack.py`: 29 passed.
- Local feed copies have identical SHA-1 (`0924085a4eeed18faad3d844727247c0aca80219`).
- Public feed and Actions history could not be fetched from this environment (`curl` connection failure; GitHub API network denied).

## Open questions for the Critic

- Approve three successful organizer observations as the probation threshold, or use two to learn faster at the cost of more volatility?
- Should an inferred organizer with high clean yield but 100% cross-source overlap rotate behind novel-yield organizers? Explicit-user fallbacks such as Liz's must remain protected either way.
- The producer crons and their scheduled watchdog stopped together. Is an external heartbeat/alert service authorized, or should the repository rely on manual dispatch plus the existing in-Actions monitor?
