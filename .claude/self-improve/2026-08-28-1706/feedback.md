# Feedback for this run

North Star: surface events the user would actually attend in NYC. Three new user-explicit directives arrived during this run and now lead the worker queue.

## Top 3 directives (workers MUST address or justify deferral)

### 1. Add and verify Liz's Book Bar's exact Eventbrite organizer
- backlog item: fb-206
- best agent: source-curator
- "addressed" criterion: configure organizer ID `83466825333`, retain Eventbrite organizer provenance through cross-source dedup, and verify after normalization that every exclusion-clean hosted event is represented on the website while `Speed Dating Book Club` remains excluded. Worker evidence already confirms 10 future Eventbrite rows, 9 exclusion-clean, and 14 deployed Liz's Book Bar events from the dedicated source; the organizer is therefore a deterministic fallback/provenance path, not a claim of nine net-new cards.

### 2. Expand Eventbrite through taste-aligned recurring top organizers
- backlog item: fb-207
- best agent: source-curator
- "addressed" criterion: add a bounded batch of recurring NYC organizer calendars with at least 5 projected surviving events each and at least 80% exclusion-clean/on-taste inventory, deduplicated against existing sources. Current live-probed leading candidates are High Line Programs (`46113016283`, 7 projected survivors), The Ripped Bodice BK (`121441877858`, 9), and Strand Bookstore (`30058841244`, 10); staged Caveat, Union Hall, Book Club for the Book Hoes, and National Arts Club calendars also meet the quality bar. Do not rank organizers by raw calendar size alone.

### 3. Make inferred taste—not generic popularity—the durable ranking and curation principle
- backlog item: fb-208
- best agent: ingestion
- "addressed" criterion: organizer selection and event ranking prioritize explicit follows plus learned save/hide/attendance/taste evidence ahead of anonymous popularity or raw event count; add a regression test where a smaller explicit/taste-aligned organizer outranks a larger anonymous organizer; restore a backend-free export path carrying saved, hidden, attended-yes, and attended-no evidence into the pipeline contract; preserve all existing exclusions and fb-001..fb-011 rules. This directly implements the user's exact instruction: “you should try to infer my interests at this point, know what i may appreciate.”

## Earlier directives retained for this run

### Restore the browser-to-pipeline taste sync so real attendance feedback can improve ranking
- backlog item: fb-178 (and the fb-199 dependency; regression of fb-197 Phase B)
- best agent: ui
- "addressed" criterion: restore a backend-free, user-visible export/sync path to `scrapers/data/user_engagement.json`; prove that positive and negative engagement are represented, the existing `nyc-events:attended:v1` response persists, and the production build passes. UI evidence recommends a download-only export with no GitHub token or external API and a durable attendance-stub cache.

### Re-probe the provisional folk-dance source and measure landed participatory quality
- backlog item: fb-187
- best agent: source-curator
- "addressed" criterion: restore the path provisionally through the dedicated Eventbrite adapter, then measure next-scrape survivors. The live probe now returns 20 future events with 11/20 strict participatory (55%) and 8 URLs beyond the broad dance search; keep normal floor, late-night, and exclusion gates, and do not close until landed quality is measured.

### Canonicalize venue aliases before deduplication and neighborhood inference
- backlog item: fb-193
- best agent: ingestion
- "addressed" criterion: use the existing canonical venue key consistently for neighborhood lookup as well as dedup; cover `BK Bowl`/`Brooklyn Bowl`, `MoMA`/`Museum of Modern Art`, `MoMA PS1`, and neighborhood-specific venue branches without changing user-facing names or merging distinct venues.

## Questions to ask the user this round

- none — gate closed. New explicit feedback was supplied directly during the run, and there are now 14 open/pending items.

## Backlog mutations applied

- Added fb-206: Add/verify Liz's Book Bar Eventbrite organizer coverage.
- Added fb-207: Broaden Eventbrite coverage through high-quality recurring organizers.
- Added fb-208: Infer what the user may appreciate from demonstrated taste.
- Re-ranked: fb-206 → fb-207 → fb-208 moved to the top of the open list; earlier directives fb-178, fb-187, and fb-193 remain active in this report.
- Closed (with sha): none. No new closing commit was established by the worker evidence.

## Status and guardrails

- fb-101 appears criterion-satisfied but remains `addressed-pending-scrape`: this run measures 50/50 historical follow-graph coverage, and all eight named priority accounts have `yield_map > 0`. The ingestion audit warns that only 6/50 accounts appear in current live-feed provenance, so do not mistake lifetime coverage for active breadth.
- The Liz's Book Bar organizer is clean at 9/10; its speed-dating listing must remain excluded. Recovering the structured `Celebrate Patricia Lockwood...` listing is compatible with this request only if hard blocks and user exclusions still run first.
- Eventbrite organizer selection must be explicit/taste-first, exclusion-aware, and bounded. Generic popularity, raw event counts, corporate networking, AI, family/kids inventory, and nightlife must not displace demonstrated interests.
- Do not surface fb-174, fb-173, or fb-139 as worker-fixable; they require platform, infrastructure, or user credential changes. fb-104 and fb-185 remain blocked on explicit user opt-in for deletion.
- fb-205 remains premature because current coordinate coverage is effectively zero.
- Preserve fb-001 through fb-011, including nightclub/late-night/networking exclusions, alcohol-free preference, client-side-only personalization, and the generalizable-source rule.
