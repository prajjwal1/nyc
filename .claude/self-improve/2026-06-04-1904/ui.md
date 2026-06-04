# UI Report — 2026-06-04 1904

## Audit notes

Verified against deployed feed (`site/public/events.json`, 347 events, today). Baseline
`next build` is clean (Next 16.2.4, TS passes).

- **High-conviction signal currently visible in**: `FeedCard` (sky `ring-1 ring-sky-300` +
  `inset 3px sky` bar for `userFollowing`; amber ring+bar for `userAffinity`) and the
  TopPicks `★ Following` / `★ Saved by you` heroes. The sky-vs-amber split in `EventCard.tsx`
  lines 130–136 is internally consistent and matches the hero intent. No prose ribbon. Good.

- **Components surfacing follow-graph provenance (the @handle itself)**: only the bottom-right
  provenance slot in `FeedCard` (lines 236–251) — and it reads ONLY `event.instagramAccount`.

- **Directive 1 — Following hero populates correctly**: CONFIRMED. `followingUpcoming`
  (TopPicks.tsx 299–307) filters `userFollowing || userAffinity` per fb-163 — correct. On the
  current feed there are 104 `userFollowing` + 1 `userAffinity` upcoming, so the hero is
  well-populated (capped at MAX_FOLLOWING=6, rest flow into date groups). Saved hero
  (312–321) reads `userSaved || isSavedLocal(e.id)` — correct; `userSaved` is 0 in the feed
  today (server-side IG-saved suppressed by stale session), so it's localStorage-driven, as
  designed. No change needed to either hero.

- **Directive 2 — conviction ring attribution**: CONFIRMED visually consistent. sky→following,
  amber→affinity/saved-local. No bug.

- **Required-detail gap found (the one real finding)**: the provenance `@handle` is MISSING on
  the 68 cross-source-enriched conviction events. Breakdown of the 105 conviction events:
  - 37 have `instagramAccount` set → card shows `@handle`. Correct.
  - 68 have `userFollowing=true` but NO `instagramAccount`; the matched follow-graph handle
    lives in the `event.account` field (already in `types.ts` line 23). The card never reads
    `account`, so it falls back to the plain source label. Examples from the live feed:
      - `bookclubbar` (17 events) → card shows "Book Club Bar" not the followed handle
      - `readingrhythms-manhattan` (10) → shows "Luma"
      - `nycforfree` (40) → shows "NYC for Free"
      - `silentbookclubnyc` (1) → shows "Meetup"
    These are EXACTLY the calibration-validated literary follows (iter-198: user said they'd
    attend all of bookclubbar / readingrhythms / litclub). The sky ★ ring tells the user "this
    is a follow"; today the card cannot tell them WHICH follow. fb-102 / feedback criterion 3a
    asks for "no missing/blank @account" on conviction events — this is the gap.

- **Clutter / preference violations found**: none. No "For You" heading, no grid toggle, no
  sidebar, no category chips, no IG-stats line, no gray-gradient boxes, uniform FeedCard sizing.
  The iter-215 simplification is intact.

## Proposals

### ui-U1: Show the followed `@account` on cross-source-enriched conviction cards
- **Metric moved**: high-conviction surfacing / correct provenance attribution (fb-102, 3a)
- **Component**: `site/app/components/EventCard.tsx` (FeedCard provenance slot, ~line 236–251)
- **localStorage key**: none
- **Scope (verified)**: `event.account`-but-no-`instagramAccount` is set on EXACTLY the 68
  conviction events and on ZERO non-conviction events in the deployed feed. So this change
  touches only conviction cards and cannot alter the look of any other card.
- **Change**: in the provenance `<span>` (currently `event.instagramAccount ? <button…> : <span source label>`),
  add a middle branch: if no IG handle but `event.account` is set, render the handle as PLAIN
  TEXT (not a clickable filter button). Plain text — not a button — deliberately, because
  `AccountBanner` filters by `instagramAccount` and would render an empty "0 upcoming events"
  banner for a `nycforfree`/`bookclubbar` click. Plain `@handle` is the same minimal
  typographic treatment already used; it is NOT the banned "Because you follow @X" prose.

  ```tsx
  {event.instagramAccount ? (
    <button
      onClick={(e) => { e.preventDefault(); e.stopPropagation();
        trackAccountClick(event.instagramAccount);
        onAccountClick?.(event.instagramAccount!); }}
      className="hover:text-gray-700 hover:underline focus:outline-none"
      title={`See more from @${event.instagramAccount}`}
    >
      @{event.instagramAccount}
    </button>
  ) : event.account && (event.userFollowing || event.userAffinity) ? (
    // Cross-source-enriched conviction event: surface WHICH follow drove it.
    // Plain text (not a filter button) — AccountBanner keys on instagramAccount
    // and would show an empty banner for these source-only handles.
    <span title={`From @${event.account}, an account you follow`}>@{event.account}</span>
  ) : (
    <span>{SOURCE_LABELS[event.source] || event.source}</span>
  )}
  ```
- **Rationale**: completes the high-conviction signal — the ring says "a follow", the handle
  says which one — on 68/105 conviction events that are currently anonymized. North Star:
  raises perceived personalization of the calibration-validated literary follows.
- **Risk**: low. Only conviction cards change; handle is plain text so no new click paths,
  no empty-banner edge case, no new localStorage. `event.account` already typed. Watch: a
  conviction event whose `account` equals an ugly raw slug — spot-checked, the four values are
  clean handles (`bookclubbar`, `readingrhythms-manhattan`, `nycforfree`, `silentbookclubnyc`).

## Directives addressed
- Directive 1 (Following/Saved heroes populate + correct filter): VERIFIED correct, no change.
- Directive 2 (sky/amber ring attribution): VERIFIED correct, no change.
- Directive 3 (clutter-reducing / missing-required-info polish): ui-U1 surfaces the missing
  provenance handle on 68 conviction events. This is the "surface missing-but-required info"
  arm of directive 3; no clutter to remove was found (iter-215 already minimal).
- fb-102 / feedback criterion 3a ("no missing/blank @account on conviction events"): ui-U1
  closes the gap for the 68 enriched events.

## Open questions for the Critic
- ui-U1 renders the enriched handle as plain (non-clickable) text to dodge the empty
  AccountBanner. Alternative: make `AccountBanner` ALSO match `event.account` so the handle
  can be clickable like IG handles. That's a larger change to a second component; I kept U1
  minimal and additive. Flag if you'd prefer the clickable route.
- `nycforfree` is a curator/aggregator handle (40 events) rather than a single venue. Showing
  `@nycforfree` is accurate provenance (it IS a followed account) but it's a high-volume one;
  if the Critic considers that noisy, the branch could be gated to exclude `nycforfree`. I left
  it in — it is a genuine follow and the org-cap in `diversifyByCategory` already limits volume.
