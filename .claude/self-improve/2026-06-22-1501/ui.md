# UI Report — 2026-06-22 1501

## Audit notes

Round lens: do recurring run clubs / repeated-title Brooklyn Contra dances render
gracefully, and is price/venue/date surfaced for fitness + dance events?

- **High-conviction signal currently visible in:** `EventCard.tsx` FeedCard
  (sky ring + inset bar for `userFollowing`, amber for `userAffinity`); `TopPicks.tsx`
  "★ Following" and "★ Saved by you" hero sections; `AccountBanner.tsx` per-account
  filter view. Signal is well-surfaced — no gap this round.
- **Components surfacing follow-graph provenance:** EventCard (clickable `@account`
  for both IG and cross-source-enriched handles, fb-169), TopPicks Following hero,
  AccountBanner. Contra + most run-club events have NO `instagramAccount` and are not
  conviction events, so they correctly fall through to the `SOURCE_LABELS` source label
  ("Brooklyn Contra", "Meetup") — provenance is honest, nothing to add.

### Recurring / repeated-title rendering (the round's central question)

I traced the data path end-to-end. Conclusion: **the feed already handles both cases
gracefully — no collapse/grouping affordance is warranted.**

- **Brooklyn Contra dances:** the scraper (`scrapers/sources/brooklyncontra.py`) emits each
  dance as a distinct dated event, embeds the date in `_parse_date_from_title`, sets
  `startTime`/`endTime`/`price`/`location.name`, and does **NOT** set `recurring`. They also
  share one `sourceUrl` (the store URL) but are de-duped by `(date, title)` at scrape.
  `normalize.py` `DISTINCT_SCHEDULE_SOURCES = {"brooklyncontra"}` exempts them from the
  same-account recurring merge (load-bearing per fb-180 — do not touch).
  - In `TopPicks.tsx`, `collapseRecurring()` only collapses events where `e.recurring`
    is truthy (line 27-28: `if (!e.recurring) { out.push(e); continue; }`). Contra events
    have `recurring` unset → they are **never collapsed**, so the full schedule shows. Good.
  - They render under per-date headers in the main date-grouped feed, so the identical
    titles ("Brooklyn Contra Dance — Live Music & Caller") are disambiguated by the date
    header above them. Not a wall of identical cards. Good.
  - Hero exposure is bounded: contra is `["dance","music"]` → low-key-social, so at most
    the soonest weekend dance lands in "This Weekend" (hero caps at 6, one weekend window).
    No stacking. Good.
- **Recurring run clubs** (via `detect_recurring_weekday` → `expand_recurring_event`)
  DO get `recurring=true` on each occurrence (event_parser.py:971). So in the feed,
  `collapseRecurring` keeps only the **soonest** occurrence per (title, account) pair —
  exactly the desired "show variety, not 6 identical run-club cards" behavior. Good.
- Net: a deliberate split — contra shows the **full schedule** (each night is a distinct
  product/decision), run-clubs **collapse to soonest** (weekly cadence, one is enough).
  This is the correct minimal-but-complete treatment. **No grouping UI needed.**

### Required-detail gaps found

- **Price is invisible on the feed card for paid events.** `EventCard.tsx` FeedCard
  renders a price badge ONLY when `event.price === "free"` (line 222). Every paid event —
  contra dances ($15), paid run-club drop-ins, fitness classes — shows no price at a glance.
  `EventModal.tsx` already renders non-free price (lines 172-176), so the card is the only
  surface missing it. For this round's fitness/dance theme (frequently paid), "is this $15
  or $40?" is a top-of-glance decision input. This is the one genuine missing-but-required
  detail. (Time, venue, neighborhood, provenance, ★/× are all already on the card.)

### Clutter / preference violations

- None found. No empty gray gradient boxes (image block is conditional on `event.imageUrl &&
  !imgFailed`, fb-008 respected). Left sidebar is view-toggle + Calendar only (fb-007
  respected). "This Weekend" hard-excludes parties/nightlife/rave text (§516 respected).
  Category chips already removed. The card is tight.

## Proposals

### U1: Show non-free price as a small badge on the feed card
- **Metric moved**: required-detail surfacing (directly serves the fitness/contra theme —
  these events are usually paid; the card currently hides it).
- **Component(s)**: `site/app/components/EventCard.tsx` (FeedCard), insert after line 226
  (the existing `event.price === "free"` block) inside the same badge row.
- **localStorage key (if any)**: none.
- **Change sketch**:
  ```tsx
  {event.price === "free" && (
    <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-100 text-emerald-800">
      FREE
    </span>
  )}
  {/* U1: surface a concrete paid price (e.g. contra "$15", class drop-ins).
      Modal already shows this; the card was the only missing surface.
      Guard against the noise values so we never render "$unknown"/"$varies". */}
  {event.price && event.price !== "free" && event.price !== "unknown" &&
    event.price !== "varies" && /\d/.test(event.price) && (
    <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-gray-100 text-gray-700">
      {event.price.startsWith("$") ? event.price : `$${event.price}`}
    </span>
  )}
  ```
- **Rationale**: makes the price an at-a-glance signal for the paid fitness/dance events this
  round adds, with zero new chrome (reuses the existing badge row + modal's guard logic).
- **Risk**: price strings are free-form across sources. The `/\d/.test()` + `unknown`/`varies`
  guards keep us from rendering junk; mirrors the modal's existing predicate (EventModal.tsx:172)
  so behavior is consistent. Worst case a malformed string renders verbatim in a gray pill —
  benign, no layout break (badge row already wraps with `flex-wrap`).

## Recommendation: otherwise a near-no-op UI round

The recurring/contra rendering is already correct by construction (verified the full
scraper → normalize → TopPicks path above). No collapse affordance, "recurring" badge, or
grouping widget is warranted — adding one would be chrome the user did not ask for and would
duplicate the date-header context. Per prior journal precedent, a minimal UI round (one
required-detail fix, no new widgets) is the right call. U1 is the only change I'd ship.

## Directives addressed
- **fb-179 (fitness/run-clubs)**: UI verified — recurring run clubs collapse to the soonest
  occurrence via `collapseRecurring` (no near-identical card wall); price now surfaced on the
  card (U1). Feedback designated UI as no-op for fb-179; confirmed the frontend handles the
  expansion gracefully and added the one missing detail (price).
- **fb-180 (Brooklyn Contra)**: UI verified — distinct dated dances render as a full schedule
  under per-date headers, never collapsed (they lack `recurring`), bounded in heroes. Price
  ($15) and venue surfaced (U1 + existing venue/time render). No frontend change needed to
  keep the DISTINCT_SCHEDULE_SOURCES exemption working; confirmed TopPicks does not re-collapse.
- **fb-181 (`'rave'` substring exclusion)**: backend/ingestion (exclusion filter in scrapers).
  Out of UI scope. NOTE: the UI `NEGATIVE_TEXT` regex in TopPicks (line 260) already uses a
  word-boundary `\brave\b` for the "This Weekend" filter, so the UI side is already correct —
  the bug is purely in the ingestion title-exclusion filter.

## Open questions for the Critic
- U1 price guard: I mirrored the modal's predicate (`!== "unknown"`) and added `!== "varies"`
  + a `/\d/` digit check. If the feed carries other sentinel price strings (e.g. "TBD",
  "donation"), they'd be filtered by the digit check — is suppressing "donation"/"pay what you
  can" acceptable, or should those render as a literal pill? I lean suppress (digit-only) to
  guarantee no junk; flag if you'd rather show qualitative price words.
- No-op confirmation: I'm asserting the contra/run-club rendering needs nothing beyond U1.
  If the Critic wants a visible "recurring/weekly" hint on run-club cards, the minimal form
  would be a single `event.recurring && <span>weekly</span>` pill — but I recommend against it
  (date header already carries the date; the user asked for events, not a schedule legend).
