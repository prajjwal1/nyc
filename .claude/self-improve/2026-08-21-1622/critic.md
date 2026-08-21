# Critic verdicts

## ingestion-P1 — APPROVE with conservative scope

The evidence supports reducing the legacy positive layer, but not deleting every zero-hit phrase from one snapshot. Apply only the structurally redundant pieces:

- remove source/venue literals that belong in `SOURCE_QUALITY` or `user_curated_sources.json`;
- remove exact positive-list overlaps with hard-blocked terms;
- cap overlapping high-value phrases to one hit;
- add regression tests for all three invariants.

This keeps explicit user policy intact and gives semantic taste and explicit follow/save/affinity signals more room in the bounded stack. The projected top-30 retains 24 organizers, 14 categories, max organizer share 6.7%, and max repeated series 1.

## Deferred directives

- fb-138: acceptable deferral; requires Reddit OAuth credentials.
- fb-158: acceptable deferral; deletion is user-gated and needs fresh live probes.
- fb-199: partial progress only; do not remove all current zero-hit phrases until explicit engagement supplies negative examples.

No dream proposal is approved this round; the change should remain tightly scoped.
