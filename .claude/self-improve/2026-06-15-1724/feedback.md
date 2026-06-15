# Feedback for this run — 2026-06-15-1724

## State summary

- **Feed:** 378 events, last scraped 2026-06-15T11:40Z.
- **Follow-graph coverage:** 12/50 (24%). Dominant cause is the IG GraphQL account-sweep block (fb-174), which is **user-blocked** and not fixable by code or even an IG-session refresh.
- **High-conviction ratio:** 30% → 18% (69/378). This drop is **EXPECTED and intentional** — the 2026-06-15 quality cleanup (commit 4fee74e) removed 38 low-quality followed-IG events. This is a quality/conviction tradeoff, **NOT a regression to reverse.** Do not chase the old 30% number by relaxing filters.
- **Topic `bk` = 0** — a real measurement gap (fb-176). `brooklyn` = 43, so the borough is covered; the `bk` shorthand simply isn't tokenizing.
- **Backlog freshness:** 11 days of feedback + shipped work (2026-06-05 → 2026-06-15) now logged durably as fb-171…fb-176. fb-170 (One Fine Day) was already present and left untouched.

## Top 3 directives (workers MUST address or justify deferral)

### 1. Close the `bk` topic-coverage measurement gap
- backlog item: fb-176
- best agent: ingestion
- rationale: `topic_counts.bk = 0` while `brooklyn = 43` on the same feed. The `bk → brooklyn` synonym fold (fb-103) and venue expansion (fb-111) exist but aren't moving the metric. Trace where `topic_counts` is computed (`interest_profile.py`) and confirm the synonym fold actually runs on the field the counter reads. A tracked topic at literal 0 is a measurement bug, not a coverage gap — do NOT solve it by adding Brooklyn sources (the borough is already well-represented).
- "addressed" criterion: `topic_counts.bk > 0` (target ≥ 5) on the next metrics snapshot, OR a Critic-approved wont-do finding that the `bk` token is not derivable from these events.

### 2. Kill the 4 residual IG-Story OCR fragments (precision-safe)
- backlog item: fb-175
- best agent: ingestion
- rationale: 38 garbage events were dropped (4fee74e) with 0 legit loss, but 4 caption-fragment residuals survive: "45 minutes of feel Sood", "2 mini lobster rolls", "Great vibe 1010 experience", "Dance your cares away". These resisted a global keyword block (FP risk). The safe lever is a **story-source-scoped title-quality floor**: short imperative/sentence-fragment titles from `source == instagram` with no date AND no venue AND no structured fields. Build the filter against the deployed feed snapshot at /tmp/si_feed.json (378 events) and prove 0 legit IG titles are removed before shipping. Also re-audit the top-of-feed for any NEW low-quality leaks now that the cleanup landed.
- "addressed" criterion: the 4 named residuals gone from a fresh feed snapshot AND 0 legitimate IG events removed (precision check against prior-feed legit IG titles).

### 3. Lift follow-graph coverage/quality via NON-IG paths + UI provenance
- backlog item: fb-177-related (see fb-174 user-blocked note) + fb-169 (open) + fb-102/115/116 enrichment thread
- best agent: source-curator (enrichment) + ui-agent (provenance)
- rationale: The IG account-sweep is blocked fleet-wide (fb-174) and CI IPs are publisher-blocked (fb-173) — both user-blocked. So coverage CANNOT be lifted via IG. Use the non-IG enrichment levers that work independent of IG: Lu.ma curator-handle matching, venue-domain hostname matching, organizer/location.name → signal_account folds (fb-115/116/118/151). 38 of 52 signal_accounts still sit at yield 0 in `user_interest_profile.json` — audit which of those have a non-IG public path (Lu.ma calendar, venue .com, Eventbrite venue-search) and enrich. UI complement: ship fb-169 (make AccountBanner key on `event.account` so the ~68 cross-source-enriched conviction handles become clickable per-account routes — the iter-1 plain-text step already landed and is confirmed clutter-free).
- "addressed" criterion: ≥ 3 currently-zero signal_accounts move to yield > 0 via a non-IG path on the next scrape, OR fb-169 ships (AccountBanner filters on `e.instagramAccount === acct || e.account === acct` and the enriched `@account` renders as a working filter button).

## Questions to ask the user this round

none — GATE CLOSED. The user has been giving extensive direct feedback over the last several days and is actively engaged; a calibration question would be redundant.

## Constraints that are user-blocked (workers cannot fix; do not propose fixes that depend on them)

- **fb-174** — IG GraphQL account-sweep blocked (400) fleet-wide from CI AND residential IPs. Only saved-posts works. NOT fixable by IG-session refresh. This is the dominant cause of low follow-graph coverage; route around it via non-IG enrichment.
- **fb-173** — GitHub Actions runner IP broadly 403/429-blocked by many publishers (substack onefinedaynyc, mcnallyjackson, centerforfiction, nycgovparks, museums, instagram). Mitigated via expanded CARRYOVER_SOURCES + feed-reader-header retry + residential-scrape practice. A source at 0 in a CI snapshot may be IP-blocked, not broken — verify against a residential run before concluding a scraper bug.
- **fb-139** — Reddit OAuth (still open; requires user to register a PRAW app + set secrets).

## Backlog mutations applied

- Added fb-171: Partiful rewritten off /explore/nyc — `addressed: 28d14c0`
- Added fb-172: Lu.ma curators + Bond & Grace literary-salon scraper — `addressed: c462147`
- Added fb-173: GitHub Actions runner IP broadly 403/429-blocked — `open (user-blocked)`
- Added fb-174: IG GraphQL account-sweep blocked fleet-wide — `open (user-blocked)`
- Added fb-175: 4 residual IG-Story OCR fragments — `open`
- Added fb-176: Brooklyn `bk` topic-coverage measurement gap — `open`
- Re-ranked: the two actionable open items (fb-176, fb-175) placed at the top of the new block; the two user-blocked constraints (fb-174, fb-173) and the two already-addressed work items (fb-172, fb-171) below them.
- Closed (with sha): none newly moved to the Closed section this round (fb-170 was already addressed in a prior run; fb-171/fb-172 logged directly as `addressed: <sha>` per the orchestrator's confirmation that they shipped to main).

## Note on the conviction-ratio drop (read before any worker touches filters)

The 30% → 18% high-conviction drop is the EXPECTED result of removing 38 low-quality followed-IG events in 4fee74e. It is a quality WIN, not a regression. Any directive that would relax the new filters to "recover" conviction ratio must be REJECTED by the Critic.
