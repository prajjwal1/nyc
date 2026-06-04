# Self-Improvement Journal

Every `/self-improve` run appends one entry here. Entries are append-only — earlier rounds are read for context but never rewritten.

Entry format:

```
## <YYYY-MM-DD HHMM> — run-id <slug>

**Shipped:**
- <one-liner per landed change, with file path and commit SHA>

**Rejected:**
- <proposal> — <reason>

**Deferred (still in backlog):**
- <item id> — <Critic-accepted reason>

**Metric delta:**
- Follow-graph coverage: <before> → <after>
- Topic coverage: <before> → <after>
- High-conviction event ratio: <before> → <after>

**Hypothesis for next round:**
<one or two sentences>
```

---

<!-- Future runs append below this line -->

## 2026-05-28 15:52 — run-id 2026-05-28-1552

**Shipped:**
- ingestion-P1: treat IG `feedback_required` / rate-limit / checkpoint as transient (not a strike) — `scrapers/sources/instagram.py`. Will revive 54 mass-killed accounts on the next scrape.
- ingestion-P2: source-agnostic `account` alias mirror — `scrapers/sources/instagram.py`. Unblocks the high-conviction metric.
- ingestion-P3 (modified): promote 15 socializing-oriented user_following accounts to `IG_ACCOUNTS` (excluded `timeoutnewyork` per Critic; excluded `alvinzx`/`j_palmer_7`/`leahcanel`/`sophiareed5` per user mid-run feedback fb-106) — `scrapers/config.py`.
- ingestion-P5 (modified): `_looks_like_glued_handle` predicate (safer than the camel-case regex) — `scrapers/sources/instagram.py`.
- ingestion-P6: `bk` ↔ `brooklyn` synonym fold in `interest_profile_boost` — `scrapers/utils/interest_profile.py`.
- source-pool-S1: 9 Brooklyn URLs added to `GENERIC_URLS` (all probed live, yield ≥ 8) — `scrapers/sources/generic.py`.
- ui-U1: card-level sky/amber ring + "Because you follow @X" ribbon on FeedCard + MediaFirstCard — `site/app/components/EventCard.tsx`.
- ui-U2 (modified): glyph-only `★`/`♥` conviction pill on GridCard — `site/app/components/EventCard.tsx`.
- ui-U3 (modified): "location in caption" placeholder gated on `!neighborhood` — `site/app/components/EventCard.tsx`.
- ui-U4 (modified): conviction-first sort in `diversifyByCategory` with `score ≥ maxScore − 0.2` floor — `site/app/components/TopPicks.tsx`.
- Event type: `account?: string` added — `site/app/lib/types.ts`.

**Rejected:**
- ingestion-P4 (lu.ma drop-off via normalize.py): rejected by Critic, replaced by D2. The Critic verified that 60 of 66 `LUMA_PAGES` entries return identical content to `/nyc` — a source-list bug, not a dedup bug. Pruning gated on D1 first.

**Deferred (still in backlog):**
- fb-100: run the user calibration ask next round. Critic-accepted (first-run, no real conviction events to anchor the question).
- fb-105 (D1): curator-calendar lu.ma path probing script (`scrapers/maintenance/probe_luma_curators.py`). Critic-accepted (scope of this round was the in-pipeline fixes; one-off maintenance script next round).
- fb-104 (D2): prune redundant `/nyc/<topic>` URLs from `LUMA_PAGES`. Critic-accepted (blocked-by fb-105 + additive-only rule).

**Mid-run user feedback (now durable as fb-106):**
- User: "we should not be including individual person's account from IG ... only the ones geared towards socializing ... private accounts are off the table"
- Applied immediately: removed `alvinzx`, `j_palmer_7`, `leahcanel`, `sophiareed5` from the in-flight P3 add list. Future agents must filter individual-person accounts before proposing IG_ACCOUNTS additions.

**Metric delta:**
- Follow-graph coverage: 22.2% (12/54) → unchanged this run; structural fixes (P1+P3) will move it on the next CI scrape. P1 will revive **54 transient-killed accounts** which include 6 of 8 priority signal_accounts (`vitalrunclub`, `nycbackgammonclub`, `reading_rhythms`, `bookclubbar`, `midnightrunnersnewyork`, `philosophy.nyc`). Expected to jump to ~80%+ once the next scrape lands.
- Topic coverage (`bk`): 2 → unchanged this run; S1 + P6 will move it on the next CI scrape. Expected to rise to 8+ once Brooklyn URLs are scraped.
- High-conviction event ratio: 3.3% (8/246) → unchanged this run; P2 + the un-deading of 54 accounts will surface more IG events from followed accounts. UI changes (U1/U2/U4) will make the existing 8 conviction events visibly distinguished.

**Hypothesis for next round:**
After the next CI scrape (which will pick up P1's auto-revive of the 54 transient-killed accounts), expect a big jump in IG share + follow-graph coverage. Next `/self-improve` should:
1. Actually run the calibration ask (fb-100) — by then there should be real userFollowing events to show.
2. Ship the curator-calendar probing maintenance script (fb-105).
3. Audit whether the un-deading uncovered any new caption-fragment patterns now that more posts flow.


## 2026-06-04 19:04 — run-id 2026-06-04-1904

**Shipped (commit 9eb458e):**
- ingestion-P1: OCR-garbage title detector `_looks_like_ocr_garbage` wired into `quality._is_caption_fragment` — purges glyph-artifact IG-story titles (`6» GOLIVIACRANDALL *ASTaa}`, `AA Mi, ill il th`, etc.).
- ingestion-P2 (MODIFIED by Critic): narrative/CTA fragment starters + leading-stray-quote regex in `quality.py`. Critic tightened `throwing `→`throwing a ` and `enter a `→`enter a ballot` for future-feed FP safety. P1+P2 together caught exactly 12 garbage IG titles across the 347-event feed, 0 false positives (verified live).
- ingestion-P3: Meetup group-slug enrichment in `normalize._enrich_provenance_from_url` — the curator handle lives in the URL path (`meetup.com/<slug>`), not the host SLD; folds + membership-checks it. Moves `silentbookclub.nyc` toward yield>0. Verified `jcrunners` etc. don't false-match.
- ingestion-P4: `luma._parse_luma_next_data` — reads `__NEXT_DATA__` for SPA curator calendars (ld+json yields 0 on them). Broad NYC gate (`_is_nyc_address`) + fully defensive parse. `lu.ma/nycbackgammonclub` recovered 0→6 live events; `litclub.nyc` returns [] cleanly.
- source-pool-S1 (MODIFIED by Critic): added `lu.ma/philosophy` to LUMA_PAGES (7 live NYC events, covers `philosophy.nyc`). Critic found it INERT without two deps: (1) hard-dep on P4 (same SPA shape) — both shipped together; (2) added a location-suffix-strip fold in `_user_following_normalized` so the bare `philosophy` slug matches the `philosophy.nyc` signal handle. Enrichment verified firing.
- ui-U1: plain-text `@account` provenance branch on `EventCard.tsx` FeedCard for the 68 cross-source-enriched conviction events (userFollowing + account but no instagramAccount: bookclubbar, readingrhythms-manhattan, nycforfree, silentbookclubnyc). Not the banned prose ribbon; not clickable (avoids empty AccountBanner). Build clean.
- D1 (APPROVE-DREAM): `_infer_time_from_text` fills absent startTime from "doors at 7pm / show starts at 8" body text (earliest plausible 06:00–23:59, fill-only). Wired into `process()` before the late-night filter.

**Rejected:** none this round (Critic APPROVE/MODIFY on all 6 worker proposals).

**Deferred (added to backlog):**
- fb-169 (D2): make `AccountBanner` key on `event.account` so ui-U1's plain handles become clickable per-account routes. Touches a 2nd component; ship after ui-U1 confirmed clutter-free.

**Feedback gate:** CLOSED (last calibration 2026-06-01, inside 7-day throttle; no force-ask). No user question this round.

**Still user-blocked (no code fix possible):**
- IG session 33 days stale (⛔ CRITICAL) → CI IG account-sweep degraded → 38 zero-yield signal accounts + sanity_check "Instagram dominant" CRITICAL (IG=46<50). The dominant cause of low follow-graph coverage. Needs interactive `instaloader --login` + IG_SESSION_B64 secret refresh.
- fb-139 (Reddit OAuth), fb-104 (prune redundant Lu.ma /nyc/<topic> URLs — additive-only rule).

**Metric delta (code-only round; events.json not re-scraped — deltas land on next CI scrape):**
- Follow-graph coverage: 12/50 (24.0%) → 12/50 (24.0%). Next scrape expected ~17/50 (+philosophy.nyc, +nycbackgammonclub, +silentbookclub.nyc, + reading_rhythms/nyc_forfree registering on profile rebuild).
- Topic coverage: 4/4 → 4/4 (stable).
- High-conviction ratio: 105/347 (30.3%) → 105/347 (30.3%). Next scrape: P1+P2 remove 12 OCR/caption-garbage IG titles (precision up), P3/P4/S1 add genuinely-followed non-IG events.

**Hypothesis for next round:**
After the next CI scrape, follow-graph coverage should tick up from the 3 newly-enriched non-IG accounts (philosophy/backgammon/silentbookclub) even with the IG session still stale — proving the non-IG enrichment lever works independent of the IG bottleneck. The binding constraint remains the IG-session refresh (user-blocked). Next run should re-audit the top-of-feed after the OCR purge lands and consider whether a story-specific title-quality floor is warranted (ingestion open question #4).
