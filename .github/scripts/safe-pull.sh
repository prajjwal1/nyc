#!/usr/bin/env bash
# Safe pull-and-rebase for workflows that have committed scrape output
# in the working tree. The naive `git pull --rebase --autostash || true`
# silently commits conflict markers when parallel crons touch the same
# data files (events.json got conflict-markered for a week before this
# was noticed). This script: stash our outputs, hard-reset to origin/main,
# pop the stash, and on conflict ALWAYS take our fresh scrape output.
#
# Usage: .github/scripts/safe-pull.sh path1 path2 ...
# Paths are the data files this run wrote; we stash & re-apply just those.
set -e
git fetch origin main
if [ "$#" -gt 0 ]; then
  git stash push -m "scrape-output" -- "$@" 2>/dev/null || true
fi
git reset --hard origin/main
git stash pop 2>/dev/null || true
# Any unresolved conflicts after stash-pop → take ours (fresh scrape wins).
for f in $(git diff --name-only --diff-filter=U); do
  git checkout --ours -- "$f"
  git add -- "$f"
done
