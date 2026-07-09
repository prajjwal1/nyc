"""Apply client-side engagement back into the pipeline's preference layer.

This closes the loop that `ranking._user_curated_boost` documents but that no
code implemented: the browser accumulates rich engagement in localStorage
(saves, opens, "did you go?", hides) as a weighted InterestProfile, but it
never reached the scraper — so preferences were hand-edited instead.

The client (see site/app/lib/tasteExport.ts, Phase B) writes a snapshot to
`scrapers/data/user_engagement.json` mirroring the localStorage
`InterestProfile` aggregate:

    {
      "updatedAt": "<ISO>",
      "accounts":    {"<handle>": <weight>},   # +5 save, +8 attended-yes, +3 open
      "hosts":       {"<domain>": <weight>},
      "categories":  {"<cat>": <weight>},
      "negAccounts": {"<handle>": <hide_count>},
      "negHosts":    {"<domain>": <hide_count>}
    }

`apply_engagement()` merges that into the LEARNED preference files:
  - positive accounts/hosts (weight >= POS_THRESHOLD) -> user_curated_sources.json
    hosts (URL-substring matchers already used by _is_curated_host /
    _user_curated_boost -> boost + lower score floor + shell bypass).
  - negative accounts/hosts (hides >= NEG_THRESHOLD) -> user_excluded_sources.json.

It is idempotent, additive (never rewrites human `user_mentioned` entries),
source-tagged (`engagement_*`), capped per run, and a no-op when the snapshot
is absent. Run at the START of run_all so the same run's ranking sees it.
"""
from __future__ import annotations

import collections
import json
import os

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

# Weight thresholds (client bumps: save +5, attended-yes +8, open +3, hide +1
# on the negative maps). >=5 ~ "saved at least once / opened repeatedly".
POS_THRESHOLD = 5
NEG_THRESHOLD = 3
MAX_ADDS_PER_RUN = 25  # backstop against a runaway snapshot

# Hosts too broad to curate as a whole — boosting these would float an entire
# aggregator, not a taste. Engagement with them is noise at the host level.
_TOO_BROAD_HOSTS = {
    "eventbrite.com", "www.eventbrite.com", "meetup.com", "www.meetup.com",
    "allevents.in", "instagram.com", "www.instagram.com", "lu.ma", "luma.com",
    "partiful.com", "dice.fm", "songkick.com", "ra.co", "facebook.com",
}


def _load(path: str) -> dict:
    try:
        with open(path) as f:
            return json.load(f, object_pairs_hook=collections.OrderedDict)
    except Exception:
        return collections.OrderedDict()


def _key(s: str) -> str:
    return (s or "").strip().lower()


def apply_engagement(data_dir: str = _DATA_DIR, *, today: str | None = None) -> dict:
    """Merge user_engagement.json into curated/excluded preference files.

    Returns a summary dict (counts) for logging. No-op (all zeros) when the
    snapshot is missing. Never raises on bad input — degrades to no-op.
    """
    summary = {"curated_added": 0, "excluded_added": 0, "skipped_conflict": 0, "present": False}
    snap_path = os.path.join(data_dir, "user_engagement.json")
    snap = _load(snap_path)
    if not snap:
        return summary
    summary["present"] = True
    today = today or snap.get("updatedAt", "")[:10] or "engagement"

    curated_path = os.path.join(data_dir, "user_curated_sources.json")
    excluded_path = os.path.join(data_dir, "user_excluded_sources.json")
    curated = _load(curated_path)
    excluded = _load(excluded_path)
    curated.setdefault("hosts", collections.OrderedDict())
    curated.setdefault("title_hints", collections.OrderedDict())
    for k in ("accounts", "hosts", "title_hints"):
        excluded.setdefault(k, collections.OrderedDict())

    excluded_keys = {_key(k) for k in excluded["accounts"]} | {_key(k) for k in excluded["hosts"]}
    curated_host_keys = {_key(k) for k in curated["hosts"]}

    # --- Negatives first: repeated hides -> exclusion (hides win over boosts) ---
    neg_added = 0
    for bucket_name, target in (("negAccounts", "accounts"), ("negHosts", "hosts")):
        for name, count in (snap.get(bucket_name) or {}).items():
            if neg_added >= MAX_ADDS_PER_RUN:
                break
            nk = _key(name)
            if not nk or (count or 0) < NEG_THRESHOLD:
                continue
            if nk in {_key(k) for k in excluded[target]}:
                continue
            excluded[target][name] = {
                "reason": "engagement_hidden",
                "added_at": today,
                "note": f"auto: {count} hides in-app",
            }
            excluded_keys.add(nk)
            neg_added += 1
    summary["excluded_added"] = neg_added

    # --- Positives: strong saves/opens/attends -> curated hosts ---
    pos_added = 0
    positives: list[tuple[str, float]] = []
    positives += list((snap.get("hosts") or {}).items())
    positives += list((snap.get("accounts") or {}).items())
    # Highest-weight first so the per-run cap keeps the strongest signals.
    for name, weight in sorted(positives, key=lambda kv: -(kv[1] or 0)):
        if pos_added >= MAX_ADDS_PER_RUN:
            break
        pk = _key(name)
        if not pk or (weight or 0) < POS_THRESHOLD:
            continue
        if pk in _TOO_BROAD_HOSTS or pk in curated_host_keys:
            continue
        if pk in excluded_keys:  # user also hid it — exclusion wins, don't curate
            summary["skipped_conflict"] += 1
            continue
        curated["hosts"][name] = {
            "score": 1.0,
            "added_at": today,
            "source": "engagement_saved",
            "note": f"auto: engagement weight {weight}",
        }
        curated_host_keys.add(pk)
        pos_added += 1
    summary["curated_added"] = pos_added

    if neg_added:
        excluded["lastUpdated"] = today
        with open(excluded_path, "w") as f:
            json.dump(excluded, f, indent=2)
    if pos_added:
        curated["lastUpdated"] = today
        with open(curated_path, "w") as f:
            json.dump(curated, f, indent=2)
    return summary
