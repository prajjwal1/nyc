# Applied changes

- [x] ingestion-P1: high-value phrases now contribute at most one +0.15 nudge per event — `scrapers/quality.py`, `scrapers/ranking.py`.
- [x] ingestion-P1: removed source-specific positive keywords and exact hard-block/positive contradictions — `scrapers/quality.py`.
- [x] ingestion-P1: added regression coverage for phrase stacking, hard-block overlap, and source-specific venue scoring — `scrapers/tests/test_quality.py`.
- [ ] fb-138: deferred; requires user-provided Reddit OAuth credentials.
- [ ] fb-158: deferred; source deletion remains opt-in and requires fresh probes.
- [~] fb-199: partially addressed through redundant zero-yield rule removal; broad zero-hit pruning remains open.
