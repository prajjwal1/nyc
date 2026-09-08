# UI Report — 2026-09-08 2135

## Audit notes
- High-conviction signal currently visible in: `EventCard.tsx` (blue/amber card chrome plus explicit `★ Saved by you`, `★ Following`, `✨ From your saves`, and `✨ your taste` labels), `EventModal.tsx` (following/affinity highlights, taste and recommendation-reason pills), and the static event-detail page (`Because you follow…` / save-affinity copy). `Header.tsx`, `Calendar.tsx`, and `EventList.tsx` correctly leave event-level conviction to the card rather than adding global UI.
- Components surfacing follow-graph provenance: `EventCard.tsx`, `EventModal.tsx`, and `site/app/events/[id]/page.tsx`. The homepage path uses `EventCard.tsx`, so the signal is visible without leaving the calendar.
- Component-by-component audit:
  - `Header.tsx`: count, freshness, new-since-last-visit, and Share only; no redundant tabs and no event-level signal is appropriate here.
  - `FilterBar.tsx`: absent, consistent with the no-search/no-feed-tab preference.
  - `Calendar.tsx`: selected date and event-density indicators; appropriately neutral to provenance.
  - `EventList.tsx`: date and count, then delegates all event detail to `EventCard`; no redundancy.
  - `EventCard.tsx`: shows organizer/external link, start/end time, venue and neighborhood, meaningful price, source, provenance, and `★` / calendar / `×` actions. Missing images collapse to text-only. Exact distance is not available in the `Event` schema.
  - `EventModal.tsx`: shows organizer link, full date/time/location/address, price, source, conviction/recommendation provenance, `★` / calendar / `×`, description, and related events. It remains used only on the legacy `/events` and `/saved` routes, not the minimalist homepage.
  - `TopPicks.tsx`, `TopAccounts.tsx`, and `AccountBanner.tsx`: absent; they have not been reintroduced.
  - `ActivityPanel.tsx`: still exists but is not mounted. Keep it dormant because it contains saved-count and bulk-export UI that the user removed from primary navigation.
  - `SiteNav.tsx`: brand link only; the removed top-right Calendar tab remains absent.
  - Community components/routes remain unlinked from the homepage, and `EventCard` renders no community chips. The removed Communities and Saved navigation stays removed.
- Expanded-source readiness: `OrganizerLink.tsx` is source-agnostic. It resolves `organizerUrl`, then an Instagram account URL, then `sourceUrl`, so every new event still exposes a working external information link. In the deployed artifact, 473/645 events have a named organizer/account and 372/645 have an explicit organizer URL; the remainder still receive the source fallback. New Eventbrite/Luma/Instagram calendars therefore require no new widget.
- Required-detail gaps found from 10 upcoming events in the deployed artifact:
  - Every sampled card lacks exact distance/travel time from Williamsburg; the schema has no coordinates or distance field. The existing optional `nearby` highlight is only a coarse signal.
  - “Bored of Dating Apps Singles Night” has time, venue, neighborhood, follow provenance, and organizer link; price and end time are absent from the feed.
  - “Reading Rhythms Prospect Heights” is complete at a glance except for distance; FREE and follow provenance are already explicit.
  - “TUESDAYS in Harlem: FREE Swinging Lindy Hop Class!” already exposes organizer, time, venue, neighborhood, and FREE; only distance is missing.
  - “RISK! live show and story slam” has organizer/time/place, but price is `unknown` upstream.
  - “Tai Chi with Pin Pin Su” has a precise venue/address behind the detail view, but only the coarse `manhattan` neighborhood and no distance.
  - “Astoria Gay Book Club Sep.26 Meetup” is dated Sep 8 in data despite “Sep.26” in its title. This is an ingestion/date-quality issue, not a card-rendering gap.
  - “The Fragility of Borrowed Intelligence” identifies the organizer only as “Personal”; the organizer link correctly falls back to the source.
  - “Alice Hoffman + Adriana Trigiani” exposes the Strand organizer link but has no price upstream.
  - “Free Ping Pong Meetup” exposes time/place/organizer/FREE but lacks an end time upstream.
- Clutter / preference violations: none on the homepage. There is no This Weekend hero, no parties hero, no left-sidebar activity/account widget, no empty gray image placeholder, no Communities/Saved/Events tab, and no top-right Calendar tab. The removed footer sentences and the “Free things to do” / “Your saved” links remain absent. `EventModal` can repeat a highlight and a recommendation reason for the same signal, but it is off the primary path and changing it would not help source expansion.
- Evidence caveat: the public GitHub Pages host was unreachable from this audit environment. Counts/examples above come from the deployed artifact checked into `origin/main` at `site/public/events.json` (`lastUpdated` 2026-09-04T15:06:43Z, 645 events); deployment freshness must be verified after the approved source changes land.

## Proposals

### U1: Defer source-expansion UI changes
- **Metric moved**: clutter reduction / required-detail surfacing
- **Component(s)**: `site/app/components/EventCard.tsx`, `site/app/components/OrganizerLink.tsx`
- **localStorage key (if any)**: none
- **Change sketch**:
  ```tsx
  // No change this round: every event already renders OrganizerLink,
  // whose organizerUrl -> Instagram -> sourceUrl fallback is source-agnostic.
  ```
- **Rationale**: Source expansion improves inventory and topic coverage; adding source badges or navigation would not increase follow-graph coverage or conviction and would work against the just-shipped minimalist calendar.
- **Risk**: Re-audit after the scrape for a new source that emits neither a readable `organizer`/`account` nor a useful `sourceUrl`; fix that in normalization before adding UI exceptions.

### U2: Defer an exact-distance badge until the feed owns the data
- **Metric moved**: required-detail surfacing
- **Component(s)**: `site/app/lib/types.ts`, `site/app/components/EventCard.tsx`
- **localStorage key (if any)**: none
- **Change sketch**:
  ```tsx
  // Do not infer distance from neighborhood strings.
  // Future, only after normalization provides a trusted value:
  {event.distanceMiles != null && <span>{event.distanceMiles.toFixed(1)} mi</span>}
  ```
- **Rationale**: Distance is the sole systematic at-a-glance gap, but fabricated neighborhood-based mileage would reduce trust; organizer links already cover deeper logistics.
- **Risk**: Adding `distanceMiles` now would create a mostly-empty badge and expand scope into data modeling; retain the existing `nearby` highlight meanwhile.

## Directives addressed
- fb-216: audited the UI impact of broader sources. Existing source-agnostic organizer/source fallbacks make UI work unnecessary; source additions can land without reintroducing tabs, communities, or saved navigation.
- fb-213: provides an evidence-based UI deferral. The measurable North-Star gain should come from source/ingestion changes, not cosmetic UI churn.
- fb-214: preserves a deployment-ready UI surface; production deployment and public timestamp/assets still require post-merge verification by the orchestrator.

## Open questions for the Critic
- Accept the no-code UI deferral if every newly approved source emits a readable organizer/account or a useful source URL in the normalized feed.
- Should exact Williamsburg distance become a future ingestion field, or is the current coarse `nearby` highlight plus organizer link intentionally sufficient for the minimalist card?
