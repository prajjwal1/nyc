import json
from bs4 import BeautifulSoup
from ..utils.http import fetch_text
from ..utils.event_parser import build_event, parse_date, parse_time, infer_categories

DISCOVER_URL = "https://partiful.com/discover"


async def scrape() -> list[dict]:
    events = []
    try:
        html = await fetch_text(DISCOVER_URL, headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
        })
        events.extend(_parse_discover(html))
    except Exception as e:
        print(f"[partiful] Failed to scrape {DISCOVER_URL}: {e}")
    return events


def _parse_discover(html: str) -> list[dict]:
    events = []
    soup = BeautifulSoup(html, "html.parser")

    # Find __NEXT_DATA__ script tag
    script = soup.find("script", id="__NEXT_DATA__")
    if not script or not script.string:
        print("[partiful] No __NEXT_DATA__ found")
        return events

    try:
        data = json.loads(script.string)
    except json.JSONDecodeError as e:
        print(f"[partiful] Failed to parse __NEXT_DATA__: {e}")
        return events

    # Navigate to trendingSections
    trending_sections = (
        data.get("props", {})
        .get("pageProps", {})
        .get("trendingSections", {})
    )

    if not trending_sections:
        print("[partiful] No trendingSections found in page data")
        return events

    # Iterate all region keys, focusing on NYC but collecting all
    for region_key, section in trending_sections.items():
        # Prioritize NYC but also check other sections
        if not isinstance(section, dict):
            continue
        items = section.get("items", [])
        for item in items:
            try:
                ev = _parse_event_item(item, region_key)
                if ev:
                    events.append(ev)
            except Exception as e:
                print(f"[partiful] Error parsing event: {e}")
                continue

    return events


def _parse_event_item(item: dict, region: str) -> dict | None:
    event_data = item.get("event", {})
    if not event_data:
        return None

    event_id = event_data.get("id", "")
    title = event_data.get("title", "")
    description = event_data.get("description", "")
    start_date_str = event_data.get("startDate", "")
    cover_photo = event_data.get("coverPhotoUrl", "")

    if not title or not start_date_str:
        return None

    # Parse date from ISO format
    event_date = parse_date(start_date_str[:10]) if start_date_str else None
    if not event_date:
        return None

    # Extract time from ISO string
    start_time = None
    if len(start_date_str) > 16:
        start_time = start_date_str[11:16]

    # Extract location info
    location_info = event_data.get("locationInfo", {})
    maps_info = location_info.get("mapsInfo", {}) if isinstance(location_info, dict) else {}
    loc_name = maps_info.get("name", "") if isinstance(maps_info, dict) else ""
    address_lines = maps_info.get("addressLines", []) if isinstance(maps_info, dict) else []
    address = ", ".join(address_lines) if address_lines else ""

    # Build source URL
    source_url = f"https://partiful.com/e/{event_id}" if event_id else DISCOVER_URL

    # Guest count info for description enrichment
    interested = event_data.get("interestedGuestCount", 0)
    going = event_data.get("goingGuestCount", 0)
    guest_info = ""
    if going or interested:
        parts = []
        if going:
            parts.append(f"{going} going")
        if interested:
            parts.append(f"{interested} interested")
        guest_info = f" ({', '.join(parts)})"

    full_description = (description[:450] + guest_info) if description else guest_info.strip()

    return build_event(
        title=title,
        description=full_description,
        event_date=event_date,
        start_time=start_time,
        location_name=loc_name,
        address=address,
        source="partiful",
        source_url=source_url,
        image_url=cover_photo if cover_photo else None,
        categories=infer_categories(title, description),
    )
