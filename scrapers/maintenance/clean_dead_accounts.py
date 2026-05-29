"""Clean stale transient-killed entries from `dead_accounts.json`.

The 2026-05-24 mass-kill swept 54 accounts as `repeated_failure` from a
transient `feedback_required` IG throttle (see iter 1 P1 in
`.claude/self-improve/`). The skip-set builder in `instagram.py` now
auto-revives these at runtime, but the file itself still carries the
stale entries. This script purges them so sanity_check + future reads
are honest.

Idempotent: running twice is a no-op once the entries are gone.

Usage:
    python -m scrapers.maintenance.clean_dead_accounts        # dry-run by default
    PURGE=1 python -m scrapers.maintenance.clean_dead_accounts  # apply
"""
from __future__ import annotations

import json
import os
from pathlib import Path


DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "dead_accounts.json"

# Re-export instagram._TRANSIENT_FAILURE_MARKERS as the single source of
# truth. The previous duplicated tuple drifted easily; importing keeps
# both definitions in lockstep.
from scrapers.sources.instagram import _TRANSIENT_FAILURE_MARKERS as TRANSIENT_MARKERS  # noqa: E402


def _is_transient_kill(info: dict) -> bool:
    if info.get("reason") != "repeated_failure":
        return False
    last_reason = (info.get("last_reason") or "").lower()
    return any(m in last_reason for m in TRANSIENT_MARKERS)


def main() -> int:
    if not DATA_PATH.is_file():
        print(f"[clean_dead_accounts] {DATA_PATH} not found")
        return 1
    data = json.loads(DATA_PATH.read_text())
    accounts = data.get("accounts", {})
    before = len(accounts)
    to_drop = [u for u, info in accounts.items() if _is_transient_kill(info)]
    if not to_drop:
        print(f"[clean_dead_accounts] {before} entries; nothing to clean (no transient repeated_failure rows)")
        return 0
    print(f"[clean_dead_accounts] Found {len(to_drop)} transient repeated_failure entries to clean:")
    for u in to_drop[:10]:
        info = accounts[u]
        print(f"  @{u}  last_reason={(info.get('last_reason') or '')[:60]}")
    if len(to_drop) > 10:
        print(f"  … and {len(to_drop) - 10} more")
    if not os.environ.get("PURGE"):
        print("\n[clean_dead_accounts] DRY-RUN. Set PURGE=1 to apply.")
        return 0
    for u in to_drop:
        del accounts[u]
    DATA_PATH.write_text(json.dumps(data, indent=2, sort_keys=True))
    print(f"\n[clean_dead_accounts] Removed {len(to_drop)} entries; {len(accounts)} remain.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
