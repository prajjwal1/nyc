# Verification — run 2026-06-23-1816

No rollback. All gates green or pre-existing-stable.

- **Functional:** P1 gate verified — well-formed fitness (startTime+venue) 0.637 > 0.55, low-info 0.536 floored. New slugs all present in GENERIC_URLS. fb-183 helper: 3 new unit tests pass (bypasses both passes; control merges).
- **tests:** 256 passed, 3 xfailed.
- **sanity_check:** 2 criticals (NYC Backgammon Club, IG dominant) — unchanged from pre-run; pre-existing data conditions, not regressions from this code-only round. No CRITICAL_CHECK regressed. No revert.
- **next build:** clean.
- **State files:** reverted test/probe-induced churn in `scrapers/data/` to HEAD — commit is code+docs only.
- **Pre-existing note:** `thebellhouseny.com/calendar/` is duplicated in GENERIC_URLS (listed under both Music venues + Bell House) — pre-existing, not introduced this round; left untouched (additive-only / out of scope).
