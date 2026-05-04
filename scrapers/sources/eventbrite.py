import json
import re
from bs4 import BeautifulSoup
from ..utils.http import fetch_text
from ..utils.event_parser import build_event, parse_date, parse_time

SEARCH_URLS = [
    # Geographic + time (density)
    "https://www.eventbrite.com/d/ny--new-york/events--this-week/",
    "https://www.eventbrite.com/d/ny--new-york/events--this-weekend/",
    "https://www.eventbrite.com/d/ny--new-york/events--next-week/",
    "https://www.eventbrite.com/d/ny--new-york/events--this-month/",
    "https://www.eventbrite.com/d/ny--new-york/events--next-month/",
    "https://www.eventbrite.com/d/ny--brooklyn/events--this-week/",
    "https://www.eventbrite.com/d/ny--brooklyn/events--this-weekend/",
    "https://www.eventbrite.com/d/ny--brooklyn/events--this-month/",
    "https://www.eventbrite.com/d/ny--new-york/free--events/",
    # Category filters (NYC 20s-30s lifestyle)
    "https://www.eventbrite.com/d/ny--new-york/music--events/",
    "https://www.eventbrite.com/d/ny--new-york/comedy--events/",
    "https://www.eventbrite.com/d/ny--new-york/food-and-drink--events/",
    "https://www.eventbrite.com/d/ny--new-york/nightlife--events/",
    "https://www.eventbrite.com/d/ny--new-york/arts--events/",
    "https://www.eventbrite.com/d/ny--new-york/film-and-media--events/",
    "https://www.eventbrite.com/d/ny--new-york/dating--events/",
    "https://www.eventbrite.com/d/ny--new-york/performing-and-visual-arts--events/",
    "https://www.eventbrite.com/d/ny--new-york/holiday--events/",
    "https://www.eventbrite.com/d/ny--new-york/sports-and-fitness--events/",
    "https://www.eventbrite.com/d/ny--new-york/health-and-wellness--events/",
    "https://www.eventbrite.com/d/ny--brooklyn/music--events/",
    "https://www.eventbrite.com/d/ny--brooklyn/comedy--events/",
    "https://www.eventbrite.com/d/ny--brooklyn/nightlife--events/",
    "https://www.eventbrite.com/d/ny--brooklyn/food-and-drink--events/",
    # Williamsburg / specific neighborhoods
    "https://www.eventbrite.com/d/ny--williamsburg/events/",
    "https://www.eventbrite.com/d/ny--bushwick/events/",
    "https://www.eventbrite.com/d/ny--greenpoint/events/",
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
            events.extend(_walk_jsonld(data))
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


_EVENT_TYPES = {
    "Event", "MusicEvent", "TheaterEvent", "DanceEvent", "ComedyEvent",
    "FoodEvent", "SportsEvent", "BusinessEvent", "EducationEvent",
    "ExhibitionEvent", "FestivalEvent", "LiteraryEvent", "ScreeningEvent",
    "SocialEvent", "ChildrensEvent",
}


def _walk_jsonld(data) -> list[dict]:
    """Recursively walk JSON-LD looking for Event objects.

    Handles: direct Event, list, ItemList.itemListElement, @graph arrays,
    Organization with nested events, etc.
    """
    found = []
    if isinstance(data, list):
        for item in data:
            found.extend(_walk_jsonld(item))
        return found
    if not isinstance(data, dict):
        return found

    t = data.get("@type", "")
    if isinstance(t, list):
        types = set(t)
    else:
        types = {t}

    if types & _EVENT_TYPES:
        ev = _parse_ld_event(data)
        if ev:
            found.append(ev)
        return found

    if "ItemList" in types:
        for el in data.get("itemListElement", []) or []:
            if isinstance(el, dict):
                # ListItem wrapper
                inner = el.get("item", el)
                found.extend(_walk_jsonld(inner))
        return found

    if "@graph" in data:
        found.extend(_walk_jsonld(data["@graph"]))

    if "Organization" in types or "LocalBusiness" in types:
        for key in ("event", "events"):
            nested = data.get(key)
            if nested:
                found.extend(_walk_jsonld(nested))

    return found


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
