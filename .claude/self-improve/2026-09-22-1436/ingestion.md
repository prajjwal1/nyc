# Ingestion Quality Report — 2026-09-22 1436

## Metrics observed

- Signal accounts with `yield_map > 0`: 50/50.
- Zero-yield signal accounts: none.
- Current feed: 693 events; Eventbrite 155, Luma 102, Partiful 80, Instagram 15.
- Exact title/date duplicate groups: zero.
- Live exclusion leaks: `Literary Met Tour: AI & Society`, `Build Your Content Operating System: An AI + Personal Brand Workshop`, `ElevenLabs × Creator Spotlight: The New Reach: How creators are growing with AI audio tooling`, plus three `closed/private event` rows.

## Proposals

### P1: Enforce title-level AI and non-public-event exclusions
- **Metric moved**: high-conviction precision; removes six events the user cannot or explicitly does not want to attend, including one falsely high-conviction row.
- **File**: `scrapers/quality.py`
- **Change**: add title-only regular expressions for uppercase `AI`, `artificial intelligence`, `private event`, and `closed for/to`. Keep them out of description-wide substring matching so incidental context does not remove legitimate events; preserve the proper name `Ai Weiwei`.
- **Examples caught**: the six live titles listed above.
- **Risk**: low; matches are title-only and regression tests cover incidental description text and mixed-case `Ai`.

## Directives addressed

- fb-218: P1 is a measured, live-feed-derived quality improvement.
- fb-219: deferred to the orchestrator until verification and deployment.
- fb-216: source expansion is already operating successfully; see the source report.

## Open questions for the Critic

- The three AI rows include a literary museum tour. The durable user preference says no AI events, so the explicit exclusion should outrank the otherwise relevant literary signal.

