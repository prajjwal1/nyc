import json
from bs4 import BeautifulSoup
from ..utils.http import fetch_text
from ..utils.event_parser import build_event, parse_date, parse_time, parse_iso_to_local

VENUES = [
    {
        "name": "Brooklyn Bowl",
        "url": "https://www.brooklynbowl.com/events",
        "base": "https://www.brooklynbowl.com",
        "address": "61 Wythe Ave, Brooklyn, NY 11249",
    },
    {
        "name": "Music Hall of Williamsburg",
        "url": "https://www.musichallofwilliamsburg.com/events",
        "base": "https://www.musichallofwilliamsburg.com",
        "address": "66 N 6th St, Brooklyn, NY 11249",
    },
    {
        "name": "National Sawdust",
        "url": "https://nationalsawdust.org/events",
        "base": "https://nationalsawdust.org",
        "address": "80 N 6th St, Brooklyn, NY 11249",
    },
    {
        "name": "Rough Trade NYC",
        "url": "https://www.roughtradenyc.com/events",
        "base": "https://www.roughtradenyc.com",
        "address": "64 N 9th St, Brooklyn, NY 11249",
    },
]


async def scrape() -> list[dict]:
    events = []
    for venue in VENUES:
        try:
            html = await fetch_text(venue["url"])
            events.extend(_parse_venue(html, venue))
        except Exception as e:
            print(f"[music_venues] Failed {venue['name']}: {e}")
    return events


def _parse_venue(html: str, venue: dict) -> list[dict]:
    events = []
    soup = BeautifulSoup(html, "lxml")

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get("@type") == "Event" or item.get("@type") == "MusicEvent":
                    ev = _from_ld(item, venue)
                    if ev:
                        events.append(ev)
        except (json.JSONDecodeError, Exception):
            continue

    if not events:
        for card in soup.select("article, .event, [class*='event-item'], [class*='event-card'], .show, .listing"):
            ev = _from_card(card, venue)
            if ev:
                events.append(ev)

    return events


def _from_ld(data: dict, venue: dict) -> dict | None:
    title = data.get("name", "")
    desc = data.get("description", "")
    start = data.get("startDate", "")
    url = data.get("url", venue["url"])

    date_str, start_time = parse_iso_to_local(start)
    event_date = parse_date(date_str) if date_str else None
    if not event_date:
        return None

    image = data.get("image", "")
    if isinstance(image, list) and image:
        image = image[0]

    offers = data.get("offers", {})
    price = "unknown"
    if isinstance(offers, dict):
        p = offers.get("price", "")
        if str(p) == "0":
            price = "free"
        elif p:
            price = f"${p}"

    return build_event(
        title=title,
        description=desc[:500],
        event_date=event_date,
        start_time=start_time,
        location_name=venue["name"],
        address=venue.get("address", ""),
        source="music_venues",
        source_url=url,
        image_url=image if image else None,
        price=price,
        categories=["music"],
    )


def _from_card(card, venue: dict) -> dict | None:
    title_el = card.select_one("h2, h3, h4, [class*='title'], [class*='artist'], [class*='name']")
    date_el = card.select_one("time, [class*='date'], [class*='Date']")

    if not title_el:
        return None
    title = title_el.get_text(strip=True)
    if len(title) < 2:
        return None

    link_el = card.select_one("a[href]")
    link = ""
    if link_el:
        href = link_el.get("href", "")
        link = href if href.startswith("http") else f"{venue['base']}{href}"

    date_text = date_el.get("datetime", date_el.get_text(strip=True)) if date_el else ""
    event_date = parse_date(date_text) if date_text else None
    if not event_date:
        return None

    time_text = ""
    time_el = card.select_one("[class*='time'], [class*='doors']")
    if time_el:
        time_text = time_el.get_text(strip=True)
    start_time = parse_time(time_text or date_text)

    return build_event(
        title=title,
        description="",
        event_date=event_date,
        start_time=start_time,
        location_name=venue["name"],
        address=venue.get("address", ""),
        source="music_venues",
        source_url=link or venue["url"],
        categories=["music"],
    )
