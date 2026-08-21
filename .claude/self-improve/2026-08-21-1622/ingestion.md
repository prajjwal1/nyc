# Ingestion and ranking review

## P1 — Bound the legacy positive-keyword layer

- Metric: top-ranked taste alignment and explicit conviction without weakening hard filters.
- Files: `scrapers/quality.py`, `scrapers/ranking.py`, `scrapers/tests/test_quality.py`.
- Finding: high-value keyword matches are anti-correlated with learned taste on the current feed (0.0162 mean taste versus 0.0254 for non-matches). Nineteen events double- or triple-match overlapping phrases, and venue names duplicate data-driven source quality.
- Proposal: collapse all high-value phrase matches to one +0.15 nudge; remove exact overlaps with hard blocks (`after hours`, `nightclub`, `matchmaking`) and venue-specific literals (`brooklyn brewery`, `brooklyn bowl`, `house of yes`, `elsewhere`, `the broadway`, `knockdown center`). Preserve hard blocks, drinking penalties, alcohol-free boosts, social priors, and the remaining generic high-value vocabulary.
- Expected effect on the current feed: top-12 mean taste 0.0582→0.0650 and explicit conviction 8/12→10/12; top-30 mean taste 0.0395→0.0452 and explicit conviction 11/30→13/30.
