"""Shared discovery inputs for hosted event platforms.

The platform scrapers should not need a growing list of hand-maintained URLs.
This module turns signals the pipeline already owns into a bounded frontier:

* the user's interest profile and explicit category engagement;
* event-platform links harvested from Instagram, newsletters, and Reddit;
* organizer/calendar URLs that produced events in the previous feed; and
* a rotating sample of followed accounts for platforms whose calendar URL is
  derived from a public handle (currently Luma).

Platform-specific endpoint shapes and parsers stay in their adapters.  This
module only decides *what is worth trying* and keeps discovery deterministic,
deduplicated, and budgeted.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
import json
import os
import re
import time
from urllib.parse import urlparse, urlunparse


SCRAPERS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(SCRAPERS_DIR, "data")
REPO_DIR = os.path.dirname(SCRAPERS_DIR)
DISCOVERED_URLS_PATH = os.path.join(DATA_DIR, "discovered_urls.json")
EVENTS_PATH = os.path.join(REPO_DIR, "data", "events.json")


@dataclass(frozen=True)
class FrontierItem:
    url: str
    kind: str
    lane: str = "explore"
    score: float = 0.0
    discovered_at: str = ""
    via: str = ""


# Canonical categories used by every platform adapter.  These are concepts,
# not source URLs; an adapter maps them to the platform's current vocabulary.
CORE_TOPICS = (
    "fitness",
    "music",
    "books",
    "wellness",
    "movies",
    "art",
    "food",
    "comedy",
    "games",
    "outdoors",
    "social",
    "dance",
)

_TOPIC_ALIASES = {
    "run": "fitness",
    "running": "fitness",
    "yoga": "wellness",
    "pilates": "fitness",
    "sport": "fitness",
    "sports": "fitness",
    "health": "wellness",
    "meditation": "wellness",
    "book": "books",
    "read": "books",
    "reading": "books",
    "literary": "books",
    "poetry": "books",
    "film": "movies",
    "cinema": "movies",
    "screening": "movies",
    "jazz": "music",
    "vinyl": "music",
    "pottery": "art",
    "photography": "art",
    "park": "outdoors",
    "outdoor": "outdoors",
    "queer": "social",
    "community": "social",
    "singles": "social",
    "gaming": "games",
    "game": "games",
}


def _load_json(path: str, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def _event_rows() -> list[dict]:
    raw = _load_json(EVENTS_PATH, [])
    if isinstance(raw, dict):
        raw = raw.get("events", [])
    return [row for row in raw if isinstance(row, dict)] if isinstance(raw, list) else []


def _canonical_topic(value: str) -> str | None:
    folded = re.sub(r"[^a-z-]", "", (value or "").lower()).replace("-", "")
    if not folded:
        return None
    aliases = {re.sub(r"[^a-z]", "", key): val for key, val in _TOPIC_ALIASES.items()}
    canonical = aliases.get(folded, folded)
    return canonical if canonical in CORE_TOPICS else None


def topic_scores() -> dict[str, float]:
    """Return canonical topic weights with a small coverage floor.

    A coverage floor is intentional: it prevents a narrow historical profile
    from making whole useful categories (health, books, film, fitness) forever
    undiscoverable. Explicit engagement and followed-account topics rank above
    that exploration floor.
    """
    scores = {topic: 0.25 for topic in CORE_TOPICS}

    profile = _load_json(os.path.join(DATA_DIR, "user_interest_profile.json"), {})
    for raw_topic, raw_weight in (profile.get("topic_counts") or {}).items():
        topic = _canonical_topic(str(raw_topic))
        if topic:
            try:
                scores[topic] += max(0.0, float(raw_weight))
            except (TypeError, ValueError):
                pass

    engagement = _load_json(os.path.join(DATA_DIR, "user_engagement.json"), {})
    negative = engagement.get("negCategories") or {}
    for raw_topic, raw_weight in (engagement.get("categories") or {}).items():
        topic = _canonical_topic(str(raw_topic))
        if not topic:
            continue
        try:
            positive_weight = max(0.0, float(raw_weight))
            negative_weight = max(0.0, float(negative.get(raw_topic, 0) or 0))
        except (TypeError, ValueError):
            continue
        scores[topic] += max(0.0, positive_weight - negative_weight) * 2.0

    # Saved/followed events are a useful fallback when the engagement snapshot
    # has not been synced into the repository yet.
    for event in _event_rows():
        if not any(event.get(flag) for flag in ("userSaved", "userFollowing", "userAffinity")):
            continue
        for raw_topic in event.get("categories") or []:
            topic = _canonical_topic(str(raw_topic))
            if topic:
                scores[topic] += 1.0
    return scores


def ranked_topics() -> list[tuple[str, float, str]]:
    """Topics ordered by preference strength, then stable coverage order."""
    scores = topic_scores()
    order = {topic: index for index, topic in enumerate(CORE_TOPICS)}
    return [
        (topic, score, "personal" if score > 0.25 else "explore")
        for topic, score in sorted(scores.items(), key=lambda row: (-row[1], order[row[0]]))
    ]


def _clean_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
    except Exception:
        return ""
    host = parsed.netloc.lower().removeprefix("www.")
    if not host:
        return ""
    path = re.sub(r"/+", "/", parsed.path).rstrip("/")
    return urlunparse(("https", host, path, "", "", ""))


def _classify(platform: str, url: str, via: str = "") -> tuple[str, str] | None:
    clean = _clean_url(url)
    if not clean:
        return None
    parsed = urlparse(clean)
    host = parsed.netloc
    path = parsed.path

    if platform == "eventbrite" and host.endswith("eventbrite.com"):
        organizer = re.search(r"/o/(?:[^/?#]*-)?(\d+)$", path, re.I)
        if organizer:
            return f"https://eventbrite.com/o/{organizer.group(1)}", "organizer"
        if "/e/" in path:
            return clean, "event"
        if "/cc/" in path:
            return clean, "collection"
        return None

    if platform == "luma" and host in {"lu.ma", "luma.com"}:
        slug = path.strip("/")
        if not slug or slug == "nyc" or slug.startswith("nyc/"):
            return None
        # Organizer provenance is authoritative. Otherwise an 6-10 character
        # alphanumeric slug is normally a Luma event shortcode.
        via_lower = via.lower()
        organizer_hint = any(token in via_lower for token in ("organizer", "calendar", "curator"))
        event_hint = any(token in via_lower for token in (
            "substack", "newsletter", "reddit", "caption", "previous_event"
        ))
        event_shortcode = bool(re.fullmatch(r"[a-z0-9]{6,10}", slug, re.I))
        kind = "calendar" if organizer_hint else "event" if event_hint or event_shortcode else "calendar"
        return f"https://lu.ma/{slug}", kind

    if platform == "partiful" and host.endswith("partiful.com"):
        if "/e/" in path:
            return clean.replace("https://www.partiful.com", "https://partiful.com"), "event"
        if re.search(r"/(?:u|profile)/[^/]+$", path):
            return clean, "organizer"
    return None


def _raw_discovered_items() -> list[dict]:
    raw = _load_json(DISCOVERED_URLS_PATH, [])
    if isinstance(raw, dict):
        raw = raw.get("urls", [])
    out = []
    for item in raw if isinstance(raw, list) else []:
        if isinstance(item, str):
            out.append({"url": item})
        elif isinstance(item, dict) and item.get("url"):
            out.append(item)
    return out


def platform_frontier(
    platform: str,
    *,
    kinds: set[str] | None = None,
    limit: int = 40,
) -> list[FrontierItem]:
    """Rank learned platform URLs from harvested links and prior yield."""
    aggregate: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"score": 0.0, "lane": "explore", "date": "", "via": set()}
    )

    for item in _raw_discovered_items():
        via = str(item.get("discovered_via") or "harvested")
        classified = _classify(platform, str(item.get("url") or ""), via)
        if not classified:
            continue
        url, kind = classified
        rec = aggregate[(url, kind)]
        rec["score"] += 2.0
        if any(token in via.lower() for token in ("user_mentioned", "user_saved", "user_tagged")):
            rec["score"] += 4.0
            rec["lane"] = "personal"
        rec["date"] = max(rec["date"], str(item.get("discovered_at") or ""))
        rec["via"].add(via)

    # Previous event yield promotes organizers/calendars automatically. One
    # recurring organizer is more valuable than a one-off platform event.
    previous_rows = [event for event in _event_rows() if event.get("source") == platform]
    luma_source_counts: dict[str, int] = defaultdict(int)
    if platform == "luma":
        for event in previous_rows:
            if event.get("sourceUrl"):
                luma_source_counts[str(event["sourceUrl"])] += 1
    for event in previous_rows:
        personal = any(event.get(flag) for flag in ("userSaved", "userFollowing", "userAffinity"))
        candidates = [(event.get("organizerUrl") or "", "previous_organizer")]
        # Luma curator pages stamp the calendar URL on every emitted event.
        # A repeated source URL is therefore observed calendar yield; one-off
        # canonical event URLs are already protected by run_all carryover and
        # should not consume the next crawl's direct-event budget.
        source_url = str(event.get("sourceUrl") or "")
        if platform == "luma" and source_url and luma_source_counts[source_url] >= 2:
            candidates.append((source_url, "previous_calendar"))
        for raw_url, via in candidates:
            classified = _classify(platform, raw_url, via)
            if not classified:
                continue
            url, kind = classified
            rec = aggregate[(url, kind)]
            rec["score"] += 1.0 if kind in {"organizer", "calendar"} else 0.15
            if personal:
                rec["score"] += 4.0
                rec["lane"] = "personal"
            rec["via"].add(via)

    # Explicitly curated Eventbrite organizer hosts belong in the same learned
    # frontier; the scraper no longer needs a parallel organizer constant.
    curated = _load_json(os.path.join(DATA_DIR, "user_curated_sources.json"), {})
    for host in (curated.get("hosts") or {}):
        classified = _classify(platform, str(host), "curated")
        if not classified:
            continue
        url, kind = classified
        rec = aggregate[(url, kind)]
        rec["score"] += 8.0
        rec["lane"] = "personal"
        rec["via"].add("curated")

    rows = []
    for (url, kind), rec in aggregate.items():
        if kinds and kind not in kinds:
            continue
        rows.append(FrontierItem(
            url=url,
            kind=kind,
            lane=rec["lane"],
            score=rec["score"],
            discovered_at=rec["date"],
            via=",".join(sorted(rec["via"])),
        ))
    def date_rank(value: str) -> float:
        if not value:
            return 0.0
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError):
            return 0.0

    rows.sort(key=lambda item: (
        item.lane != "personal", -item.score, -date_rank(item.discovered_at), item.url
    ))
    return rows[: max(0, limit)]


def rotating_luma_probes(limit: int = 6, slot: int | None = None) -> list[FrontierItem]:
    """Build a rotating calendar probe set from followed/signal handles.

    Rotation keeps discovery bounded while eventually testing the full follow
    graph. Productive calendars graduate naturally through previous-event
    yield and no longer depend on this exploration lane.
    """
    if limit <= 0:
        return []
    profile = _load_json(os.path.join(DATA_DIR, "user_interest_profile.json"), {})
    handles = sorted({
        str(handle).strip().lower()
        for handle in (profile.get("signal_accounts") or [])
        if re.fullmatch(r"[a-z0-9._-]{2,40}", str(handle).strip(), re.I)
    })
    learned = {
        urlparse(item.url).path.strip("/").lower()
        for item in platform_frontier("luma", kinds={"calendar"}, limit=500)
    }
    handles = [handle for handle in handles if handle not in learned]
    if not handles:
        return []
    # One slot per two-hour platform refresh. Tests can pass an explicit slot.
    slot = int(time.time() // 7200) if slot is None else slot
    start = (slot * limit) % len(handles)
    rotated = handles[start:] + handles[:start]
    return [
        FrontierItem(
            url=f"https://lu.ma/{handle}",
            kind="calendar",
            lane="explore",
            score=0.1,
            via="signal_account_probe",
        )
        for handle in rotated[:limit]
    ]


def extract_tokens(node, keys: set[str], *, max_depth: int = 12) -> set[str]:
    """Recursively collect string values for platform metadata keys."""
    found: set[str] = set()

    def walk(value, depth: int) -> None:
        if depth > max_depth:
            return
        if isinstance(value, list):
            for item in value:
                walk(item, depth + 1)
            return
        if not isinstance(value, dict):
            return
        for key, child in value.items():
            if key in keys and isinstance(child, str) and child.strip():
                found.add(child.strip())
            walk(child, depth + 1)

    walk(node, 0)
    return found


def is_dedicated_platform_url(url: str) -> bool:
    """True when a URL is owned by one of the dedicated platform adapters."""
    clean = _clean_url(url)
    host = urlparse(clean).netloc if clean else ""
    return host.endswith("eventbrite.com") or host in {
        "lu.ma", "luma.com", "partiful.com"
    } or host.endswith(".partiful.com")
