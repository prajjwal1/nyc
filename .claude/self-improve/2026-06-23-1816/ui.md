# UI Report — 2026-06-23 1816

## Audit notes
- **High-conviction signal currently visible in:** `EventCard.tsx` FeedCard via card-level ribbon — `convictionFollow` → `ring-1 ring-sky-300` + `shadow-[inset_3px_0_0_0_#0ea5e9]`; `convictionAffinity` → amber ring + inset bar (lines 130–136). `following`/`affinity` highlight chips are intentionally filtered out of the badge row (line 208) since the ribbon already carries the signal.
- **Components surfacing follow-graph provenance:** `EventCard.tsx` — clickable `@account` (IG) and the cross-source-enriched `@event.account` button (fb-169, lines 263–279) showing WHICH follow drove a non-IG event. No gap.
- **Required-detail gaps found:** Price legibility for *qualitative low-commitment* strings. U1 (run 2026-06-22-1501) badges only digit-bearing non-free prices (lines 232–240, `/\d/.test(...)` guard). Any non-numeric price word ("donation", "pay what you can", "sliding scale", "suggested") is silently dropped on the FeedCard — yet these are strong attend-probability signals for a meet-people user. Confirmed reachable: `scrapers/sources/eventbrite.py:236` lifts raw price-element text verbatim (`price_el.get_text(...)`), so these strings CAN populate `event.price` from a card-grid Eventbrite source.
- **Live-feed reality check (385 events, fetched this run):** current snapshot has ZERO qualitative price strings — `price` is normalized to `unknown`(288)/`free`(69)/`$NN`(~28). So fb-182 is forward-looking hardening: it adds a positive pill that lights up the moment a qualitative-price source lands, and is a strict no-op on today's data (no regression risk to U1).
- **Clutter / preference violations:** None found. Left sidebar minimal (fb-007 respected). No empty gray gradient boxes — image block only renders when `event.imageUrl && !imgFailedF` (line 151), text-only otherwise (fb-008 respected). No backend calls (fb-010). No changes needed.

## Proposals

### U1: Qualitative / low-commitment price pill (fb-182)
- **Metric moved:** High-conviction ratio (surfaces a positive low-commitment signal at a glance → nudges attendance) + required-detail surfacing.
- **Component(s):** `site/app/components/EventCard.tsx` — FeedCard badge row, immediately AFTER the existing U1 numeric pill (insert after line 240, before the `iter 215` category-chip comment at line 241).
- **localStorage key (if any):** none.
- **Precedence decision (verified, important):** The qualitative branch must be guarded so it does NOT double-fire with the numeric pill on mixed strings like `"sliding scale $10"`. Chosen rule: **numeric pill keeps priority; qualitative pill only renders when there is NO digit** (`!/\d/.test(event.price)`). Rationale: when a concrete dollar figure exists, that number is the more actionable at-a-glance fact (the user knows the cost); the qualitative word is then redundant chrome. A pure-word price ("Donation", "Pay what you can") has no number, so it falls through to this branch and gets the positive pill. This keeps exactly one price pill per card and guarantees U1's numeric pill is untouched.
- **Change sketch** (drop in after the numeric-pill block ending at line 240):
  ```tsx
  {/* fb-182: qualitative low-commitment price words are positive
      attend-probability signals (meet-people user). Render a pill that
      is visually LIGHTER than the emerald FREE pill — reads "cheap/
      flexible", not "free". Guard: only when NO digit is present, so the
      U1 numeric pill (above) keeps priority on mixed strings like
      "sliding scale $10" and never double-fires. No-op on current feed
      (all prices are unknown/free/$NN); lights up when a qualitative
      source (e.g. Eventbrite card text) lands. */}
  {event.price &&
    event.price !== "free" &&
    event.price !== "unknown" &&
    event.price !== "varies" &&
    !/\d/.test(event.price) &&
    /donation|pay what|pwyc|sliding scale|suggested/i.test(event.price) && (
      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-sky-50 text-sky-700">
        {event.price}
      </span>
    )}
  ```
- **Rationale:** A "pay what you can" event is one a meet-people user is *more* likely to attend than a $40 ticket — surfacing it at a glance serves the North Star (events the user would actually attend).
- **Risk:** Low. Purely additive conditional, no Next.js APIs (per AGENTS.md note, the framework caveat doesn't apply). Worst case a long qualitative string ("Suggested donation, no one turned away") renders verbatim and wraps — acceptable since the badge row is `flex-wrap`; the regex anchors are word-fragments so this only fires on genuinely low-commitment language. `bg-sky-50/text-sky-700` is deliberately lighter than `bg-emerald-100/text-emerald-800` (FREE) and distinct from the conviction-ribbon `sky-300` ring tone, so it does not read as a follow-graph signal.

### EventModal — out of scope (no change)
`EventModal.tsx:172` already renders ANY non-free / non-unknown price verbatim in a `bg-gray-100 text-gray-700` pill, so qualitative words ALREADY display in the modal. A styled sky pill there would be cosmetic-only (the modal is the deep-dive view where a plain price chip is fine, and it has no `/\d/` suppression to compound). Adding it is nice-to-have, not required — deferred to keep this round tight and single-file, consistent with the "minimal-but-complete / removing chrome over adding it" rule. Noted for the Critic in case cross-surface consistency is wanted.

## Directives addressed
- **fb-182 (PRIMARY):** Addressed — U1 above adds the qualitative positive pill on the FeedCard badge row, `bg-sky-50 text-sky-700` (lighter than emerald FREE), regex `/donation|pay what|pwyc|sliding scale|suggested/i`, inserted after the existing numeric pill (after line 240). Guard ordering resolved: numeric pill keeps priority (qualitative only fires when `!/\d/`), so no double-pill and no regression to U1's numeric pill. EventModal treatment evaluated and deferred as out-of-scope (already shows the word verbatim).
- **fb-183 (backend / ingestion):** Out of UI scope — `DISTINCT_SCHEDULE_SOURCES` helper refactor in `scrapers/normalize.py`. No UI surface.
- **fb-184 (backend / ingestion):** Out of UI scope — legacy Eventbrite fitness/dance slug recovery. No UI surface.

## Open questions for the Critic
- Confirm the precedence call: numeric-wins (chosen) vs. show-both on mixed "sliding scale $10" strings. I chose numeric-wins to guarantee one pill per card and zero risk to U1, but a meet-people user might value seeing BOTH "$10" and "sliding scale". Easy to flip by dropping the `!/\d/` guard if the Critic prefers both — flagging because the directive explicitly left this to my judgment.
- Worth a one-line follow-up backlog item to give EventModal the matching sky pill for cross-surface consistency? Deferred this round (cosmetic, modal already legible).
