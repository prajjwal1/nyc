"""Shared helper for user_excluded_sources.json::accounts.

Six different modules were each defining a near-identical loader for the
excluded-accounts set. Consolidating here so changes to the file format
(or its location) only need to be made in one place. The loader is
side-effect-free and re-reads on every call — small enough that caching
is unnecessary, and re-reading lets `user_excluded_sources.json` edits
take effect on the next call without a process restart.
"""
from __future__ import annotations

import json
import os


_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "user_excluded_sources.json",
)


def load_excluded_account_set() -> set[str]:
    """Lowercased usernames in user_excluded_sources.json::accounts.

    Returns an empty set if the file is missing or malformed. Callers
    should subtract this set before doing follow-graph operations
    (priority cache, signal_accounts, enrichment, topAccounts widget,
    discovery harvest) so excluded handles never propagate.
    """
    if not os.path.isfile(_PATH):
        return set()
    try:
        with open(_PATH) as f:
            d = json.load(f)
        return {k.lower() for k in (d.get("accounts") or {}).keys()}
    except Exception:
        return set()
