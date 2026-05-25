import json
from bs4 import BeautifulSoup
from ..utils.http import fetch_text
from ..utils.event_parser import build_event, parse_date, parse_time, parse_iso_to_local, parse_offers_price

MUSEUMS = [
    {
        "name": "MoMA",
        "url": "https://www.moma.org/calendar/",
        "base": "https://www.moma.org",
    },
    {
        "name": "The Met",
        "url": "https://www.metmuseum.org/events",
        "base": "https://www.metmuseum.org",
    },
    {
        "name": "Whitney Museum",
        "url": "https://whitney.org/events",
        "base": "https://whitney.org",
    },
    {
        "name": "Brooklyn Museum",
        "url": "https://www.brooklynmuseum.org/calendar",
        "base": "https://www.brooklynmuseum.org",
    },
    {
        "name": "New Museum",
        "url": "https://www.newmuseum.org/calendar",
        "base": "https://www.newmuseum.org",
    },
    {
        "name": "Guggenheim",
        "url": "https://www.guggenheim.org/calendar",
        "base": "https://www.guggenheim.org",
    },
]


async def scrape() -> list[dict]:
    events = []
    for museum in MUSEUMS:
        try:
            html = await fetch_text(museum["url"])
            events.extend(_parse_museum(html, museum))
        except Exception as e:
            print(f"[museums] Failed {museum['name']}: {e}")
    return events


def _parse_museum(html: str, museum: dict) -> list[dict]:
    events = []
    soup = BeautifulSoup(html, "lxml")

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get("@type") == "Event":
                    ev = _from_ld(item, museum)
                    if ev:
                        events.append(ev)
        except (json.JSONDecodeError, Exception):
            continue

    if not events:
        selectors = [
            "article", ".event-card", "[class*='event']", "[class*='calendar-item']",
            ".card", ".listing-item", "[class*='Event']", "[class*='program']",
        ]
        for sel in selectors:
            for card in soup.select(sel):
                ev = _from_card(card, museum)
                if ev:
                    events.append(ev)
            if events:
                break

    return events


def _from_ld(data: dict, museum: dict) -> dict | None:
    title = data.get("name", "")
    desc = data.get("description", "")
    start = data.get("startDate", "")

    date_str, start_time = parse_iso_to_local(start)
    event_date = parse_date(date_str) if date_str else None
    if not event_date:
        return None
    url = data.get("url", museum["url"])
    image = data.get("image", "")
    if isinstance(image, list) and image:
        image = image[0]

    price = parse_offers_price(data.get("offers"))

    return build_event(
        title=title,
        description=desc[:500],
        event_date=event_date,
        start_time=start_time,
        location_name=museum["name"],
        source="museums",
        source_url=url,
        image_url=image if image else None,
        categories=["art"],
        price=price,
    )


def _from_card(card, museum: dict) -> dict | None:
    title_el = card.select_one("h2, h3, h4, [class*='title'], [class*='name']")
    date_el = card.select_one("time, [class*='date'], [class*='Date']")

    if not title_el:
        return None

    title = title_el.get_text(strip=True)
    if len(title) < 3 or len(title) > 300:
        return None

    link_el = card.select_one("a[href]")
    link = ""
    if link_el:
        href = link_el.get("href", "")
        link = href if href.startswith("http") else f"{museum['base']}{href}"

    date_text = ""
    if date_el:
        date_text = date_el.get("datetime", date_el.get_text(strip=True))
    event_date = parse_date(date_text) if date_text else None
    if not event_date:
        return None

    return build_event(
        title=title,
        description="",
        event_date=event_date,
        location_name=museum["name"],
        source="museums",
        source_url=link or museum["url"],
        categories=["art"],
    )
