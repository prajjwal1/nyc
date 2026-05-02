import json
import re
from bs4 import BeautifulSoup
from ..utils.http import fetch_text
from ..utils.event_parser import build_event, parse_date, parse_time

SEARCH_URLS = [
    "https://www.eventbrite.com/d/ny--new-york/events--this-week/",
    "https://www.eventbrite.com/d/ny--new-york/free--events/",
    "https://www.eventbrite.com/d/ny--brooklyn/events--this-week/",
]


async def scrape() -> list[dict]:
    events = []
    for url in SEARCH_URLS:
        try:
            html = await fetch_text(url)
            events.extend(_parse_search_page(html, url))
        except Exception as e:
            print(f"[eventbrite] Failed {url}: {e}")
    return events


def _parse_search_page(html: str, source_url: str) -> list[dict]:
    events = []
    soup = BeautifulSoup(html, "lxml")

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get("@type") == "Event":
                    ev = _parse_ld_event(item)
                    if ev:
                        events.append(ev)
        except (json.JSONDecodeError, Exception):
            continue

    if not events:
        for card in soup.select("[class*='event-card'], [class*='SearchResultCard'], article"):
            title_el = card.select_one("h2, h3, [class*='title']")
            date_el = card.select_one("p[class*='date'], [class*='date'], time")
            link_el = card.select_one("a[href*='eventbrite.com/e/']")

            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            date_text = date_el.get_text(strip=True) if date_el else ""
            link = link_el.get("href", "") if link_el else source_url

            event_date = parse_date(date_text)
            if not event_date:
                continue

            price_el = card.select_one("[class*='price'], [class*='Price']")
            price = price_el.get_text(strip=True) if price_el else "unknown"
            if "free" in price.lower():
                price = "free"

            loc_el = card.select_one("[class*='location'], [class*='venue']")
            loc_name = loc_el.get_text(strip=True) if loc_el else ""

            events.append(build_event(
                title=title,
                description="",
                event_date=event_date,
                start_time=parse_time(date_text),
                location_name=loc_name,
                source="eventbrite",
                source_url=link,
                price=price,
            ))

    return events


def _parse_ld_event(data: dict) -> dict | None:
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
        elif isinstance(addr, str):
            loc_addr = addr

    event_date = parse_date(start[:10]) if start else None
    if not event_date:
        return None

    start_time = start[11:16] if len(start) > 16 else None
    url = data.get("url", "")

    offers = data.get("offers", {})
    price = "unknown"
    if isinstance(offers, dict):
        p = offers.get("price", "")
        if p == "0" or p == 0:
            price = "free"
        elif p:
            price = f"${p}"
    elif isinstance(offers, list) and offers:
        p = offers[0].get("price", "")
        if p == "0" or p == 0:
            price = "free"
        elif p:
            price = f"${p}"

    image = data.get("image", "")
    if isinstance(image, list) and image:
        image = image[0]

    return build_event(
        title=title,
        description=desc[:500],
        event_date=event_date,
        start_time=start_time,
        location_name=loc_name,
        address=loc_addr,
        source="eventbrite",
        source_url=url,
        image_url=image if image else None,
        price=price,
    )
