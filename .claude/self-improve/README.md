# Self-Improvement Loop

This directory is the home of the agent team that keeps making the NYC events website better. It's invoked by `/self-improve` from inside Claude Code.

## North Star

> **Surface events the user would actually attend in NYC.**

Operationalized as three metrics computed before/after every run:

1. **Follow-graph coverage** — % of `signal_accounts` in `scrapers/data/user_interest_profile.json` whose `yield_map` value > 0.
2. **Topic coverage** — every `topic_counts` entry with count ≥ 2 (`run`, `club`, `book`, `yoga`, `comedy`, `bk`, …) is represented in the deployed feed.
3. **High-conviction event ratio** — % of feed events where at least one of `userFollowing` / `userSaved` / `userAffinity` boosts fires.

## The team

- **Orchestrator** — `.claude/commands/self-improve.md`. Runs the phases, applies fixes, commits.
- **Feedback Collector** — `.claude/agents/feedback-collector.md`. Asks the user (throttled to once per 7 days), maintains `feedback-backlog.md`, ensures no item silently drops.
- **Ingestion Quality** — `.claude/agents/ingestion-quality.md`. Closes the 0-yield gap; improves IG + high-quality source extraction.
- **Source Curator** — `.claude/agents/source-curator.md`. Expands the URL/account pool along the user's interest vector (probes live).
- **UI Agent** — `.claude/agents/ui-agent.md`. Minimal-but-complete; surfaces follow-graph provenance.
- **Dreamer/Critic** — `.claude/agents/dreamer-critic.md`. Thinks, ponders, criticizes, tells other agents what they missed.

## What persists here

- `journal.md` — append-only log of every run: what shipped, what got rejected, metric deltas, hypothesis for next round.
- `feedback-backlog.md` — durable list of every piece of user feedback with `id` / `created_at` / `source` / `status` / `resolution`. Seeded from `README.md` §480–533.
- `<YYYY-MM-DD-HHMM>/` — per-run artifacts: `feedback.md`, `ingestion.md`, `source-pool.md`, `ui.md`, `critic.md`, `applied.md`, `metrics-before.md`, `metrics-after.md`, `verification.md` (if relevant).

## Invariants

- Every run reads `feedback-backlog.md` and `journal.md` *first* — past decisions inform present ones.
- An item is `addressed: <sha>` only when a commit actually implements the fix.
- Deferrals require an explicit Critic-accepted reason. No silent drops.
- `python -m scrapers.sanity_check` and `cd site && npx next build` both pass before any commit.
- If verify fails, the orchestrator reverts the failing area and ships only the safe subset.
