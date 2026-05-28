# Feedback Backlog

Durable, structured log of every piece of user feedback (explicit or inferred). **No item silently drops.** The Feedback Collector reads this first; workers must address the top 3 `open` items or the Critic must approve a deferral.

Each entry has:
- `id` — short stable identifier (`fb-NNN`)
- `created_at` — ISO date
- `source` — `user-explicit` / `user-inferred` / `agent-proposal`
- `status` — `open` / `in-progress` / `addressed: <sha>` / `wont-do: <reason>`
- `body` — the feedback itself
- `resolution` — set when status becomes `addressed` or `wont-do`

Items at the top are highest priority. Re-rank when adding new items.

---

## Seeded from README.md §480–533 (user feedback log)

These are the durable preferences the user has stated. They're marked `addressed: README` because they're already enforced in the codebase (see referenced filters); future agents must not regress them.

### fb-001 — Exclude nightclub events
- created_at: seeded
- source: user-explicit
- status: addressed: README (enforced in `scrapers/quality.py::HARD_BLOCK_KEYWORDS`)
- body: No `nightclub`, `bottle service`, `vip table/booth/section`, `table service`, `bottle minimum`.
- resolution: Keep these in HARD_BLOCK_KEYWORDS. If any leak, fix immediately.

### fb-002 — Exclude late-night-only events (past midnight)
- created_at: seeded
- source: user-explicit
- status: addressed: README (enforced via `_likely_past_midnight` in `scrapers/normalize.py` + HARD_BLOCK list)
- body: Anything running past midnight: `after hours`, `till 4am`, `until 5am`, `all night long`. Plus startTime ≥ 23:00 / endTime 00:00–04:59 / "1am-5am" text.
- resolution: Audit Ingestion runs for leaks; tighten filter if any 1am/2am text slips through.

### fb-003 — Exclude language mixers, reggaeton, professional networking
- created_at: seeded
- source: user-explicit
- status: addressed: README
- body: Blocked: `language mixer`, `language exchange`, `internationals and language mixer`, reggaeton genre, `professional networking/mixer`, `finance networking/mixer`, `business networking/mixer`, `wall street`, `executive networking`, `career`, `industry`, `corporate`, `investor`, `founders mixer`, `real estate`, `lawyer`, `consulting`, `banking`, `linkedin`, `b2b`, `sales`. Tech mixer is OK.
- resolution: Watch for new variations leaking through and add patterns.

### fb-004 — Soft-penalize heavy-drinking emphasis
- created_at: seeded
- source: user-explicit
- status: addressed: README (`soft_penalty_hits` in ranking)
- body: `open bar`, `all you can drink`, `free drinks all night`, `unlimited drinks`, `bottomless mimosas`, `pre-game`, `kegger`, `shotgun beer` → −0.15 per hit, capped −0.40. "Fine to have some, just downweight."

### fb-005 — Boost alcohol-free events
- created_at: seeded
- source: user-explicit
- status: addressed: README (`alcohol_free_boost` up to +0.10)
- body: `alcohol free`, `sober`, `sober curious`, `non-alcoholic`, `zero proof`, `mocktail`, `tea ceremony`, `matcha`, `specialty coffee`, `kombucha tasting`, `tea tasting` — boost.

### fb-006 — Curated IG accounts must not be auto-pruned
- created_at: seeded
- source: user-explicit
- status: addressed: README (stale-prune now skips `IG_ACCOUNTS` entirely)
- body: The accounts in `IG_ACCOUNTS` (run clubs, yoga, comedy, bookstores, music, alcohol-free nightlife, spot curators) — all explicitly user-named. Stale-prune must skip them.

### fb-007 — Left sidebar simplified (TopAccounts + ActivityPanel removed)
- created_at: seeded
- source: user-explicit
- status: addressed: README
- body: Sidebar shows only view-toggle, calendar, and search/filters.
- resolution: Don't reintroduce widgets to the left sidebar without explicit permission.

### fb-008 — No empty gray gradient boxes for events without images
- created_at: seeded
- source: user-explicit
- status: addressed: README
- body: When an event has no image, render text-only. Applies to ActivityPanel past saves, EventModal "More from"/"More like this" strips, GridCard.
- resolution: Any new "card" surface must follow the same rule.

### fb-009 — "This Weekend" hero must not be parties/nightclub/drinking-heavy
- created_at: seeded
- source: user-explicit
- status: addressed: README
- body: Filters to low-key social: brunch, books, runs, art, outdoors, comedy, supper-club, workshops. Excludes `parties` cat, `nightlife` highlight, drinking-text. Saturday + Sunday only (not Friday).

### fb-010 — No backend; personalization stays client-side in localStorage
- created_at: seeded
- source: user-explicit
- status: addressed: README
- body: All personalization in `nyc-events:*:v1` localStorage keys with reset button. Never sent to a server.

### fb-011 — Don't write per-source code; prefer generalizable solutions
- created_at: seeded
- source: user-explicit
- status: addressed: README
- body: bookclubbar.com etc. caught by generic `_EVENT_PLATFORM_RE` venue-events pattern; no per-site scraper code.

---

## Open items (top of list = highest priority)

### fb-106 — IG_ACCOUNTS must only contain socializing-oriented accounts; no individual people
- created_at: 2026-05-28
- source: user-explicit (mid-run-1552 correction)
- status: addressed: 2026-05-28-1552 (initial 4 personal accounts removed)
- body: We must NOT include individual person IG accounts in `scrapers/config.py::IG_ACCOUNTS` (e.g. `alvinzx`, `j_palmer_7`, `leahcanel`, `sophiareed5`, `maggie_onthemove` — anything that looks like a personal account of one human). Only socializing-themed entities: clubs, venues, curators, social brands, orgs, institutions. **Private IG accounts are off the table entirely** (they can't be scraped anyway, but also won't be added).
- resolution: This applies to every future agent. Source Curator and Ingestion Quality must filter individual-person accounts out of any `IG_ACCOUNTS` add-list before proposing. Heuristic: drop handles that look like `firstname_lastname`, `firstinitial_lastname`, `firstname<number>`, or that the user follows but are clearly a personal profile (no event-flyer posts, no "club"/"venue"/"NYC"/"BK"/etc. in handle or bio).

### fb-101 — Close the follow-graph 0-yield gap
- created_at: 2026-05-28
- source: agent-proposal (from metrics-before, run 2026-05-28-1552)
- status: open
- body: 42 of 54 `signal_accounts` in `user_interest_profile.json` have `yield_map` = 0.0. Highest-priority subset (user-named in README §480–533 or required by `sanity_check.py`): `vitalrunclub`, `silentbookclub.nyc`, `nycbackgammonclub`, `reading_rhythms`, `bookclubbar`, `crownheightscraftclub`, `midnightrunnersnewyork`, `philosophy.nyc`. Each is a follow that produces no events — either the account isn't in `IG_ACCOUNTS`, the scraper is failing silently, or there's a `dead_accounts.json` blocker.
- "addressed" criterion: ≥ 5 of the named accounts move to `yield_map > 0` within ~3 runs.

### fb-102 — Raise IG share + surface follow-graph provenance
- created_at: 2026-05-28
- source: agent-proposal
- status: open
- body: IG is 21/246 (8.5%) of the deployed feed though README §40–45 says it should be dominant. Separately, 0/246 events have an `account` field whose value matches a `signal_account` — either the field isn't being populated or the metric is reading the wrong key (audit `build_event` in `instagram.py` for the `account` / `creator` / `authorAccount` field name).
- "addressed" criterion: IG share ≥ 20% AND ≥ 10% of events have an `account` matching a `signal_account`.

### fb-103 — Fix the `bk` topic gap
- created_at: 2026-05-28
- source: agent-proposal
- status: open
- body: `topic_counts.bk = 4` but only 2 events match the shorthand, vs `brooklyn = 3` surfacing 14 events. Likely needs (a) a synonym map (bk ↔ brooklyn) in category inference, (b) Brooklyn-specific accounts in `signal_accounts` that may not have BK in their captions.
- "addressed" criterion: `bk` topic count rises to ≥ 8 within 2 runs.

### fb-105 — Curator-calendar lu.ma path probing for every signal_account
- created_at: 2026-05-28
- source: agent-proposal (dreamer-critic D1, APPROVE-DREAM but deferred this round)
- status: in-progress (script shipped: 21d916c on 2026-05-28; live run blocked by IP rate-limit)
- body: For every `signal_account` (54 today, 69 after this round's P3 promotions), probe `https://lu.ma/<handle>` once. If yield ≥ 3 distinct events not in `/nyc`, add to `LUMA_PAGES`. Implement as `scrapers/maintenance/probe_luma_curators.py` (one-off, not in hot path). Replaces the broken `/nyc/<topic>` URLs.
- "addressed" criterion: the maintenance script exists in `scrapers/maintenance/` ✓ shipped 21d916c. Still needed: run it at least once, apply candidate diff to `luma.py`.
- run blocker (2026-05-28 iter 67-68): Lu.ma rate-limited this IP after the initial concurrent burst — every URL returns 429 even at 2s/request sequential pacing. Need to either wait for the rate-limit window to expire (try in 1+ hour from a fresh session), or run from CI (different IP, presumably uncluttered budget). Pacing now defaults to 1.5s/req in the committed script.

### fb-107 — Lower IG-session staleness threshold from 30 to 25 days
- created_at: 2026-05-28
- source: agent-proposal (iter 68)
- status: addressed (committed in iter 68)
- body: The 2026-05-24 mass-kill of 54 accounts happened while the session was ~23 days old. The 30-day STALE threshold in `sanity_check.py` was too lenient — by the time it fires, the session is fully dead and accounts have already been wrongly struck. New thresholds: ⚠ STALE at 25 days, ⛔ CRITICAL at 28 days, with explicit refresh command in the warning.

### fb-108 — Dedup `bookclubbar` in IG_ACCOUNTS
- created_at: 2026-05-28
- source: agent-proposal (iter 68; Critic flagged in run 2026-05-28-1552)
- status: addressed (committed in iter 68)
- body: `bookclubbar` appeared twice in `scrapers/config.py` IG_ACCOUNTS (lines 54 and 133). `list(dict.fromkeys([...]))` made it harmless functionally but it's noise. Removed line 133.

### fb-104 — Prune redundant `/nyc/<topic>` URLs from LUMA_PAGES (after fb-105)
- created_at: 2026-05-28
- source: agent-proposal (dreamer-critic D2, DREAM-DEFER)
- status: open (blocked-by: fb-105)
- body: Critic verified that 60 of 66 `LUMA_PAGES` entries (`scrapers/sources/luma.py:7-91` `/nyc/<topic>` block) return identical content to `/nyc`. The 6 curator calendars at the bottom DO yield distinct content. Once fb-105 grows the curator-calendar list, drop the redundant 60 URLs (8x scrape budget savings).
- deferred reason: additive-only rule. Removing seed URLs needs explicit user opt-in. The 60 URLs scrape redundant content but don't fail; downstream dedup absorbs it.
- "addressed" criterion: `LUMA_PAGES` contains only `/nyc` + a non-empty list of curator calendars. No `/nyc/<topic>` entries.

### fb-100 — Run calibration ask next round
- created_at: 2026-05-28
- source: agent-proposal
- status: open
- body: This first invocation deferred the user-ask. Next run should call `AskUserQuestion` with 3 real events from `account ∈ signal_accounts` and ask which the user would actually attend. That answer is the ground-truth signal for whether the loop is improving.
- "addressed" criterion: A `/self-improve` run logs a user response to the calibration question in `<run-dir>/feedback.md`.

<!-- Append new feedback above this comment as it comes in. Top of list is highest priority. -->


---

## Closed items

<!-- Items move here when status becomes addressed: <sha> or wont-do: <reason>, except for the seeded README rules above which stay near the top as durable references. -->
