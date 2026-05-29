# Session Summary — agent-source-expansion branch

This is a snapshot of what shipped across the 100+ iterations in this session, in case you want to review before merging to `main`.

## TL;DR

- **~120 commits**, all on `agent-source-expansion` (no push to remote done)
- **NO PRODUCTION DEPLOY** — feature branch only
- Build clean (`next build`), sanity_check exit=0 throughout
- **Bottleneck unchanged**: IG session is expired (~28 days old). Until refreshed, CI scrapes won't capture new IG events. Everything else is ready to flow once that's fixed.

## What you'd need to do to ship

1. Refresh IG session locally:
   ```
   instaloader --login prajfb
   base64 < ~/.config/instaloader/session-prajfb | pbcopy
   ```
   Paste into the `IG_SESSION_B64` GitHub secret.

2. Merge to main (or just `git push --set-upstream origin agent-source-expansion` if you want to review on GitHub first).

3. The next CI scrape will pick up everything.

## Headline metric expectations (post next-CI-scrape)

| Metric | Iter-1 baseline | Expected after merge + scrape |
|---|---|---|
| Follow-graph coverage | 12/54 (22.2%) | ~80%+ (iter 1 P1 revives 54 transient-killed) |
| `bk` topic events | 2 | ~14+ (iter 1 P6 synonym fold + S1 Brooklyn URLs) |
| High-conviction ratio | 3.3% | ~15% (iter 73-109 cross-source enrichment) |
| Music events | 18 | ~150 (iter 88 Songkick 6× pagination) |
| Brooklyn events | 14 | ~200 (iter 89 AllEvents time-windows + iter 108 venues) |
| Comedy events | 8 | ~25 (iter 91 dynamic month URLs) |
| Free events | 8 | ~80 (iter 100 nycforfree revival) |

## What shipped

### Backend — source pool

Cumulative yield lifts:
| Source | Was | Now (live yield) | How |
|---|---|---|---|
| Songkick | 49 | 306 | iter 88: `?page=N` pagination fix |
| AllEvents | ~65 | 353 | iter 89: time-window paths (`/today`, `/upcoming`, `/all`) |
| Eventbrite | 111 | top-100 of 300 | iter 90: pagination + 100-event cap |
| Comedy clubs | 8 | top-25 of 235 | iter 91: dynamic `/calendar/YYYY-MM` URLs |
| Partiful | 1 | 8 | iter 85: image-field rename fix |
| Substack | 1 | +33 venues, -13 noise | iter 86 venue parsing, iter 87 affiliate filter |
| Eater NY | 0 | 8 | iter 96: Atom feed support |
| nycforfree | 0 | 83 | iter 100: Squarespace eventlist rewrite |
| DICE | 0 | 25 | iter 101: `__NEXT_DATA__` extraction |
| Parks | mis-doc'd | 22 | iter 99: was already working |
| McNally Jackson | 3 | 44 | iter 102: month-pagination |
| Green-Wood | 0 | 10 | iter 103: URL update |
| **New scrapers added** | | | |
| Smorgasburg | n/a | 16 (recurring) | iter 106: synthesized from known schedule |
| Pioneer Works (via EB) | n/a | 17 | iter 110 |
| Verified-working Eventbrite venue slugs | n/a | 4 venues × ~20 | iter 113 (after iter 107-108 false positives backed out) |

### Backend — enrichment (the follow-graph signal)

4 active paths feeding `userFollowing` (sky ribbon + 👤 Following hero):
1. **Lu.ma URL handle** (iter 73): `lu.ma/litclub.nyc` → `litclub.nyc` IG handle
2. **Venue-domain hostname** (iter 74): `bookclubbar.com` → `bookclubbar` IG handle
3. **JSON-LD organizer name** (iter 77): `"Vital Run Club"` → `vitalrunclub`
4. **Location name** (iter 109): `"Greenpoint Comedy Club"` → `greenpointcomedyclub`

Cumulative effect on deployed feed: **0 → 29 cross-source userFollowing events** before next scrape.

### Backend — quality

Filters added across the session:
- IG-Stories glued-handle leak (iter 81): caught the `Ggretavanfleet` event scoring 1.00
- Categorizer FPs: `premiere` → movies, `meet & greet` → celebrities (iter 82)
- `[private event` (iter 93), `canceled:`/`cancelled:` (iter 99), `playdate`+`caregivers` (iter 92)
- `bar crawl`/`pub crawl` soft-penalty (iter 69)
- AWS/cloud meetup hard-block (iter 69): "Amazon Quick", "AWS meetup", etc.
- B2B coaching hard-block (iter 69): `career reset`, `supercharge your startup`
- GED substring FP fixed (iter 85): `ged ` was matching "collaged", "encouraged"

### UI threads (`site/app/`)

7 threads, all themed sky/amber/emerald:
1. **iter 71**: "Did you go?" prompt in EventModal — calibration signal
2. **iter 75**: visible ✓ went badge on past cards
3. **iter 78**: 👤 Following hero in TopPicks
4. **iter 95**: aggregate attended counter in subhead
5. **iter 104**: `?account=X` URL state — shareable account-filter views
6. **iter 105**: Header staleness color cue (gray/amber/rose + tooltip)
7. **iter 122**: Following hero now also includes `userAffinity` events

Build clean (`next build` succeeds) on every UI commit.

### Self-correction iterations

The "ship, then verify" loop caught my own mistakes:
- **iter 111**: backed out iter 107's HoY + KDC additions (user-excluded in `user_excluded_sources.json` — I should have checked first). Also extended `is_user_excluded` to match `location.name`.
- **iter 113**: pruned 11 noise venue-search URLs from iter 108 — discovered Eventbrite venue-search is keyword-search, not strict venue-match (`comedy-cellar` returned "Whiskey Cellar", "Oak Cellar", "Grove 34"). Only 4 unique-slug venues kept.

### Infrastructure

- iter 79: cleaned 54 transient-killed IG accounts from `dead_accounts.json`
- iter 115: `audit_urls.py` maintenance script — classifies HEALTHY/WARN/STALE/EMPTY/ERROR/HARVEST
- iter 123: enhanced audit script with URL-harvest classification (saved onefinedaynyc.substack from incorrect STALE removal)
- iter 116-118, 120, 124: cleaned ~38 dead URLs across multiple rounds
- iter 125: SOURCE_LABELS for new sources
- iter 126: SOURCE_VOLUME_CAPS for nycforfree + mcnallyjackson (40, 30)
- iter 127: workflow git-add fix — `image_hashes.json` + `user_interest_profile.json` were generated but not committed (state was wiped each CI run)
- iter 128: **shipped 3 untracked scrapers (`brooklyncomedy.py`, `centerforfiction.py`, `powerhousearena.py`) that `run_all.py` has been importing since iter 106**. They existed locally but were never `git add`ed. Merging this branch *before* iter 128 would have crashed CI at module import. Smoke-tested: brooklyncomedy 119 events, powerhousearena 11, centerforfiction 0 (403, graceful)
- iter 129-130: sanity_check de-noised — dropped HoY/KDC phantom warnings (user-excluded), filtered excluded accounts from "Silenced high-yield" diagnostic
- iter 131: **fb-106 hard-enforce** — 4 personal IG accts (leahcanel, alvinzx, j_palmer_7, sophiareed5) added to `user_excluded_sources.json::accounts`. `signal_accounts` went 54 → 50.
- iter 132: normalize() re-derives categories every run. Stops stale categorizations (e.g. book clubs tagged "fitness" from cross-promo blurbs) from lingering. Local: fitness false-positives 13 → 7.
- iter 133: source-topic hints for brooklyncomedy/powerhousearena/centerforfiction (default category fallback for cryptic titles)
- iter 134: `normalize._enrich_provenance_from_url` respects excluded accounts — closes loophole where Eventbrite organizer="Leah Canel" could still bestow userFollowing boost
- iter 135-136: **North-Star metrics in `sanity_check`** every run logs follow-graph coverage / topic coverage / high-conviction ratio. De-boost topics (ai/tech/startup/founder) excluded from coverage counting.
- iter 137: `instagram._FOLLOWING_ACCOUNTS_CACHE` filters excluded — completes the fb-106 chain. Personal accounts no longer get tier-1 protected priority in the hourly priority cron, and won't receive `userFollowing=True` boost on emitted posts.
- iter 138-150: persistence + diagnostics + small cleanups. North-Star metrics now persist to `stats_history.jsonl` (iter 139). IG sweep hard-skips excluded accounts (iter 140 — full account-list filter, not just demotion). Quality scores + labels added for new sources (143-145, 155-156, 160). Source regressions diagnostic in sanity_check flags any source that drops to 0 events vs prior run baseline (iter 150).
- iter 151-158: pipeline ordering + defense-in-depth. Re-categorize now runs AFTER enrichment so categorize fallback can see the enriched `account` field (iter 151). Union IG-account topic hints when title cats are venue-only (iter 152) — "Read on the Lawn" from @reading_rhythms gets [books, outdoors] not just [outdoors]. Stats history rotates at 5000 records (iter 153). Network/5xx markers added to transient-failure list (iter 154). 7-layer fb-106 enforcement chain (account-list → cache → signal_accounts → enrichment → ranking → topAccounts → discover harvest). 4 `_load_user_excluded_*` helpers consolidated into `utils/user_excluded.py` (iter 158).
- iter 159-169: drift audit pass on config maps. Removed unused `_is_dead_url`. Fixed `SOURCE_QUALITY` keys that didn't match `_domain_source` output (iter 163: `'92ny.org'` → `'92ny'`, `'elsewhere'` → `'elsewherebrooklyn'`). Added `green-wood` → `greenwoodcemetery` alias (iter 162) so new Green-Wood events match existing config. Strip-outdoors-indoor-arena pass moved after re-categorize (iter 166). `_OUTDOORS_INDOOR_ARENAS` and `_OUTDOORS_STRONG_SIGNALS` deduped between normalize.py and event_parser.py (167-168). `_COMEDY_LINEUP_SOURCES` cleaned of 3 dead IG-handle entries and added `brooklyncomedy` (iter 169).
- iter 170-180: **categorizer coverage audit** — the biggest single quality lift this session. ~50 missing event-phrasing patterns added across 9 categories (music, comedy, books, singles, outdoors, food, art, parties, fitness/games/dance) — each FP-checked. Examples: "Birthday Bash" → parties, "Bagel Crawl" → food, "Catan Night" → games, "Walking Tour" → outdoors, "Magic Tournament" → games (180). Plus `'fidi'` neighborhood key was missing from its own value list (179).

### Knowledge consolidation

- iter 112: baked lessons from iter 83-111 into the iter-1 self-improve agent prompts. Source-curator and ingestion-quality must now check `user_excluded_sources.json` before any add proposal. Dreamer-critic has a new "silent-failure watch" cross-check.
- iter 119: updated README §64 "tried and blocked" with current state (DICE works via `__NEXT_DATA__`, Atom feeds work, Eventbrite venue-search caveats documented).

## Open items (backlog state)

Truly open:
- **fb-100**: Run calibration ask next time `/self-improve` runs interactively
- **fb-104**: Prune `/nyc/<topic>` Lu.ma URLs (gated on explicit user opt-in; iter 67 confirmed all 60 return same content as `/nyc`)
- **fb-139**: Set up Reddit OAuth (PRAW) — Reddit `.json` API now requires it
- **fb-158**: 41 EMPTY URLs in `GENERIC_URLS` — most are JS-rendered venue own-sites (Met, MoMA, Lincoln Center, etc.). Documented as known-blocked.

## How to operate from here

- For **one-off URL audit**: `python -m scrapers.maintenance.audit_urls`
- For **purging stale IG dead-accounts**: `PURGE=1 python -m scrapers.maintenance.clean_dead_accounts`
- For **probing Lu.ma curators for new URLs**: `python -m scrapers.maintenance.probe_luma_curators`
- For **self-improving cycle**: `/self-improve` from inside Claude Code (the agent prompts now know everything from iter 83-111)
