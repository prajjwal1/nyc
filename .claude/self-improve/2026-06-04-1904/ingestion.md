# Ingestion Quality Report — 2026-06-04 1904

## Metrics observed (against /tmp/deployed.json, 347 events)
- Follow-graph coverage (yield_map > 0): 12 / 50 (24%) — confirms metrics-before.
- High-conviction event ratio: 105 / 347 (30.3%) — confirms metrics-before.
- Source distribution: eventbrite 100, instagram 46, nycforfree 40, meetup 29, songkick 25, bookclubbar 17, lizsbookbar 16, newyorkcomedyclub 15, allevents 13, luma 10, eastvillecomedy 10, brooklyncomedy 9, powerhousearena 6, partiful 3, nypl 3, thebellhouseny 2, smorgasburg 2, greenwoodcemetery 1.
- IG breakdown: 46 IG events = 38 from `/stories/`, 6 from `/p/`, 0 reels. The 38 story events are the dominant top-of-feed quality problem — ~30 of them have OCR-garbage or caption-fragment titles yet score high because the userFollowing boost dominates.
- Leak regexes that came back CLEAN (no matches): late-night/nightclub, professional-networking, excluded `title_hints` (rave/dj marathon/speed dating/ai), events past 2026-12. No date misparses.

## Directive 1 — Leak audit on the top-of-feed (root cause: IG-story OCR)

Five of the top-17 events by score are IG-story OCR garbage / caption fragments sitting at score 1.0 because they come from followed/curated accounts. Root cause: `quality.py::_is_caption_fragment` matches *literal* caption starters, and `_title_quality` only nukes <8/>100 chars or trailing-punct; neither catches random OCR character runs or these specific narrative openers. `ranking.py:48-53` already nukes anything `_is_caption_fragment` flags or `title_quality<0.3` to 0.0 — so tightening those two predicates is the correct, source-agnostic lever (fb-011).

Leaks found (title | score | source | account):
- `6» GOLIVIACRANDALL *ASTaa} see x` | 1.000 | instagram | center4fiction  (OCR garbage)
- `Gh / ead books from 2017` | 1.000 | instagram | litclub.nyc  (OCR fragment)
- `' Things making me happy` | 1.000 | instagram | litclub.nyc  (leading-quote caption fragment)
- `Not able to join us tonight for @ramonaausubel’s` | 1.000 | instagram | center4fiction  (narrative opener)
- `Throwing a sober Y2K party` | 0.969 | instagram | (brightnightssocial story)  (narrative opener)
- `AA Mi, ill il th` | 0.929 | instagram | -  (OCR garbage)
- `Dryeet Sony * —s ———«` | 0.878 | instagram | greenpointers  (OCR garbage)
- `Invited! —— GREENPOINT ——` | 0.798 | instagram | greenpointers  (OCR garbage)
- `Enter a ballot for free tickets to watch a mixed` | 0.763 | instagram | nyc_forfree  (CTA caption)
- `A N Fr SA ‘ @flowercatnyc` | 0.749 | instagram | omgreenpoint  (OCR garbage)
- `House of @demaf.us starts tomorrow` | 0.733 | instagram | nyc_forfree  (caption fragment)
- `below. Registration ends on June 24! @ 7` | 0.623 | instagram | omgreenpoint  (sentence-continuation fragment)
- `iconic soccer hairstyles @) &` | 0.535 | instagram | nyc_forfree  (caption fragment)
- `Enter to win a pair of tickets to see @scarymovie!` | 0.564 | instagram | -  (giveaway CTA)

### ingestion-P1 — Add an OCR-garbage detector to `_is_caption_fragment`
- **Metric moved**: top-of-feed quality (leak audit) + high-conviction ratio precision (purges 5 garbage-titled events that currently inflate the followed-account count).
- **File**: `scrapers/quality.py` — add helper near `_is_caption_fragment` (after line ~707) and call it at the top of `_is_caption_fragment` (return True if it fires).
- **Change** (exact logic, verified against the full 347-event feed):
  ```python
  _OCR_COMMON_SHORT = {"a","i","to","of","in","on","at","an","is","no","we","my","ok",
      "so","up","by","x","vs","am","pm","st","nd","rd","th","dj","ny","us","go","do",
      "if","as","or","be","it","he","me"}

  def _looks_like_ocr_garbage(title: str) -> bool:
      t = (title or "").strip()
      words = t.split()
      if len(words) < 3:
          return False
      # Strong OCR-artifact glyph signatures.
      if re.search(r"[»«}{]|———|\*[A-Z]{2,}", t) or re.search(r"\b[A-Z]{6,}[a-z]", t):
          return True
      # Fallback: high fraction of stray 1-2 char non-word tokens / symbol tokens.
      noise = 0
      for w in words:
          a = re.sub(r"[^A-Za-z]", "", w)
          if not a:
              if re.fullmatch(r"[&]+", w) or re.fullmatch(r"[\d\$.,:/&+-]+", w):
                  continue
              noise += 1; continue
          if re.search(r"\d", w):
              continue
          wl = w.lower().strip(".,!?'’‘")
          if len(a) <= 2 and wl not in _OCR_COMMON_SHORT:
              noise += 1
      return noise / len(words) >= 0.45
  ```
  Then in `_is_caption_fragment`, before the `fragment_starts` loop: `if _looks_like_ocr_garbage(title): return True`.
- **Catches**: `6» GOLIVIACRANDALL *ASTaa} see x`, `AA Mi, ill il th`, `Dryeet Sony * —s ———«`, `Invited! —— GREENPOINT ——`, `A N Fr SA ‘ @flowercatnyc` (5 events).
- **False-positive check**: ran across all 347 titles → exactly those 5 match. Verified it does NOT hit `Omar ؏ - Omar’s World`, `40s & Over Singles Party`, `iconic soccer hairstyles @) &`, `Wine, Explained: A Guided Tasting`, `Book Club² - "The Heaven & Earth Grocery Store"`, or any legit title.
- **Risk**: low. The `noise>=0.45` threshold requires the majority of tokens to be junk; the glyph signatures (`»«}{`, `———`, `*CAPS`, 6+ glued caps) are OCR artifacts that essentially never appear in real event names.

### ingestion-P2 — Add 6 narrative/CTA fragment starters + leading-quote regex to `_is_caption_fragment`
- **Metric moved**: top-of-feed quality; removes the two score-1.000 leaks (`Not able to join…`, `' Things making me happy`) plus 4 more.
- **File**: `scrapers/quality.py::_is_caption_fragment`.
- **Change A** — append these literals to the `fragment_starts` list (they are matched via the existing `startswith` + `_strip_leading_decoration` machinery, so curly-quote/emoji-led variants are already handled):
  - `"not able to"` — catches `Not able to join us tonight for @ramonaausubel’s` (1.000)
  - `"throwing "` — catches `Throwing a sober Y2K party` (0.969)
  - `"enter to win"`, `"enter a "` — catches `Enter to win a pair of tickets…` (0.564), `Enter a ballot for free tickets…` (0.763)
  - `"house of @"` — catches `House of @demaf.us starts tomorrow` (0.733); the trailing `@` scopes it to handle-glued captions so it can't hit a real "House of X" venue title.
  - `"below."` — catches `below. Registration ends on June 24! @ 7` (0.623)
- **Change B** — add a leading-stray-quote regex right after the `fragment_starts` block (where the other `re.match` fragment checks live, ~line 913):
  ```python
  # Leading stray apostrophe/quote + space + word: "' Things making me happy"
  # — an OCR-split caption line, never a real title.
  if re.match(r"^['\"’‘]\s+\S", title.strip()):
      return True
  ```
- **Catches/excludes (verified against full feed)**: the 6 starters drop exactly 5 garbage IG titles and ZERO good titles. The leading-quote regex matches exactly 1 title (`' Things making me happy`) across all 347 — no FPs. `below.` matches exactly 1 (the garbage). `enter `/`throwing `/`house of @` matched no legitimate events in the current feed.
- **Risk**: low. `"throwing "` could in theory hit a "Throwing Workshop" title, but none exists in the feed; if the Critic wants extra safety, scope to `"throwing a "`. All others are tightly anchored.

> Deliberately NOT proposed: `block party on` (FP risk — a real "Block Party on Bedford Ave" title is plausible; the one leak `block party on June 20! @ &&` is already low-score and will instead be caught by the trailing `@ &&` if the Critic wants a separate trailing-glued-handle rule — flagged as an open question).

## Directive 2 — Lift non-IG follow-graph coverage

Audited all 38 zero-yield signal accounts for a non-IG event path in the live feed. Only **3** have any non-IG presence:
- `nyc_forfree` → 40 nycforfree.co events, ALREADY enriched (`userFollowing:true`). yield_map shows 0.0 only because the profile was built 2026-06-01 from the IG sweep; the live enrichment is firing. No action needed — will register on next profile rebuild.
- `reading_rhythms` → 10 lu.ma events (`account: readingrhythms-manhattan`), ALREADY enriched (`userFollowing:true`). Same stale-profile situation. No action needed.
- `silentbookclub.nyc` → 2 Meetup events from group `meetup.com/silentbookclubnyc/`. ONE is enriched (`Uptown Reading Morning`, account=silentbookclubnyc, following=true), the OTHER is NOT (`Booze & Books in Brooklyn`, account=None, following=false) despite the identical group slug. **Enrichment bug** → P3.

A live Lu.ma probe also surfaced a separate **scraper bug** affecting a 4th account → P4.

The remaining 34 zero-yield accounts have NO non-IG path in the current feed (checked URL path-segments, location.name, organizer against the alphanumeric fold of each handle — zero matches). Live-probed `lu.ma/<handle>` for the bookish/games accounts: `philosophynyc`, `philosophy`, `thenewyorkgames`, `richardsgamesnyc`, `fortheplotnyc`, `strangersorfriendsbk`, `quietreadingclub`, `openbookclub` all return Lu.ma's ~26KB "calendar not found" shell (no event JSON). **Documented as IG-session-blocked — future runs need not re-investigate these via Lu.ma.**

### ingestion-P3 — Enrich provenance from the Meetup group slug in the URL path
- **Metric moved**: follow-graph coverage (moves `silentbookclub.nyc` toward yield>0 via a non-IG path) + high-conviction ratio (the `Booze & Books` event gains `userFollowing`).
- **Root cause**: `normalize.py::_extract_handle_from_url` only reads the hostname SLD. For Meetup, the host SLD is the aggregator `meetup` (rejected); the curator handle lives in the *path* (`meetup.com/<group-slug>/events/…`). So the URL-handle enrichment path can never match a Meetup group. Today only events where the Meetup scraper itself happened to set `organizer`/`account` get enriched — inconsistent per-event.
- **File**: `scrapers/normalize.py::_enrich_provenance_from_url` (after the SLD-handle block, ~line 1170).
- **Change**: before falling through to the organizer/location path, add a Meetup-group-slug extractor:
  ```python
  # Meetup group slug lives in the URL path, not the host. meetup.com/<slug>/events/...
  if not ev.get("userFollowing"):
      mu = re.search(r"meetup\.com/([^/?#]+)", ev.get("sourceUrl") or "", re.I)
      if mu:
          slug = mu.group(1)
          fold = re.sub(r"[^a-z0-9]", "", slug.lower())
          if fold and len(fold) >= 5 and fold in following:
              ev["account"] = slug
              ev["userFollowing"] = True
              _apply_quality_for(ev, fold, quality)
              matched += 1
  ```
  (`following` and `quality` are already in scope; `re` is imported as `_re` in this module — use `_re`.)
- **Live-probe evidence**: `meetup.com/silentbookclubnyc/` folds to `silentbookclubnyc`, which is in the user-following set (matches signal account `silentbookclub.nyc` via the alphanumeric fold). The `Booze & Books in Brooklyn` event (currently account=None, following=false) would gain account=`silentbookclubnyc` + `userFollowing:true`.
- **False-positive check**: applied the fold to all 25 distinct Meetup group slugs in the live feed (thewritinggroup, jcrunners, nyc-fun-run, runningsouls-net, reading-philosophy, books-and-restaurants, etc.) → the ONLY slug that matches the following set is `silentbookclubnyc`. Zero false positives. The `len(fold)>=5` guard mirrors the existing organizer-match guard.
- **Risk**: low. Purely additive enrichment on non-IG events that lack provenance; gated on an exact membership test against the (excluded-handles-removed) following set.

### ingestion-P4 — Parse Lu.ma curator-calendar events from `__NEXT_DATA__` (recovers NYC Backgammon Club)
- **Metric moved**: follow-graph coverage (`nycbackgammonclub` is signal account, yield 0.0) + topic coverage (`games`) + high-conviction ratio (6 new userFollowing events via the existing `lu.ma/nycbackgammonclub` enrichment at normalize.py:1141).
- **Root cause**: `luma.py::_parse_luma_page` only reads `<script type="application/ld+json">` (0 present on curator-calendar pages) and a CSS `event-card` fallback (no match on the un-rendered SPA). Lu.ma curator calendars embed their event roster in `<script id="__NEXT_DATA__">`. Result: `lu.ma/nycbackgammonclub` (in LUMA_PAGES since iter, line 85) silently yields **0 events** even though 6 are live. The only "backgammon" event in the deployed feed is an unrelated IG OCR false-positive (`Brunch is for the gals!!! Let's make some` — backgammon is in its *description*), which is the sole reason `sanity_check.py`'s "NYC Backgammon Club ≥1" assertion isn't already failing.
- **File**: `scrapers/sources/luma.py::_parse_luma_page` (add a `__NEXT_DATA__` fallback, after the ld+json loop, before the `_parse_luma_html` fallback at line 173).
- **Change** (sketch — Critic to confirm exact build_event wiring; reuses existing `parse_iso_to_local` / `parse_date` / `build_event`):
  ```python
  if not events:
      import re as _re
      m = _re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, _re.S)
      if m:
          try:
              data = json.loads(m.group(1))
          except Exception:
              data = None
          if data:
              events.extend(_parse_luma_next_data(data, source_url))
  ```
  with a new `_parse_luma_next_data` that walks the JSON for dicts having `name` + `start_at`, then maps:
  `name→title`, `start_at` (ISO UTC) → `parse_iso_to_local` → date+start_time, `end_at`→end_time,
  `geo_address_info.full_address`/`.address`→location_name+address (city="New York" gate to keep it NYC),
  `cover_url`→image, `url`→`https://lu.ma/<slug>` (skip if slug empty). Dedupe by event `api_id`.
- **Live-probe evidence**: `lu.ma/nycbackgammonclub` `__NEXT_DATA__` contains 6 dated NYC events: Midtown Backgammon Night (6/8), Chouette Backgammon (6/9), Soho Diner Backgammon Night (6/15), Backgammon Night for Singles (6/16), Spring Place Backgammon Night (6/23), Gals Who Gammon Backgammon Brunch (6/27). Each has full `geo_address_info` (e.g. "Astro, 1361 6th Ave, New York, NY 10019"), `cover_url`, `start_at`/`end_at`. Probed all 6 curator calendars in LUMA_PAGES: backgammon=6, founderscoffee=1, litclub/thinkolio/cinemaclub=0 currently (no upcoming or different shape — harmless). `readingrhythms` already yields 10 via cross-listing on the broad `/nyc/literary` discover page, which is why it works today and backgammon doesn't.
- **False-positive check**: the NEXT_DATA walk is gated on `name` + `start_at` + a parseable date; NYC gate via `geo_address_info.city == "New York"` (or address contains "New York"/"NY") prevents pulling a curator's out-of-town events. The existing curator-handle enrichment (normalize.py:1141, which already names `lu.ma/nycbackgammonclub`) will tag these 6 with `userFollowing` once they exist.
- **Risk**: medium-low. New parse path; must be defensive (wrapped in try/except, per-event date validation). Generalizes to ALL curator calendars in LUMA_PAGES, not per-site (fb-011). Run `sanity_check.py` after the next scrape — the backgammon assertion will then pass for the right reason.

## Directive 3 — Other observations
- High-quality non-IG sources are extracting cleanly: Lu.ma 10/10 with time+loc, Partiful 3/3 complete, Eventbrite 100 events with only 2 missing startTime and 0 missing location. No fixable extraction patterns found there this round.
- `nyc_forfree` and `reading_rhythms` are a measurement artifact, not a bug: their live events are correctly enriched to `userFollowing:true`; the yield_map=0.0 is just the stale 2026-06-01 profile snapshot. The follow-graph metric will rise on the next `interest_profile.py` rebuild regardless of this round's code — worth noting so the Critic doesn't attribute the future delta solely to P3/P4.

## Directives addressed
- Directive 1 (leak audit): ADDRESSED. 14 leaks found at top-of-feed, all IG-story OCR/caption garbage; P1 (OCR-garbage detector) + P2 (6 starters + leading-quote regex) purge the high-scoring ones with verified zero false positives across all 347 titles.
- Directive 2 (lift non-IG follow-graph coverage): ADDRESSED. P3 (Meetup-slug enrichment → `silentbookclub.nyc`) + P4 (Lu.ma NEXT_DATA → `nycbackgammonclub`) move 2 accounts toward yield>0 via non-IG paths; `nyc_forfree` + `reading_rhythms` are already non-IG-enriched (stale-profile artifact). The other 34 are documented IG-session-blocked (no non-IG path exists — Lu.ma handle probes returned the not-found shell).
- Directive 3: minor — confirmed non-IG sources extract cleanly; no additional fixes.

## Hard-rule compliance
- No IG_ACCOUNTS / LUMA_PAGES / GENERIC_URLS additions or deletions proposed. All four proposals are additive predicate/parser logic. `nycbackgammonclub` is ALREADY in LUMA_PAGES — P4 fixes the parser, not the source list.
- Checked `user_excluded_sources.json`: none of the affected accounts (`silentbookclub.nyc`, `nycbackgammonclub`) are excluded; no excluded venue/title-hint is being re-admitted.
- fb-106: no individual-person accounts touched. `silentbookclub.nyc` and `nycbackgammonclub` are socializing entities.
- No MIN_SCORE / threshold changes.
- Every regex/keyword tested against the live 347-title feed before being written down (FP counts reported per proposal).

## Open questions for the Critic
- P2: keep `"throwing "` or tighten to `"throwing a "`? No FP in the current feed, but a real "Throwing Workshop" (pottery) is conceivable. I lean tighten.
- P2: I dropped `block party on` (FP risk). The remaining `block party on June 20! @ &&` and `below. Registration … @ 7` both end in a glued-handle artifact (`@ &&`, `@ 7`). Worth a separate trailing `\s@\s*[&\d]{1,3}$` fragment rule, or is that over-fitting to two examples? I left it out.
- P4: confirm the NEXT_DATA NYC gate. Using `geo_address_info.city == "New York"` keeps it tight, but a curator could list a Jersey City event with city="Jersey City" that the user still wants. Current LUMA_PAGES curator calendars are NYC-focused so this is low-stakes; flagging the choice.
- Structural: 38/46 IG events are `/stories/` OCR, the bulk of which are low-quality even after P1/P2. Is there appetite (future round) for a story-specific title-quality floor (e.g. require a real ld+json/caption-derived title for `/stories/` URLs, not raw OCR), or is that too aggressive while the IG session is the binding constraint? Not proposed this round.
