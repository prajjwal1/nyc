"""Deterministic evaluation for the recommendation surface."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path


def _organizer(event: dict) -> str:
    return (
        event.get("instagramAccount")
        or event.get("account")
        or event.get("organizer")
        or (event.get("location") or {}).get("name")
        or event.get("source")
        or "unknown"
    ).lower()


def _series(event: dict) -> str:
    title = re.sub(r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b", "", (event.get("title") or "").lower())
    title = re.sub(r"\b\d{1,4}(?:st|nd|rd|th)?\b|[^a-z]+", " ", title)
    return f"{_organizer(event)}::{re.sub(r'\s+', ' ', title).strip()}"


def evaluate_ranked_feed(events: list[dict], *, top_n: int = 30, today: str | None = None) -> dict:
    today = today or date.today().isoformat()
    upcoming = [event for event in events if (event.get("date") or "") >= today]
    ranked = sorted(upcoming, key=lambda event: event.get("score") or 0, reverse=True)[:top_n]
    sources = Counter(event.get("source") or "unknown" for event in ranked)
    organizers = Counter(_organizer(event) for event in ranked)
    categories = Counter(
        category
        for event in ranked
        for category in (event.get("categories") or [])
        if category not in {"other", "free"}
    )
    series = Counter(_series(event) for event in ranked)
    personal = sum(
        event.get("discoveryLane") == "personal"
        or any(event.get(flag) for flag in ("userSaved", "userFollowing", "userAffinity", "userTagged"))
        for event in ranked
    )
    total = max(1, len(ranked))
    return {
        "evaluated": len(ranked),
        "personalRatio": round(personal / total, 3),
        "distinctOrganizers": len(organizers),
        "distinctCategories": len(categories),
        "topSourceShare": round(max(sources.values(), default=0) / total, 3),
        "topOrganizerShare": round(max(organizers.values(), default=0) / total, 3),
        "maxRepeatedSeries": max(series.values(), default=0),
        "sources": dict(sources.most_common()),
        "categories": dict(categories.most_common()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, nargs="?", default=Path("data/events.json"))
    parser.add_argument("--top", type=int, default=30)
    args = parser.parse_args()
    payload = json.loads(args.path.read_text())
    events = payload.get("events", payload) if isinstance(payload, dict) else payload
    print(json.dumps(evaluate_ranked_feed(events, top_n=args.top), indent=2))


if __name__ == "__main__":
    main()
