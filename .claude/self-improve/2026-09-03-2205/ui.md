# UI Report — 2026-09-03 2205

## Audit notes

- **Rendered/build audit:** the current Next.js 16.2.4 static export builds successfully (616 pages). Direct live-feed access was unavailable from this environment, so the event-detail audit used the checked-in production snapshot (`site/public/events.json`, 556 events, `lastUpdated=2026-08-28T18:04:42Z`). Chromium visual capture is still blocked before page load by the known macOS Mach-port denial, so the final implementation needs CI/browser screenshots at 390×844 and 1280×900.
- **`Header.tsx` (`site/app/components/Header.tsx:84-153`):** does not need event-level conviction; it clearly exposes inventory, freshness, and new-since-last-visit. On mobile its actions plus the second homepage introduction consume valuable above-the-fold space.
- **`FilterBar.tsx`:** absent, intentionally. This preserves the explicit no-search homepage preference.
- **`Calendar.tsx` (`site/app/components/Calendar.tsx:47-138`):** clearly communicates event density and the selected date. It does not surface conviction, which is appropriate, but its padding/row height plus the redundant page introduction delays the first event on a 390px-wide screen.
- **`EventList.tsx` (`site/app/components/EventList.tsx:17-44`):** clearly shows selected date and event count, but its generic gray heading does not visually connect to the editorial palette used elsewhere.
- **`EventCard.tsx` (`site/app/components/EventCard.tsx:145-395`):** currently the strongest decision surface. It shows title, time when known, venue/neighborhood fallback, price, recommendation reason, source/account, ★ save, calendar, and × hide. High-conviction follow events have both a blue rail and a textual `★ following` chip. Gaps: affinity can remain color-only; follow provenance is often repeated three times; unknown time is silent; the `Williamsburg` proximity pill is ambiguous; and the three 16px action icons have undersized touch targets.
- **`EventModal.tsx` (`site/app/components/EventModal.tsx:143-400`):** surfaces full date/time, address, neighborhood, price, provenance, source, Save/Calendar/Share/Hide, and cross-source confirmation. It is complete but visually more generic/grayscale than the rest of the site. Do not alter its carousel behavior this round.
- **`TopPicks.tsx`, `TopAccounts.tsx`, `AccountBanner.tsx`:** not present in the current component tree. Do not recreate them. The account-filter chip in `app/page.tsx:160-170` is enough context.
- **`ActivityPanel.tsx`:** still exists but is not mounted. This is correct under fb-007; do not restore it to a sidebar.
- **High-conviction signal currently visible in:** `EventCard` (rail + following/taste chips), `EventModal` (highlight/recommendation chips), and static event detail pages. It is not summarized at calendar/date level, which is acceptable.
- **Components surfacing follow-graph provenance:** `EventCard`, `EventModal`, and event detail pages. The card is the key surface, but its message is fragmented between the reason line, following chip, and footer account.
- **Required-detail gaps found from representative events:**
  - `KIKO Milano SoHo Grand Opening`: no start time; the card currently shows nothing instead of an honest `Time TBA` cue.
  - `M+C Summer Happy Hour`: blank venue name; the neighborhood fallback correctly shows Long Island City, so preserve this behavior.
  - `Collector Park by OpenSea & Pudgy Penguins`: `Manhattan` is the only location precision available; the UI should not invent a neighborhood or distance.
  - `Shelly Jay Shore Brooklyn Event for Love Me Like a Rock Song`: useful literary organizer provenance exists, but non-follow organizer identity is reduced to generic `Eventbrite` in the card footer.
  - `L'Oréal Paris Gloss Clubhouse`: `nycforfree` follow provenance currently appears as recommendation text + `★ following` + `@nycforfree`, creating duplication rather than one decisive explanation.
  - `Parra for Cuva @ Ballroom, Arlo Williamsburg`: the existing `nearby` highlight renders only `Williamsburg`; `Near Williamsburg` would state why the location matters.
  - Exact travel distance is not present in `EventLocation` (`site/app/lib/types.ts:1-5`). Do not fabricate minutes/miles; use the existing proximity highlight until coordinates or travel-time data exist.
- **Clutter / preference violations:**
  - `app/page.tsx:154-171` repeats the already-obvious calendar purpose with an eyebrow, second `<h1>`, and explanatory sentence before the calendar and before `EventList` repeats the selected date. This is the main mobile hierarchy problem.
  - Following events can show the same preference fact in three adjacent places (`recommendationReasons[0]`, `★ following`, account footer).
  - Card source/likes/actions share one tiny 10px row; this makes provenance and actions compete on mobile.
  - No forbidden sidebar widgets, free-text search, empty event-image placeholder, or party-heavy weekend hero are present. Preserve those absences.

## Proposals

### U1: Put the first event closer to the fold

- **Metric moved:** clutter reduction / required-detail surfacing
- **Component(s):** `site/app/page.tsx:153-181`, `site/app/components/Calendar.tsx:47-138`, `site/app/components/EventList.tsx:17-24`
- **localStorage key (if any):** none
- **Change sketch**:
  ```tsx
  // page.tsx: remove the Calendar / Choose a date explainer block.
  <main className="mx-auto max-w-5xl px-4 py-3 sm:px-6 sm:py-6">
    {accountFilter && <AccountFilterChip />}
    <div className="grid gap-4 lg:grid-cols-[20rem_minmax(0,1fr)] lg:gap-6">
      <aside className="lg:sticky lg:top-20 lg:self-start"><Calendar ... /></aside>
      <section aria-label="Events for selected date"><EventList ... /></section>
    </div>
  </main>

  // Calendar.tsx: compact only the phone layout; keep the desktop rhythm.
  <div className="rounded-[1.5rem] border ... p-3 sm:p-4">
  <button className="... h-8 sm:h-9 ...">...</button>

  // EventList.tsx: let the selected day be the single section heading.
  <h2 className="font-editorial text-xl font-bold text-[#173c35]">{dateLabel}</h2>
  <span className="rounded-full bg-[#eee8da] px-2.5 py-1 text-xs text-[#66716c]">...</span>
  ```
- **Mobile:** removes the duplicate ~100px introduction and tightens the month grid so at least the first event title/action area begins near the initial viewport.
- **Desktop:** keeps the sticky 20rem calendar and two-column composition; only the redundant heading disappears.
- **Rationale:** the user reaches an actual event sooner without adding a feed, search bar, or widget.
- **Risk:** the account-filter chip must remain visible and clearable after the intro wrapper is removed; preserve `?date` and `?account` URL behavior.
- **Verification:** at 390×844 and 1280×900, assert no horizontal overflow, one page-level `<h1>`, selected-date `<h2>` present, calendar controls reachable, account chip clears, and the first card appears earlier than baseline.

### U2: Consolidate conviction into one explicit provenance chip

- **Metric moved:** high-conviction signal visibility / clutter reduction
- **Component(s):** `site/app/components/EventCard.tsx:145-159`, `site/app/components/EventCard.tsx:239-273`, `site/app/components/EventCard.tsx:326-363`
- **localStorage key (if any):** none
- **Change sketch**:
  ```tsx
  const provenanceAccount = event.instagramAccount || event.account;
  const provenance = event.userFollowing
    ? `★ Following${provenanceAccount ? ` @${provenanceAccount}` : ""}`
    : event.userSaved
      ? "★ Saved by you"
      : event.userAffinity
        ? "✨ From accounts you save"
        : null;

  {provenance && (
    provenanceAccount && onAccountClick ? (
      <button onClick={filterAccount} className="relative z-10 max-w-full truncate rounded-full bg-sky-100 px-2 py-1 text-[11px] font-semibold text-sky-900">
        {provenance}
      </button>
    ) : <span className="rounded-full bg-sky-100 px-2 py-1 text-[11px] font-semibold text-sky-900">{provenance}</span>
  )}
  {!provenance && event.recommendationReasons?.[0] && <RecommendationReason />}
  ```
- **Mobile:** the compact, truncating chip states both why the event is special and which followed account caused it; the footer can show the source instead of repeating the same handle.
- **Desktop:** retains the existing conviction rail but makes it independently understandable without relying on border color.
- **Rationale:** turns the product's strongest differentiator into one legible explanation rather than three weak repetitions, and gives affinity/saved signals a non-color treatment too.
- **Risk:** organizer names are not handles. Prefix `@` only for `instagramAccount`/`account`, never for `organizer`; preserve account filtering only when the filterable account field exists.
- **Verification:** fixture-test following, saved, affinity, and neutral cards; assert exactly one conviction explanation per card, correct `@` handling, keyboard focus on clickable provenance, and no source/footer wrap at 390px.

### U3: Make time and proximity scan anchors

- **Metric moved:** required-detail surfacing
- **Component(s):** `site/app/components/EventCard.tsx:202-231`, `site/app/lib/types.ts:85-105`
- **localStorage key (if any):** none
- **Change sketch**:
  ```tsx
  <div className="mt-1.5 flex min-w-0 flex-wrap items-center gap-1.5 text-xs">
    <span className={`rounded-full px-2 py-1 font-semibold ${timeStr ? "bg-[#edf5f1] text-[#173c35]" : "bg-[#f1ede3] text-[#8b918e]"}`}>
      {timeStr || "Time TBA"}
    </span>
    {placeName && (
      <span className="flex min-w-0 items-center gap-1 text-[#5d6964]">
        <PinIcon /><span className="truncate">{placeName}</span>
        {showNeighborhood && <span className="shrink-0 text-[#8b918e]">· {event.location.neighborhood}</span>}
      </span>
    )}
  </div>

  // HIGHLIGHT_CONFIG
  nearby: { label: "Near Williamsburg", color: "bg-teal-100 text-teal-800" },
  ```
- **Mobile:** time becomes the first stable visual anchor; venue remains truncatable and a missing time is explicit rather than looking like a rendering omission.
- **Desktop:** the same compact decision line improves vertical scanning without increasing card height materially.
- **Rationale:** time and travel relevance are the first attendance decisions. This exposes the truth already in the feed without inventing distance data.
- **Risk:** `Time TBA` could become repetitive on low-quality sources; keep it subdued, never infer a time, and retain the text-only card behavior when no image exists.
- **Verification:** render known-time, unknown-time, blank-venue/neighborhood-only, long-venue, and `nearby` fixtures at both viewports; assert no overflow and only one proximity pill.

### U4: Make ★ / calendar / × actions trustworthy on touch and honor Hide immediately

- **Metric moved:** clutter reduction / personalization signal quality
- **Component(s):** `site/app/components/EventCard.tsx:326-395`, `site/app/hooks/useEvents.ts:45-61`
- **localStorage key (if any):** existing `nyc-events:hidden:v1`, `nyc-events:interests:v1` only; no schema/version change
- **Change sketch**:
  ```tsx
  // useEvents.ts: hidden choices apply to Calendar as well as /events.
  import { ..., isHidden } from "../lib/interests";
  const upcoming = data.events.filter(stillUpcoming).filter((event) => !isHidden(event.id));

  // EventCard.tsx: separate provenance from an accessible action group.
  <div className="mt-2 flex items-center justify-between gap-2 border-t border-[#eee9dc] pt-2">
    <span className="min-w-0 truncate text-[10px] uppercase tracking-wide text-[#8b918e]">{sourceLabel}</span>
    <div className="relative z-10 flex shrink-0 items-center gap-0.5">
      <button className="grid min-h-9 min-w-9 place-items-center rounded-full hover:bg-amber-50 focus-visible:ring-2 ..." aria-label="Save">...</button>
      <button className="grid min-h-9 min-w-9 place-items-center rounded-full hover:bg-[#edf5f1] focus-visible:ring-2 ..." aria-label="Add to calendar">...</button>
      <button className="grid min-h-9 min-w-9 place-items-center rounded-full hover:bg-rose-50 focus-visible:ring-2 ..." aria-label="Hide">...</button>
    </div>
  </div>
  ```
- **Mobile:** 36px controls are materially easier to hit, stay separate from the full-card link, and no longer compete with provenance text.
- **Desktop:** the thin divider gives every card a consistent action baseline without introducing a toolbar widget.
- **Rationale:** save/hide are the site's direct substitutes for Instagram feedback; immediate removal makes the learning loop perceptible and reduces unwanted inventory.
- **Risk:** `PROFILE_CHANGE_EVENT` must trigger recomputation after hide (it already does through `hideEvent`); avoid double-removing or changing any `:v1` schema.
- **Verification:** click × on the homepage and assert the card disappears immediately and remains absent after reload; verify ★ and calendar do not open the card; tab through all three controls; check 390px cards do not wrap or clip.

## Directives addressed

- **fb-212:** U1–U4 form one coherent responsive pass: less preamble, stronger decision hierarchy, explicit personalization, and touch-safe feedback controls.
- **fb-210 / fb-211:** the report preserves the visible freshness timestamp and explicitly requires the final visual QA to use the newly refreshed feed rather than the August 28 snapshot.
- **fb-208:** U2 makes inferred/follow/save/affinity provenance legible without adding generic-popularity UI.
- **fb-007:** no sidebar widget is added; `TopAccounts` and `ActivityPanel` remain unmounted.
- **fb-008:** every proposal preserves text-only rendering when artwork is absent.
- **fb-009:** no weekend hero is introduced.
- **fb-010:** all interactions remain client-side and retain existing `nyc-events:*:v1` keys.

## Recommended implementation order

1. **U1 + U2 + U4** — together they satisfy the requested meaningful design improvement with the highest decision-making and personalization payoff.
2. **U3** — include if `Time TBA` remains visually quiet in the responsive review; it is useful but should not overpower real times.

## Open questions for the Critic

- Is `Time TBA` sufficiently useful to show on every unknown-time card, or should it appear only when no description contains a likely time?
- Should the existing generic `recommendationReasons[0]` line be suppressed only for conviction cards, or removed wherever it merely says `Happening this week` (the date grouping already communicates that)?
- The current feed has no coordinates/travel-time field. Confirm that relabeling `nearby` to `Near Williamsburg` is preferable to inventing a brittle neighborhood-to-distance table.
- Browser screenshots could not be produced locally because Chromium fails before launch with `MachPortRendezvousServer ... Permission denied`; require CI Playwright screenshots or another browser-capable environment before calling fb-212 visually verified.
