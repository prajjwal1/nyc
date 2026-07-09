# Verification — run 2026-06-22-1501

No rollback this round. All gates green or pre-existing-stable.

- **Functional (this round's edits):** P1 fitness "every-tuesday" soft_penalty_hits 1→0 for fitness, still 1 for admin; P2 "Raven & Goose"/"travel" now survive, "warehouse rave"/standalone "RAVE" still blocked; P3 Brooklyn Contra 8→10 survivors (both Sep-26 sessions + Oct-4 Raven & Goose recovered).
- **tests:** 253 passed, 3 xfailed.
- **sanity_check:** 2 criticals (NYC Backgammon Club, IG dominant) — unchanged from pre-run; pre-existing data conditions (fb-174 IG block, backgammon), not regressions from this code-only round. No CRITICAL_CHECK regressed. No revert.
- **next build:** clean.
- **State files:** reverted test-induced churn (`url_health.json`, `user_interest_profile.json`) to HEAD — code+docs only commit.
