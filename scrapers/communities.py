"""Deterministic community identity, history, and public aggregation.

This module deliberately does no network discovery.  It turns the canonical
identities already attached to events into a small, auditable community
registry.  Exact platform IDs/URLs are the only automatic merge keys; fuzzy
name matches are emitted as candidates rather than silently merged.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
OVERRIDES_PATH = ROOT / "scrapers" / "data" / "community_overrides.json"
HISTORY_PATH = ROOT / "data" / "community_history.json"
CANDIDATES_PATH = ROOT / "data" / "community_candidates.json"
ANALOG_INDEX_PATH = ROOT / "data" / "analog_directory_index.json"
PUBLIC_PATHS = (ROOT / "data" / "communities.json", ROOT / "site" / "public" / "communities.json")

DEDICATED_SOURCES = {
    "bookclubbar": ("Book Club Bar", "community_space"),
    "lizsbookbar": ("Liz's Book Bar", "community_space"),
    "brooklyncontra": ("Brooklyn Contra", "club"),
    "brooklyncomedy": ("Brooklyn Comedy Collective", "community_space"),
    "centerforfiction": ("The Center for Fiction", "institutional_program"),
    "mcnallyjackson": ("McNally Jackson", "institutional_program"),
    "powerhousearena": ("POWERHOUSE Arena", "institutional_program"),
}


def _fold(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")


def _load(path: Path, default):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def _atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2) + "\n")
    tmp.replace(path)


def _identity_groups(event: dict) -> list[list[tuple[str, str, str]]]:
    """Identity aliases grouped by real-world organizer (one group per host)."""
    groups = []
    for ref in event.get("organizerRefs") or []:
        if not isinstance(ref, dict) or ref.get("role") in {"venue", "performer"}:
            continue
        platform = _fold(str(ref.get("platform") or event.get("source") or "unknown"))
        external = str(ref.get("externalId") or "").lower().strip().strip("@")
        handle = str(ref.get("handle") or "").lower().strip().strip("@")
        url = str(ref.get("url") or "").strip()
        name = str(ref.get("name") or handle or "").strip()
        if not name:
            continue
        aliases = []
        if external:
            aliases.append((f"{platform}:{external}", name, url))
        elif url:
            aliases.append(("url:" + url.split("?")[0].rstrip("/").lower(), name, url))
        if handle:
            aliases.append((f"instagram:{handle}", name, f"https://www.instagram.com/{handle}/"))
        if aliases:
            groups.append(list(dict.fromkeys(aliases)))
    if groups:
        return groups
    primary = _fallback_identity(event)
    return [[primary]] if primary else []


def platform_identities(event: dict) -> list[tuple[str, str, str]]:
    """Return exact (stable key, display name, public URL) organizer identities."""
    return [identity for group in _identity_groups(event) for identity in group]


def _fallback_identity(event: dict) -> tuple[str, str, str] | None:
    source = event.get("source") or ""
    if source in DEDICATED_SOURCES:
        name, _ = DEDICATED_SOURCES[source]
        return (f"source:{source}", name, event.get("organizerUrl") or event.get("sourceUrl") or "")

    organizer_url = (event.get("organizerUrl") or "").strip()
    organizer = (event.get("organizer") or "").strip()
    if organizer_url:
        normalized = organizer_url.split("?")[0].rstrip("/").lower()
        if organizer:
            return (f"url:{normalized}", organizer, organizer_url)

    if source == "meetup":
        match = re.search(r"meetup\.com/([^/]+)/", event.get("sourceUrl") or "", re.I)
        if match and match.group(1).lower() not in {"events", "find"}:
            slug = match.group(1).lower()
            return (f"meetup:{slug}", organizer or slug.replace("-", " ").title(), f"https://www.meetup.com/{slug}/")

    # Luma calendar/account identifiers are canonical even where an organizer
    # display name was not included in the listing response.
    if source == "luma" and event.get("account"):
        account = str(event["account"]).lower().strip("@")
        return (f"luma:{account}", organizer or account.replace("-", " ").title(), f"https://lu.ma/{account}")

    # IG publishers are only candidates by default. Overrides can promote a
    # true community; this avoids treating every media/recommendation account
    # as a community.
    if source == "instagram" and event.get("instagramAccount"):
        account = str(event["instagramAccount"]).lower().strip("@")
        return (f"instagram:{account}", f"@{account}", f"https://www.instagram.com/{account}/")
    return None


def platform_identity(event: dict) -> tuple[str, str, str] | None:
    """Backward-compatible accessor for the primary exact identity."""
    identities = platform_identities(event)
    return identities[0] if identities else None


def _community_id(identity: str) -> str:
    return "com_" + hashlib.sha256(identity.encode()).hexdigest()[:12]


def _infer_type(source: str, name: str) -> str:
    if source in DEDICATED_SOURCES:
        return DEDICATED_SOURCES[source][1]
    if source == "meetup":
        return "club"
    text = name.lower()
    if any(x in text for x in ("club", "society", "group", "meetup")):
        return "club"
    if any(x in text for x in ("center", "library", "museum", "university")):
        return "institutional_program"
    return "recurring_series"


def _cadence(observations: list[dict]) -> dict | None:
    dates = sorted({o["date"] for o in observations if o.get("date")})
    if len(dates) < 2:
        return None
    parsed = [date.fromisoformat(d) for d in dates]
    gaps = [(b - a).days for a, b in zip(parsed, parsed[1:]) if b > a]
    median = sorted(gaps)[len(gaps) // 2] if gaps else 0
    if median <= 10:
        label = "weekly"
    elif median <= 21:
        label = "biweekly"
    elif median <= 45:
        label = "monthly"
    else:
        label = "occasional"
    weekdays = Counter(d.strftime("%A") for d in parsed)
    times = Counter(o.get("startTime") for o in observations if o.get("startTime"))
    return {
        "label": label,
        "sampleSize": len(dates),
        "confidence": round(min(1.0, len(dates) / 6), 2),
        "typicalWeekdays": [x for x, _ in weekdays.most_common(2)],
        "typicalStartTimes": [x for x, _ in times.most_common(2)],
    }


def build_communities(events: list[dict], *, today: date | None = None, persist: bool = True, update_registry: bool = True) -> list[dict]:
    """Link events in-place and return the qualified public communities."""
    today = today or datetime.now(timezone.utc).date()
    override_doc = _load(OVERRIDES_PATH, {"communities": {}})
    overrides = override_doc.get("communities", {})
    previous = _load(HISTORY_PATH, {"communities": {}}).get("communities", {})
    analog_by_community_id = {
        entry.get("matchedCommunityId"): entry
        for entry in (_load(ANALOG_INDEX_PATH, {"communities": []}).get("communities") or [])
        if entry.get("matchedCommunityId") and entry.get("sourceUrl")
    }
    parent = {}
    def find(x):
        parent.setdefault(x, x)
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        def priority(key):
            return (key.startswith("url:"), key.startswith("instagram:"), key)
        winner, loser = sorted((ra, rb), key=priority)
        parent[loser] = winner

    event_groups = []
    for event in events:
        groups = _identity_groups(event)
        event_groups.append((event, groups))
        for group in groups:
            for identity in group:
                find(identity[0])
            for identity in group[1:]:
                union(group[0][0], identity[0])

    grouped: dict[str, list[dict]] = defaultdict(list)
    metadata = {}
    explicit_ref_keys = set()

    for event, groups in event_groups:
        identities = [identity for group in groups for identity in group]
        if event.get("organizerRefs"):
            explicit_ref_keys.update(key for key, _, _ in identities)
        for key, name, url in identities:
            if overrides.get(key, {}).get("excluded"):
                continue
            root = find(key)
            if event not in grouped[root]:
                grouped[root].append(event)
            # Prefer a named platform profile over its IG alias metadata.
            if root not in metadata or not key.startswith("instagram:"):
                metadata[root] = (name, url, event.get("source") or "unknown")

    communities = []
    candidates = []
    history_out = {}
    for key, current_events in sorted(grouped.items()):
        name, url, source = metadata[key]
        alias_keys = sorted(k for k in parent if find(k) == key)
        # An override may be authored against any known exact identity.
        override = {}
        for alias in alias_keys:
            override.update(overrides.get(alias, {}))
        name = override.get("name") or name
        old_cids = [old_cid for old_cid, old in previous.items() if old.get("identity") in alias_keys or set(old.get("aliases", [])) & set(alias_keys)]
        cid = override.get("id") or (sorted(old_cids)[0] if old_cids else _community_id(key))
        old_obs = previous.get(cid, {}).get("observations", [])
        new_obs = [
            {
                "eventId": e.get("id"), "date": e.get("date"),
                "startTime": e.get("startTime"), "title": e.get("title"),
                "neighborhood": (e.get("location") or {}).get("neighborhood"),
                "venue": (e.get("location") or {}).get("name"),
            }
            for e in current_events if e.get("date")
        ]
        cutoff = (today - timedelta(days=365)).isoformat()
        obs_by_id = {(o.get("eventId"), o.get("date")): o for o in old_obs + new_obs if (o.get("date") or "") >= cutoff}
        observations = sorted(obs_by_id.values(), key=lambda o: (o.get("date") or "", o.get("eventId") or ""))
        history_out[cid] = {"identity": key, "aliases": alias_keys, "observations": observations}

        # Exact organizer/calendar channels qualify. Instagram remains opt-in;
        # weak singletons without organizer identity remain candidates.
        qualified = bool(
            override.get("verified")
            or source in DEDICATED_SOURCES
            or key in explicit_ref_keys
            or (not key.startswith("instagram:") and (len(observations) >= 2 or key.startswith(("url:", "meetup:", "luma:"))))
        )
        if not qualified:
            candidates.append({"identity": key, "name": name, "url": url, "eventCount": len(current_events), "reason": "needs_first_party_verification"})
            continue

        for event in current_events:
            ids = list(dict.fromkeys((event.get("communityIds") or []) + [cid]))
            event["communityIds"] = ids
            event.setdefault("primaryCommunityId", cid)

        upcoming = sorted((e for e in current_events if (e.get("date") or "") >= today.isoformat()), key=lambda e: (e.get("date") or "", e.get("startTime") or ""))
        past_dates = [o.get("date") for o in observations if (o.get("date") or "") <= today.isoformat()]
        latest = max(past_dates, default="")
        age = (today - date.fromisoformat(latest)).days if latest else 9999
        state = "active" if upcoming or age <= 60 else "quiet" if age <= 180 else "stale"
        cats = Counter(c for e in current_events for c in (e.get("categories") or []))
        neighborhoods = Counter((e.get("location") or {}).get("neighborhood") for e in current_events if (e.get("location") or {}).get("neighborhood"))
        venues = Counter((e.get("location") or {}).get("name") for e in current_events if (e.get("location") or {}).get("name"))
        images = [e.get("imageUrl") for e in upcoming + current_events if e.get("imageUrl")]
        cadence = _cadence(observations)
        ninety_days_ago = (today - timedelta(days=90)).isoformat()
        event_count_90d = sum(ninety_days_ago <= (o.get("date") or "") <= today.isoformat() for o in observations)
        slug = override.get("slug") or f"{_fold(name) or 'community'}-{cid[-6:]}"
        community = {
            "id": cid, "slug": slug, "name": name,
            "kind": override.get("kind") or override.get("type") or _infer_type(source, name),
            "tagline": override.get("tagline") or (f"{name} events in NYC" if name else ""),
            "description": override.get("description") or "",
            "categories": [x for x, _ in cats.most_common(5)],
            "tags": [x for x, _ in cats.most_common(5)],
            "neighborhoods": [x for x, _ in neighborhoods.most_common(4)],
            "homeVenue": venues.most_common(1)[0][0] if venues else "",
            "imageUrl": override.get("imageUrl") or (images[0] if images else None),
            "links": [{"type": source, "label": f"View on {source.title()}", "url": override.get("officialUrl") or url}] if (override.get("officialUrl") or url) else [],
            "joinMethod": override.get("joinMethod") or "View an upcoming event",
            "activity": {"state": state, "lastEventDate": latest or None, "upcomingEventCount": len(upcoming), "eventCount90d": event_count_90d},
            "schedule": ({
                "cadence": cadence["label"], "typicalDays": cadence["typicalWeekdays"],
                "typicalTime": cadence["typicalStartTimes"][0] if cadence["typicalStartTimes"] else None,
                "confidence": cadence["confidence"], "sampleSize": cadence["sampleSize"],
            } if cadence else None),
            "upcomingEventIds": [e.get("id") for e in upcoming[:12] if e.get("id")],
            "sourceAttributions": [source],
            "lastVerifiedAt": today.isoformat(),
            "verified": True,
            "aliases": list(dict.fromkeys(override.get("aliases", []) + alias_keys)),
            "similarCommunityIds": [],
        }
        analog_reference = analog_by_community_id.get(cid)
        if analog_reference:
            community["links"].append({
                "type": "directory_reference",
                "label": "Analog Directory reference",
                "url": analog_reference["sourceUrl"],
            })
            community["sourceAttributions"].append("Analog Directory (reference)")
        communities.append(community)

    # Transparent, deterministic similarity. Popularity is never an input.
    for community in communities:
        scored = []
        for other in communities:
            if other["id"] == community["id"]:
                continue
            cats = set(community["categories"]); other_cats = set(other["categories"])
            hoods = set(community["neighborhoods"]); other_hoods = set(other["neighborhoods"])
            score = .5 * (len(cats & other_cats) / max(1, len(cats | other_cats))) + .2 * (len(hoods & other_hoods) / max(1, len(hoods | other_hoods)))
            if community.get("schedule") and other.get("schedule") and community["schedule"]["cadence"] == other["schedule"]["cadence"]:
                score += .15
            if score > 0:
                scored.append((score, other["id"]))
        community["similarCommunityIds"] = [cid for _, cid in sorted(scored, key=lambda x: (-x[0], x[1]))[:6]]

    if persist:
        generated = datetime.now(timezone.utc).isoformat()
        if update_registry:
            _atomic_json(HISTORY_PATH, {"communities": history_out, "updatedAt": generated})
            _atomic_json(CANDIDATES_PATH, {"candidates": candidates, "updatedAt": generated})
        payload = {"communities": communities, "lastUpdated": generated, "version": 1, "schemaVersion": 1}
        for path in PUBLIC_PATHS:
            _atomic_json(path, payload)
    return communities


def main() -> None:
    """Regenerate the registry/history and public aggregate from events.json."""
    payload = _load(ROOT / "data" / "events.json", {"events": []})
    communities = build_communities(payload.get("events", []), update_registry=True)
    _atomic_json(ROOT / "data" / "events.json", payload)
    _atomic_json(ROOT / "site" / "public" / "events.json", payload)
    print(f"Generated {len(communities)} communities")


if __name__ == "__main__":
    main()
