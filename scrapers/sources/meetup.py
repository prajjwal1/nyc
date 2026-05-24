import json
from datetime import datetime
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from ..utils.http import fetch_text
from ..utils.event_parser import build_event, parse_date, parse_time

_NYC_TZ = ZoneInfo("America/New_York")


def _ld_start_to_local(start: str) -> tuple[str | None, str | None]:
    """Parse Meetup's JSON-LD startDate (typically UTC, e.g.
    "2026-05-26T22:00:00Z") into America/New_York date + HH:MM. Falls
    back to the previous naive substring approach if parsing fails.
    """
    if not start:
        return None, None
    # Handle "Z" suffix that fromisoformat() didn't accept pre-3.11.
    s = start.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            # No timezone info — assume already local NYC.
            local = dt
        else:
            local = dt.astimezone(_NYC_TZ)
        return local.date().isoformat(), local.strftime("%H:%M")
    except Exception:
        date_str = parse_date(start[:10])
        time_str = start[11:16] if len(start) > 16 else None
        return (date_str.isoformat() if date_str else None), time_str

SEARCH_URLS = [
    "https://www.meetup.com/find/?location=us--ny--New%20York&source=EVENTS&categoryId=546",  # Arts
    "https://www.meetup.com/find/?location=us--ny--New%20York&source=EVENTS&categoryId=622",  # Book Clubs
    "https://www.meetup.com/find/?location=us--ny--New%20York&source=EVENTS&categoryId=436",  # Games
    "https://www.meetup.com/find/?location=us--ny--Brooklyn&source=EVENTS",
]


async def scrape() -> list[dict]:
    events = []
    for url in SEARCH_URLS:
        try:
            html = await fetch_text(url)
            events.extend(_parse_meetup(html, url))
        except Exception as e:
            print(f"[meetup] Failed {url}: {e}")
    return events


def _parse_meetup(html: str, source_url: str) -> list[dict]:
    events = []
    soup = BeautifulSoup(html, "lxml")

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get("@type") == "Event":
                    ev = _from_ld(item)
                    if ev:
                        events.append(ev)
        except (json.JSONDecodeError, Exception):
            continue

    if not events:
        for card in soup.select("[id*='event-card'], [class*='eventCard'], [data-testid*='event']"):
            title_el = card.select_one("h2, h3, [class*='title']")
            date_el = card.select_one("time, [class*='date']")
            link_el = card.select_one("a[href*='/events/']")

            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            date_text = date_el.get("datetime", date_el.get_text(strip=True)) if date_el else ""
            event_date = parse_date(date_text) if date_text else None
            if not event_date:
                continue

            link = link_el.get("href", "") if link_el else source_url
            if link and not link.startswith("http"):
                link = f"https://www.meetup.com{link}"

            loc_el = card.select_one("[class*='venue'], [class*='location']")
            loc_name = loc_el.get_text(strip=True) if loc_el else ""

            events.append(build_event(
                title=title,
                description="",
                event_date=event_date,
                start_time=parse_time(date_text),
                location_name=loc_name,
                source="meetup",
                source_url=link,
            ))

    return events


def _from_ld(data: dict) -> dict | None:
    title = data.get("name", "")
    desc = data.get("description", "")
    start = data.get("startDate", "")
    location = data.get("location", {})

    loc_name = ""
    loc_addr = ""
    if isinstance(location, dict):
        loc_name = location.get("name", "")
        addr = location.get("address", {})
        if isinstance(addr, dict):
            loc_addr = addr.get("streetAddress", "")

    date_str, start_time = _ld_start_to_local(start)
    if not date_str:
        return None
    event_date = parse_date(date_str)
    if not event_date:
        return None
    url = data.get("url", "")
    image = data.get("image", "")
    if isinstance(image, list) and image:
        image = image[0]
    if image and not image.startswith("http"):
        image = f"https://www.meetup.com{image}"

    return build_event(
        title=title,
        description=desc[:500],
        event_date=event_date,
        start_time=start_time,
        location_name=loc_name,
        address=loc_addr,
        source="meetup",
        source_url=url,
        image_url=image if image else None,
    )
