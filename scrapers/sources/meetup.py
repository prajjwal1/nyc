import json
from bs4 import BeautifulSoup
from ..utils.http import fetch_text
from ..utils.event_parser import (
    build_event,
    parse_date,
    parse_time,
    parse_iso_to_local,
    parse_offers_price,
)

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


# Schema.org Event subtypes — the bare "Event" check missed philosophy /
# language / education events (Meetup tags them EducationEvent), routing
# them through the empty-description DOM fallback instead. Audit at iter
# 83 found "Word and Object by Quine Week 4" with a wrong description
# bleeding in. Iter 84 DRY'd this up across all source scrapers using the
# canonical set in generic.EVENT_TYPES.
from .generic import EVENT_TYPES as _MEETUP_EVENT_TYPES


def _is_meetup_event_type(t) -> bool:
    if isinstance(t, str):
        return t in _MEETUP_EVENT_TYPES
    if isinstance(t, list):
        return any(isinstance(s, str) and s in _MEETUP_EVENT_TYPES for s in t)
    return False


def _parse_meetup(html: str, source_url: str) -> list[dict]:
    events = []
    soup = BeautifulSoup(html, "lxml")

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            items = data if isinstance(data, list) else [data]
            for item in items:
                if _is_meetup_event_type(item.get("@type")):
                    ev = _from_ld(item)
                    if ev:
                        events.append(ev)
        except (json.JSONDecodeError, Exception):
            continue

    if not events:
        for card in soup.select(
            "[id*='event-card'], [class*='eventCard'], [data-testid*='event']"
        ):
            title_el = card.select_one("h2, h3, [class*='title']")
            date_el = card.select_one("time, [class*='date']")
            link_el = card.select_one("a[href*='/events/']")

            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            date_text = (
                date_el.get("datetime", date_el.get_text(strip=True)) if date_el else ""
            )
            event_date = parse_date(date_text) if date_text else None
            if not event_date:
                continue

            link = link_el.get("href", "") if link_el else source_url
            if link and not link.startswith("http"):
                link = f"https://www.meetup.com{link}"

            loc_el = card.select_one("[class*='venue'], [class*='location']")
            loc_name = loc_el.get_text(strip=True) if loc_el else ""

            events.append(
                build_event(
                    title=title,
                    description="",
                    event_date=event_date,
                    start_time=parse_time(date_text),
                    location_name=loc_name,
                    source="meetup",
                    source_url=link,
                )
            )

    return events


def _from_ld(data: dict) -> dict | None:
    title = data.get("name", "")
    desc = data.get("description", "")
    start = data.get("startDate", "")
    location = data.get("location", {})

    loc_name = ""
    loc_addr = ""
    region = ""
    if isinstance(location, dict):
        loc_name = location.get("name", "")
        addr = location.get("address", {})
        if isinstance(addr, dict):
            loc_addr = addr.get("streetAddress", "")
            region = (addr.get("addressRegion") or "").strip().upper()

    # NYC-only gate: meetup's NYC-scoped search still returns the occasional
    # out-of-metro event (observed: a Washington, DC group's "AI Side Income"
    # event). When the JSON-LD carries an explicit state, drop anything outside
    # the tri-state area. Gate on state (precise) rather than the group slug, so
    # NYC groups like "Washington Square ..." aren't false-dropped. Events with
    # no region are kept (online/unspecified) — the search scope covers them.
    if region and region not in (
        "NY",
        "NJ",
        "CT",
        "NEW YORK",
        "NEW JERSEY",
        "CONNECTICUT",
    ):
        return None

    date_str, start_time = parse_iso_to_local(start)
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

    # Extract price from offers — most meetup events are free; users
    # benefit from seeing the FREE pill prominently.
    price = parse_offers_price(data.get("offers"))

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
        price=price,
    )
