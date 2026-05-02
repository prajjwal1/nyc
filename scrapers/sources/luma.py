import json
import re
from bs4 import BeautifulSoup
from ..utils.http import fetch_text
from ..utils.event_parser import build_event, parse_date, parse_time

LUMA_PAGES = [
    "https://lu.ma/nycbackgammonclub",
    "https://lu.ma/readingrhythms-manhattan",
]


async def scrape() -> list[dict]:
    events = []
    for url in LUMA_PAGES:
        try:
            html = await fetch_text(url)
            events.extend(_parse_luma_page(html, url))
        except Exception as e:
            print(f"[luma] Failed to scrape {url}: {e}")
    return events


def _parse_luma_page(html: str, source_url: str) -> list[dict]:
    events = []
    soup = BeautifulSoup(html, "lxml")

    script_tags = soup.find_all("script", type="application/ld+json")
    for script in script_tags:
        try:
            data = json.loads(script.string)
            if isinstance(data, list):
                for item in data:
                    ev = _parse_ld_json(item, source_url)
                    if ev:
                        events.append(ev)
            elif isinstance(data, dict):
                ev = _parse_ld_json(data, source_url)
                if ev:
                    events.append(ev)
        except (json.JSONDecodeError, Exception):
            continue

    if not events:
        events.extend(_parse_luma_html(soup, source_url))

    return events


def _parse_ld_json(data: dict, source_url: str) -> dict | None:
    if data.get("@type") != "Event":
        return None
    title = data.get("name", "")
    desc = data.get("description", "")
    start = data.get("startDate", "")
    end = data.get("endDate", "")
    location = data.get("location", {})
    loc_name = ""
    loc_addr = ""
    if isinstance(location, dict):
        loc_name = location.get("name", "")
        addr = location.get("address", {})
        if isinstance(addr, dict):
            loc_addr = addr.get("streetAddress", "")
        elif isinstance(addr, str):
            loc_addr = addr

    image = data.get("image", "")
    if isinstance(image, list) and image:
        image = image[0]

    event_date = parse_date(start[:10]) if start else None
    if not event_date:
        return None

    start_time = start[11:16] if len(start) > 16 else None
    end_time = end[11:16] if len(end) > 16 else None

    offers = data.get("offers", {})
    price = "free"
    if isinstance(offers, dict):
        p = offers.get("price", 0)
        if p and float(p) > 0:
            price = f"${p}"

    return build_event(
        title=title,
        description=desc,
        event_date=event_date,
        start_time=start_time,
        end_time=end_time,
        location_name=loc_name,
        address=loc_addr,
        source="luma",
        source_url=source_url,
        image_url=image if image else None,
        price=price,
    )


def _parse_luma_html(soup: BeautifulSoup, source_url: str) -> list[dict]:
    events = []
    for card in soup.select("[class*='event-card'], [class*='EventCard'], .event-link, a[href*='/event/']"):
        title_el = card.select_one("h2, h3, [class*='title'], [class*='name']")
        date_el = card.select_one("[class*='date'], [class*='time'], time")
        if title_el:
            title = title_el.get_text(strip=True)
            date_text = date_el.get_text(strip=True) if date_el else ""
            event_date = parse_date(date_text)
            if event_date:
                events.append(build_event(
                    title=title,
                    description="",
                    event_date=event_date,
                    source="luma",
                    source_url=source_url,
                ))
    return events
