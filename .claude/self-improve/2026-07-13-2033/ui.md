# UI Report — 2026-07-13 2033

## Audit notes
- High-conviction signal currently visible in: `EventCard.tsx` (sky/amber ring + inset left bar via `feedChrome`, `✨ your taste` indigo chip, price/FREE pills), `TopPicks.tsx` (★ Following sky hero, ★ Saved amber hero), `EventModal.tsx` (Promoted-by / Recommended-by provenance boxes, ✨ your taste chip).
- Components surfacing follow-graph provenance: `EventCard.tsx` (clickable @account/@source button), `EventModal.tsx` (contributingAccounts + affinityComentionSources), `TopPicks.tsx` (Following hero). Adequate — no gap here; this run is polish, not new signal.
- Required-detail gaps found: none new (start time, neighborhood, distance-substitute via neighborhood pill, provenance, ★/× actions, relative-day, price all present from prior Phase D work).
- Clutter / preference violations: none. 5 heroes intact, no left-sidebar widgets on Feed, no empty gray gradient boxes, no parties in This Weekend hero. All durable prefs respected.

### Mobile-first / a11y issues found (the actual scope this run)
- **Conviction signal is color-only** (`EventCard.tsx:163-167`): `ring-sky-300`/`ring-amber-300` + colored inset bar are the ONLY cue that an event is from your follow-graph vs. affinity vs. neither. A colorblind user (sky vs. amber deuteranopia confusion, or either vs. plain gray border) cannot distinguish conviction tiers. WCAG 1.4.1 (use of color) violation. This is the North-Star-relevant a11y bug: the high-conviction signal must be perceivable without color.
- **Icon-only buttons missing labels in Calendar** (`Calendar.tsx:46-64`): the prev/next month chevron buttons have no `aria-label` (screen reader announces "button"). EventCard save/hide/calendar buttons already have `aria-label` (good); modal buttons good.
- **No visible focus rings on interactive elements**: EventCard @account button (`EventCard.tsx:326`) uses `focus:outline-none` with NO replacement ring — keyboard focus is invisible. Calendar day buttons (`Calendar.tsx:83-91`) and the Feed/Calendar toggle (`page.tsx:196-211`) rely on the browser default outline which Tailwind Preflight suppresses on some elements; no explicit `focus-visible:` ring. Keyboard users can't see where they are.
- **6-item footer crowds on narrow screens** (`EventCard.tsx:312-382`): likes + @account + verified + save + calendar + hide all live in one `ml-auto` flex span sharing the meta row. On a ~320px viewport with a 96px image (`w-24`) eating width, this wraps awkwardly or truncates the @account. The `flex-wrap` on the parent (line 243) helps but the footer span itself is a single non-wrapping run.
- **Card image fixed at `w-24 h-24` (96px)** (`EventCard.tsx:183`): on a 320px screen that is ~30% of width before padding, squeezing the text column. Minor — a `w-20 h-20 sm:w-24 sm:h-24` step-down buys real estate.
- **TopPicks stacks up to 5 heroes before the dated feed** (`TopPicks.tsx:364-436`): Tonight(6) + This Weekend(6) + Just Added(6) + Following(6) + Saved(6) = up to 30 cards before the ranked date-grouped feed. On mobile the ranked feed can start ~30 cards down. Critic-flagged. Heroes are a durable pref — must NOT remove; the fix is to make heroes scannable, not gone.
- **No explicit viewport export** (`layout.tsx`): Next injects a default, but there is no explicit `export const viewport`. Low risk to leave; noting for completeness.

## Proposals

### U1: Non-color conviction cue on cards (a11y — WCAG 1.4.1)
- **Metric moved**: high-conviction event ratio (makes the signal perceivable, not just present) + a11y
- **Component(s)**: `site/app/components/EventCard.tsx`
- **localStorage key (if any)**: none
- **Change sketch** — add a tiny labeled pill in the badge row (after the `✨ your taste` block, ~line 259), so the follow/affinity tier is conveyed by text+icon, not only the ring color:
  ```tsx
  {convictionFollow && (
    <span
      className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-sky-100 text-sky-800"
      title="From an account you follow"
    >
      ★ following
    </span>
  )}
  {convictionAffinity && (
    <span
      className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-100 text-amber-800"
      title="From an account you save from"
    >
      ◆ your scene
    </span>
  )}
  ```
  `convictionFollow`/`convictionAffinity` already exist (lines 161-162). The glyph (★ vs ◆) + word is the non-color cue; the pill background still reinforces for color users.
- **Rationale**: the follow-graph signal is the UI's one job (North Star); it must survive colorblindness. Text label doubles as clarity for everyone.
- **Risk**: adds one pill to conviction cards — watch the footer row on narrow screens (mitigated by U3). Note: prior iter 214 removed *verbose* "Because you follow @X" hero text; this is a compact chip, not that. If the Critic reads it as re-clutter, gate to `convictionFollow` only (drop the affinity pill) since following is the higher-value tier.

### U2: aria-labels + visible focus rings on icon/nav buttons (a11y)
- **Metric moved**: a11y (keyboard + screen-reader access; no direct metric but zero-risk correctness)
- **Component(s)**: `site/app/components/Calendar.tsx`, `site/app/components/EventCard.tsx`, `site/app/page.tsx`
- **localStorage key (if any)**: none
- **Change sketch**:
  ```tsx
  // Calendar.tsx:46 — prev button
  <button aria-label="Previous month" onClick={...}
    className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-600 focus-visible:ring-2 focus-visible:ring-sky-500 focus:outline-none">
  // Calendar.tsx:57 — next button
  <button aria-label="Next month" onClick={...}
    className="... focus-visible:ring-2 focus-visible:ring-sky-500 focus:outline-none">
  // Calendar.tsx:83 — day button: add focus-visible ring to className
  //   ... focus-visible:ring-2 focus-visible:ring-sky-500 focus:outline-none
  // EventCard.tsx:326 — @account button: replace bare focus:outline-none
  className="hover:text-gray-700 hover:underline rounded focus-visible:ring-2 focus-visible:ring-sky-500 focus:outline-none"
  // page.tsx:196/204 — Feed/Calendar toggle buttons: append
  //   focus-visible:ring-2 focus-visible:ring-sky-500 focus:outline-none
  ```
- **Rationale**: keyboard/AT users must be able to operate and see the calendar and account-drilldown — the drilldown is how they explore the follow graph.
- **Risk**: purely additive class strings; `focus-visible:` won't show on mouse click so no visual regression for mouse users. Verify `focus-visible` variant is available (Tailwind v3+ ships it by default).

### U3: Mobile-first responsive tightening (card footer + image + modal)
- **Metric moved**: clutter reduction / required-detail surfacing on small screens (no data buried below a broken layout)
- **Component(s)**: `site/app/components/EventCard.tsx`, `site/app/components/EventModal.tsx`
- **localStorage key (if any)**: none
- **Change sketch**:
  ```tsx
  // EventCard.tsx:183 — step image down on mobile
  <div className="shrink-0 w-20 h-20 sm:w-24 sm:h-24 rounded-lg overflow-hidden bg-gray-100">
  // EventCard.tsx:312 — let the footer action span wrap instead of forcing one row
  <span className="text-[10px] text-gray-400 ml-auto uppercase tracking-wide
                   flex flex-wrap items-center justify-end gap-x-1 gap-y-0.5">
  // EventModal.tsx:71 — cap modal height a touch below viewport on mobile so the
  //   sheet never renders taller than the screen (top-sheet with no visible close)
  className="relative bg-white rounded-t-2xl sm:rounded-2xl w-full max-w-2xl
             max-h-[90vh] sm:max-h-[95vh] overflow-y-auto"
  ```
- **Rationale**: on a phone (the primary IG-replacement device) the card footer and modal must not clip the ★/hide/@account controls — those are the interaction surface for personalization.
- **Risk**: `justify-end` + `flex-wrap` may push icons to a 2nd line on very narrow cards — acceptable (better than truncation). Confirm the `ml-auto` still right-aligns within the wrapped span. Calendar `grid-cols-7` is intentional and fine (7 columns is a calendar's semantic width and each cell is only a 1-2 digit number — it fits 320px; no change needed).

### U4: Cap hero density so the ranked feed isn't buried on mobile (Critic fix, heroes preserved)
- **Metric moved**: high-conviction event ratio surfaced above the fold vs. buried; clutter reduction
- **Component(s)**: `site/app/components/TopPicks.tsx`
- **localStorage key (if any)**: none
- **Change sketch** — the two lower-conviction/discovery heroes (Just Added, This Weekend) are the ones that most delay the ranked feed. Trim their mobile slice while keeping all 5 heroes and full desktop counts. Cheapest build-safe move: reduce the `.slice()` caps for the discovery heroes from 6 to 4 (keeps Tonight/Following/Saved at 6 — those are the highest-conviction):
  ```tsx
  // TopPicks.tsx:224 — Just Added
  .slice(0, 4);
  // TopPicks.tsx:283 — This Weekend
  .slice(0, 4);
  ```
  Following (307) and Saved (321) stay at MAX_FOLLOWING/MAX_SAVED (6); Tonight (203) stays at 6. Net: up to 22 hero cards instead of 30 before the dated feed — heroes all still render.
- **Rationale**: the ranked date feed and the highest-conviction heroes reach the viewport sooner; discovery rails (Just Added / Weekend) are the least-committed signal so they yield the vertical space first. North Star: get high-conviction + ranked events in front of the user faster.
- **Risk**: shows fewer discovery cards. If the Critic prefers zero behavior change, alternative is a pure-CSS collapse (`max-h` + fade on the discovery hero card-lists at `< sm`) but that adds chrome and a "show more" affordance — heavier than a slice tweak. Recommend the slice tweak. Do NOT touch the hero set, ordering, or the Tonight/Following/Saved counts.

## Directives addressed
- Outstanding Phase D mobile-first + a11y pass: U1 (non-color conviction cue), U2 (aria-labels + focus rings), U3 (mobile responsive card/modal), U4 (hero density cap — Critic flag, heroes preserved).
- Top-3 feedback directives (fb-194 neighborhood mistags, fb-195 keyword-list retirement, fb-196 coverage gaps): NOT UI — ingestion/source-curator scope. Correctly deferred; no UI lever moves them.

## Open questions for the Critic
- U1: is a compact "★ following" / "◆ your scene" chip acceptable, or does it read as re-introducing the iter-214-removed provenance text? My read: iter 214 removed a verbose *hero heading* sentence, not a card-level a11y label — but flag it. Fallback: ship the following-tier chip only.
- U4: slice 6→4 on the two discovery heroes vs. a CSS mobile-collapse — I recommend the slice (simpler, no new affordance). Confirm the discovery-count reduction is acceptable vs. keeping 6 everywhere.
- Should `layout.tsx` get an explicit `export const viewport = { width: "device-width", initialScale: 1 }`? Next injects a default so it's likely a no-op; omitted from proposals to stay minimal — flag if wanted.
