# Feedback for this run

North Star: surface events the user would actually attend in NYC. The user explicitly requested an updated, fresh, better-designed website, a full self-improvement pass, and deployment when complete.

## Top 3 directives (workers MUST address or justify deferral)

### 1. Refresh, update, and ship the production website
- backlog items: fb-210, fb-211, fb-214
- best agent: ingestion
- "addressed" criterion: generate a fresh today-onwards event feed, integrate the run's approved site changes, pass sanity checks and the production build, then deploy and verify the public site serves the final commit and event timestamp. The checked-in feed is currently dated `2026-08-28T18:04:42Z` with 556 events, six days behind this run, so a code-only change does not satisfy “make it fresh.” The orchestrator owns the final push/deployment confirmation.

### 2. Deliver a meaningful, low-clutter design improvement
- backlog item: fb-212
- best agent: ui
- "addressed" criterion: ship and visually verify a coherent responsive improvement to discovery hierarchy and event decision-making on mobile and desktop; required details and preference provenance remain easy to scan; the production build passes. Preserve fb-007 through fb-009: no sidebar widget creep, no empty image placeholders, and no party/nightlife-heavy weekend hero.

### 3. Complete the self-improvement loop with a measurable North-Star gain
- backlog items: fb-213, fb-209
- best agent: ingestion
- "addressed" criterion: run the documented worker/critic/apply/verify cycle and land at least one measurable improvement in active-feed follow coverage, high-conviction quality, freshness, or learned organizer selection. The strongest carried-forward candidate is fb-209: persist bounded Eventbrite organizer quality across scrapes, keep explicit user-mentioned organizers first, and put inferred organizers on evidence-based probation rather than accumulating them by generic popularity.

## Questions to ask the user this round

- none — gate closed. The user supplied direct feedback today, and the backlog now contains 15 open/pending items.

## Backlog mutations applied

- Added fb-210: Update the website.
- Added fb-211: Make the website fresh.
- Added fb-212: Improve the design.
- Added fb-213: Run the self-improvement loop.
- Added fb-214: Deploy the website after the work is complete.
- Re-ranked: fb-210 → fb-211 → fb-212 → fb-213 → fb-214 placed at the top of the open list; the operationally coupled items are consolidated into the three directives above.
- Closed (with sha): none.

## Guardrails and context

- “Fresh” requires current event data as well as visual polish. Do not claim completion from a redesign over the August 28 feed.
- Deployment is an explicit terminal requirement, but it happens only after approved changes pass verification.
- Continue applying fb-208's durable principle: infer likely appreciation from follows, saves, hides, attendance, and taste history—not generic popularity.
- Preserve fb-001 through fb-011, particularly nightclub/late-night/networking exclusions, alcohol-free preference, client-side-only personalization, and generalizable source handling.
- Do not re-add user-excluded venues or personal IG accounts, and do not treat blocked IG/CI infrastructure items as worker-fixable.
