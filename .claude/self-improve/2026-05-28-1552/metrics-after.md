# Metrics — After (run 2026-05-28-1552)

**Note**: events.json was NOT re-scraped this round (no API key). These numbers reflect the *same deployed feed* as metrics-before. Structural changes ship on the next CI scrape:
- P1 will revive 54 mass-killed accounts → expected follow-graph coverage jump to ~80%+ over 2-3 scrapes.
- P2 will populate the `account` field on every IG event → high-conviction metric will read correctly.
- P3 will give 15 new socializing-oriented accounts the 21-day cooldown protection.
- S1 will surface Brooklyn-tagged events → `bk` topic count should rise from 2 → 8+.
- P6 immediately fixes the bk↔brooklyn fold (next ranking pass).
- U1/U2/U3/U4 will render the existing 8 conviction events visibly.

## Baseline (same as metrics-before)
- signal_accounts with yield_map > 0: 12 / 54 (22.2%)
- `bk` topic events in feed: 2
- events with userFollowing/userSaved/userAffinity boost: 8 / 246 (3.3%)
- events whose account/instagramAccount is in signal_accounts: 9 / 246 (3.7%)
  (was 0/246 using `account` only; now reads correctly via the fallback to `instagramAccount`)

## Dead-pool snapshot (will be auto-revived by P1 on next scrape)
- accounts currently in `repeated_failure` state with a transient last_reason: **54**
- these will all be revived on the next `python -m scrapers.run_all` invocation.
