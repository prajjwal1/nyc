"""Fill missing recommendation descriptions with bounded, source-native requests.

The previous events feed is the cache: canonical event identity plus date keeps
tracking links, Luma's host alias, and recurring occurrences from mixing prose.
Only the description is copied. The caller must normalize again before publishing
so newly discovered text still goes through the usual exclusion rules.
"""

from __future__ import annotations

import asyncio
import re
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import httpx

from .http import fetch_text

SUPPORTED_SOURCES = frozenset({"luma", "eventbrite"})
MIN_DESCRIPTION_LENGTH = 40


def _event_key(event: dict) -> tuple[str, str, str] | None:
    source = event.get("source")
    if source not in SUPPORTED_SOURCES:
        return None
    try:
        day = date.fromisoformat(event.get("date") or "").isoformat()
        url = urlsplit(event.get("sourceUrl") or "")
        if url.scheme not in {"http", "https"} or url.username or url.password:
            return None
        if url.port not in {None, 80, 443}:
            return None
        path = url.path.rstrip("/")
        if source == "luma" and url.hostname in {"lu.ma", "luma.com", "www.luma.com"}:
            match = re.fullmatch(r"/([A-Za-z0-9_.-]+)", path)
        elif source == "eventbrite" and url.hostname in {"eventbrite.com", "www.eventbrite.com"}:
            match = re.fullmatch(r"/e/(?:[^/]+-)?(\d+)", path)
        else:
            return None
        return (source, match.group(1), day) if match else None
    except (TypeError, ValueError):
        return None


def _description(event: dict) -> str:
    value = event.get("description")
    return value.strip() if isinstance(value, str) else ""


def restore_cached_descriptions(events: list[dict], previous_events) -> int:
    """Restore missing prose without requests, overwrites, or metadata changes."""
    cache = {}
    for previous in previous_events:
        key = _event_key(previous)
        text = _description(previous)
        if key and len(text) >= MIN_DESCRIPTION_LENGTH:
            cache[key] = text
    restored = set()
    for event in events:
        key = _event_key(event)
        if key in cache and not _description(event):
            event["description"] = cache[key]
            restored.add(key)
    return len(restored)


def _shortlist(candidates: list[dict], today: date) -> list[dict]:
    """Top 40 normalized recommendations per day in the next seven days."""
    end = (today + timedelta(days=7)).isoformat()
    days = defaultdict(list)
    for event in candidates:
        if today.isoformat() <= (event.get("date") or "") < end:
            days[event["date"]].append(event)
    return [
        event
        for day in sorted(days)
        for event in sorted(days[day], key=lambda e: -(e.get("score") or 0))[:40]
    ]


def _matching_description(html: str, candidate: dict, url: str) -> str:
    # Reuse the platforms' structured parsers, never unrelated page/OG copy.
    from ..sources import eventbrite, luma

    parsed = (
        luma._parse_luma_page(html, url)
        if candidate["source"] == "luma"
        else eventbrite._parse_search_page(html, url)
    )
    key = _event_key(candidate)
    for detail in parsed:
        text = _description(detail)
        if _event_key(detail) == key and len(text) >= MIN_DESCRIPTION_LENGTH:
            return text
    return ""


async def enrich_descriptions(
    events: list[dict],
    *,
    candidates: list[dict],
    sources=SUPPORTED_SOURCES,
    limit: int = 24,
    max_seconds: float = 45,
    request_timeout: float = 8,
    today: date | None = None,
) -> dict:
    """Fill raw and preview rows for a bounded shortlist of normalized survivors.

Each platform has one worker and stops on its first 429. A failure leaves the
original listing intact. Successfully filled rows survive the pass deadline.
"""
    started = time.monotonic()
    today = today or datetime.now(ZoneInfo("America/New_York")).date()
    window = _shortlist(candidates, today)
    targets = {}
    allowed = set(sources) & SUPPORTED_SOURCES
    for event in window:
        key = _event_key(event)
        if key and event["source"] in allowed and not _description(event):
            targets.setdefault(key, event)
    selected = list(targets.items())[: max(0, limit)]
    stats = {
        "windowEvents": len(window),
        "eligibleMissing": len(targets),
        "requestLimit": max(0, limit),
        "attempted": 0,
        "enriched": 0,
        "failed": 0,
        "timedOut": 0,
        "cancelled": 0,
        "rateLimitedSources": [],
        "deadlineHit": False,
        "sources": {},
    }
    rows = defaultdict(list)
    for event in events:
        key = _event_key(event)
        if key:
            rows[key].append(event)
    groups = defaultdict(list)
    for key, candidate in selected:
        groups[key[0]].append((key, candidate))

    async def worker(source: str, items: list) -> None:
        counts = {"attempted": 0, "enriched": 0, "failed": 0}
        stats["sources"][source] = counts
        for key, candidate in items:
            url = (
                f"https://luma.com/{key[1]}"
                if source == "luma"
                else f"https://www.eventbrite.com{urlsplit(candidate['sourceUrl']).path.rstrip('/')}"
            )
            stats["attempted"] += 1
            counts["attempted"] += 1
            try:
                html = await asyncio.wait_for(
                    fetch_text(url, timeout=request_timeout), timeout=request_timeout
                )
                text = _matching_description(html, candidate, url)
                if text:
                    for row in [candidate, *rows[key]]:
                        if not _description(row):
                            row["description"] = text
                    stats["enriched"] += 1
                    counts["enriched"] += 1
                    continue
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    stats["rateLimitedSources"].append(source)
                    stats["failed"] += 1
                    counts["failed"] += 1
                    break
            except (asyncio.TimeoutError, httpx.TimeoutException):
                stats["timedOut"] += 1
            except asyncio.CancelledError:
                stats["cancelled"] += 1
                raise
            except Exception as exc:
                print(f"[descriptions] {source} detail skipped: {exc}")
            stats["failed"] += 1
            counts["failed"] += 1

    try:
        async with asyncio.timeout(max_seconds):
            await asyncio.gather(*(worker(source, items) for source, items in groups.items()))
    except asyncio.TimeoutError:
        stats["deadlineHit"] = True
    stats["rateLimitedSources"].sort()
    stats["elapsedSeconds"] = round(time.monotonic() - started, 2)
    print(
        f"[descriptions] filled {stats['enriched']}/{stats['attempted']} pages "
        f"in {stats['elapsedSeconds']}s; rate-limited={stats['rateLimitedSources']}, "
        f"deadline={stats['deadlineHit']}"
    )
    return stats
