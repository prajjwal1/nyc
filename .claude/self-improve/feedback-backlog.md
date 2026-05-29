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
- status: addressed: probe ran iter 76 (rate-limit cleared); zero new candidates found
- body: For every `signal_account` (54 today, 69 after this round's P3 promotions), probe `https://lu.ma/<handle>` once. If yield ≥ 3 distinct events not in `/nyc`, add to `LUMA_PAGES`. Implement as `scrapers/maintenance/probe_luma_curators.py` (one-off, not in hot path). Replaces the broken `/nyc/<topic>` URLs.
- resolution: ran the script against 169 candidates (excluding the 6 handles already covered). Result: **0 net-new lu.ma curator URLs** worth adding. Most signal_accounts don't have public lu.ma calendars (404 on the handle path). The existing 6 curator URLs (`nycbackgammonclub`, `readingrhythms-manhattan`, `litclub.nyc`, `thinkolio`, `founderscoffee`, `cinemaclub`) cover everything available. Also fixed a `_existing_handles` bug that was falsely flagging `nycbackgammonclub` as a candidate (the earlier `startswith("nyc")` filter was too broad).
- implication for fb-104: deferral premise (replacement curator-calendar list before prune) doesn't materialize — there's no replacement list to add. Pruning `/nyc/<topic>` URLs would now be safe (they're redundant) but is still a deletion, which the additive-only rule blocks without explicit user opt-in.

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

### fb-109 — Block leaks: corporate AWS meetups, B2B coaching, bar crawls
- created_at: 2026-05-28
- source: agent-proposal (iter 69 audit of deployed feed)
- status: addressed (committed in iter 69)
- body: Three leak patterns found in the live feed by sampling non-IG sources:
  (a) "Amazon Quick - NYC Meetup" — Amazon AWS product demo classified as `food/free/outdoors/parties`. Hard-block added: `amazon quick`, `amazon quicksight`, `aws meetup`, `aws user group`, `google cloud meetup`, `azure meetup`, `salesforce meetup`, `snowflake meetup`.
  (b) "The Career Reset: …" + "The AI Edge: Supercharge Your Startup Vision" — B2B coaching framings. Hard-block added: `career reset`, `career strategy`, `supercharge your startup`, `startup vision`, `your startup growth`.
  (c) 3 "Brooklyn Bar Crawl: <neighborhood>" events at 0.65-0.71 — drinking-centric, same spirit as `open bar`/`unlimited drinks`. Soft-penalty added: `bar crawl`, `pub crawl`.
- "addressed" criterion: ✓ patterns block their target titles; verified no false positives on "throughout her career" or "asianfoundersclub mixer".

### fb-110 — Bake fb-106 into agent system prompts
- created_at: 2026-05-28
- source: agent-proposal (iter 69)
- status: addressed (committed in iter 69)
- body: User correction fb-106 ("socializing entities only in IG_ACCOUNTS — no individual people") added directly to `.claude/agents/source-curator.md` (hard filter + heuristic checks) and `.claude/agents/ingestion-quality.md` (hard rule). Future /self-improve runs will respect this automatically.

### fb-111 — Venue synonym expansion in normalize (BK ↔ Brooklyn, MoMA, BAM, HOY, KDC, BMA)
- created_at: 2026-05-28
- source: agent-proposal (iter 70; README §354 known gap)
- status: addressed (committed in iter 70)
- body: `_normalize_venue_name` now expands NYC venue abbreviations before suffix-stripping. `\bbk\b → brooklyn`, `\bmoma\b → museum of modern art`, `\bbam\b → brooklyn academy of music`, `\bkdc\b → knockdown center`, `\bhoy\b → house of yes`, `\bbma\b → brooklyn museum`, `\bthe met\b → metropolitan museum`. Word-boundary regex avoids false-positives on "Backgammon" / "Botanic". Cross-source dedup now collapses "BK Bowl" + "Brooklyn Bowl" + "Brooklyn Bowl Williamsburg" into one event.

### fb-122 — Top-event audit + purge glued-handle leak at top of feed
- created_at: 2026-05-28
- source: agent-proposal (iter 81)
- status: addressed (committed in iter 81)
- body: Audited top 20 events by score. Found 2 critical issues:
  1. **"Ggretavanfleet gave fans quite"** ranked #2 at score 1.00 — an IG-Stories OCR glued-handle leak that iter 1 P5 was supposed to catch. Inspection revealed the iter 1 regex (`^[A-Z]{1,2}[a-z]{2,}[A-Z][a-z]{2,}$`) requires an *internal* uppercase, but the actual leaks (`Glibertybagelsny`, `Ggretavanfleet`) are 1 capital + long lowercase. The Critic's "verified against live titles" claim was wrong.
  2. **"Glibertybagelsny grand opening"** also leaking, score 0.66.
- fix: added shape-(a) regex `^[A-Z][a-z]{12,}$` (1 capital + 12+ lowercase, min title-word length 14). Now caught in:
  - `scrapers/sources/instagram.py::_looks_like_glued_handle` — checks both shape (a) and shape (b) at extraction time
  - `scrapers/normalize.py::_is_glued_handle_title` — post-filter pass in `process()` so already-stored leaks self-clean without a re-scrape (purges 2 events on the very next normalize run)
- defensive scope: shape (a) checks first word length ≥14 AND all-lowercase-after-first-capital. The deployed feed has 0 legitimate words of this shape; the regex catches exactly the 2 leaks.
- other audit findings (not yet addressed): some events have wrong categories ("Silver Sapphics: Speed Dating" tagged `movies`; "Word and Object by Quine" tagged `fitness`). Categorizer false-positives — separate issue, queued as fb-123.

### fb-127 — Substack venue extraction from title (~+33 events per scrape)
- created_at: 2026-05-28
- source: agent-proposal (iter 86 audit of Substack low yield)
- status: addressed (committed in iter 86)
- body: Audit: live Substack yield is 493 events but only 1 in deployed feed. Most surviving events (237 → "ok") are actually junk product affiliates ("J.Crew Cosmo pant", "Mini Phone Tripod") while 235 *real* events were shell-filtered. Inspected the shell pool: titles like "Pet Adoption Day (@ Elizabeth Street Garden)" had the venue baked into the title string but `location.name=""` — so the shell filter (`no desc + no img + no loc`) dropped them.
- fix: `_extract_from_headings` now matches `\((?:@|at)\s+([^)]+)\)\s*$` on the title, pulls the venue into `location.name`, and strips the parenthetical from the title. Result: shell pool 235 → 202 (+33 real events recovered including Brooklyn Ceramic Arts Tour, Pet Adoption Day, High Line Plant Sale, Pupper West Side Street Fair, Brooklyn Bridge Sunset Yoga).
- known issue (separate, not addressed): substack's 237 surviving events include many product-affiliate noise ("Mini Phone Tripod", "Apple AirTag") that should be filtered out. The "(link)" suffix is a strong tell. Logged as fb-128.
- 2 of the Substack FEEDS URLs return 404 (untappedcities.com/feed/, nycgovparks.org/news.rss). Harmless but wasted budget. Not addressed this iteration.

### fb-136 — Aggregate attended counter in TopPicks header
- created_at: 2026-05-28
- source: agent-proposal (iter 95; completes the iter 71+75 attended thread)
- status: addressed (committed in iter 95)
- body: Iter 71 shipped the "Did you go?" button + iter 75 the on-card ✓ badge. Adding a small `· ✓ N attended` suffix in the "For You" subhead so the user sees their feedback history accumulating at a glance. Only renders when `yes >= 1` — no zero-state clutter. Subtle emerald color matches the badge color.
- new helper: `getAttendedCount()` in `lib/interests.ts` returns `{yes, no}` counts.
- intentionally minimal: no "no" count surfaced (negatives stay invisible per iter 75 spec); no "manage attended" UI. The counter exists to reward engagement, not to drive interaction.

### fb-138 — Reddit harvester broken (`.json` 403) + RSS fallback
- created_at: 2026-05-28
- source: agent-proposal (iter 97 audit)
- status: addressed-partial (committed in iter 97; full fix needs OAuth)
- body: reddit.py harvester was returning "No event-platform URLs found" silently. Probed: Reddit cracked down on `/.json` endpoints — 403s every UA (browser, custom, old.reddit). Their API now requires OAuth (PRAW credentials).
- fix (this round): added `_report_reddit_403()` so the silent failure is now a clear log line about the OAuth requirement. Added `.rss` (Atom) fallback that yields 7 URLs from r/AskNYC/new — comments unavailable but post titles/summaries sometimes contain event-platform links. Mirrors the iter 96 Atom-parsing pattern.
- not addressed: the actual harvest yield is degraded (README says comments are the main URL source; RSS doesn't include them). Full restoration requires PRAW creds + `praw.Reddit(client_id=..., client_secret=...)` configuration. Logged as fb-139 for the user to set up auth out-of-band.
- bonus result: harvester now logs visibly when broken; future iters won't waste time re-investigating "is reddit silently failing?"

### fb-147 — Data freshness color cue in Header
- created_at: 2026-05-29
- source: agent-proposal (iter 105)
- status: addressed (committed in iter 105)
- body: Header already shows "Updated <date>" in gray-400 but doesn't visually warn when data is stale. With the IG session-refresh bottleneck leaving feeds stale for days at a time, the user wasn't getting a clear signal.
- fix: compute `ageHours` from `lastUpdated`. Color the "Updated" line gray when < 8h, amber when 8-48h ("feed is getting stale; the scraper may be blocked"), red + bold + ⚠ when > 48h ("IG session likely expired"). Tooltip explains the exact age.
- result: visible at-a-glance staleness signal. The current deployed feed timestamps as ~21h stale; with this iter the user will see amber + tooltip explanation instead of silently looking at old data.

### fb-146 — Shareable account-filtered URLs via `?account=X` query param
- created_at: 2026-05-29
- source: agent-proposal (iter 104; smaller scope than README §361 dedicated route)
- status: addressed (committed in iter 104)
- body: AccountBanner already renders when `search` starts with `@`. Added URL state sync: `?account=<handle>` is read on mount (with safe-handle regex `^[A-Za-z0-9_.\-]{1,40}$` to keep XSS surface minimal) and written when `search.startsWith("@")`. Makes account-filter views bookmarkable + shareable without needing static-route generation. Cleaner than the README §361 idea (which would require `generateStaticParams` for every known account).
- usage: `https://prajjwal1.github.io/nyc/?account=bookclubbar` → opens with the bookclubbar account filter active. Also chains: `?account=bookclubbar&view=calendar&date=2026-06-15`.

### fb-145 — Green-Wood Cemetery URL update (greenwoodcemetery.org → green-wood.com)
- created_at: 2026-05-29
- source: agent-proposal (iter 103 audit)
- status: addressed (committed in iter 103)
- body: `https://greenwoodcemetery.org/events/` (in GENERIC_URLS) redirects to green-wood.com which 503s on bare host. The direct path `https://www.green-wood.com/events` works and yields 10 events (Green-Wood After Hours evening tours through June+).
- bonus negative finding: bookmanager API helper (powers bookclubbar + lizsbookbar) doesn't need pagination — already returns multi-month data (May through September for bookclubbar). No fix needed there.

### fb-144 — mcnallyjackson month-pagination (3 → 44 future events)
- created_at: 2026-05-29
- source: agent-proposal (iter 102 audit)
- status: addressed (committed in iter 102)
- body: mcnallyjackson.py yielded 33 events but only 3 future — same current-month-only issue as the iter 91 comedy-club fix. Inspected page HTML: found 6 unique `/events` URLs including `/events/2026/06` (35 June events) and `/events/2026/07` (11 July events). The bare `/events` route only ships current-month.
- fix: added `_month_urls()` generating `/events/YYYY/MM` for the current + next 2 months at scrape time (handles year rollover). Dedup by (title, date) so any overlap with the bare /events doesn't double-count.
- result: 33 → 79 events extracted, 3 → 44 future events surviving filters (14× lift). Sample: "Matthew Campbell & Mike Bird" (Jun 1), "New Directions Book Club" (Jun 2) — actual literary programming the user follows.

### fb-143 — dice.py rewritten for __NEXT_DATA__ (0 → 30 events)
- created_at: 2026-05-29
- source: agent-proposal (iter 101 audit)
- status: addressed (committed in iter 101)
- body: README marked dice as `✗ "URL changes. Try harder."`. Live probe: `dice.fm/browse?location=new-york` returns 625KB with 3 JSON-LD blocks (all site-metadata: Brand, WebSite) AND a `__NEXT_DATA__` script containing `pageProps.events` — 30 events with structured fields (name, dates.event_start_date, venues[].name/address/location, images.landscape, perm_name). The iter-84 `EVENT_TYPES` fix was reading from the wrong data shape.
- fix: read events from `__NEXT_DATA__.props.pageProps.events`. Build full event with venue name + address + lat/lng + image URL + ticket URL (`dice.fm/event/<perm_name>`). Kept JSON-LD path as defensive fallback in case DICE flips schemes again. Quirk: `about` is `{description, highlights}` dict (not a string).
- result: 30 events / 25 future surviving filters. Sample: "Horse Meat Disco NY in The Ruins", "T4T LUV NRG Pride: Eris Drew b2b Octo Octa", "Elsewhere Presents: Chanel Beads" — indie DJ + live music programming.
- doc cleanup: KNOWLEDGE.md ✗ entries corrected for **dice** (`✅ __NEXT_DATA__`), **theskint** (`✅ RSS via substack`), **bookclubbar** (`✅ bookmanager API`). All 4 remaining `✗` rows in the source table are now resolved over iter 99-101.

### fb-142 — nycforfree.py rewritten for Squarespace eventlist (+126 events)
- created_at: 2026-05-29
- source: agent-proposal (iter 100 audit)
- status: addressed (committed in iter 100)
- body: README marked nycforfree as `✗ "HTML structure unclear. Use IG @nycforfree.co."`. Live probe: nycforfree.co/events is a standard **Squarespace eventlist** with 129 articles (`article.eventlist-event`), same pattern as brooklyncomedy.py. The old scraper looked at the wrong URL (`/`, no events) and CSS selectors. Rewritten to fetch `/events` with 90s timeout (~2MB page) and parse `a.eventlist-title-link`, `time.event-time-24hr-start[datetime]`, `.eventlist-description`, `.eventlist-column-thumbnail img`.
- result: 0 → 126 events, 83 future surviving filters. All correctly tagged `price="free"`. Sample: "U.S. SailGP Fan Zone", "Last Crumb Grand Opening", "Jung Saem Mool Glass Skin Atelier Pop-Up" — exactly the free/pop-up coverage nycforfree.co specializes in.
- KNOWLEDGE.md status: ✗ → ✅ with yield numbers.

### fb-141 — parks.py is actually working + CANCELED leak
- created_at: 2026-05-28
- source: agent-proposal (iter 99 audit)
- status: addressed (committed in iter 99)
- body: README §66 / KNOWLEDGE.md marked parks scraper as `✗` ("didn't return events. Try API."). Live probe found it's actually working: **50 events from nycgovparks.org/events**. Most are "Kids in Motion" (correctly blocked by existing kids/word-boundary filter), leaving 22 legit events surviving: Bellydance, Yoga, Cardio, Bootcamp, Dance Fitness, "Hudson Classical Theater: Uncle Vanya", "Bryant Park Picnic Performance: Jazzmobile", "World Cinema Nights".
- but: 5 "CANCELED: <event>" entries were leaking through. The leading marker is unambiguous.
- fix:
  1. HARD_BLOCK_KEYWORDS += `canceled:`, `cancelled:` (both spellings)
  2. KNOWLEDGE.md status `✗ parks` → `✅ parks` with the actual yield numbers.
- 5 canceled → 0; 22 legit events continue to surface. Parks events should appear in the next scrape (cultural / fitness programming is high-value for the user).

### fb-140 — Museums.py shipped page-scaffold strings as events
- created_at: 2026-05-28
- source: agent-proposal (iter 98 audit)
- status: addressed (committed in iter 98)
- body: Iter 84 extended museums.py's @type acceptance but didn't probe live yield. Audit found:
  - MoMA returns 403 to every UA (bot block)
  - Guggenheim `/calendar` 404s (URL moved to `/event`)
  - Brooklyn Museum / Whitney / New Museum / The Met all JS-render their event data (no JSON-LD, no `__NEXT_DATA__`)
  - The DOM-card fallback was scraping page-scaffold strings as "events": `"Thursday, May 28"` (calendar header), `"Narrow search"` (filter widget), `"Today's events"` (page heading) — all dated 2027-05-28 or 2031-05-01 from far-future date misparse.
- fix:
  - Removed MoMA from MUSEUMS (bot-blocked).
  - Updated Guggenheim URL `/calendar` → `/event`.
  - `_MUSEUM_TITLE_REJECT_RES`: 7 patterns rejecting page-scaffold titles (weekday-headers, "Today's events" with straight + curly apostrophes, "Narrow search", "view/see all events", bare dates, "Upcoming/Featured events").
  - `_is_museum_card_junk(title)` gate applied in `_from_card`.
- result: 3 garbage events → 0. Honest empty is better than fake events polluting the feed with "Thursday, May 28" at score 0.5+.
- known-broken (no fix this round): museum sites JS-render; full restoration would need a JS-rendering pipeline. README §70-83 already documents this class of source. The Met + Brooklyn Museum are in "tried and blocked".

### fb-139 — Set up Reddit OAuth (PRAW) for full comment-mining
- created_at: 2026-05-28
- source: agent-proposal (iter 97)
- status: open (requires user action)
- body: Reddit's `/.json` API now requires OAuth. To restore comment-mining (the main URL source per README), the user needs to:
  1. Register an app at https://www.reddit.com/prefs/apps (script type)
  2. Set GitHub secrets: `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`
  3. Add a small `praw.Reddit(...)` wrapper to `scrapers/sources/reddit.py`
- once done, the iter 97 RSS fallback can stay as defense-in-depth.

### fb-137 — Substack parser only handled RSS, missed Atom (eaterny 0→8)
- created_at: 2026-05-28
- source: agent-proposal (iter 96 audit of substack feeds)
- status: addressed (committed in iter 96)
- body: Surveyed all 7 substack-style feeds. `eaterny` (Eater NY, food/restaurant openings) was returning 0 events. Root cause: Eater NY uses **Atom XML** (`<feed><entry>` with default Atom xmlns) instead of RSS (`<channel><item>`). The substack parser strictly looked for `<channel>` and bailed otherwise.
- fix: `_parse_feed` now falls back to `root.findall("a:entry", ...)` when no `<channel>` found. `_parse_item` extended to read Atom-namespaced `title`, `published`/`updated`, `summary`/`content`, and `<link rel="alternate" href=...>`.
- result: eaterny 0 → 8 events extracted. Sample: "Taqueria Ramirez's Soccer Bar Opens Just In Time for the World Cup", "A Force Behind Ultra-Lauded Atomix Is Opening Her Own NYC Restaurant" — these are restaurant openings = legit user-attendable food events.
- bonus finding: meetup search-page pagination doesn't actually paginate. Probed 6 param patterns + 20 category IDs — most cats ignored. The 4 SEARCH_URLs yield ~45 events, can't grow via pagination. Logged as "no actionable" so future iters don't re-investigate.

### fb-135 — theskint over-fragmentation: 172 events from 11 RSS posts
- created_at: 2026-05-28
- source: agent-proposal (iter 94 audit)
- status: addressed (committed in iter 94)
- body: theskint substack feed was generating 172 "events" from 11 RSS posts because `_extract_from_headings` treats every body `<h2>/<h3>/<strong>/<b>` as an event title. theskint posts are mixed: weekday-roundup posts ("WEDS-THURS, 5/27-28: MANHATTANHENGE, BUSTA RHYMES, ...") SHOULD be fragmented, but single-event sponsored posts ("CELEBRATE THE MODERN AMERICAN THEATER AT HB STUDIO'S FESTIVAL") were leaking dozens of button-text + paragraph fragments.
- fix: added `_looks_like_roundup(title)` heuristic that matches weekday-pair prefixes (`WEDS-THURS,`, `FRI-TUES,`, `MON, 6/3:`). Single-event posts skip heading fragmentation. Also extended `_is_date_only_title` to drop day-name fragments ("wednesday") and date ranges ("May 30 to June 5") that were leaking from roundup posts.
- result: 172 → 106 extracted events. The real-event count from theskint is small either way (~6 surviving filters) because theskint's HTML doesn't have clean per-event structure, but noise is materially reduced. Single-event posts now contribute 1 event instead of 15-30 fragments each.

### fb-134 — bookclubbar venue-rental "[PRIVATE EVENT" leak
- created_at: 2026-05-28
- source: agent-proposal (iter 93 audit)
- status: addressed (committed in iter 93)
- body: bookclubbar live yield is 34 events, mostly high-quality (Author Event, Galinsky Poetry, etc). Two duplicate "[PRIVATE EVENT - closed from 6pm to 10pm]" entries were leaking — those are venue closures for private rentals, not public events. Added `[private event` (with bracket) to HARD_BLOCK_KEYWORDS. The bracketed form is specifically a Book Club Bar / event-calendar convention so won't false-positive on legit phrases like "host your private event tips". Verified 3/3 test cases.
- bonus finding: lizsbookbar yield is healthy at 19 events all passing filters — no fixes needed there.

### fb-133 — NYPL audit: 79 events surviving filters, "Playdate at the Library" leak
- created_at: 2026-05-28
- source: agent-proposal (iter 92 audit)
- status: addressed (committed in iter 92)
- body: NYPL was 3/246 events in deployed feed. Live yield is 121 events (all future from Refinery API + HTML keyword searches). 42 correctly blocked as kids programming, 79 survive — including "Playdate at the Library" which is clearly a parent/kid event but had no caught keywords.
  - Refinery API doesn't expose an `audience` attribute (confirmed via API inspection — keys are `event-id, name, description-short, image, registration-type` only). Can't filter structurally; must use text patterns.
- fix: added `playdate`, `caregivers`, `caregiver and child` to HARD_BLOCK_KEYWORDS. All 3 are near-exclusively parent/kid terms. 4/4 tests pass including negative cases (Adult Book Club, Author Talk).
- note: the 79 surviving NYPL events are still mostly not surfacing in deployed feed because their score < MIN_SCORE=0.5 (NYPL events have generic titles + DEFAULT_IMAGE + thin descriptions, scoring low). That's working as intended — score floor is the right gate for low-info library events.

### fb-132 — Comedy-club month pagination + dynamic URL injection
- created_at: 2026-05-28
- source: agent-proposal (iter 91 audit)
- status: addressed (committed in iter 91)
- body: Comedy clubs were at 2 + 6 events in deployed feed despite stats_history showing yields of 33 + 60 two weeks ago. Probed: NYCC `/calendar` and East Ville Comedy `/events` return ~267 events combined but **all in May 2026** — only 32 are future after today (2026-05-28). The default calendar page only shows the current month; past-date filter strips most.
- discovery: `/calendar/YYYY-MM` pattern reaches future months. NYCC has 109 June + 22 July events; East Ville has 34 June + 38 July events.
- fix: added `_dynamic_calendar_urls()` that generates URLs for the current + next 2 months for both clubs at scrape time (handles year rollover). Avoids hardcoding dates that would go stale monthly.
- expected impact: ~235 future comedy events available, capped to top-25 by existing SOURCE_VOLUME_CAPS (newyorkcomedyclub=15 + eastvillecomedy=10). The comedy category share rises meaningfully and the events are top-quality picks from a much deeper pool.

### fb-131 — Eventbrite pagination works but only page 1 was scraped
- created_at: 2026-05-28
- source: agent-proposal (iter 90 audit)
- status: addressed (committed in iter 90)
- body: Eventbrite was 111/246 events in deployed feed. Probed `?page=N` query param — it paginates correctly (page 2 returns "OkayAfrica x Elsewhere" vs page 1's "BROOKLYN CARNIVAL"; page 5 of all-events still yielded 20 distinct events for a cumulative 100 unique). All ~30 categorical URLs in `GENERIC_URLS` only fetched page 1, missing ~200+ events per scrape.
- fix: added `?page=2` and `?page=3` for the 3 high-density `all-events` URLs (new-york, brooklyn, queens) and `?page=2` for 5 high-priority categorical URLs (music, comedy, parties, dating, singles) — +9 new fetches total.
- bounded with SOURCE_VOLUME_CAPS["eventbrite"]=100. The user explicitly likes "less is more" per the existing cap comments. 100 events keeps Eventbrite from dominating while letting the top-N bubble up from a much deeper pool — same feed size, higher quality, more diversity.
- expected impact: same eventbrite share (~100/feed_total) but the events are top-quality picks from a ~300-event pool instead of all 111 page-1 hits. Music/comedy/parties/singles depth improves significantly.

### fb-130 — AllEvents.in pagination broken (`?page=N` returns page 1)
- created_at: 2026-05-28
- source: agent-proposal (iter 89 audit, following the Songkick thread)
- status: addressed (committed in iter 89)
- body: AllEvents had 14 events in deployed feed. `GENERIC_URLS` had 6 borough URLs using `?page=2..5` for pagination but live probe showed every `?page=N` returns the same page-1 events as the bare URL — 4-5 wasted fetches per scrape.
- discovery: AllEvents uses time-window paths (`/today`, `/tomorrow`, `/this-weekend`, `/upcoming`, `/all`) which return distinct event slices. Probed against the bare URL: each yields 5-30 net-new events.
- fix: replaced the 6 dead `?page=N` URLs with 7 time-window URLs across the 4 borough pages. Live verified: total unique events 353 from 13 URLs (vs ~65 prior with 12 URLs that included duplicates) — 5.4× lift.

### fb-129 — Songkick pagination broken (path suffix vs query param)
- created_at: 2026-05-28
- source: agent-proposal (iter 88 audit)
- status: addressed (committed in iter 88)
- body: Audit: Songkick listed at 16 events in deployed feed despite README claiming "major live-music coverage." Investigated: `GENERIC_URLS` had 7 metro-area URLs using path-suffix pagination — `/metro-areas/.../2`, `/3`, etc. **All 7 path-suffix URLs returned the same page-1 49 events.** Effectively scraping the same content 7 times, costing 6 wasted fetches and capping yield at ~49 unique titles.
- fix: switched to `?page=N` query-param pagination. Live-verified each `?page=2..7` returns ~48 distinct MusicEvent JSON-LD items. Total yield: 334 events, 306 unique titles (6.2× lift). Many duplicates across pages because Songkick repeats artists across venues/dates — downstream dedup handles cleanly.
- expected impact on next scrape: music category share rises substantially; `Instagram is dominant source` sanity_check threshold becomes easier to satisfy as the overall feed grows.

### fb-128 — Substack product-affiliate noise ("Mini Phone Tripod (link)")
- created_at: 2026-05-28
- source: agent-proposal (iter 86 audit)
- status: addressed (committed in iter 87)
- body: Substack RSS includes product affiliate links as RSS items: "J.Crew Cosmo pant", "Mini Phone Tripod (link)", "Apple Wired Ear Pods (link)". Trailing "(link)" + retail-host sourceUrl = clear non-event.
- fix: `_is_affiliate_noise(title, source_url)` checks: title ends with `(link)`/`[link]` OR sourceUrl host matches a deny-list of retail/social hosts (amazon, jcrew, macys, apple, llbean, shopstyle, ltk, distrokid, mirror.xyz, audius, spotify, variety, gofundme, twitter, x.com). Applied per-heading in `_extract_from_headings` before `build_event`. Audit confirmed 13 noise → 0 remaining post-fix.
- bonus: removed 2 confirmed-404 FEEDS URLs (untappedcities.com/feed/, nycgovparks.org/news.rss) so scrape budget isn't wasted.

### fb-126 — Partiful image-field rename + "ged" substring false-positive
- created_at: 2026-05-28
- source: agent-proposal (iter 85 audit of Partiful low yield)
- status: addressed (committed in iter 85)
- body: Audit: live Partiful yield is 15 events but the deployed feed had 1. Two causes:
  1. **Image-field rename**: the scraper read `event_data["coverPhotoUrl"]` but Partiful's __NEXT_DATA__ now uses a nested `image: {url, upload: {url}}` object. Every event came in with `imageUrl=None`, then `_IMAGE_REQUIRED_SOURCES` (partiful is in that set) dropped them all as shell. Fix: read `coverPhotoUrl` first, fall back to `image.url` or `image.upload.url`. Verified: 15/15 events now carry an image URL.
  2. **"ged " substring false-positive**: `HARD_BLOCK_KEYWORDS` had `"ged "` (with trailing space) to block GED prep classes. It false-fired on "collaged", "encouraged", "aged", "engaged" — substring match doesn't respect word boundaries. Moved `ged` and `tefl` (same shape) into `_WORD_BOUNDARY_KEYWORDS` so they only block on real word boundaries.
- result: surviving partiful events 1 → 8 (+7, of which 7 were image-field, 1 was the GED unblock).

### fb-125 — Same strict-@type bug across luma / music_venues / museums / dice
- created_at: 2026-05-28
- source: agent-proposal (iter 84; followed fb-124's thread)
- status: addressed (committed in iter 84)
- body: Audited every source scraper for the same strict `@type == "Event"` filter that iter 83 fixed in Meetup. Found 4 more affected:
  - `luma.py:212` — strict `@type != "Event"` — dropping all subtypes
  - `music_venues.py:54` — Event|MusicEvent only — dropping ComedyEvent, TheaterEvent, ScreeningEvent, Festival
  - `museums.py:60` — Event only — dropping ExhibitionEvent, VisualArtsEvent, EducationEvent (artist talks), ScreeningEvent (film series)
  - `dice.py:20` — Event|MusicEvent only — dropping ComedyEvent, TheaterEvent
- fix: each now imports `EVENT_TYPES` from `generic.py` (canonical set of 18 subtypes) + uses a small `_is_event(t)` helper supporting str-or-list `@type` values. `meetup.py` DRY'd to use the same import.
- expected impact: more events captured from these sources on next scrape — especially museum talks/screenings + venue comedy/theater shows that were silently invisible.

### fb-124 — Meetup Schema.org Event-subtype acceptance
- created_at: 2026-05-28
- source: agent-proposal (iter 83 trace of the Quine event)
- status: addressed (committed in iter 83)
- body: Traced the iter 81 "Word and Object by Quine Week 4 — TMIRCE brunch desc" anomaly. The Meetup page's JSON-LD correctly carries the right title + the right description ("How does language come to have meaning…") tagged `@type: EducationEvent`. But `_parse_meetup` strictly filtered on `@type == "Event"`, so EducationEvent / MusicEvent / TheaterEvent / etc. were all routed to the empty-description DOM card fallback. Wrong descriptions could then bleed in from sibling cards on search pages.
- fix: extended acceptance to a Schema.org Event-subtype set: `Event, EducationEvent, BusinessEvent, SocialEvent, MusicEvent, SportsEvent, TheaterEvent, DanceEvent, ComedyEvent, FoodEvent, Festival, ScreeningEvent, ExhibitionEvent, VisualArtsEvent, LiteraryEvent`. Mirrors `generic.py::EVENT_TYPES`.
- verified: re-parsed Quine's Meetup page → "Word and Object by Quine Week 4" + the correct philosophy description (no more TMIRCE bleed). All philosophy / language / education Meetup groups will now extract correctly.

### fb-123 — Categorizer false-positives ("movies" on dating, "celebrities" on dog rescue)
- created_at: 2026-05-28
- source: agent-proposal (iter 81 audit)
- status: addressed (committed in iter 82)
- body: Identified two trigger phrases in `event_parser.CATEGORY_KEYWORDS`:
  1. `premiere` was in `movies` — false-fired on "NYC's Premiere Party for lesbians" and "Premiere Brunch Series" (means "best/first", not "movie premiere"). Replaced with disambiguated phrases: `movie premiere`, `film premiere`, `premiere screening`.
  2. `meet & greet` was in `celebrities` — false-fired on "meet & greet shelter dogs" (TMIRCE bRUNch) and "Founders Coffee Meet & Greet". Replaced with `celebrity meet`, `celebrity m&g`.
- Verified: 4 positive tests still pass (real movie nights / celebrity m&g still tag correctly), 4 negative tests pass (no false positives on Sapphics, brunch with dogs, founders coffee).
- separate issue still open: "Word and Object by Quine Week 4" event's title doesn't match its description (description was about TMIRCE bRUNch). That's a data-quality bug, not a categorizer one — likely cross-source title swap during dedup. Tracked separately if it recurs.

### fb-121 — Audit iter 77 organizer-match real-world yield
- created_at: 2026-05-28
- source: agent-proposal (iter 80; validation of iter 77 claim)
- status: addressed (committed in iter 80)
- body: Iter 77 added an organizer-name match path to the enrichment, claiming it would surface Eventbrite events from accounts the user follows. Probed 15 random Eventbrite + 15 random Meetup events live: 0/30 organizer names overlap with user_following. NYC Eventbrite organizers are mostly tour/event companies / one-off promoters / venues ("Crush Wine Experiences", "lululemon Williamsburg", "Mireve for Women") not the indie social/curator IG brands the user follows. Meetup groups have entirely different naming. The match path stays as defensive infrastructure (cheap, harmless, may catch future matches) but is documented as low-yield in practice.
- also fixed: iter 77 was storing the FULL org name ("Vital Run Club") as `event.account`, breaking the UI ribbon's @account link semantics. Now stores the matched IG handle ("vitalrunclub") in `account` and keeps the human org name in `event.organizer` for display.

### fb-120 — Clean stale transient-killed entries from dead_accounts.json
- created_at: 2026-05-28
- source: agent-proposal (iter 79; janitorial follow-up to iter 1 P1)
- status: addressed (committed in iter 79)
- body: Iter 1 P1 added a runtime auto-revive for the 54 accounts mass-killed on 2026-05-24 by transient `feedback_required` errors. The skip-set builder correctly bypasses them, but the JSON file itself still carried the stale entries — misleading for sanity_check + ops readers. New `scrapers/maintenance/clean_dead_accounts.py` is an idempotent purger (dry-run by default, `PURGE=1` to apply). Removed 54 entries; 58 remain (26 legitimate `not_exists` + 32 legitimate `stale_no_recent_posts`).
- side benefit: `sanity_check.py` "Newly-dead accounts in last 7 days" dropped from 54 → 0, killing the "sudden dead-account growth" WARNING signal.

### fb-119 — "From accounts you follow" hero in TopPicks
- created_at: 2026-05-28
- source: agent-proposal (iter 78; surfaces the iter 73-77 enrichment work)
- status: addressed (committed in iter 78)
- body: 5th hero in TopPicks, sky-themed, sandwiched between Just Added and Saved. Filters `upcoming` events where `userFollowing` fires (capped at 6). Hero ordering: Tonight → Weekend → Just Added → Following → Saved → per-day. Follow-graph signal is the highest-conviction predictor of "events the user would attend" — surfacing them as a dedicated hero (instead of buried per-day) directly serves the North Star. Combined with iter 73-74 (URL handle + venue-domain) + iter 77 (organizer name), this hero will populate with up to ~35 events post next-scrape (6 current IG userFollowing + 29 enriched).
- Visual choice: 👤 emoji + sky-50/60 background to match the iter 71 U1 ribbon (sky for follow signal).

### fb-118 — Extract organizer name from JSON-LD + match against IG follows
- created_at: 2026-05-28
- source: agent-proposal (iter 77; extends iter 73-74 enrichment to JSON-LD events)
- status: addressed (committed in iter 77)
- body: Eventbrite/Lu.ma/etc. JSON-LD events include `organizer.name`. The generic JSON-LD parser was discarding this field. Now stamped onto the event as `event.organizer`, then `_enrich_provenance_from_url` matches `event.organizer` against user_following via alphanumeric fold + suffix stripping (`nyc`, `ny`, `brooklyn`, `bk`, `manhattan`). Catches: "Vital Run Club" → `vitalrunclub`, "Reading Rhythms NYC" → `readingrhythms` → `reading_rhythms`, "BookClubBar" → `bookclubbar`. Rejects: generic short names ("AB Productions", "Yoga Studio") via 5-char floor.
- Impact will land on next scrape — current deployed feed has no `organizer` field (only `organizerUrl`); the JSON-LD extraction starts populating it on the next CI scrape.

### fb-117 — Surface attended-yes on cards
- created_at: 2026-05-28
- source: agent-proposal (iter 75; completes the iter 71 UI loop)
- status: addressed (committed in iter 75)
- body: Iter 71 shipped the EventModal "Did you go?" Yes/No prompt + localStorage state, but the user could only see the answer by re-opening the modal. Added at-a-glance badges on past events:
  - GridCard: emerald `✓` circle at bottom-right (5x5), title hover "You marked attended"
  - FeedCard + MediaFirstCard: inline `✓ went` pill next to the title (emerald-100 bg, emerald-800 text, 10px)
- Only renders when `event.date < today AND getAttendedState(event.id) === "yes"`. No render for "no" or unmarked. Build + TypeScript clean.

### fb-116 — Extend follow-graph signal to venue-domain hosts (bookclubbar.com)
- created_at: 2026-05-28
- source: agent-proposal (iter 74)
- status: addressed (committed in iter 74)
- body: Extension of fb-115. Beyond Lu.ma + Partiful, venues that run their own .com (bookclubbar.com, theskint.com, lizsbookbar.com, green-wood.com) have a second-level domain that often is the canonical handle. `_extract_handle_from_url` now falls back to hostname extraction when the URL is not a lu.ma/partiful pattern. An `_AGGREGATOR_HOSTS` deny-list keeps eventbrite/meetup/songkick/allevents/instagram/luma/dice from being misread as handles. Matches against user_following only; lizsbookbar (curated but user doesn't follow on IG) correctly DOES NOT fire userFollowing.
- impact: +13 bookclubbar.com events get userFollowing. Combined with iter 73, non-IG userFollowing events 0 → 29 (Lu.ma 16 + bookclubbar 13). Combined with deployed-feed's existing 6 IG userFollowing events, high-conviction ratio rises from 3.3% to projected 15.0% on next scrape.

### fb-115 — Extend follow-graph signal to Lu.ma via curator-handle URL match
- created_at: 2026-05-28
- source: agent-proposal (iter 73)
- status: addressed (committed in iter 73)
- body: Audit finding: Lu.ma events have the curator handle right in the sourceUrl (`lu.ma/litclub.nyc`, `lu.ma/readingrhythms-manhattan`), and those handles are often signal_accounts the user follows on IG. Currently userFollowing only fires on IG events. New `_enrich_provenance_from_url` in `normalize.py` walks all events post-extraction, extracts handles from Lu.ma + Partiful URLs, and matches them against the user_following set (`discovered_accounts.json::discovered_via==user_following`). Handle normalization: strips `-manhattan/-brooklyn/-nyc` suffixes, swaps `_↔-`, and falls back to alphanumeric-only fold so `readingrhythms-manhattan` ↔ `reading_rhythms` matches.
- impact (against today's deployed feed): non-IG userFollowing events 0 → 16 (+10 Reading Rhythms events all attributable to the user's follows). High-conviction ratio rises from 6/246 (non-IG) → 16/246 by enriching alone.
- next-iter follow-ups: same pattern for Eventbrite organizer slugs, Substack newsletter handles.

### fb-114 — Fold title + location.name into neighborhood inference
- created_at: 2026-05-28
- source: agent-proposal (iter 72 audit; 47% of deployed feed has null neighborhood)
- status: addressed (committed in iter 72)
- body: Audit found 32 of 116 events with `location.neighborhood: null` whose **title** explicitly contained a neighborhood keyword ("Harlem Book Company", "The 9:30 Comedy Show - Williamsburg", "Astoria Speed Dating", "Bushwick Collective"). The address had no neighborhood signal but the title did. `infer_neighborhood` now accepts `*extras` (title + location.name) and the two call sites (`event_parser.build_event` + `normalize._reinfer_neighborhood`) pass them. 8/8 test cases pass including negative tests for "Asian Founders Club" and "Backgammon Club" (no false-positive on "club" or "bk"-inside-Backgammon).
- expected lift: neighborhood coverage rises from 53% to ~66% next scrape; topic-coverage for `bk` / `brooklyn` should also lift since the synonym fold (fb-103/fb-111) now has more events to attach to.

### fb-113 — "Did you go?" feedback on past events (README §362)
- created_at: 2026-05-28
- source: agent-proposal (iter 71; ships the calibration loop the user named as the North Star input)
- status: addressed (committed in iter 71)
- body: Closes the loop between "events the system surfaces" and "events the user actually attends." EventModal now shows a "Did you go? [Yes, I went] [No, I didn't]" block on any event whose `date < today`. Persisted in `nyc-events:attended:v1` localStorage map ({eventId: "yes"|"no"}). Profile bumps: yes = +8 account, +5 category, +3 host (strongest positive signal we have — stronger than save). No = -2 account, -1 category, clamped to 0 to prevent NaN in `interestBoost`'s log2 path. Cap 500 most recent. Shows the previous answer on subsequent opens with a confirmation message.
- next-iteration follow-ups: (a) consider also rendering on FeedCard for past events directly, (b) surface aggregate stats in ActivityPanel ("you've attended N saved events"), (c) feed attended-yes events back into the calibration ask for fb-100.

### fb-112 — WNYC.org is a JS-rendered SPA, no RSS/iCal
- created_at: 2026-05-28
- source: agent-proposal (iter 70)
- status: wont-do: requires JS rendering — not in current scraper toolkit. Out of scope.
- body: Critic suggested probing `wnyc.org/series/wnyc-book-club` (interest_profile `curated_title_hints`). Tested: `/series/wnyc-book-club` and `/series/wnyc-book-club/events` return 404; `/events` is an SPA (the generic scraper SPA-salvage already queues 4 child URLs into `discovered_urls.json` but they're also SPAs with no extractable structure). No `/feeds/events.{rss,atom,ics}` or `/calendar.ics`. WNYC is in the same bucket as Met / Book Club Bar / Time Out — JS-only sites that need a different access pattern.

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
