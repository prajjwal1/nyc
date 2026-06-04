# Handoff — for the next agent

If you're picking this project up, **read this first.** It captures the
user's expressed preferences, the constraints that have already been
litigated, and the architectural decisions you should not silently
relitigate.

For the long-form session history see [`.claude/self-improve/SESSION_SUMMARY.md`](.claude/self-improve/SESSION_SUMMARY.md).
For the running journal + open feedback see [`.claude/self-improve/journal.md`](.claude/self-improve/journal.md)
and [`.claude/self-improve/feedback-backlog.md`](.claude/self-improve/feedback-backlog.md).

---

## North star

**Surface NYC events the user would actually attend.** The IG follow-graph
+ saves are the ground-truth signal. Iter 198 calibration confirmed
this: shown 3 high-conviction events from `@bookclubbar`, `@litclub.nyc`,
`@readingrhythms-manhattan` — user picked all 3.

Three operational proxies the loop optimizes for:

1. **Follow-graph coverage** — % of `signal_accounts` (in
   `scrapers/data/user_interest_profile.json`) with non-zero yield.
2. **Topic coverage** — every `topic_counts >= 2` topic has events in
   the feed (with `tech`/`ai`/`startup`/`founder` deliberately excluded
   — see preferences below).
3. **High-conviction ratio** — % of feed events with `userFollowing` /
   `userSaved` / `userAffinity` firing.

Sanity check logs all three on every CI run. Persisted to
`scrapers/data/stats_history.jsonl` for trend tracking.

---

## User preferences (durable, do not relitigate)

### Categories of events the user wants

- **Literary** — book clubs, reading rhythms, author events, lit
  salons. The calibrated top attend-target. `bookclubbar`, `lizsbookbar`,
  `litclub.nyc`, `readingrhythms`, `mcnallyjackson`, `centerforfiction`,
  `franklinparkreading`, `booksaremagic`, `greenlightbookstore`,
  `pioneerworks`, `caveatnyc`, `murmrr`, `catapult.story`.
- **Run clubs / fitness** — the user follows 5 run-club accounts. NYC
  sprints, Vital Run Club, Zoomies, Midnight Runners, etc.
- **Social / meeting-people events** — singles mixers, supper clubs,
  dinner-with-strangers (`timeleft`, `offlineclub`), phone-free social
  hours.
- **Outdoor / waterfront / picnic** events — rooftop, pier, park
  (when actually outdoors — see indoor-arena false-positive
  notes).
- **Comedy** (improv, stand-up, sketch — not nightclub-vibe), **art**
  (galleries, exhibitions, museum openings), **food** (tastings, supper
  clubs, NYC food crawls), **music** (live, concerts, jazz).

### Categories the user explicitly does NOT want

These all live in `scrapers/data/user_excluded_sources.json`:

- **Speed dating** (`title_hints`: `speed dating`, `speed-dating`) —
  iter 209. Also removed from `quality.SOCIAL_KEYWORDS` boost (iter 195).
- **Nightclubs / late-night DJ-marathon venues** — `houseofyesnyc`,
  `knockdowncenter` excluded as `accounts` + multiple `title_hints`
  for `rave`, `open to close`, `warehouse rave`, `underground rave`,
  `afterparty @`, `dj marathon`, `@ 99 scott`.
- **AI events** — `title_hints` cover `ai workflows`, `ai chatbots`,
  `ai live demo`, `abacus.ai`, `software book club` (an AI book club).
  Note: the user follows some AI-adjacent accounts (incidentally), so
  the "tech / ai / startup / founder" topic words live in the
  `_USERNAME_TOPIC_HINTS` de-boost zone in `scrapers/utils/interest_profile.py`,
  and are also filtered out of the North-Star topic-coverage metric.
- **Personal IG accounts** (fb-106) — `leahcanel`, `alvinzx`,
  `j_palmer_7`, `sophiareed5`. The user follows individuals on IG; we
  only want socializing/venue accounts. **fb-106 is enforced across 7
  layers**:
  1. `scrapers/config.py::IG_ACCOUNTS` — never seeded
  2. `scrapers/sources/instagram.py::_FOLLOWING_ACCOUNTS_CACHE` — subtracted
  3. `scrapers/sources/instagram.py::all_accounts` — hard-skipped before scrape
  4. `scrapers/utils/interest_profile.py::signal_accounts` — subtracted
  5. `scrapers/normalize.py::_enrich_provenance_from_url` — never tag userFollowing
  6. `scrapers/ranking.py::is_user_excluded` — drops event entirely
  7. `scrapers/run_all.py::_top_ig_accounts` — never recommended in topAccounts widget
- **B2B / professional networking** — career fairs, lawyer/consultant/
  finance mixers, founder summits, leadership development. All in
  `quality.HARD_BLOCK_KEYWORDS`.
- **Kids / family events** — storytime, playdates, caregivers. Hard-block.
- **Excessive-drinking culture** — open bar, all-you-can-drink, bar
  crawls. **Soft penalty** (not block) so events that mention drinks in
  passing aren't excluded but events that center on drinking get
  pushed down.
- **Reggaeton** — single hard-block entry. NB: `reggae` is still a music
  category keyword (reggaeton inherits music classification — the block
  drops the event after categorization, so no conflict).

### UI preferences (from this session)

- **No "Because you follow @X" text** on cards (too preachy). The sky ★
  glyph alone is the conviction signal.
- **No "For You" heading** ("I know it's for me"). Toggle relabeled
  `Feed` / `Calendar`.
- **No grid view** — uniform card layout only.
- **No left sidebar search/filter box** (search, categories, price,
  quick-filters meet-people / saved / free) — heroes in TopPicks
  already slice by time + signal in a more meaningful way.
- **No IG capture stats line** ("📲 40 from Instagram (32 from
  stories...)") in header.
- **No category chips on cards** — categories drive ranking internally
  but are visual noise on every card.
- **No raw ISO timestamps** in description text. `build_event` in
  `scrapers/utils/event_parser.py` scrubs `\d{4}-\d{2}-\d{2}T...` patterns
  out of description before emit.
- **IG events should not take 4-5x the vertical space** of other
  source events — uniform `FeedCard` sizing (no `MediaFirstCard`).

### What stays even though it might look like clutter

- **Five hero sections** (Tonight, This Weekend, Just Added, Following,
  Saved) with light colored tints — each is functionally distinct
  (time / freshness / signal). Don't merge.
- **Calendar view + per-day list** — the user wants both browsing modes.
- **The sky ★ glyph + colored card ring** for conviction events — kept
  as typography over prose.

---

## Architecture cheatsheet

### Scrapers

- **`scrapers/run_all.py`** — orchestrator. Async scrapers + IG (sync).
  Carryover from previous events.json for `instagram`, `eventbrite`,
  `songkick`, `meetup` so a single flaked CI run doesn't wipe the feed.
- **`scrapers/sources/`** — 21 scrapers. Add new sources here. Each
  emits events with a `source` field. The dedicated scrapers
  (`bookclubbar.py`, `lizsbookbar.py`, `mcnallyjackson.py`, etc.) use
  bookmanager / squarespace eventlist patterns. `generic.py` covers
  JSON-LD via `GENERIC_URLS`.
- **`scrapers/sources/instagram.py`** — biggest. IG_ACCOUNTS list +
  user_following discovery + hashtag mining + saved/tagged posts.
  Needs IG session (`~/.config/instaloader/session-prajfb`) refreshed
  every ~28 days. CI uses `IG_SESSION_B64` GitHub secret.
- **`scrapers/normalize.py::process(events)`** — the pipeline:
  dedup → categorize → filter (hard-blocks, kids, etc.) → enrich
  provenance (URL handle / organizer / location-name match for
  `userFollowing`) → re-categorize → strip outdoor false-positives
  → rank → drop-below-score-floor.
- **`scrapers/quality.py`** — `HARD_BLOCK_KEYWORDS`, `SOFT_PENALTY_KEYWORDS`,
  `SOCIAL_KEYWORDS` (ranking boost), `HIGH_VALUE_KEYWORDS` (ranking
  boost), `_is_caption_fragment`, `_title_quality`.
- **`scrapers/ranking.py`** — `compute_score`, `is_user_excluded`
  (multi-path: account, location.name substring, host, title_hints),
  `_user_curated_boost`, `_user_excluded_penalty`.
- **`scrapers/sanity_check.py`** — runs after every CI scrape.
  Critical/warning checks + IG diagnostics + North-Star metrics.

### Site

- **`site/app/page.tsx`** — main page. Feed/Calendar toggle.
- **`site/app/components/TopPicks.tsx`** — Feed view. Hero sections
  (Tonight, Weekend, Just Added, Following, Saved) + date-grouped list.
- **`site/app/components/EventCard.tsx`** — `FeedCard` + `CompactCard`.
  `MediaFirstCard` + `GridCard` were removed iter 215.
- **`site/app/components/EventModal.tsx`** — event detail.
- **`site/app/components/Calendar.tsx`** — month grid (Calendar view).
- **`site/app/lib/interests.ts`** — localStorage `:v1` keys
  (`nyc-events:saved:v1`, `:hidden:v1`, `:attended:v1`,
  `:profile:v1`). All personalization is client-side.

### Data files

- `scrapers/data/user_interest_profile.json` — auto-built from
  `discovered_accounts.json` + `account_quality.json` +
  `user_curated_sources.json` + `user_excluded_sources.json`. Contains
  `signal_accounts`, `topic_counts`, `yield_map`.
- `scrapers/data/user_curated_sources.json` — hosts + title_hints
  that boost ranking (read by `ranking._user_curated_boost`).
  **Add literary venues here** when found.
- `scrapers/data/user_excluded_sources.json` — accounts + hosts +
  title_hints that DROP events (read by `ranking.is_user_excluded`).
  **Add user-rejected venues / preferences here** with reason.
- `scrapers/data/account_quality.json` — lifetime IG account stats
  (posts_scraped, events_emitted). Drives ranking yield-boost.
  Read keyed by both `handle` and alphanumeric-fold variant
  (`reading_rhythms` AND `readingrhythms`).
- `scrapers/data/dead_accounts.json` — IG accounts that hit
  repeated_failure. Transient failures (`feedback_required`, 429,
  5xx, connection, timeout, ssl) auto-revived per
  `_TRANSIENT_FAILURE_MARKERS`.

---

## CI / deploy

- **`.github/workflows/scrape.yml`** — full 50-min sweep every 4h
  (incl. IG hashtag mining).
- **`.github/workflows/quick-scrape.yml`** — 5-10 min cron every 30
  min (skips IG full account-sweep, only saved posts).
- **`.github/workflows/scrape-priority.yml`** — hourly priority IG
  scrape (only `_FOLLOWING_ACCOUNTS_CACHE` accounts).
- **`.github/workflows/freshness-monitor.yml`** — every 15 min,
  dispatches `quick-scrape` if `events.json` is >90 min stale.
- **`.github/workflows/deploy.yml`** — Pages deploy. Triggers on
  push to `main` with paths `site/**` or `data/events.json`. Hourly
  cron at :10 also rebuilds (because GitHub Actions skips workflow
  triggers from GITHUB_TOKEN commits — the scrape bot's pushes
  wouldn't otherwise re-deploy the site).
- **Deployed URL**: `https://prajjwal1.github.io/nyc/` —
  `events.json` at `https://prajjwal1.github.io/nyc/events.json`.

---

## Patterns / lessons that paid off

1. **Cross-file drift audits**. When changing a keyword, search EVERY
   list using that keyword across files (iter 195: same bare `social`
   was in two parallel lists). Same for indoor-arena lists, transient-
   failure markers.
2. **Substring-FP testing**. Bare keywords substring-match too much.
   Use `' word '` (leading + trailing space) when the word is common
   (`' park'` matched `' parking'` — iter 184; `'rowing'` matched
   `'throwing'` — iter 197).
3. **Real-data QA on deployed feed**. Fetch
   `https://prajjwal1.github.io/nyc/events.json`, audit for leaks
   (excluded venues, fragment titles, OCR garbage). Iter 211-213 found
   3 real leaks this way.
4. **Calibration-driven action**. Ask the user about 3 high-conviction
   events; let their answer drive ranking-weight tuning (iter 198 →
   iter 200 books boost 1.15→1.3, iter 206 bookclubbar/lizsbookbar
   added to curated hosts).
5. **Carryover for flaky CI sources**. `CARRYOVER_SOURCES = {instagram,
   eventbrite, songkick, meetup}` — these have anti-bot blocking on
   GHActions runner IPs. Carry from previous events.json so a single
   flake doesn't wipe the section. `filter_future` ages out naturally.
6. **Atomic writes**. `events.json` writes use `tmp + os.replace`. Same
   for `discovered_urls.json`, `url_health.json`, etc. Never leave
   partial state.
7. **`is_user_excluded` checks 4 paths**: instagramAccount, location.name
   (alphanumeric-fold + suffix-strip + substring for ≥8-char accounts —
   iter 211), sourceUrl host, title+description text.

---

## How to operate this thing

- **One-off URL audit**: `python -m scrapers.maintenance.audit_urls`
- **Purge stale IG dead-accounts**: `PURGE=1 python -m scrapers.maintenance.clean_dead_accounts`
- **Probe Lu.ma curators for new URLs**: `python -m scrapers.maintenance.probe_luma_curators`
- **Self-improving cycle**: `/self-improve` in Claude Code
- **Build site locally**: `cd site && npm run build`
- **Sanity check**: `python -m scrapers.sanity_check`
- **QA against deployed**: `curl -sS -o /tmp/d.json https://prajjwal1.github.io/nyc/events.json && python -c "..."`

## Things blocked on user action

- **IG session refresh** — `instaloader --login prajfb` locally,
  base64-encode the session file, paste into `IG_SESSION_B64` GitHub
  secret. Refresh every ~25-28 days. Sanity check warns when stale.
- **fb-104** — prune `/nyc/<topic>` Lu.ma URLs (60 of them — iter 67
  confirmed all return same content as `/nyc`). Gated on explicit opt-in.
- **fb-139** — Set up Reddit PRAW OAuth for the `.json` API path.
- **fb-158** — 41 EMPTY URLs in `GENERIC_URLS` (JS-rendered venue
  sites). Documented as known-blocked.

---

*Last updated: iter 215, 2026-06-04. ~215 commits on
`agent-source-expansion`, all merged to main. Top of feed: literary
events at bookclubbar / litclub.nyc / readingrhythms (calibration-
validated 3/3).*
