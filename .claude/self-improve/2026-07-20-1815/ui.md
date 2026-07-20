# UI Report — 2026-07-20 1815

## Audit notes
- High-conviction signal currently visible in: `EventCard.tsx` FeedCard via `feedChrome` (sky ring + inset bar = following; amber ring + inset bar = affinity). Also the `✨ your taste` indigo pill (tasteScore path).
- Components surfacing follow-graph provenance: `EventCard.tsx` (@account button links to per-account filter; the ring color implies the tier but does NOT name it). The verbose "From accounts you follow" highlight badges are filtered OUT of the badge row (line 262-263) since the ring replaced them.
- Required-detail gaps found (a11y, per directive):
  - **WCAG 1.4.1 (use of color)**: The ONLY thing distinguishing following-tier from affinity-tier from plain is ring/bar COLOR (`feedChrome`, lines 163-167). Colorblind users cannot tell tiers apart. No text/glyph cue exists.
  - **Focus visibility (WCAG 2.4.7)**: @account buttons (lines 326, 343) use bare `focus:outline-none` with NO focus-visible replacement — keyboard users get no focus indicator. Feed/Calendar toggle buttons (`page.tsx` 196-211) have no focus-visible ring and no aria state.
- Clutter / preference violations: none new. Footer was tightened last round (U3); this report does NOT re-add to it. The single following pill goes in the BADGE row (top, near `✨ your taste`), not the footer.

## Proposals

### U1: Non-color "★ following" text+glyph pill (WCAG 1.4.1)
- **Metric moved**: high-conviction event ratio (makes the top-tier signal perceivable by everyone, not just full-color-vision users)
- **Component(s)**: `site/app/components/EventCard.tsx`
- **localStorage key (if any)**: none
- **Change sketch** — insert at the TOP of the badge row (inside `<div className="mt-1.5 flex flex-wrap items-center gap-1">`, i.e. immediately after line 243, BEFORE the `✨ your taste` block). Following-tier ONLY per the Critic's MODIFY; affinity keeps the ring alone to avoid footer/badge clutter:
  ```tsx
  {/* U1 (a11y WCAG 1.4.1): non-color cue for the top conviction tier.
      The sky ring alone can't be perceived by colorblind users, so name
      the tier with a glyph+text pill. Following ONLY — affinity keeps the
      amber ring by itself to avoid badge-row clutter. Compact label, NOT
      the removed "Because you follow @X" hero prose. */}
  {convictionFollow && (
    <span
      className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-sky-100 text-sky-800"
      title="From an account you follow"
    >
      ★ following
    </span>
  )}
  ```
  - `convictionFollow` is already computed at line 161, in scope.
- **Rationale**: The follow-graph tier is the single strongest attend signal; a text+glyph label makes it survive colorblindness and grayscale, reinforcing perceived personalization (North Star).
- **Risk**: Badge-row wrap on very narrow cards — mitigated: single compact pill, `flex-wrap` already handles overflow. Do NOT add an affinity pill (would double the row and re-clutter).

### U2: Focus-visible rings + aria on @account and Feed/Calendar toggles (WCAG 2.4.7 / 4.1.2)
- **Metric moved**: clutter reduction / required-detail surfacing (keyboard-operability parity with the Calendar's c2be7e8 pass)
- **Component(s)**: `site/app/components/EventCard.tsx`, `site/app/page.tsx`
- **localStorage key (if any)**: none
- **Change sketch**:

  1. `EventCard.tsx` @account buttons — replace the bare `focus:outline-none` on BOTH buttons (lines 326 and 343). Current className on each:
  ```tsx
  className="hover:text-gray-700 hover:underline focus:outline-none"
  ```
  becomes:
  ```tsx
  className="hover:text-gray-700 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:rounded-sm"
  ```
  (Both instances get the identical replacement. `aria-label` not needed — the visible `@handle` text is the accessible name.)

  2. `page.tsx` Feed/Calendar toggles — add focus-visible ring + `aria-pressed` to both buttons (lines 196-211). For the Feed button (line 196-203):
  ```tsx
  <button
    onClick={() => setView("for-you")}
    aria-pressed={view === "for-you"}
    className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 ${
      view === "for-you" ? "bg-gray-900 text-white" : "text-gray-600 hover:bg-gray-50"
    }`}
  >
    Feed
  </button>
  ```
  Apply the same `aria-pressed={view === "calendar"}` + focus-visible ring classes to the Calendar button (line 204-211). Both have visible text labels, so no aria-label needed.
- **Rationale**: Keyboard users must see focus and hear toggle state; this completes the a11y sweep the Calendar started (c2be7e8), same pattern.
- **Risk**: `focus-visible` (not `focus`) means mouse clicks won't show the ring — intended, avoids visual noise. Tailwind `focus-visible:` variant is available in this project (used elsewhere per the Calendar pass). No layout shift (ring is outline-style, not border).

## Directives addressed
- fb-192 thread U1: non-color conviction cue shipped as the `★ following` text+glyph pill in the badge row (following-tier only, per Critic MODIFY; affinity intentionally NOT pilled).
- fb-192 thread U2: focus-visible rings on both @account buttons and both Feed/Calendar toggles; `aria-pressed` added to the toggles. Extends the c2be7e8 (fb-204) Calendar pattern to the rest of the interactive card/toggle controls.

## Open questions for the Critic
- U1 pill background is `bg-sky-100` to echo the sky ring (visual coherence with the following tier). Confirm sky-100/sky-800 contrast reads distinctly from the indigo `✨ your taste` pill sitting beside it — they can co-occur (a followed account can also be a taste match). If too similar, swap the pill glyph to a filled star only. No functional risk either way.
