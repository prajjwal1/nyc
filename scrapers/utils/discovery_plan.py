"""Shared personalized discovery lanes and bounded 70/30 selection.

Scrapers should discover broadly, then use this module when a source needs a
volume cap.  Seventy percent of a capped source is reserved for events that
match explicit engagement/profile signals; the remaining thirty percent is a
deliberate exploration lane.  The lane and human-readable reasons are also
written to the public event payload for recommendation explainability.
"""
from __future__ import annotations

import json
import os
import re
from datetime import date
from urllib.parse import urlparse

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
PERSONAL_SHARE = 0.70


def _load(name: str) -> dict:
    try:
        with open(os.path.join(DATA_DIR, name)) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def preference_snapshot() -> dict:
    engagement = _load("user_engagement.json")
    profile = _load("user_interest_profile.json")
    curated = _load("user_curated_sources.json")
    excluded = _load("user_excluded_sources.json")
    return {
        "categories": engagement.get("categories") or {},
        "neg_categories": engagement.get("negCategories") or {},
        "accounts": engagement.get("accounts") or {},
        "hosts": engagement.get("hosts") or {},
        "topics": profile.get("topic_counts") or {},
        "signal_accounts": set(profile.get("signal_accounts") or []),
        "curated_hosts": set((curated.get("hosts") or {}).keys()),
        "excluded_accounts": set((excluded.get("accounts") or {}).keys()),
        "excluded_hosts": set((excluded.get("hosts") or {}).keys()),
    }


def _fold(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def _fallback_reason(event: dict) -> str:
    """Return a specific, user-legible reason for non-conviction picks."""
    if (event.get("tasteScore") or 0) >= 0.04:
        return "Similar to events you liked"
    highlights = set(event.get("highlights") or [])
    if "meet-people" in highlights:
        return "Good for meeting people"
    if "trending" in highlights:
        return "Trending across NYC"
    neighborhood = ((event.get("location") or {}).get("neighborhood") or "").strip()
    if neighborhood.lower() in {"williamsburg", "greenpoint", "bushwick", "ridgewood"}:
        return f"Nearby in {neighborhood.title()}"
    sources = event.get("contributingSources") or []
    if len(sources) >= 2:
        return f"Confirmed by {len(sources)} sources"
    try:
        days = (date.fromisoformat(event.get("date") or "") - date.today()).days
        if 0 <= days <= 7:
            return "Happening this week"
    except ValueError:
        pass
    categories = [c for c in (event.get("categories") or []) if c not in {"other", "free"}]
    if categories:
        return f"A strong {categories[0]} pick"
    source = (event.get("source") or "").replace("_", " ").strip()
    return f"From {source.title()}" if source else "New to the feed"


def annotate_event(event: dict, prefs: dict | None = None) -> dict:
    prefs = prefs or preference_snapshot()
    reasons: list[str] = []
    cats = set(event.get("categories") or [])
    account = (event.get("account") or event.get("organizer") or event.get("instagramAccount") or "").lower()
    account_fold = _fold(account)
    url = event.get("organizerUrl") or event.get("sourceUrl") or ""
    host = urlparse(url).hostname or ""

    positive_cats = sorted(
        (c for c in cats if (prefs["categories"].get(c, 0) or 0) > 0),
        key=lambda c: -(prefs["categories"].get(c, 0) or 0),
    )
    if positive_cats:
        reasons.append("Matches " + " + ".join(positive_cats[:2]))
    elif cats:
        topic_match = [c for c in cats if (prefs["topics"].get(c, 0) or 0) >= 2]
        if topic_match:
            reasons.append("Matches your " + topic_match[0] + " interests")

    known_accounts = {_fold(a) for a in prefs["signal_accounts"]} | {
        _fold(a) for a, n in prefs["accounts"].items() if (n or 0) > 0
    }
    if account_fold and account_fold in known_accounts:
        reasons.insert(0, f"From {event.get('organizer') or event.get('account') or account}")
    if any(h and (h in url.lower() or h in host) for h in prefs["curated_hosts"]):
        reasons.append("From a source you like")
    if event.get("userSaved"):
        reasons.insert(0, "You saved this")
    elif event.get("userFollowing"):
        reasons.insert(0, "From an account you follow")

    planned_personal = event.get("discoveryLane") == "personal"
    if not reasons and planned_personal:
        reasons.append(_fallback_reason(event))
    event["discoveryLane"] = "personal" if reasons else "explore"
    if reasons:
        event["recommendationReasons"] = list(dict.fromkeys(reasons))[:3]
    else:
        event["recommendationReasons"] = [_fallback_reason(event)]
    return event


def select_mixed(events: list[dict], limit: int, personal_share: float = PERSONAL_SHARE) -> list[dict]:
    """Select a deterministic score-ordered mix, backfilling either lane."""
    prefs = preference_snapshot()
    for event in events:
        annotate_event(event, prefs)
    ordered = sorted(events, key=lambda e: e.get("score", 0), reverse=True)
    personal = [e for e in ordered if e.get("discoveryLane") == "personal"]
    explore = [e for e in ordered if e.get("discoveryLane") == "explore"]
    p_limit = round(limit * personal_share)
    chosen = personal[:p_limit] + explore[: max(0, limit - min(p_limit, len(personal)))]
    if len(chosen) < limit:
        used = {id(e) for e in chosen}
        chosen.extend(e for e in ordered if id(e) not in used and len(chosen) < limit)
    return sorted(chosen[:limit], key=lambda e: e.get("score", 0), reverse=True)
