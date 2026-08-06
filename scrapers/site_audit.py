"""Audit the deployed event/community experience with deterministic metrics.

The scheduled workflow uses this module before asking an independent model for
qualitative product criticism. Keeping the facts deterministic makes trends
comparable and prevents an AI review from declaring a thin or stale feed good.
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


CAPTION_LIKE = re.compile(
    r"^(if you(?:['’]re| are)|when you|the cutest little|pov\b|tag (?:a|your)|send this|"
    r"who else|we(?:'re| are) excited|come with me|things to do\b)", re.I
)
GENERIC_TITLE = re.compile(r"^(event|untitled|tba|coming soon|meetup group\b)", re.I)


def _fetch_json(url: str, timeout: int = 25) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "City-Kin-quality-audit/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def _fetch_status(url: str, timeout: int = 20) -> int:
    req = urllib.request.Request(url, headers={"User-Agent": "City-Kin-quality-audit/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except (urllib.error.URLError, TimeoutError):
        return 0


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _normalized_title(event: dict) -> str:
    return re.sub(r"[^a-z0-9]+", " ", event.get("title", "").lower()).strip()


def _actionable_location(event: dict) -> bool:
    location = event.get("location") or {}
    values = [location.get("address"), location.get("name"), location.get("neighborhood")]
    return any(v and str(v).strip().lower() not in {"nyc", "new york", "tba", "online"} for v in values)


def _feature_ready(event: dict) -> bool:
    return bool(
        event.get("startTime")
        and str(event.get("sourceUrl") or "").startswith("http")
        and event.get("imageUrl")
        and len((event.get("description") or "").strip()) >= 20
        and _actionable_location(event)
        and not CAPTION_LIKE.search((event.get("title") or "").strip())
        and not GENERIC_TITLE.search((event.get("title") or "").strip())
    )


def _showcase(events: list[dict], today: date, now: datetime) -> list[dict]:
    """Approximate the unauthenticated home feed's visible inventory.

    Browser instrumentation records the exact rendered IDs. This deterministic
    projection remains useful when Pages itself is unavailable.
    """
    upcoming = [e for e in events if (e.get("date") or "") >= today.isoformat() and _feature_ready(e)]
    upcoming.sort(key=lambda e: (e.get("date") or "", -(e.get("score") or 0)))
    picked: list[dict] = []
    seen: set[str] = set()

    def take(pool: list[dict], limit: int) -> None:
        added = 0
        for event in sorted(pool, key=lambda e: -(e.get("score") or 0)):
            event_id = str(event.get("id") or "")
            if event_id and event_id not in seen and added < limit:
                picked.append(dict(event))
                seen.add(event_id)
                added += 1

    today_s = today.isoformat()
    take([e for e in upcoming if e.get("date") == today_s], 6)
    recent_cutoff = now - timedelta(hours=72)
    take([e for e in upcoming if (_parse_time(e.get("firstSeenAt")) or datetime.min.replace(tzinfo=timezone.utc)) >= recent_cutoff], 4)
    take([e for e in upcoming if e.get("userFollowing") or e.get("userAffinity")], 6)
    take([e for e in upcoming if e.get("userSaved")], 6)

    by_date: dict[str, list[dict]] = defaultdict(list)
    for event in upcoming:
        if event.get("id") not in seen:
            by_date[event.get("date") or ""].append(event)
    for event_date in sorted(by_date)[:10]:
        take(by_date[event_date], 4)
    return picked


def audit_payloads(events_doc: dict, communities_doc: dict, *, now: datetime | None = None, route_status: dict | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    today = now.date()
    events = events_doc.get("events") or []
    communities = communities_doc.get("communities") or []
    upcoming = [e for e in events if (e.get("date") or "") >= today.isoformat()]
    next_7_end = (today + timedelta(days=7)).isoformat()
    next_7 = [e for e in upcoming if (e.get("date") or "") < next_7_end]
    feature_ready_upcoming = [e for e in upcoming if _feature_ready(e)]
    showcased = _showcase(events, today, now)
    updated = _parse_time(events_doc.get("lastUpdated"))
    age_hours = round((now - updated).total_seconds() / 3600, 2) if updated else None

    sources = Counter(e.get("source") or "unknown" for e in next_7)
    organizers = Counter(
        (e.get("instagramAccount") or e.get("account") or e.get("organizer") or e.get("source") or "unknown").lower()
        for e in next_7
    )
    categories = Counter(c for e in next_7 for c in (e.get("categories") or []) if c not in {"other", "free"})
    neighborhoods = Counter((e.get("location") or {}).get("neighborhood") or "unknown" for e in next_7)
    weekdays = Counter()
    dayparts = Counter()
    for event in next_7:
        try:
            weekdays[date.fromisoformat(event["date"]).strftime("%A")] += 1
        except (KeyError, ValueError):
            pass
        start = event.get("startTime") or ""
        try:
            hour = int(start.split(":", 1)[0])
            dayparts["morning" if hour < 12 else "afternoon" if hour < 17 else "evening"] += 1
        except (ValueError, IndexError):
            dayparts["unknown"] += 1

    duplicate_keys = Counter((_normalized_title(e), e.get("date")) for e in upcoming)
    duplicate_count = sum(count - 1 for (title, _), count in duplicate_keys.items() if title and count > 1)
    caption_like = [e for e in showcased if CAPTION_LIKE.search((e.get("title") or "").strip())]
    raw_caption_like = [e for e in next_7 if CAPTION_LIKE.search((e.get("title") or "").strip())]
    generic = [e for e in showcased if GENERIC_TITLE.search((e.get("title") or "").strip())]

    def ratio(predicate, pool=showcased) -> float:
        return round(sum(1 for item in pool if predicate(item)) / max(1, len(pool)), 3)

    linked = sum(1 for e in upcoming if e.get("primaryCommunityId") or e.get("communityIds"))
    top_source_share = round(max(sources.values(), default=0) / max(1, len(next_7)), 3)
    top_organizer_share = round(max(organizers.values(), default=0) / max(1, len(next_7)), 3)
    detail_quality = {
        "startTime": ratio(lambda e: bool(e.get("startTime"))),
        "location": ratio(_actionable_location),
        "description": ratio(lambda e: len((e.get("description") or "").strip()) >= 40),
        "image": ratio(lambda e: bool(e.get("imageUrl"))),
        "sourceUrl": ratio(lambda e: str(e.get("sourceUrl") or "").startswith("http")),
    }

    failures = []
    warnings = []
    if age_hours is None or age_hours > 2:
        failures.append("live feed is more than two hours old")
    if len(next_7) < 100:
        failures.append("fewer than 100 upcoming events in the next seven days")
    if len(organizers) < 50:
        warnings.append("fewer than 50 distinct organizers in the next seven days")
    if caption_like or generic:
        failures.append("caption-like or generic titles leak into the showcased feed")
    if raw_caption_like:
        warnings.append("caption-like titles remain in the full upcoming dataset but are excluded from the featured feed")
    if detail_quality["startTime"] < .95:
        warnings.append("showcased start-time completeness is below 95%")
    if detail_quality["location"] < .90:
        warnings.append("showcased actionable-location completeness is below 90%")
    if detail_quality["description"] < .85:
        warnings.append("showcased description completeness is below 85%")
    if detail_quality["image"] < .95:
        warnings.append("showcased image completeness is below 95%")
    if top_source_share > .35:
        warnings.append("one source supplies more than 35% of the next-seven-day feed")
    if len(communities) < 150:
        warnings.append("community directory is below the 150-community launch target")
    if upcoming and linked / len(upcoming) < .65:
        warnings.append("fewer than 65% of upcoming events are linked to a community")
    if route_status and any(status != 200 for status in route_status.values()):
        failures.append("one or more deployed product routes are unavailable")

    return {
        "auditedAt": now.isoformat(),
        "feed": {
            "lastUpdated": events_doc.get("lastUpdated"),
            "ageHours": age_hours,
            "total": len(events),
            "upcoming": len(upcoming),
            "next7Days": len(next_7),
            "distinctOrganizersNext7Days": len(organizers),
            "duplicateUpcoming": duplicate_count,
            "featureReadyUpcoming": len(feature_ready_upcoming),
            "topSourceShareNext7Days": top_source_share,
            "topOrganizerShareNext7Days": top_organizer_share,
            "captionLikeNext7Days": len(raw_caption_like),
        },
        "showcase": {
            "count": len(showcased),
            "eventIds": [e.get("id") for e in showcased],
            "events": [{"id": e.get("id"), "title": e.get("title"), "date": e.get("date"), "source": e.get("source"), "score": e.get("score")} for e in showcased[:40]],
            "captionLike": [{"id": e.get("id"), "title": e.get("title")} for e in caption_like],
            "genericTitles": [{"id": e.get("id"), "title": e.get("title")} for e in generic],
            "detailQuality": detail_quality,
        },
        "communities": {
            "count": len(communities),
            "linkedUpcomingEvents": linked,
            "linkedUpcomingRatio": round(linked / max(1, len(upcoming)), 3),
        },
        "gaps": {
            "sources": dict(sources.most_common()),
            "weekdays": dict(weekdays),
            "dayparts": dict(dayparts),
            "categories": dict(categories.most_common(20)),
            "neighborhoods": dict(neighborhoods.most_common(20)),
        },
        "routeStatus": route_status or {},
        "status": "fail" if failures else "attention" if warnings else "pass",
        "failures": failures,
        "warnings": warnings,
    }


def markdown_report(audit: dict) -> str:
    feed = audit["feed"]
    showcase = audit["showcase"]
    communities = audit["communities"]
    lines = [
        "# City Kin deployed-site quality review",
        "",
        f"**Status:** {audit['status'].upper()} · audited {audit['auditedAt']}",
        "",
        "## User-value scorecard",
        "",
        "| Signal | Result | Target |",
        "|---|---:|---:|",
        f"| Live feed age | {feed['ageHours']}h | ≤2h |",
        f"| Events in next 7 days | {feed['next7Days']} | ≥100 |",
        f"| Distinct organizers in next 7 days | {feed['distinctOrganizersNext7Days']} | ≥50 |",
        f"| Community directory | {communities['count']} | ≥150 |",
        f"| Upcoming events linked to communities | {communities['linkedUpcomingRatio']:.0%} | ≥65% (then 80%) |",
        f"| Showcased events with time | {showcase['detailQuality']['startTime']:.0%} | ≥95% |",
        f"| Showcased events with actionable location | {showcase['detailQuality']['location']:.0%} | ≥90% |",
        f"| Showcased events with useful description | {showcase['detailQuality']['description']:.0%} | ≥85% |",
        f"| Showcased events with image | {showcase['detailQuality']['image']:.0%} | ≥95% |",
        "",
    ]
    rendered = showcase.get("rendered") or {}
    if rendered:
        lines.extend([
            "## Exact rendered feed evidence",
            "",
            f"- Unique rendered event IDs: {rendered.get('uniqueEventCount', 0)}",
            f"- Mobile rendered cards: {rendered.get('mobileCount', 0)}",
            f"- Desktop rendered cards: {rendered.get('desktopCount', 0)}",
            "",
        ])
    lines.extend(["## Findings", ""])
    findings = [("Failure", item) for item in audit["failures"]] + [("Watch", item) for item in audit["warnings"]]
    lines.extend([f"- **{level}:** {item}" for level, item in findings] or ["- No threshold violations."])
    lines.extend(["", "## Events currently projected for the feed", ""])
    lines.extend([f"- `{e['id']}` — **{e['title']}** · {e['date']} · {e['source']} · score {e['score']}" for e in showcase["events"][:20]])
    lines.extend(["", "## Seven-day coverage gaps", "", f"- Weekdays: {audit['gaps']['weekdays']}", f"- Dayparts: {audit['gaps']['dayparts']}", f"- Sources: {audit['gaps']['sources']}", f"- Neighborhoods: {audit['gaps']['neighborhoods']}"])
    return "\n".join(lines) + "\n"


def merge_browser_evidence(output_dir: Path) -> dict:
    audit_path = output_dir / "audit.json"
    browser_path = output_dir / "browser-audit.json"
    audit = json.loads(audit_path.read_text())
    browser = json.loads(browser_path.read_text())
    home_results = [result for result in browser.get("results", []) if result.get("route") == "home" and result.get("status") == 200]
    rendered_events = []
    for result in home_results:
        for event in result.get("showcased") or []:
            rendered_events.append({**event, "viewport": result.get("viewport")})
    unique_ids = list(dict.fromkeys(event.get("id") for event in rendered_events if event.get("id")))
    audit["showcase"]["rendered"] = {
        "uniqueEventCount": len(unique_ids),
        "eventIds": unique_ids,
        "mobileCount": sum(1 for event in rendered_events if event.get("viewport") == "mobile"),
        "desktopCount": sum(1 for event in rendered_events if event.get("viewport") == "desktop"),
        "events": rendered_events,
    }
    if home_results and not unique_ids:
        audit["failures"].append("deployed home page exposed no instrumented showcased events")
        audit["failures"] = list(dict.fromkeys(audit["failures"]))
        audit["status"] = "fail"
    audit_path.write_text(json.dumps(audit, indent=2) + "\n")
    (output_dir / "report.md").write_text(markdown_report(audit))
    return audit


def run(base_url: str, output_dir: Path) -> dict:
    base = base_url.rstrip("/") + "/"
    routes = {name: _fetch_status(base + suffix) for name, suffix in {
        "home": "", "events": "events/", "communities": "communities/", "map": "map/", "saved": "saved/"
    }.items()}
    try:
        events_doc = _fetch_json(base + "events.json")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
        events_doc = {"events": []}
    try:
        communities_doc = _fetch_json(base + "communities.json")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
        communities_doc = {"communities": []}
    audit = audit_payloads(events_doc, communities_doc, route_status=routes)
    if not events_doc.get("events"):
        audit["failures"].append("deployed events.json is unavailable or empty")
        audit["failures"] = list(dict.fromkeys(audit["failures"]))
        audit["status"] = "fail"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    (output_dir / "report.md").write_text(markdown_report(audit))
    return audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://prajjwal1.github.io/nyc/")
    parser.add_argument("--output-dir", type=Path, default=Path("audit-output"))
    parser.add_argument("--merge-browser", action="store_true")
    args = parser.parse_args()
    result = merge_browser_evidence(args.output_dir) if args.merge_browser else run(args.base_url, args.output_dir)
    print(json.dumps({"status": result["status"], "failures": result["failures"], "warnings": result["warnings"]}, indent=2))


if __name__ == "__main__":
    main()
