import re
from ..utils.http import fetch_json
from ..utils.event_parser import build_event, parse_date

API_URL = "https://refinery.nypl.org/api/nypl/ndo/v0.1/site-data/events?limit=50"


async def scrape() -> list[dict]:
    events = []
    try:
        data = await fetch_json(API_URL)
        for item in data.get("data", []):
            ev = _parse_event(item)
            if ev:
                events.append(ev)
    except Exception as e:
        print(f"[nypl] Failed: {e}")
    return events


def _parse_event(item: dict) -> dict | None:
    attrs = item.get("attributes", {})
    title = attrs.get("name", "")
    if not title:
        return None

    start = attrs.get("start-date", "")
    event_date = parse_date(start[:10]) if start else None
    if not event_date:
        return None

    start_time = start[11:16] if len(start) > 16 else None
    end = attrs.get("end-date", "")
    end_time = end[11:16] if len(end) > 16 else None

    desc_short = attrs.get("description-short", "")
    desc = re.sub(r"\s+", " ", desc_short).strip()[:400]

    uri = attrs.get("uri", {})
    url = uri.get("full-uri", "") if isinstance(uri, dict) else ""

    location_name = "NYPL"

    return build_event(
        title=title,
        description=desc,
        event_date=event_date,
        start_time=start_time,
        end_time=end_time,
        location_name=location_name,
        source="nypl",
        source_url=url or "https://www.nypl.org/events",
        price="free",
        categories=["books", "free"],
    )
