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
from datetime import datetime, timedelta, timezone
import asyncio
import html
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

LINK_AGGREGATOR_HOSTS = {
    "linktr.ee", "linktree.com", "beacons.ai", "linkin.bio", "sprout.link",
    "stan.store", "withkoji.com", "koji.to", "allmylinks.com", "lnk.bio",
    "snipfeed.co", "tap.bio", "msha.ke", "campsite.bio", "bio.site",
    "hoo.be", "solo.to", "milkshake.app",
}


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


def _canonical_discovery_url(url: str, discovered_via: str = "") -> tuple[str, str, str]:
    """Return a stable URL plus its dedicated platform/kind when known.

    Platform URLs are aggressively canonicalized because tracking parameters
    otherwise turn one Instagram bio link into many frontier entries.  Other
    public URLs retain their query string because it can be functional.
    """
    raw = (url or "").strip()
    if not raw:
        return "", "", ""
    for platform in ("luma", "partiful", "eventbrite"):
        classified = _classify(platform, raw, discovered_via)
        if classified:
            clean, kind = classified
            return clean, platform, kind
    try:
        parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    except Exception:
        return "", "", ""
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "", "", ""
    host = parsed.netloc.lower().removeprefix("www.")
    path = re.sub(r"/+", "/", parsed.path).rstrip("/")
    return urlunparse(("https", host, path, "", parsed.query, "")), "", ""


def persist_discovered_urls(
    urls: list[str] | set[str] | tuple[str, ...],
    *,
    discovered_via: str,
    source_account: str = "",
    lane: str = "explore",
) -> int:
    """Persist public source links with enough provenance to rank them.

    This is intentionally shared by Instagram and the platform adapters.  A
    discovered organizer/calendar therefore survives after its first event
    ages out of ``events.json``. Existing legacy rows remain compatible.
    """
    raw = _load_json(DISCOVERED_URLS_PATH, [])
    wrapper = isinstance(raw, dict)
    items = raw.get("urls", []) if wrapper else raw
    items = list(items) if isinstance(items, list) else []
    now = datetime.now(timezone.utc).isoformat()

    by_url: dict[str, dict] = {}
    passthrough: list[dict] = []
    for item in items:
        row = {"url": item} if isinstance(item, str) else dict(item) if isinstance(item, dict) else {}
        existing_url = str(row.get("url") or "")
        clean, platform, kind = _canonical_discovery_url(
            existing_url, str(row.get("discovered_via") or "")
        )
        if not clean:
            if row:
                passthrough.append(row)
            continue
        row["url"] = clean
        if platform:
            row.setdefault("platform", platform)
            row.setdefault("kind", kind)
        by_url.setdefault(clean, row)

    added = 0
    changed = False
    for url in urls:
        clean, platform, kind = _canonical_discovery_url(str(url), discovered_via)
        if not clean:
            continue
        row = by_url.get(clean)
        if row is None:
            row = {
                "url": clean,
                "discovered_at": now,
                "first_seen_at": now,
                "discovered_via": discovered_via,
            }
            by_url[clean] = row
            added += 1
            changed = True
        previous = dict(row)
        row.setdefault("first_seen_at", row.get("discovered_at") or now)
        row["last_seen_at"] = now
        if platform:
            row["platform"] = platform
            row["kind"] = kind
        if source_account:
            accounts = row.get("source_accounts") or []
            if isinstance(accounts, str):
                accounts = [accounts]
            row["source_accounts"] = list(dict.fromkeys([
                *[str(account).lower() for account in accounts if account],
                source_account.lower(),
            ]))[-12:]
        if lane == "personal" or row.get("lane") != "personal":
            row["lane"] = lane
        vias = row.get("discovery_vias") or []
        if isinstance(vias, str):
            vias = [vias]
        row["discovery_vias"] = list(dict.fromkeys([
            *[str(via) for via in vias if via], discovered_via,
        ]))[-12:]
        changed = changed or row != previous

    if not changed:
        return 0
    payload_items = [*passthrough, *by_url.values()]
    payload = dict(raw) if wrapper else payload_items
    if wrapper:
        payload["urls"] = payload_items
        payload["lastDiscovery"] = now
    os.makedirs(os.path.dirname(DISCOVERED_URLS_PATH), exist_ok=True)
    tmp = DISCOVERED_URLS_PATH + ".tmp"
    with open(tmp, "w") as file:
        json.dump(payload, file, indent=2)
    os.replace(tmp, DISCOVERED_URLS_PATH)
    return added


def record_platform_results(results: list[dict]) -> None:
    """Batch per-target attempt/yield lifecycle data into the frontier."""
    if not results:
        return
    for kind in {str(result.get("kind") or "") for result in results}:
        persist_discovered_urls(
            {
                str(result.get("url") or "") for result in results
                if str(result.get("kind") or "") == kind
            },
            discovered_via=f"platform_{kind}_fetch" if kind else "platform_fetch",
        )
    raw = _load_json(DISCOVERED_URLS_PATH, [])
    wrapper = isinstance(raw, dict)
    items = raw.get("urls", []) if wrapper else raw
    if not isinstance(items, list):
        return
    now = datetime.now(timezone.utc)
    by_url = {
        str(item.get("url") or ""): item
        for item in items if isinstance(item, dict) and item.get("url")
    }
    for result in results:
        clean, _platform, kind = _canonical_discovery_url(
            str(result.get("url") or ""),
            str(result.get("kind") or result.get("via") or "platform_fetch"),
        )
        row = by_url.get(clean)
        if row is None:
            continue
        error = str(result.get("error") or "")
        try:
            parsed_yield = max(0, int(result.get("yield") or 0))
        except (TypeError, ValueError):
            parsed_yield = 0
        row["last_attempt_at"] = now.isoformat()
        row["last_parsed_yield"] = parsed_yield
        if error:
            failures = int(row.get("consecutive_failures") or 0) + 1
            row["consecutive_failures"] = failures
            row["last_error"] = error[:180]
            row["status"] = "error"
            row["next_retry_at"] = (
                now + timedelta(hours=min(24 * 7, 2 ** min(failures, 7)))
            ).isoformat()
            continue
        row["last_success_at"] = now.isoformat()
        row["consecutive_failures"] = 0
        row.pop("last_error", None)
        empty_runs = int(row.get("consecutive_empty_runs") or 0) + 1 if parsed_yield == 0 else 0
        row["consecutive_empty_runs"] = empty_runs
        stale_event = (row.get("kind") or kind) == "event" and empty_runs >= 3
        row["status"] = "stale" if stale_event else "active" if parsed_yield else "empty"
        row["next_retry_at"] = (
            now + timedelta(days=30) if stale_event
            else now + timedelta(hours=6 if parsed_yield else 24)
        ).isoformat()
    tmp = DISCOVERED_URLS_PATH + ".tmp"
    payload = dict(raw) if wrapper else items
    if wrapper:
        payload["urls"] = items
    with open(tmp, "w") as file:
        json.dump(payload, file, indent=2)
    os.replace(tmp, DISCOVERED_URLS_PATH)


def record_platform_survival(events: list[dict]) -> None:
    """Record how many normalized feed events each durable source retained."""
    raw = _load_json(DISCOVERED_URLS_PATH, [])
    wrapper = isinstance(raw, dict)
    items = raw.get("urls", []) if wrapper else raw
    if not isinstance(items, list):
        return
    counts: dict[str, int] = defaultdict(int)
    for event in events:
        source = str(event.get("source") or "")
        if source not in {"luma", "partiful", "eventbrite"}:
            continue
        event_urls: set[str] = set()
        for url, via in (
            (str(event.get("sourceUrl") or ""), "previous_event"),
            (str(event.get("organizerUrl") or ""), "previous_organizer"),
        ):
            clean, platform, _kind = _canonical_discovery_url(url, via)
            if clean and platform == source:
                event_urls.add(clean)
        for clean in event_urls:
            counts[clean] += 1
    changed = False
    for item in items:
        if not isinstance(item, dict) or not item.get("platform"):
            continue
        item["last_surviving_yield"] = counts.get(str(item.get("url") or ""), 0)
        changed = True
    if not changed:
        return
    tmp = DISCOVERED_URLS_PATH + ".tmp"
    payload = dict(raw) if wrapper else items
    if wrapper:
        payload["urls"] = items
    with open(tmp, "w") as file:
        json.dump(payload, file, indent=2)
    os.replace(tmp, DISCOVERED_URLS_PATH)


def _is_link_aggregator_url(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    except Exception:
        return False
    return host in LINK_AGGREGATOR_HOSTS or any(
        host.endswith(f".{candidate}") for candidate in LINK_AGGREGATOR_HOSTS
    )


def extract_platform_links(document: str) -> set[str]:
    """Extract canonical dedicated-platform URLs from an aggregator page."""
    normalized = html.unescape(document or "").replace(r"\/", "/").replace(r"\u002F", "/")
    candidates = re.findall(r"https?://[^\s\"'<>]+", normalized, re.I)
    found: set[str] = set()
    for raw in candidates:
        clean, platform, _kind = _canonical_discovery_url(raw.rstrip(".,;:!?)\\"))
        if clean and platform:
            found.add(clean)
    return found


async def expand_link_aggregator_frontier(limit: int = 30) -> dict[str, int]:
    """Resolve queued public bio hubs before platform adapters choose work."""
    from .http import fetch_text

    rows = [
        row for row in _raw_discovered_items()
        if _is_link_aggregator_url(str(row.get("url") or ""))
    ]

    def freshness(row: dict) -> float:
        value = str(row.get("last_seen_at") or row.get("discovered_at") or "")
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError):
            return 0.0

    rows.sort(key=lambda row: (
        str(row.get("lane") or "") != "personal",
        -freshness(row),
        str(row.get("url") or ""),
    ))
    rows = rows[:max(0, limit)]
    sem = asyncio.Semaphore(5)

    async def one(row: dict) -> tuple[dict, set[str]]:
        async with sem:
            try:
                document = await fetch_text(str(row.get("url") or ""))
            except Exception:
                return row, set()
        return row, extract_platform_links(document)

    results = await asyncio.gather(*(one(row) for row in rows))
    found_total = 0
    added_total = 0
    for row, links in results:
        if not links:
            continue
        found_total += len(links)
        accounts = row.get("source_accounts") or []
        source_account = str(accounts[0]) if isinstance(accounts, list) and accounts else ""
        added_total += persist_discovered_urls(
            links,
            discovered_via="link_aggregator:instagram_bio",
            source_account=source_account,
            lane=str(row.get("lane") or "explore"),
        )
    return {"pages": len(rows), "links": found_total, "added": added_total}


def platform_frontier(
    platform: str,
    *,
    kinds: set[str] | None = None,
    limit: int = 40,
) -> list[FrontierItem]:
    """Rank learned platform URLs from harvested links and prior yield."""
    aggregate: dict[tuple[str, str], dict] = defaultdict(
        lambda: {
            "score": 0.0,
            "preference_tier": 0,
            "lane": "explore",
            "date": "",
            "via": set(),
        }
    )

    for item in _raw_discovered_items():
        retry_at = str(item.get("next_retry_at") or "")
        if item.get("status") in {"error", "stale"} and retry_at:
            try:
                retry_time = datetime.fromisoformat(retry_at.replace("Z", "+00:00"))
                if retry_time.tzinfo is None:
                    retry_time = retry_time.replace(tzinfo=timezone.utc)
                if retry_time > datetime.now(timezone.utc):
                    continue
            except ValueError:
                pass
        via = str(item.get("discovered_via") or "harvested")
        classified = _classify(platform, str(item.get("url") or ""), via)
        if not classified:
            continue
        url, kind = classified
        rec = aggregate[(url, kind)]
        rec["score"] += 2.0
        explicit_lane = str(item.get("lane") or "") == "personal"
        all_vias = " ".join(str(value) for value in (item.get("discovery_vias") or []))
        if explicit_lane or any(token in f"{via} {all_vias}".lower() for token in (
            "user_mentioned", "user_saved", "user_tagged", "instagram_browser_saved",
            "instagram_browser_tagged",
        )):
            rec["score"] += 4.0
            rec["preference_tier"] = max(rec["preference_tier"], 3)
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
                rec["preference_tier"] = max(rec["preference_tier"], 2)
                rec["lane"] = "personal"
            rec["via"].add(via)

    # Explicitly curated Eventbrite organizer hosts belong in the same learned
    # frontier; the scraper no longer needs a parallel organizer constant.
    curated = _load_json(os.path.join(DATA_DIR, "user_curated_sources.json"), {})
    for host, metadata in (curated.get("hosts") or {}).items():
        source = str(metadata.get("source") or "curated") if isinstance(metadata, dict) else "curated"
        via = f"curated:{source}"
        classified = _classify(platform, str(host), via)
        if not classified:
            continue
        url, kind = classified
        rec = aggregate[(url, kind)]
        if source == "user_mentioned":
            rec["score"] += 12.0
            rec["preference_tier"] = max(rec["preference_tier"], 3)
        elif source.startswith("engagement_"):
            rec["score"] += 11.0
            rec["preference_tier"] = max(rec["preference_tier"], 2)
        else:
            rec["score"] += 8.0
            rec["preference_tier"] = max(rec["preference_tier"], 1)
        rec["lane"] = "personal"
        rec["via"].add(via)

    rows: list[tuple[FrontierItem, int]] = []
    for (url, kind), rec in aggregate.items():
        if kinds and kind not in kinds:
            continue
        rows.append((
            FrontierItem(
                url=url,
                kind=kind,
                lane=rec["lane"],
                score=rec["score"],
                discovered_at=rec["date"],
                via=",".join(sorted(rec["via"])),
            ),
            rec["preference_tier"],
        ))
    def date_rank(value: str) -> float:
        if not value:
            return 0.0
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError):
            return 0.0

    rows.sort(key=lambda row: (
        -row[1],
        row[0].lane != "personal",
        -row[0].score,
        -date_rank(row[0].discovered_at),
        row[0].url,
    ))
    return [item for item, _tier in rows[: max(0, limit)]]


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
