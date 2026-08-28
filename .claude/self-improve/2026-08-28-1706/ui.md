# UI Report — 2026-08-28 1706

## Audit notes

- High-conviction signal currently visible in: `EventCard.tsx` (sky following ring, amber affinity ring, explicit `★ following`, `✨ your taste`, recommendation reason, and account handle) and `EventModal.tsx` (highlight/recommendation pills, cross-promotion, and affinity provenance). The live recheck at `2026-08-28T17:07:01Z` had 90/537 high-conviction events (16.8%); all 90 were `userFollowing`, and the 3 `userAffinity` events were also followed.
- Components surfacing follow-graph provenance: `EventCard.tsx` explicitly; `EventModal.tsx` through highlights/recommendation reasons and IG attribution. The new SEO event page, `site/app/events/[id]/page.tsx`, currently surfaces neither follow-graph provenance nor local actions — a gap for users arriving from search.
- Component-by-component audit:
  - `Header.tsx`: count, freshness, new-since-last-visit, and Share are useful; no event-level conviction. Regression: the former taste export/sync control is gone (`Header.tsx:20-40`, `108-126`).
  - `FilterBar.tsx`: removed; this matches the calendar-first/no-search preference.
  - `Calendar.tsx`: complete for date selection and density (`Calendar.tsx:85-123`); conviction is intentionally left to the event list.
  - `EventList.tsx`: useful thin renderer; conviction/details come from `EventCard`. It does not pass an `onSelect`, so homepage card clicks now follow the SEO detail link.
  - `EventCard.tsx`: strongest current surface. It shows time, venue, conditional neighborhood, price, provenance, ★ save, calendar, and × hide (`EventCard.tsx:211-240`, `248-405`). It preserves text-only rendering when there is no image. Gap: when venue name is empty but neighborhood is present, the whole location row disappears (`222-239`).
  - `EventModal.tsx`: most complete evaluation surface: full date/time/location/address, price, provenance, save/calendar/share/hide, attendance, and related discovery (`143-453`). Do not change its carousel.
  - `TopPicks.tsx`: removed; therefore no “This Weekend” hero can leak parties/nightlife.
  - `TopAccounts.tsx`: removed; do not restore it to the left sidebar.
  - `AccountBanner.tsx`: removed; account filtering is represented by the compact pill in `page.tsx:160-170`.
  - `ActivityPanel.tsx`: file remains but is not wired into a page. It summarizes local activity and calendar export, but restoring it to the sidebar would violate the user preference. Reuse none of its layout for taste export.
  - `SiteNav.tsx` / `Footer.tsx`: useful, low-clutter navigation; no high-conviction signal needed.
  - `CommunityCard.tsx` / `FollowButton.tsx` / `CommunityChips.tsx`: visibly expose community following and provenance, but this signal is separate from event follow-graph conviction.
- Taste-sync diagnosis:
  - The browser still records saved events (`interests.ts:439-485`), attendance yes/no under the unchanged `nyc-events:attended:v1` key (`491-577`), and hidden events plus negative account/category/host maps (`579-663`).
  - `scrapers/data/user_engagement.json` is absent, so `apply_engagement()` is a no-op (`scrapers/utils/engagement.py:73-76`) and the semantic model falls back to follow-graph examples (`scrapers/utils/taste.py:123-147`). Demonstrated browser behavior cannot improve the next scrape.
  - Commit `1c157eb1` removed both `site/app/lib/tasteExport.ts` and the Header control. Blindly restoring that file is insufficient: its last version exported saved text and hidden text, but never read the attendance response map despite claiming to include attendance. It also used a GitHub PAT and the GitHub Contents API, which conflicts with this run's no-external-API rule.
  - `markAttended()` overwrites the final response correctly, but clicking the same answer again re-applies profile weights. The export should key attendance by final event ID/state, not infer it from aggregate weights.
- Required-detail gaps found from the live feed:
  - `THE ROTATION: live music @ Chelsea Cannabis Co.` has neighborhood `chelsea` but an empty venue name; the card shows no location at all.
  - `8/28 Friday Night Muay Thai` similarly loses `flushing`; `Work & Brew Social No. 001` loses `bed-stuy`. This affects 25/537 live events.
  - `Parra for Cuva @ Ballroom, Arlo Williamsburg` and `The Summer Berry Sorbet` have no start time; the UI cannot safely invent one. `The Summer Berry Sorbet` does correctly show its following provenance.
  - `L'Oréal Paris Gloss Clubhouse` correctly shows 10 AM, FREE, venue, `★ following`, and `@nycforfree`; it is the current complete-card baseline.
  - `Warm Up: TDJ/ De Schuurman/keiyaA/ DJ WORKING CLASS` renders `4 PM – 4 PM`; equal start/end cleanup belongs in ingestion rather than a UI guess.
  - `Great Outdoors Comedy Festival ... Edmonton` paired with Central Park is a source/location contradiction; route to ingestion, not UI masking.
  - Distance from Williamsburg is formally deferred: 0/537 live events contain coordinates, and `Event` has no coordinate fields. A distance badge would fabricate or hide nearly the whole feed.
- Clutter / preference violations:
  - No left-sidebar TopAccounts/ActivityPanel, no Feed tab, no free-text search, no empty event-image gradients, and no party-oriented weekend hero are present — preferences are respected.
  - `/events` already has a sticky date heading but passes `showDay` to every card (`events/page.tsx:203-216`), repeating “Today/Tomorrow/Sat” on every event in the group.
  - The SEO implementation keeps crawlable links in `EventCard.tsx:179-184`, which should stay. However, `events/[id]/page.tsx:153-218` is a less capable landing experience than the card/modal because it lacks follow provenance and ★/calendar/× actions.

## Proposals

### U1: Preserve final attendance examples without changing `attended:v1`
- **Metric moved**: high-conviction event ratio
- **Component(s)**: `site/app/lib/interests.ts:491`, `site/app/components/EventModal.tsx:403`
- **localStorage key (if any)**: keep `nyc-events:attended:v1`; add `nyc-events:attendedCache:v1`
- **Change sketch**:
  ```tsx
  const ATTENDED_CACHE_KEY = "nyc-events:attendedCache:v1";

  export function loadAttendedExamples() {
    const states = loadAttended();
    const saved = Object.fromEntries(loadSavedStubs().map((s) => [s.id, s]));
    const hidden = Object.fromEntries(loadHiddenStubs().map((s) => [s.id, s]));
    const cached = JSON.parse(localStorage.getItem(ATTENDED_CACHE_KEY) || "{}");
    return Object.entries(states).flatMap(([id, state]) => {
      const stub = cached[id] || saved[id] || hidden[id];
      return stub ? [{ id, state, stub }] : [];
    });
  }

  // In markAttended: same answer must not inflate weights; cache text separately.
  if (loadAttended()[eventId] === answer) return;
  if (hint.stub) {
    const cache = JSON.parse(localStorage.getItem(ATTENDED_CACHE_KEY) || "{}");
    localStorage.setItem(ATTENDED_CACHE_KEY, JSON.stringify({ ...cache, [eventId]: hint.stub }));
  }

  // EventModal passes the same SavedEventStub fields already used by Save/Hide.
  markAttended(event.id, answer, { ...hint, stub: eventStub });
  ```
- **Rationale**: final “went”/“didn't go” behavior becomes durable training evidence even if the event later leaves the feed or is unsaved; the existing attendance response schema and key remain intact.
- **Risk**: historical attendance IDs without any saved/hidden stub cannot recover event text. Preserve their yes/no map entries and export them as counts/IDs; do not delete them. Add a regression check that reload still returns the same `getAttendedState(event.id)`.

### U2: Restore a safe, download-only taste export
- **Metric moved**: high-conviction event ratio
- **Component(s)**: new `site/app/lib/tasteExport.ts`, `site/app/components/Header.tsx:20`, `site/scripts/test-ui.mjs:43`
- **localStorage key (if any)**: reads existing `nyc-events:interests:v1`, `saved:v1`, `savedCache:v1`, `hidden:v1`, `hiddenCache:v1`, `attended:v1`, and `attendedCache:v1`; do not restore `nyc-events:ghtoken:v1`
- **Change sketch**:
  ```tsx
  import { loadProfile, loadSavedStubs, loadHiddenStubs, loadAttendedExamples } from "./interests";

  const text = (s: SavedEventStub) =>
    [s.title, s.description, ...(s.categories || []), s.locationName,
     s.organizer, s.account, s.instagramAccount].filter(Boolean).join(" ").trim();

  export function buildTasteSnapshot() {
    const p = loadProfile();
    const positive = new Map(loadSavedStubs().map((s) => [s.id, s]));
    const negative = new Map(loadHiddenStubs().map((s) => [s.id, s]));
    const attended = loadAttendedExamples();
    for (const item of attended) {
      (item.state === "yes" ? positive : negative).set(item.id, item.stub);
      (item.state === "yes" ? negative : positive).delete(item.id);
    }
    return {
      updatedAt: new Date().toISOString(),
      accounts: p.accounts, categories: p.categories, hosts: p.hosts,
      negAccounts: p.negAccounts, negCategories: p.negCategories, negHosts: p.negHosts,
      timeBuckets: p.timeBuckets, dayOfWeek: p.dayOfWeek,
      attended: Object.fromEntries(attended.map(({ id, state }) => [id, state])),
      positiveTexts: [...new Set([...positive.values()].map(text).filter(Boolean))],
      negativeTexts: [...new Set([...negative.values()].map(text).filter(Boolean))],
    };
  }

  export function downloadTasteSnapshot() {
    downloadJson("user_engagement.json", buildTasteSnapshot());
  }
  ```
  ```tsx
  // Header: small control beside Share; no PAT, prompt, backend, or network call.
  {hasTasteSignal() && (
    <button onClick={downloadTasteSnapshot} title="Copy the download to scrapers/data/user_engagement.json">
      Export taste
    </button>
  )}
  ```
- **Rationale**: this directly addresses the user's new durable preference to infer what they may appreciate from accumulated saves, hides, and attendance rather than generic popularity. The exact downloaded filename is already the pipeline contract consumed by `engagement.py` and `taste.py`.
- **Risk**: static GitHub Pages cannot write into a local checkout without a backend or external API, so one manual move/commit remains. Make that explicit in the success message. In Playwright, seed one saved, hidden, attended-yes, and attended-no event; assert the download has both text arrays, both attendance states, and that `nyc-events:attended:v1` is unchanged after reload. Then run `npm run build` and `npm run test:ui`.

### U3: Make SEO event landings personalized and actionable
- **Metric moved**: high-conviction event ratio / required-detail surfacing
- **Component(s)**: new `site/app/components/EventDetailActions.tsx`, `site/app/events/[id]/page.tsx:153`
- **localStorage key (if any)**: existing `nyc-events:saved:v1`, `savedCache:v1`, `hidden:v1`, `hiddenCache:v1`, `interests:v1`
- **Change sketch**:
  ```tsx
  // Server-rendered provenance remains indexable.
  const account = event.account || event.instagramAccount || event.organizer;
  {event.userFollowing && account && (
    <p className="mt-3 text-sm font-semibold text-sky-800">★ Because you follow @{account}</p>
  )}
  {event.userAffinity && !event.userFollowing && account && (
    <p className="mt-3 text-sm font-semibold text-amber-800">From an account you save from · @{account}</p>
  )}
  <EventDetailActions event={event} />

  // Client component: reuse existing helpers; keep the crawlable page itself.
  <button onClick={() => setSaved(toggleSavedLocal(event.id, eventHint))}>
    {saved ? "★ Saved" : "☆ Save"}
  </button>
  <button onClick={() => downloadIcs(event)}>Add to calendar</button>
  <button onClick={() => hideEvent(event.id, eventHint)}>× Hide</button>
  ```
- **Rationale**: search visitors should see why an event is personal and be able to train the system immediately; crawlable `EventCard` links and all uncommitted metadata/JSON-LD work remain intact.
- **Risk**: action logic could drift from `EventModal`. Keep the component thin and reuse the same stub/hint helper rather than copying scoring semantics. Verify one generated event page on mobile and desktop, including a followed-account event.

### U4: Show neighborhood fallback and remove repeated day scent
- **Metric moved**: required-detail surfacing / clutter reduction
- **Component(s)**: `site/app/components/EventCard.tsx:158`, `site/app/events/page.tsx:213`
- **localStorage key (if any)**: none
- **Change sketch**:
  ```tsx
  const venue = event.location?.name?.trim();
  const neighborhood = event.location?.neighborhood?.trim();
  const place = venue || neighborhood?.replace(/\b\w/g, (c) => c.toUpperCase());

  {place && (
    <span className="flex items-center gap-1 truncate">
      <PinIcon /><span className="truncate">{place}</span>
      {venue && showNeighborhood && <span className="shrink-0 text-gray-400">· {neighborhood}</span>}
    </span>
  )}

  // /events already has a sticky day heading.
  <EventCard event={event} onAccountClick={setAccountFilter} ... />
  ```
- **Rationale**: 25 live events regain useful at-a-glance geography without adding a new badge, while grouped listings stop repeating the same date on every card.
- **Risk**: keep the existing “location in caption” fallback only when both venue and neighborhood are absent; verify the three named Partiful examples plus an IG event with no parsed location.

## Directives addressed

- fb-178: U1+U2 restore a backend-free, user-visible path from local behavior to the pipeline contract and explicitly include saved, hidden, attended-yes, and attended-no evidence. The old `nyc-events:attended:v1` response remains authoritative and persistent.
- fb-199: U1+U2 provide the explicit positive and negative examples required before more keyword/taste cleanup. This is grounded in the user's new instruction to infer future appreciation from accumulated demonstrated behavior, not generic popularity.
- fb-187: formally deferred to the source-curator. UI has no defensible way to measure landed participatory-dance share or repair a failing Eventbrite path.
- fb-193: formally deferred to ingestion. UI should display the canonical venue/neighborhood it receives; it must not maintain a second alias table or mask source contradictions.

## Open questions for the Critic

- Does the no-external-API rule make the exact-file download plus manual move the accepted completion for fb-178, or is an in-repo import helper required outside the UI scope?
- Attendance “no” currently means “planned but did not make it,” not necessarily dislike. U2 places it in `negativeTexts`, where the existing taste model already applies only half-weight; confirm that this is the intended negative strength.
- Should U3 ship in this round with the SEO work, or should the SEO event page temporarily remain view-only? From the North Star, a search landing that cannot save/hide is incomplete.
