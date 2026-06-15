---
name: self-improve
description: Run the self-improving agent team. Audits the deployed NYC events site, collects user feedback (throttled), gets proposals from Ingestion / Source Curator / UI workers, runs the Dreamer/Critic for verdicts, applies approved changes, verifies (sanity_check + build), and auto-commits to main.
argument-hint: <optional override — "force-ask" to bypass the 7-day feedback throttle, "dry-run" to skip the commit>
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - WebFetch
  - Agent
  - AskUserQuestion
---

# /self-improve — the orchestrator

This command runs the full agent loop for the NYC events site. Read this top-to-bottom before doing anything — phases are sequential and each depends on the prior one's artifacts.

## North Star (don't lose sight of this)

> **Surface events the user would actually attend in NYC.**

Three metrics, computed before/after the run:
1. **Follow-graph coverage** — % of `signal_accounts` in `scrapers/data/user_interest_profile.json` whose `yield_map` value > 0.
2. **Topic coverage** — every `topic_counts` entry (count ≥ 2) is represented in the deployed feed.
3. **High-conviction event ratio** — % of feed events where `userFollowing` / `userSaved` / `userAffinity` boost fires.

Argument: `$ARGUMENTS`. Recognized values:
- empty → normal run
- `force-ask` → bypass the 7-day feedback throttle and ask the user a question this round
- `dry-run` → run all phases but skip the commit + push at the end

## Phase 0 — Bootstrap

1. Generate `run_id = $(date -u +%Y-%m-%d-%H%M)`. Create `/Users/prajj/nyc-events/.claude/self-improve/<run_id>/`.
2. Read prior context (all of these go into your working memory before invoking workers):
   - `/Users/prajj/nyc-events/.claude/self-improve/journal.md`
   - `/Users/prajj/nyc-events/.claude/self-improve/feedback-backlog.md`
   - `/Users/prajj/nyc-events/scrapers/data/user_interest_profile.json`
3. Compute "metrics-before" by writing and running a small inline Python script:
   ```bash
   cd /Users/prajj/nyc-events && source venv/bin/activate && python3 <<'PY'
   import json
   from collections import Counter
   prof = json.load(open('scrapers/data/user_interest_profile.json'))
   sig = set(prof.get('signal_accounts', []))
   ymap = prof.get('yield_map', {})
   topics = prof.get('topic_counts', {})
   nz = sum(1 for a in sig if ymap.get(a, 0) > 0)
   import urllib.request
   try:
       feed = json.loads(urllib.request.urlopen('https://prajjwal1.github.io/nyc/events.json', timeout=20).read())
   except Exception as e:
       feed = json.load(open('site/public/events.json'))
   events = feed.get('events', [])
   TOPIC_SYNONYMS = {'bk': ('bk', 'brooklyn'), 'brooklyn': ('brooklyn', 'bk')}
   topic_rep = {t: 0 for t, c in topics.items() if c >= 2}
   for e in events:
       txt = (e.get('title','') + ' ' + ' '.join(e.get('categories', []) or []) + ' ' + e.get('description','')[:300]).lower()
       for t in list(topic_rep):
           needles = TOPIC_SYNONYMS.get(t, (t,))
           if any(n in txt for n in needles): topic_rep[t] += 1
   high = sum(1 for e in events if any(e.get(k) for k in ('userFollowing','userSaved','userAffinity')))
   print('FOLLOW_GRAPH_COVERAGE:', f'{nz}/{len(sig)}', f'({100*nz/max(1,len(sig)):.1f}%)')
   print('TOPIC_COVERAGE:', {t: topic_rep[t] for t in topic_rep})
   print('HIGH_CONVICTION_RATIO:', f'{high}/{len(events)}', f'({100*high/max(1,len(events)):.1f}%)')
   PY
   ```
   Save the output to `<run_dir>/metrics-before.md`.

## Phase 1 — Feedback collection

1. Determine the 7-day throttle: read `feedback-backlog.md` for the most recent `created_at: user-explicit` entry. If `$ARGUMENTS` contains `force-ask` OR (more than 7 days have passed AND fewer than 3 open items exist), the question gate is open.
2. Invoke the **feedback-collector** subagent. Hand it: the backlog path, the journal path, the user_interest_profile path, and whether the question gate is open.
3. If the agent's report (`<run_dir>/feedback.md`) lists "Questions to ask the user this round", call `AskUserQuestion` with those questions. The first question should typically be a calibration question grounded in the follow-graph — pull 3 highest-scored events from the live feed where `userFollowing` fired, and ask "Which of these would you actually go to?" with those 3 as options.
4. After the user answers, re-invoke the feedback-collector with the answers so it can persist them to `feedback-backlog.md` and finalize the top-3 directives. The final `feedback.md` is what Phase 2 workers consume.

If the gate is closed, skip steps 3 + 4; the agent just refreshes the top-3 directives from existing open items.

## Phase 2 — Workers (parallel)

Spawn three agents in a **single message with three Agent tool calls** so they run in parallel:

- `ingestion-quality` → writes `<run_dir>/ingestion.md`
- `source-curator` → writes `<run_dir>/source-pool.md`
- `ui-agent` → writes `<run_dir>/ui.md`

Each agent prompt must include:
- The run dir absolute path.
- The North Star block (verbatim — copy the three metrics from this file).
- The path to `<run_dir>/feedback.md` (the top-3 directives — they MUST be addressed or formally deferred).
- The path to `journal.md` (prior context).

Wait for all three to finish before moving on.

## Phase 3 — Dreamer/Critic

Invoke the **dreamer-critic** subagent. Hand it:
- All four prior reports (`feedback.md`, `ingestion.md`, `source-pool.md`, `ui.md`).
- `<run_dir>/metrics-before.md`.
- The journal + backlog paths.

It writes `<run_dir>/critic.md` with one verdict per proposal + critique-back notes + dream proposals.

## Phase 4 — Apply approved changes

Parse `critic.md`. For each verdict:
- **APPROVE** → apply the worker's original change (Edit/Write/Bash).
- **MODIFY** → apply the Critic's modified change.
- **REJECT** → skip; log to `<run_dir>/applied.md` as `[skipped] <id> — <reason>`.
- **APPROVE-DREAM** → apply the Critic's dream change.
- **DREAM-DEFER** → append a new entry to `feedback-backlog.md` with `source: agent-proposal`, `status: open`.

Group fixes by area for atomicity:
- All `scrapers/` edits together.
- All `site/` edits together.

Write `<run_dir>/applied.md`:
```
# Applied changes
- [x] ingestion-P1: <title> — file:line
- [ ] ingestion-P2: <skipped, rejected by critic — reason>
- [x] source-pool-S1: <title>
…
- Deferred to backlog: D2 (added as fb-NNN)
```

## Phase 5 — Verify

Run both:
```bash
cd /Users/prajj/nyc-events && source venv/bin/activate && python -m scrapers.sanity_check
```
```bash
cd /Users/prajj/nyc-events/site && npx next build
```

If `sanity_check` fails:
- Identify which `CRITICAL_CHECK` regressed.
- Revert the most recent `scrapers/` edits via `git checkout HEAD -- scrapers/` (only files modified in this run — use `git diff --name-only` to scope).
- Re-run sanity_check to confirm clean.
- Log to `<run_dir>/verification.md` what was rolled back and why.

If `next build` fails:
- Revert `site/` edits with `git checkout HEAD -- site/`.
- Re-run build to confirm.
- Log to `<run_dir>/verification.md`.

After any rollback, the run proceeds with only the safe subset.

Then re-compute the metrics from Phase 0 and write `<run_dir>/metrics-after.md`. Compute the deltas.

## Phase 6 — Commit + journal + backlog update

If `$ARGUMENTS` contains `dry-run`, skip the commit. Otherwise:

1. Stage and commit:
   ```bash
   cd /Users/prajj/nyc-events && git add scrapers/ site/ .claude/self-improve/
   git commit -m "$(cat <<'EOF'
   Self-improve <run_id>: <one-line summary>

   <bullet list of what shipped, one line each>

   Metrics: follow-graph <before>→<after>, topic <before>→<after>, conviction <before>→<after>.
   EOF
   )"
   git push
   ```
2. Append to `journal.md` with the standard entry format (see the journal file itself for the template). Include the metric deltas verbatim.
3. Update `feedback-backlog.md`: for every backlog item whose directive was addressed, set status to `addressed: <sha>` (the new commit's SHA). For deferrals approved by the Critic, set `wont-do: <Critic-reason>` only if the deferral was final; otherwise leave `open` so a future run can pick it up.

If nothing was applied this round (Critic REJECTed everything or no proposals were made), still append a journal entry: `"no fixes needed; metrics stable"`. Do not force a change.

## Phase 7 — Report back

Summarize for the user in 4–6 lines:
- Run id + what shipped.
- Metric delta (the three numbers, before → after).
- Anything rejected and why.
- Any user feedback collected.
- Anything deferred to the backlog.

End with the commit SHA + a link to the run directory.

## Operational rules

- **Never** call `git push --force`, `git reset --hard`, or skip pre-commit hooks. Use `git checkout HEAD -- <path>` for surgical reverts.
- **Never** edit `feedback-backlog.md` entries' `body` text. You may change their `status` (with a SHA or Critic-approved reason) and add new entries.
- **Never** wipe pipeline state files (`scrapers/data/*.json`). They are the system's memory.
- If a subagent's report is empty, malformed, or doesn't follow its template: re-invoke it once with the failure noted. If it fails twice, log it to `verification.md` and continue without that worker's contribution.
- If you're unsure whether to apply a Critic verdict, default to skipping and logging — safer than committing the wrong thing.
- This loop trusts the team but verifies via sanity_check + build. Don't bypass either step.
