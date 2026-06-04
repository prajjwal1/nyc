# Feedback for this run — 2026-06-04-1904

## State summary

- Feed is fresh: 347 events, lastUpdated 2026-06-04 (today). Deployed == local.
- metrics-before: follow-graph coverage **12/50 (24%)**, **38 zero-yield signal accounts**, high-conviction ratio **105/347 (30.3%)**, all topics with count>=2 represented (ai/bk/club substring counts are noisy — ignore).
- **Dominant root cause of the 38 zero-yield accounts is the stale IG session (33 days old, past the 28-day CRITICAL threshold).** This degrades the CI IG account-sweep. It is **user-blocked** (needs interactive instaloader login) and NOT fixable in worker code this round. Do not chase it with code.
- Only two genuinely open backlog items, both user-blocked:
  - **fb-139** — Reddit OAuth (PRAW). Requires the user to register an app + set `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` secrets. No worker action available.
  - **fb-104** — prune redundant `/nyc/<topic>` Lu.ma URLs. Blocked on the additive-only rule (deletion needs explicit user opt-in). fb-105 already confirmed there is no replacement curator-calendar list to add, so the deferral premise is settled — leave it parked until the user opts in.
- Journal has one real shipped entry (2026-05-28-1552); the iter-198 calibration (2026-06-01, fb-100) is logged in the backlog. **No prior-run commits reference any open item**, so no status is being promoted to `addressed: <sha>` this round.

Because both open items are user-blocked, the top-3 below are forward-looking improvement directives that do NOT depend on a fresh IG session. They target deployed-feed quality, non-IG yield, and provenance/ranking calibration — all things workers can verify against the current 347-event feed today.

## Top 3 directives (workers MUST address or justify deferral)

### 1. Leak audit on the deployed 347-event feed (top-of-feed quality)
- backlog item: fb-109 / fb-122 (leak-audit lineage; this is a fresh pass, not a regression of those closed items)
- best agent: **ingestion-quality**
- rationale: The feed is fresh today and IG is degraded, so non-IG sources (Eventbrite, AllEvents, Songkick, Substack, parks, museums) are carrying more weight than usual — exactly the sources where corporate/B2B/bar-crawl/glued-handle/page-scaffold leaks have historically slipped in. Past audits (fb-109, fb-122, fb-140, fb-141) each found 2-5 leaks at the top of the feed.
- "addressed" criterion: Sample the top 30 events by score on the deployed feed. Either (a) **0 events match HARD_BLOCK / glued-handle / page-scaffold / B2B-networking patterns**, or (b) any new leak pattern found is added to `scrapers/quality.py` HARD_BLOCK_KEYWORDS / soft-penalty / the relevant `_looks_like_*` predicate AND verified to purge on the next normalize pass with no false positives. If 0 leaks found, that's a valid "addressed" — log the sampled titles as evidence.

### 2. Lift non-IG follow-graph coverage via deployed-feed provenance enrichment
- backlog item: fb-101 / fb-102 (follow-graph coverage; this is the non-IG-dependent slice)
- best agent: **ingestion-quality** (enrichment lives in `normalize.py::_enrich_provenance_from_url` + location.name path)
- rationale: 38 of 50 signal accounts are zero-yield. Most are IG-session-blocked, but several map to venues/curators reachable through non-IG sources already in the feed (e.g. `nycbackgammonclub`, `reading_rhythms`, `bookclubbar`, `philosophy.nyc`, `crownheightscraftclub`, `franklinparkbk`, `anaiswinebk`). The iter-73/74/77/109 enrichment paths (Lu.ma handle, venue-domain host, organizer.name, location.name) can fire on Eventbrite/Lu.ma/Substack events WITHOUT a fresh IG sweep. Audit which of the 38 zero-yield accounts have a non-IG event path and whether enrichment is firing on it.
- "addressed" criterion: For the 38 zero-yield accounts, produce a count of how many have at least one non-IG event in the deployed feed whose provenance SHOULD enrich to `userFollowing` but currently does not. Either fix the enrichment normalization (suffix/fold/alias) so **>= 3 additional accounts move to yield_map > 0 against the current feed**, or document with evidence that the remaining zero-yield accounts are genuinely IG-session-blocked (no non-IG path exists) — making this a clean user-blocked deferral.

### 3. Provenance / ranking-calibration polish on high-conviction surfacing
- backlog item: fb-100 (iter-198 calibration validated literary-host enrichment) + fb-102 (provenance surfacing)
- best agent: **ui-agent**
- rationale: The iter-198 calibration was the strongest possible signal — the user said they'd attend ALL THREE curated-host events (`bookclubbar`, `litclub.nyc`, `readingrhythms-manhattan`). High-conviction ratio is healthy at 30.3% (105/347). The lever now is making sure those 105 high-conviction events are visibly surfaced and correctly attributed, since IG share is suppressed and the Following/Affinity heroes (fb-119/fb-163) are doing more work than usual.
- "addressed" criterion: Verify on the deployed feed that (a) every event with `userFollowing` or `userAffinity` true renders its provenance ribbon/badge correctly (no missing/blank `@account`), and (b) the 👤 Following hero in TopPicks populates from the current feed (count > 0). Fix any event where the conviction flag is set but the ribbon shows no handle, OR confirm 100% correct attribution with a sampled count as evidence. No new left-sidebar widgets (fb-007); no gray gradient boxes (fb-008).

## Questions to ask the user this round

**none — throttled.** QUESTION GATE is CLOSED. Last user calibration was 2026-06-01 (iter-198, fb-100), only 3 days ago — inside the 7-day throttle. No `force-ask` was given. Do not call AskUserQuestion this round.

## Backlog mutations applied

- Added: none (no new user input handed in this run).
- Re-ranked: none (open-item order unchanged; fb-139 and fb-104 remain the only genuinely-open items and stay where they are).
- Closed (with sha): none (no prior-run commit references an open item; no status promoted this round).
- Status recommendations (NOT written to backlog — for orchestrator/Critic awareness only):
  - fb-139 — keep `open (requires user action)`; surface to user when the gate next opens.
  - fb-104 — keep `open (blocked-by: fb-105 / additive-only rule)`; ready to action only on explicit user opt-in to delete the 60 redundant `/nyc/<topic>` URLs.
