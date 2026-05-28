import json
import re
from bs4 import BeautifulSoup
from ..utils.http import fetch_text
from ..utils.event_parser import build_event, parse_date, parse_time, parse_iso_to_local, parse_offers_price

# Iter 98 audit:
# - MoMA returns 403 to every UA — bot block. Removed from the list.
# - Guggenheim moved /calendar to /event. Updated.
# - Brooklyn Museum / Whitney / New Museum / Met all JS-render their event
#   data (no JSON-LD, no __NEXT_DATA__). The DOM-card fallback now rejects
#   page-scaffold junk titles ("Today's events", "Narrow search", date-only
#   strings) so the museums scraper degrades gracefully instead of shipping
#   garbage events.
MUSEUMS = [
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
        "url": "https://www.guggenheim.org/event",  # iter 98: was /calendar (404)
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

    # Accept Schema.org Event subtypes (iter 84). Museums host
    # ExhibitionEvent, VisualArtsEvent, EducationEvent (artist talks),
    # ScreeningEvent (film series), Festival, etc. — strict
    # `@type == "Event"` was missing all of these.
    from .generic import EVENT_TYPES

    def _is_event(t) -> bool:
        if isinstance(t, str):
            return t in EVENT_TYPES
        if isinstance(t, list):
            return any(isinstance(x, str) and x in EVENT_TYPES for x in t)
        return False

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            items = data if isinstance(data, list) else [data]
            for item in items:
                if _is_event(item.get("@type")):
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


# Title patterns the DOM-card fallback should refuse. Iter 98 audit found
# museums was emitting page-scaffold strings as "events": "Thursday, May 28"
# (calendar header), "Narrow search" (a filter widget), "Today's events"
# (page heading). These are UI chrome, not events.
_MUSEUM_TITLE_REJECT_RES = [
    re.compile(r"^\s*(?:mon|tue|tues|wed|weds|thu|thur|thurs|fri|sat|sun)(?:day)?[\s,].*\d", re.IGNORECASE),
    # "Today's events" / "Today’s events" — straight + curly apostrophe.
    re.compile(r"^\s*today['’]?s?\s+events?\s*$", re.IGNORECASE),
    re.compile(r"^\s*(?:narrow|filter|refine|browse)\b", re.IGNORECASE),
    re.compile(r"^\s*(?:view|see|all|more|next|previous|prev)\s+(?:all\s+)?events?\b", re.IGNORECASE),
    re.compile(r"^\s*search\s*(?:events?|results?)?\s*$", re.IGNORECASE),
    re.compile(r"^\s*\d{1,2}\s*[-/]\s*\d{1,2}(?:\s*[-/]\s*\d{2,4})?\s*$"),  # bare date
    re.compile(r"^\s*(?:upcoming|featured)\s+events?\s*$", re.IGNORECASE),
]


def _is_museum_card_junk(title: str) -> bool:
    return any(rx.match(title) for rx in _MUSEUM_TITLE_REJECT_RES)


def _from_card(card, museum: dict) -> dict | None:
    title_el = card.select_one("h2, h3, h4, [class*='title'], [class*='name']")
    date_el = card.select_one("time, [class*='date'], [class*='Date']")

    if not title_el:
        return None

    title = title_el.get_text(strip=True)
    if len(title) < 3 or len(title) > 300:
        return None
    if _is_museum_card_junk(title):
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
