# Critic Report — 2026-09-22 1436

## Cross-check results

- Sanity-check regression risk: low; none of the six rejected rows satisfies a critical inventory check uniquely.
- Duplicate source proposals: all three Lu.ma topic URLs duplicate the city catalog; reject.
- User-excluded check: P1 directly enforces the durable no-AI rule and public-attendance requirement.
- UI preference compliance: OK; no UI code proposed.
- Top-three directive coverage: fb-218 approved and implemented; fb-219 proceeds after verification; fb-216 is closed with current learned-frontier evidence.

## Verdicts

### ingestion-P1: Enforce title-level AI and non-public-event exclusions
- **Verdict**: APPROVE
- **Metric moved**: quality of high-conviction inventory; six false-positive rows go to zero. The raw high-conviction ratio moves 69/693 (9.96%) to 68/687 (9.90%) because one excluded AI event had a personalization flag; this is a correction of a false signal, not a relevance regression.
- **Reasoning**: the matches come from the current feed and reflect explicit durable preferences. Title-only matching and the `Ai Weiwei`/incidental-description controls keep the rule narrow.

### source-pool-S1: Add the seven probed candidate URLs
- **Verdict**: REJECT
- **Metric moved**: topic coverage would not improve; expected net distinct clean events are zero.
- **Reasoning**: three URLs are duplicate catalog aliases, three are blocked or empty, and the Eventbrite collection is mostly outside NYC. Lowering the source gate would trade quality for count.

### ui-U1: Keep the current UI unchanged
- **Verdict**: APPROVE
- **Metric moved**: preserves the current 57% personal signal among top recommendations and the clean interaction model.
- **Reasoning**: the audit found no UI regression, and the live defect belongs in normalization.

## Notes back to each worker

### Notes back to ingestion-quality
- You missed: future sanity checks do not yet assert that every persisted event still passes `is_blocked`; consider a post-normalization invariant after the checked-in feed is regenerated.
- Strong work on: using actual live titles and protecting incidental description text.

### Notes back to source-curator
- You missed: source expansion from `344a2f0f` now has enough longitudinal evidence to close fb-216; evaluating only static config would undercount it.
- Strong work on: refusing duplicate/off-geography candidates despite nominal yields.

### Notes back to ui-agent
- You missed: the 36% description-completeness warning is severe, although correctly classified as upstream.
- Strong work on: preserving the user-requested removal of Hide/× controls.

## Dream proposals

### D1: Source-native description enrichment with a bounded fetch budget
- **Verdict**: DREAM-DEFER
- **Metric moved**: event decision quality; target showcased description completeness from 36% toward 60% without reducing freshness.
- **File**: `scrapers/sources/luma.py`, `scrapers/sources/eventbrite.py`
- **Change sketch**: hydrate only missing-description events that enter the top recommendation window, cache successful detail payloads, cap requests per run, and measure fill rate plus rate-limit failures before expanding.

