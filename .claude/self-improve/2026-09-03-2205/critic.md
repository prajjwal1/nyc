# Critic Report — 2026-09-03 2205

## Cross-check results

- sanity_check regression risk: the stale local feed still clears every hard floor: NYC Backgammon Club 1, Reading Rhythms 10, music 198, Williamsburg/Greenpoint/Bushwick 45, and free 125. Instagram remains a known warning at 7 versus 50. The approved subset changes ordering, measurement, carryover filtering, and UI only, so it should not reduce these counts; the fresh scrape must rerun all checks before deployment.
- Duplicate source proposals: none. No worker proposes a new account, static URL, Lu.ma page, or organizer. P2/S1 describe the same organizer-ledger work, P3/S2 the same explicit-precedence fix, and P1/S4 the same fresh-run release gate; the orchestrator should implement each accepted change once.
- User-excluded check: no account/host add is proposed. Organizer-quality work, when resumed, must compute `exclusionClean` only after both hard blocks and `is_user_excluded`; a network failure or unscheduled organizer is never a zero-yield observation.
- UI preference compliance: U1/U2/U4 comply with fb-007 through fb-009: no sidebar widget, no empty image placeholder, and no party-heavy hero. U3 is deferred to keep this round's visual change focused and testable.
- Top-3 directive coverage: fb-210/fb-211/fb-214 are addressed only when P1/S4 actually produce and deploy a September 3-or-later feed; currently **not complete** because GitHub Actions and Pages are unreachable from this environment. fb-212 is addressed by U1 + modified U2 + modified U4, conditional on responsive screenshot QA. fb-213 is addressed by P3, P5, and M1 as the measurable shippable improvement; fb-209 is deferred with an acceptable scope/safety reason below.
- Silent-failure watch: all live probes are indeterminate, not zero yield—the known-productive Bell House control failed identically to Eventbrite and Lu.ma. Do not dead-list or demote any source from this run. The fresh full run must explicitly check whether previously absent `mcnallyjackson` and `bondandgrace` recover, and distinguish source failure from calendar exhaustion.
- External verification constraint: a second check from this critic environment also failed to connect to GitHub Pages and the GitHub API. This prevents deployment verification, but it does not imply source failure. The orchestrator must not close freshness/deployment directives until workflow success, final SHA, and public `events.json.lastUpdated` are observed externally.

## Verdicts

### ingestion-P1: Restore a genuinely current feed before shipping the redesign
- **Verdict**: APPROVE
- **Metric moved**: feed age target ~148 hours -> under 1 hour; removes 199 past rows and establishes a truthful active-follow/high-conviction baseline.
- **Reasoning**: This is the user's primary request and the release gate. A UI-only deployment over the August 28 payload is not completion. Carryover-heavy or timestamp-only output must not be called fresh.
- **Acceptance**: successful full scrape; zero past rows; `ingestionStats.run.runCompleted == true`; all hard sanity checks pass; fresh source counts/logs reviewed; production build passes; final deployed SHA and timestamp match the repository. Dispatch platform/quick refresh only for lanes the full run demonstrably missed.

### ingestion-P2: Persist bounded Eventbrite organizer quality and evidence-based probation
- **Verdict**: REJECT
- **Metric moved**: projected high-conviction improvement is unmeasurable this round; immediate delta 0 pp.
- **Reasoning**: The concept is good, but the proposed implementation spans scraper diagnostics, post-normalization state, client export, frontier ranking, two workflows, and a new persistent file while no fresh run can validate it. Full and quick workflows have separate concurrency groups, so a shared writer also risks lost observations. Repeated four-hour scrapes could falsely satisfy a sample threshold on one unchanged calendar day.
- **If REJECT**: keep fb-209 open. Next implementation must use a **single full-scrape writer**, expose run-scoped Eventbrite diagnostics in memory, append at most one successful observation per organizer per NYC calendar day (replace same-day samples), require three distinct successful observation days, and store current organizer engagement separately from yield history. Saves and attended-yes are positive; hides are negative; attended-no is recorded but not treated as a full dislike. Seed old snapshots only as `lastKnownLanded`, never as a completed observation.

### ingestion-P3: Fix explicit-user precedence before organizer learning
- **Verdict**: APPROVE
- **Metric moved**: explicit St. Mazie moves from frontier rank 16 to the explicit tier/top four; active taste coverage may gain one organizer on the next successful quick scrape.
- **Reasoning**: This is a small, testable correctness fix independent of the deferred ledger. `user_mentioned` must be a sort tier, not merely a +4 score that inferred curated hosts can outrank.

### ingestion-P4: Complete organizer identity before scoring organizer quality
- **Verdict**: REJECT
- **Metric moved**: 0 pp this round; eventual organizer attribution could improve from 80% toward 100%.
- **Reasoning**: It is a valid prerequisite for fb-209, but the ledger is deferred and extra detail hydration can consume scarce Eventbrite calls during the freshness recovery. The proposed “taste/score” ordering is also unavailable at this pre-ranking stage.
- **If REJECT**: carry this with fb-209. When resumed, hydrate any row missing a canonical numeric organizer ID, order personal rows before explore rows using existing discovery provenance only, preserve the current request cap, and never overwrite better event fields.

### ingestion-P5: Apply date-range-title rejection during normalization
- **Verdict**: APPROVE
- **Metric moved**: high-conviction ratio improves about +0.03 pp overall (90/556 -> 90/555) or +0.05 pp on the upcoming slice (62/357 -> 62/356).
- **Reasoning**: This closes the carryover hole with one anchored, source-agnostic rule. The current exact title is junk, while a title containing a subject plus a date range remains valid.

### ingestion-M1: Count only upcoming events in active follow coverage
- **Verdict**: APPROVE
- **Metric moved**: active follow coverage is corrected from 6/50 (12%) to 4/50 (8%); this is a 4 pp truth correction, not an inventory loss.
- **Reasoning**: A stale feed must not claim past followed events as active coverage. Use `datetime.now(ZoneInfo("America/New_York")).date()` rather than UTC/server-local `date.today()`, and test one past and one future followed event.

### source-pool-S1: Persist bounded Eventbrite organizer quality history
- **Verdict**: REJECT
- **Metric moved**: projected future high-conviction gain, 0 pp now.
- **Reasoning**: This duplicates P2 and inherits the same multi-writer, same-day oversampling, and unverified-observation risks. Two successful runs are too weak when full scrapes run every four hours against an unchanged calendar.
- **If REJECT**: use P2's deferred single-writer design with three distinct successful observation days, eight daily observations maximum, explicit organizers protected forever, and failure/unscheduled states stored separately from yield.

### source-pool-S2: Fix explicit-user precedence in the Eventbrite frontier
- **Verdict**: APPROVE
- **Metric moved**: the direct-user St. Mazie organizer moves from rank 16 into the four-slot explicit quick lane; expected active taste coverage +0 to one organizer next scrape.
- **Reasoning**: This is the same low-risk change as P3 and should be implemented once under P3 ownership. Stable numeric IDs must collapse slug variants.

### source-pool-S3: Reserve frontier capacity for measured probation
- **Verdict**: REJECT
- **Metric moved**: 0 pp until reliable organizer observations exist.
- **Reasoning**: A learned/probation split cannot be evidence-based before the ledger has trustworthy samples. Shipping it now merely renames fixed buckets and may strand productive organizers.
- **If REJECT**: resume after fb-209's three-day observation model exists. Start quick mode at the current four explicit organizers + three proven + one rotating probation; full mode keeps all explicit and at least three probation slots. Unused learned slots must flow to probation so the budget is not artificially underfilled.

### source-pool-S4: Run one full scrape before adding another organizer cohort
- **Verdict**: APPROVE
- **Metric moved**: freshness target ~148 hours -> under 1 hour; provides the first valid post-August organizer/source baseline.
- **Reasoning**: No further cohort should be added from blocked probes or a six-day-old snapshot. A connection error is an external constraint, not a zero-yield result.

### ui-U1: Put the first event closer to the fold
- **Verdict**: APPROVE
- **Metric moved**: high-conviction ratio is unchanged; roughly 100px of duplicate mobile preamble is removed, surfacing the first ranked event earlier.
- **Reasoning**: Removing the second `<h1>` and redundant explanation materially improves hierarchy without adding a new surface. Preserve the account filter, URL date/account behavior, and desktop sticky calendar.

### ui-U2: Consolidate conviction into one explicit provenance chip
- **Verdict**: MODIFY
- **Metric moved**: high-conviction ratio remains 17.4% upcoming; signal visibility improves for all 62 upcoming conviction events while removing repeated copy.
- **Reasoning**: One chip is clearer than reason + badge + footer handle, and affinity needs non-color treatment. The proposed precedence hides the stronger saved signal behind `userFollowing`, and local saved state is not represented by `event.userSaved` alone.
- **If MODIFY**: use `savedF || event.userSaved` first, then `userFollowing`, then `userAffinity`. For saved events include the source handle in the same chip when available (for example `★ Saved by you · @nycforfree`); use `@` only for `instagramAccount`/`account`, never organizer names. Suppress the generic recommendation line only when this conviction chip is present, and keep the chip keyboard-filterable when a real account field exists.

### ui-U3: Make time and proximity scan anchors
- **Verdict**: REJECT
- **Metric moved**: 0 pp; it would affect 13/357 upcoming unknown-time rows and 30 nearby rows.
- **Reasoning**: The information is useful, but this adds another badge treatment while U1/U2/U4 already form a meaningful redesign and browser screenshots are unavailable. Keep the shippable visual surface focused this round.
- **If REJECT**: revisit after visual QA of U1/U2/U4. `Time TBA` should remain subdued and `nearby` may be relabeled `Near Williamsburg`; never infer time or distance.

### ui-U4: Make actions trustworthy on touch and honor Hide immediately
- **Verdict**: MODIFY
- **Metric moved**: high-conviction ratio changes 0 pp immediately; every Hide becomes visible feedback at once and improves future negative-example quality after export.
- **Reasoning**: Filtering hidden IDs in `useEvents` fixes a real homepage inconsistency, and separating source provenance from actions reduces clutter. A 36px mobile target is still smaller than the conventional 44px touch target.
- **If MODIFY**: use mobile-first `min-h-11 min-w-11` controls, optionally reducing to 36px at desktop breakpoints; retain `preventDefault`/`stopPropagation`; import `isHidden` into the upcoming filter; verify Hide removes the card immediately and after reload, while Save/Calendar never open the detail link.

## Notes back to each worker

## Notes back to ingestion-quality
- You missed: organizer history would be written by workflows with separate concurrency groups; without a single writer, `organizer_quality.json` can lose or duplicate observations.
- You missed: three ordinary successful scrapes could occur within 12 hours against the same calendar. Samples must be distinct NYC days or materially changed catalogs, not raw run count.
- You missed: P4 proposes taste/score priority before ranking has computed either value.
- Strong work on: identifying freshness as the binding constraint, separating current/upcoming conviction, and refusing to treat network failure as zero yield.

## Notes back to source-curator
- You missed: the two-observation threshold is too volatile for a four-hour full-scrape cadence and low-frequency literary/game organizers.
- You missed: probation buckets need borrowing rules; otherwise an empty learned tier wastes crawl budget while seven organizers remain unobserved.
- Strong work on: adding no speculative sources, using a productive Bell House control to prove the network block, and distinguishing unobserved organizers from failed ones.

## Notes back to ui-agent
- You missed: U2 must consider component-local `savedF`, not only the server event's `userSaved`, and saved should outrank following in a single-chip hierarchy.
- You missed: 36px is still undersized for a primary mobile action target; use 44px mobile-first.
- You missed: a successful build is not visual verification. fb-212 remains conditional on 390x844 and 1280x900 screenshots in a browser-capable environment.
- Strong work on: identifying the duplicate homepage introduction, preserving location fallback/text-only cards, and making Hide visibly affect the calendar immediately.

## Dream proposals

### D1: Refuse stale production deployments by default
- **Verdict**: APPROVE-DREAM
- **Metric moved**: freshness cannot silently remain at ~148 hours while a deployment reports success; target deployed age remains under 6 hours, ideally under 1 hour after scrape.
- **File**: `.github/workflows/deploy.yml`
- **Change sketch**: before the build, parse `data/events.json.lastUpdated` and fail if it is older than 6 hours or contains past rows. Allow no automatic stale override; a manual override, if ever needed, must be an explicit `workflow_dispatch` input and must not close fb-211. Keep the existing post-deploy repository-vs-public timestamp check.

### D2: Add an external scheduler heartbeat
- **Verdict**: DREAM-DEFER
- **Metric moved**: expected freshness outage detection from six days to under 30 minutes; no direct inventory change.
- **File**: external uptime/cron configuration plus a short runbook in `README.md`
- **Change sketch**: monitor the public `events.json.lastUpdated` from outside GitHub Actions and alert when older than 90 minutes. It should not mutate the repository or auto-deploy. Deferred because selecting and authorizing an external service/notification channel requires user authority; the current in-Actions monitor shares the producer scheduler's failure domain.
