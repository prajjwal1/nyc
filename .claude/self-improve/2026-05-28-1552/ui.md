# UI Report — 2026-05-28-1552

## Audit notes

### Component inventory
- **Header.tsx** — title, week/total count, "X new since last visited" badge, IG capture stats. No high-conviction signal. Per task rules, do not touch.
- **FilterBar.tsx** — search + history, quick-filter chips (Today/Weekend/Week/Meet People/Saved/Free), categories, price. No conviction signal. Clean.
- **Calendar.tsx** — date picker (not re-read; not in scope).
- **EventList.tsx** — thin wrapper around `EventCard`. Fine.
- **EventCard.tsx** — three variants (`FeedCard`, `MediaFirstCard`, `GridCard`). See gaps below.
- **EventModal.tsx** — full-screen detail. Already surfaces `contributingAccounts`, `affinityComentionSources`, multi-source provenance well. Don't touch carousel.
- **TopPicks.tsx** — Tonight / Weekend / Just Added / Saved heroes + per-day grouped feed. View-mode toggle. Correctly excludes parties from Weekend.
- **TopAccounts.tsx** — present in code but NOT mounted in `page.tsx` sidebar (correct per §513).
- **AccountBanner.tsx** — only renders on `@account` filter. Fine.
- **ActivityPanel.tsx** — present but NOT mounted in sidebar (correct per §513).

### High-conviction signal — current state
- Visible in: `FeedCard` and `MediaFirstCard` as a small text pill from `HIGHLIGHT_CONFIG.following` ("From accounts you follow", `bg-blue-50 text-blue-700`) and `HIGHLIGHT_CONFIG.affinity` ("From accounts you save", `bg-amber-50`). Mixed into a `slice(0, 3)` highlight row that competes with other badges.
- **GridCard surfaces NONE of these signals** — no border, no pill, no icon. The 6 `userFollowing` events become invisible in grid view.
- `affinityComentionSources` provenance has a dedicated fuchsia row in MediaFirstCard + EventModal — good — but the **deployed feed has 0 events with this field populated**, so the row never fires.
- **No card-level distinction** (no border tint, no left rail, no "Because you follow @X" header). The 6 `userFollowing` events look identical to the other 240 non-personalized events at first glance.

### Required-detail gaps (from inspecting deployed events)
- **IG `userFollowing` events have empty `location` objects** (`name: ""`, `address: ""`, `neighborhood: null`) — examples: ids `5b9dfcecfc161161`, `97f603bf804cfb7c`, `962f7173ffe40bc1`. The location row in FeedCard short-circuits when `location.name` is empty, so the only spatial cue is the @account. Card should fall back to "via @{account}" as a place hint or surface the neighborhood inferred from the title.
- **Eventbrite/meetup events have `price: "unknown"`** which never renders (only `price === "free"` is shown). Most non-IG events look priceless — fine for now, but a `$` indicator for confirmed-paid would aid quick scanning. Not proposing — out of scope.
- **`endTime` is null on most events** — already handled (`timeStr` only shows start). No gap.
- **Neighborhood missing on many cards**: e.g. random sample "Rise Up, Sing Out" has `neighborhood: "manhattan"` but `"Sober Sapphic Social"` has `neighborhood: null` despite a Brooklyn address. That's a scraper concern, not UI.
- **GridCard lacks**: time, neighborhood, account handle, follow/affinity signal. Only date pill + image. For follow-graph events, this is a regression in IG-grid view.

### Clutter / preference violations
- None spotted. Sidebar correctly omits TopAccounts/ActivityPanel. Weekend hero correctly excludes parties (verified in TopPicks.tsx:256-269). Empty grid cells use neutral text card, not gray gradient (EventCard.tsx:73-77). EventModal "More from"/"More like this" require `e.imageUrl` to render the thumbnail (line 402, 461) — only render the `<img>` when present, no placeholder. Compliant with §513–516.

---

## Proposals

### U1: Card-level "From accounts you follow" treatment in FeedCard + MediaFirstCard
- **Metric moved**: high-conviction event ratio (primary lever). The 6 userFollowing events and 2 userAffinity events should be visually unmissable instead of fading into 246 cards.
- **Component(s)**: `site/app/components/EventCard.tsx` (FeedCard + MediaFirstCard wrappers)
- **localStorage key**: none
- **Change sketch**: Add a sky-tinted left border + small "@account follows" ribbon at the top of the card when `event.userFollowing` is true (sky), or amber when `event.userAffinity` is true. Replaces nothing — adds a distinct visual frame.

  ```tsx
  // Inside FeedCard (and mirror in MediaFirstCard), wrap the existing <a> with:
  const convictionClass = event.userFollowing
    ? "ring-1 ring-sky-300 shadow-[inset_3px_0_0_0_theme(colors.sky.500)]"
    : event.userAffinity
    ? "ring-1 ring-amber-300 shadow-[inset_3px_0_0_0_theme(colors.amber.500)]"
    : "border border-gray-200";

  // Add header strip ABOVE the existing content row when conviction fires:
  {(event.userFollowing || event.userAffinity) && event.instagramAccount && (
    <div className={`px-3 py-1 text-[11px] font-semibold flex items-center gap-1 ${
      event.userFollowing ? "bg-sky-50 text-sky-800" : "bg-amber-50 text-amber-800"
    }`}>
      <span>{event.userFollowing ? "Because you follow" : "From accounts you save from"}</span>
      <span className="font-bold">@{event.instagramAccount}</span>
    </div>
  )}
  ```
  Then drop `following` and `affinity` from the existing in-card highlight chip row to avoid duplication (`(event.highlights || []).filter((h) => h !== "free" && h !== "following" && h !== "affinity")`).
- **Rationale**: Makes the 3.3% high-conviction signal perceptible at glance, directly serving North Star metric #3.
- **Risk**: If userFollowing fires on too many events later, the ribbon could feel noisy. Mitigated by the fact that current account-graph rules keep this signal sparse (~3%).

### U2: Surface follow-graph signal in GridCard
- **Metric moved**: high-conviction event ratio (visibility in IG-explore-style grid view, which is one of two view modes).
- **Component(s)**: `site/app/components/EventCard.tsx` (`GridCard`)
- **localStorage key**: none
- **Change sketch**: Add a small sky/amber corner dot or pill on grid thumbnails when conviction signals fire. Currently GridCard only shows date pill (top-left), multi-image badge or NOW badge (top-right). Need a third corner cue.

  ```tsx
  // Inside GridCard, after the "Multi-image badge" block, add:
  {(event.userFollowing || event.userAffinity) && (
    <div
      className={`absolute bottom-1.5 left-1.5 rounded-full px-1.5 py-0.5 text-[9px] font-bold backdrop-blur ${
        event.userFollowing ? "bg-sky-500/95 text-white" : "bg-amber-500/95 text-white"
      }`}
      title={event.userFollowing ? `Follows @${event.instagramAccount}` : `From accounts you save from`}
    >
      {event.userFollowing ? "★ FOLLOW" : "★ AFFINITY"}
    </div>
  )}
  ```
- **Rationale**: Without this, switching to grid view erases all personalization cues — undermining the primary North Star lever for users in grid mode.
- **Risk**: Visual collision with bottom-hover title gradient. Mitigated: dot sits at `bottom-1.5 left-1.5`, hover overlay covers the gradient zone but the dot remains legible above it (z-stack is implicit via DOM order; both absolutely positioned).

### U3: Account-handle fallback for empty-location IG events
- **Metric moved**: required-detail surfacing (the FeedCard currently shows blank space below the title on most `userFollowing` events because they're IG stories without location).
- **Component(s)**: `site/app/components/EventCard.tsx` (`FeedCard`)
- **localStorage key**: none
- **Change sketch**: When `location.name` is empty AND `instagramAccount` is present, render an attribution-style "via @account" placeholder in the location row so the card isn't visually empty below the title.

  ```tsx
  // In FeedCard, replace the existing location block (line 434-442) with:
  {event.location.name ? (
    <span className="flex items-center gap-1 truncate">
      <PinIcon />
      <span className="truncate">{event.location.name}</span>
      {event.location.neighborhood && (
        <span className="text-gray-400 shrink-0">· {event.location.neighborhood}</span>
      )}
    </span>
  ) : event.instagramAccount ? (
    <span className="flex items-center gap-1 truncate text-gray-400">
      <PinIcon />
      <span className="truncate italic">location in caption</span>
    </span>
  ) : null}
  ```
- **Rationale**: Tells the user "tap to see where" instead of leaving the metadata row blank — better hint than absence. Tied to required-detail surfacing.
- **Risk**: Could clutter cards that already have meaningful structure. Italic + gray-400 keeps it visually subordinate.

### U4: Lift conviction events to the top of date-grouped sections in TopPicks (sort-only, no new component)
- **Metric moved**: high-conviction event ratio — perceived ratio at the top of each day. The user sees more conviction-signal events without scrolling.
- **Component(s)**: `site/app/components/TopPicks.tsx`
- **localStorage key**: none
- **Change sketch**: Inside `diversifyByCategory`, give a conviction-event-first bias. Currently top-K is pure score order; bump conviction events into the top-K pool first.

  ```tsx
  // Replace the "Take top-K strictly by score" block in diversifyByCategory:
  const convictionFirst = [...events].sort((a, b) => {
    const ac = (a.userFollowing || a.userAffinity || a.userSaved) ? 1 : 0;
    const bc = (b.userFollowing || b.userAffinity || b.userSaved) ? 1 : 0;
    if (ac !== bc) return bc - ac;
    return (b.score ?? 0) - (a.score ?? 0);
  });
  const sorted = convictionFirst;  // rest of function untouched
  ```
- **Rationale**: Even before more conviction events exist, the existing 6–8 should never be buried below generic Eventbrite events on the same date. Directly raises perceived high-conviction ratio in the visible viewport.
- **Risk**: Could surface a low-quality conviction event above a great non-conviction one. Mitigated by `topK = 2` cap — only the first 2 slots favor conviction, then category round-robin resumes.

---

## Directives addressed
- **fb-102 (surface follow-graph provenance)**: U1 + U2. U1 puts an unmistakable "Because you follow @X" ribbon on FeedCard/MediaFirstCard with a sky border. U2 adds a `★ FOLLOW`/`★ AFFINITY` corner pill on GridCard so the signal survives the IG-explore-style view. U4 also lifts conviction events to the top-of-day so the user encounters them first.
- **fb-101 (follow-graph 0-yield gap)**: not a UI directive. Out of scope.
- **fb-103 (`bk` topic gap)**: not a UI directive. Out of scope.

## Open questions for the Critic
- U1's left-rail ring uses `shadow-[inset_3px_0_0_0_...]` for the inset border. Acceptable, or prefer a literal `border-l-4 border-l-sky-500` (which would shift internal padding)?
- U4: is the conviction-first bias even within `topK = 2` too aggressive given how few conviction events exist (6/246)? Alternative: only apply if the conviction event's score is within 0.2 of the day's max score.
- Should U2's pill use the word "FOLLOW" (loud, IG-style) or a quieter ★ glyph alone? "FOLLOW" is more legible at thumbnail scale but louder.
- `userSaved` is currently 0 in the deployed feed (all client-side via localStorage). Should U1's ribbon also fire for `isSavedLocal(event.id)` star events, or keep it strictly to server-signaled conviction? Leaning: don't, since saved already has the `★ Saved by you` hero in TopPicks.
