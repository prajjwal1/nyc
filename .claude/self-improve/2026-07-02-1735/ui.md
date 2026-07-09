# UI Report — 2026-07-02 1735

## Audit notes
- High-conviction signal currently visible in: `EventCard.tsx` FeedCard (sky ring + inset sky bar for `userFollowing`, amber ring + amber bar for `userAffinity`; clickable `@account`/`@event.account` provenance link), `EventModal.tsx` (emerald "Promoted by" block for `contributingAccounts`, fuchsia "Recommended by" block for `affinityComentionSources`, "seen on N sources").
- Components surfacing follow-graph provenance: FeedCard (conviction ring/ribbon + `@account` pill), EventModal (Promoted-by / Recommended-by blocks). No gap this round — provenance surfacing shipped in prior sessions (b6a0cf3 and earlier).
- Required-detail gaps found (price parity only — the one this round targets):
  - `EventModal.tsx:172-176` renders **any** non-free, non-unknown `event.price` as a single plain gray pill with no distinction — so `"varies"` shows as a junk pill, and qualitative low-commitment words ("donation" / "pay what you can" / "PWYC" / "sliding scale" / "suggested") render as flat gray text instead of the positive sky signal FeedCard now gives them. FeedCard already splits these into numeric-gray (`EventCard.tsx:271-279`) and qualitative-sky (`EventCard.tsx:286-292`), and excludes `"varies"`. The modal, which is where the user makes the actual attend decision, is the LESS informative surface today — a parity regression.
- Clutter / preference violations: none observed this round. Left sidebar minimal (fb-007 honored), no empty gray gradient boxes (fb-008), no backend calls (fb-010), price pills are additive.

## Proposals

### U1: EventModal price-pill parity with FeedCard (fb-188)
- **Metric moved**: required-detail surfacing (price is a top attend-decision factor; qualitative-sky pills reinforce low-commitment = higher attend likelihood, feeding high-conviction perception).
- **Component(s)**: `site/app/components/EventModal.tsx`
- **localStorage key (if any)**: none
- **Change sketch** — replace the single plain pill at `EventModal.tsx:172-176` with the exact FeedCard split (same guards/regex, scaled to the modal's `px-2 py-0.5 text-[11px]` sizing; `font-medium` matches FeedCard):
  ```tsx
  {/* fb-188: parity with FeedCard price pills. Numeric → gray pill
      (varies/unknown excluded, digit-guarded). Qualitative low-commitment
      words → sky pill. Guards copied verbatim from EventCard.tsx so the
      modal and feed never disagree on how a price reads. */}
  {event.price &&
    event.price !== "free" &&
    event.price !== "unknown" &&
    event.price !== "varies" &&
    /\d/.test(event.price) && (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-gray-100 text-gray-700">
        {event.price}
      </span>
    )}
  {event.price &&
    !/\d/.test(event.price) &&
    /donation|pay what|pwyc|sliding scale|suggested/i.test(event.price) && (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-sky-50 text-sky-700">
        {event.price}
      </span>
    )}
  ```
  The existing `{event.price === "free" && ...}` FREE pill at `EventModal.tsx:167-171` stays untouched, directly above this block.
- **Rationale**: the modal is the attend-decision surface; it must not read a price worse than the feed card the user tapped from.
- **Risk**: low. Pure JSX, no new imports, no state. One behavior change vs. today: prices that are `"varies"` or arbitrary non-numeric non-low-commitment strings (e.g. "TBA") now render NOTHING instead of a plain pill — this is intentional parity with FeedCard (junk-pill suppression) and matches the fb-188 addressed criterion ("no regression to the free/unknown states" — free/unknown are preserved; varies/junk suppression is the desired FeedCard behavior). Watch: confirm no event relies on the modal being the only place a "varies" string appears — it isn't (the black date/time pill and Open-original link carry the actionable info; exact price lives at the source).

## Directives addressed
- fb-188 (PRIMARY): addressed via U1 — modal now renders numeric prices as a gray pill and qualitative low-commitment words as a sky pill, reusing the exact FeedCard guards/regex; FREE and unknown states preserved. Meets the addressed criterion.
- fb-189, fb-186: ingestion-owned (normalizer / time-inference), correctly deferred — not UI.

## Open questions for the Critic
- U1 suppresses non-numeric, non-low-commitment price strings (e.g. "varies", "TBA") in the modal to match FeedCard. Confirm that's the intended parity target and not a detail the Critic wants preserved verbatim in the modal only. If preservation is preferred, add a trailing `else`-style plain-gray fallback pill — but that would diverge from FeedCard and reintroduce the junk-pill fb-182 was cleaning up, so I recommend against it.
