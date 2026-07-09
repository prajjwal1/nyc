# Metrics — after (run 2026-07-02-1735)

Code-only round (3rd consecutive); events.json NOT re-scraped → live-feed metrics unchanged by construction. Deltas land on the next scrape.

| Metric | Before | After | Delta |
|---|---|---|---|
| Follow-graph coverage | 15/50 (30.0%) | 15/50 (30.0%) | 0 (frozen) |
| Topic coverage | 0 zero-topics | 0 zero-topics | stable |
| High-conviction ratio | 64/365 (17.5%) | 64/365 (17.5%) | 0 (frozen) |

## What shipped (scrape-independent, test/build-verified)
- fb-189: neighborhood/name contradiction fix — conflicts 10→0 on the frozen feed (Critic-verified), also fixed "Singles Night"→LES mistag; WGB CRITICAL_CHECK strengthened 36→38.
- fb-186: `_infer_time_from_text` rebuilt (keyword cues + guarded bare-clock fallback); adversarially probed against 13 hostile inputs. Unblocks the fb-184 fitness startTime gate.
- fb-188: EventModal price-pill parity with FeedCard.

## Verification
- tests: 289 passed, 3 xfailed (20 new: 5 fb-189 + 15 fb-186).
- sanity_check: 2 criticals (NYC Backgammon Club, IG-dominant) — IDENTICAL to pre-run, pre-existing frozen-feed artifacts (fb-174 IG block), NOT regressions. No rollback.
- next build: clean.

## ⚠ 3rd consecutive frozen round — SCRAPE IS THE BINDING LEVER
Feed frozen at 2026-06-15 (408h / 17 days). ~4 rounds of committed levers unlanded (fitness/dance/games slugs, brooklyncontra, +12 IG seeds, philosophy fix, this round's neighborhood/time/modal fixes). Follow-graph (30%) and conviction (17.5%) CANNOT move without a scrape. Critic + source-curator both endorse: run `python -m scrapers.run_all` on a residential IP (CI IPs 403/429-blocked per fb-173; IG sweep blocked per fb-174). This is the single highest-leverage action available and has been flagged 3 rounds running.
