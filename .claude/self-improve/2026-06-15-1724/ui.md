# UI Report — 2026-06-15 1724

## Audit notes
- **High-conviction signal currently visible in:** `EventCard` FeedCard (sky ★ ring + inset bar for `userFollowing`; amber for `userAffinity`), `TopPicks` `★ Following` / `★ Saved` heroes. Constraint-compliant (no prose ribbon, no "Because you follow @X").
- **Components surfacing follow-graph provenance:** `EventCard` footer — IG events render `@handle` as a clickable filter button; cross-source-enriched conviction events (62 in the feed: nycforfree 19, bookclubbar 17, readingrhythms-manhattan 12, litclub.nyc 12, silentbookclubnyc 2) currently render `@account` as **plain text** (ui-U1, run 2026-06-04-1904). This is the gap fb-169 closes.
- **Required-detail gaps found:** The 62 `account`-only conviction handles are dead text — not clickable, and even if they were, the `@`-filter would return **zero events** (see Critical finding). These are the user's calibration-validated literary follows (iter-198: "would attend ALL of bookclubbar/readingrhythms/litclub").
- **Clutter / preference violations:** None found. iter-215 simplification holds — no grid, no sidebar, no category chips, no IG-stats line, uniform FeedCard. `★ Following`/`★ Saved` heroes are each individually `.length > 0`-guarded (TopPicks L409/L423), so the empty server-saved set (0 events) renders nothing awkward. Following hero is healthy (69 upcoming conviction events). No change warranted for directive-2's empty-hero concern.

## CRITICAL finding (fb-169 is a 3-file change, not 2)
The backlog spec names only `EventCard.tsx` + `AccountBanner.tsx`. But the **actual account-filter predicate lives in `site/app/lib/events.ts` `filterEvents()` (L42–43)** and matches `instagramAccount` ONLY:
```ts
if (accountQuery) {
  return (e.instagramAccount || "").toLowerCase().includes(accountQuery);
}
```
`AccountBanner` is a passive header; the feed itself is narrowed by `filterEvents` via the `search="@handle"` state. If only `EventCard` + `AccountBanner` are touched, clicking `@bookclubbar` sets `search="@bookclubbar"` → `filterEvents` returns **0 events** → empty feed + a banner that (without the AccountBanner fix) also shows "0 upcoming". The lib fix is load-bearing and MUST ship with the other two. Verified by building all three changes together: `next build` passes clean.

## Proposals

### ui-U1: Make the `@account` filter (lib + banner + card) key on `event.account`, not just `instagramAccount` — ships fb-169
- **Metric moved:** high-conviction event ratio (turns 62 dead conviction provenance handles into working per-account browse routes; surfaces the follow-graph signal the user validated).
- **Component(s):** `site/app/lib/events.ts`, `site/app/components/AccountBanner.tsx`, `site/app/components/EventCard.tsx`
- **localStorage key:** none touched.
- **Change sketch (verified: `next build` clean with all three applied together):**

  **(a) `site/app/lib/events.ts` L42–43** — the load-bearing predicate:
  ```ts
  if (accountQuery) {
    return (
      (e.instagramAccount || "").toLowerCase().includes(accountQuery) ||
      (e.account || "").toLowerCase().includes(accountQuery)
    );
  }
  ```

  **(b) `site/app/components/AccountBanner.tsx` L16–18** — count `account` events + suppress IG-only "Open on IG" chrome for non-IG handles (those handles have no IG profile to open):
  ```tsx
  const lc = account.toLowerCase();
  const upcoming = events.filter((e) =>
    e.instagramAccount?.toLowerCase() === lc ||
    e.account?.toLowerCase() === lc
  );
  const isIg = upcoming.some((e) => e.instagramAccount?.toLowerCase() === lc);
  ```
  Then wrap the existing `<a href={igUrl}>…</a>` block in `{isIg && ( … )}`. (The `if (upcoming.length === 0 && !topAccount) return null;` empty-banner guard at L29 is preserved — confirmed it does NOT render an empty banner.)

  **(c) `site/app/components/EventCard.tsx` L249–256** — swap the plain-text `<span>@{event.account}</span>` for a clickable filter button mirroring the IG branch:
  ```tsx
  ) : event.account && (event.userFollowing || event.userAffinity) ? (
    <button
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        trackAccountClick(event.account);
        onAccountClick?.(event.account!);
      }}
      className="hover:text-gray-700 hover:underline focus:outline-none"
      title={`See more from @${event.account}`}
    >
      @{event.account}
    </button>
  ) : (
  ```
  (`trackAccountClick(account: string | undefined)` already accepts the optional type — type-safe.)
- **Rationale:** Completes the iter-1 plain-text step into working per-account routes for the user's highest-conviction literary follows; consistent with simplification (no new widget, reuses the existing IG button pattern, removes the dead-text dead-end).
- **Risk:** (1) If the lib fix is omitted, the feature is broken (empty feed) — all three pieces must land together. (2) `event.account` can equal a generic source token for non-conviction events, but the EventCard branch is gated on `userFollowing || userAffinity`, and the filter is only reachable by clicking that gated button, so no generic-source filter pollution. (3) `isIg` guard correctly hides "Open on IG" for handles like `bookclubbar` that aren't real IG profiles — avoids a dead external link.

### ui-U2: (none) — directive-2 empty-hero concern is already handled
Audited per directive: with IG events at 14 and conviction at 18%, the `★ Following` hero has 69 healthy upcoming conviction events and `★ Saved` (server) has 0. Both heroes are individually `.length > 0`-guarded (TopPicks L409 / L423), and `isSavedLocal` still feeds `★ Saved` from browser saves. No empty/near-empty hero renders awkwardly. No clutter or correctness defect found worth a change. Honest no-op for U2 — shipping ui-U1 alone is the right scope for this round.

## Directives addressed
- **fb-169 (directive 1):** Shipped as ui-U1, expanded from the 2-file spec to the correct 3-file change (added `lib/events.ts` — the actual filter predicate, without which the feature is non-functional). AccountBanner empty-banner guard preserved; IG-only chrome suppressed for non-IG handles. Build verified clean.
- **Directive 2 (empty-hero / clutter check):** Audited; no change needed. Following hero healthy (69 events), Saved hero correctly self-hides when empty. Reported as no-op with evidence rather than inventing a change.

## Open questions for the Critic
- fb-169 spec said 2 files; I'm shipping 3 (adding `lib/events.ts`). The third edit is mandatory for correctness, not scope creep — confirm you're comfortable with the expanded surface.
- The `isIg`-gated "Open on IG" suppression is an additive correctness fix (don't render a dead IG link for `bookclubbar`-type handles). If you'd rather keep U1 strictly minimal, the IG link could be left unconditional, but it would 404 for non-IG handles — recommend keeping the guard.
