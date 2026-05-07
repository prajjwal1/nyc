import json
import re
from bs4 import BeautifulSoup
from ..utils.http import fetch_text
from ..utils.event_parser import build_event, parse_date, parse_time

LUMA_PAGES = [
    # /nyc is Luma's curated NYC discover page — broad mix, ~20 events per fetch.
    "https://lu.ma/nyc",
    # Per-category NYC pages — each yields 20 events with strong topical
    # overlap to user interests (social/parties = meet-people focus).
    "https://lu.ma/nyc/social",
    "https://lu.ma/nyc/parties",
    "https://lu.ma/nyc/networking",
    "https://lu.ma/nyc/community",
    "https://lu.ma/nyc/music",
    "https://lu.ma/nyc/art",
    "https://lu.ma/nyc/food",
    "https://lu.ma/nyc/comedy",
    "https://lu.ma/nyc/literary",
    "https://lu.ma/nyc/wellness",
    "https://lu.ma/nyc/fitness",
    "https://lu.ma/nyc/running",
    "https://lu.ma/nyc/run-clubs",
    "https://lu.ma/nyc/yoga",
    # Singles / meeting people — directly serves user's primary goal
    "https://lu.ma/nyc/dating",
    "https://lu.ma/nyc/singles",
    "https://lu.ma/nyc/queer",
    # Music / creative
    "https://lu.ma/nyc/jazz",
    "https://lu.ma/nyc/dance",
    "https://lu.ma/nyc/open-mic",
    "https://lu.ma/nyc/acoustic",
    "https://lu.ma/nyc/photography",
    "https://lu.ma/nyc/design",
    # Active / outdoor social
    "https://lu.ma/nyc/climbing",
    "https://lu.ma/nyc/biking",
    "https://lu.ma/nyc/volleyball",
    # Hands-on social workshops
    "https://lu.ma/nyc/pottery",
    "https://lu.ma/nyc/craft",
    "https://lu.ma/nyc/workshops",
    # Food
    "https://lu.ma/nyc/breakfast",
    "https://lu.ma/nyc/brunch",
    "https://lu.ma/nyc/mixology",
    # Games + meditation (aligns with games/wellness interests)
    "https://lu.ma/nyc/gaming",
    "https://lu.ma/nyc/meditation",
    # Curator calendars (verified live)
    "https://lu.ma/nycbackgammonclub",
    "https://lu.ma/readingrhythms-manhattan",
    "https://lu.ma/litclub.nyc",
    "https://lu.ma/thinkolio",
    "https://lu.ma/founderscoffee",
    "https://lu.ma/cinemaclub",
]


async def scrape() -> list[dict]:
    """Scrape Luma calendars.  Retries with browser-like headers on 403."""
    events = []
    for url in LUMA_PAGES:
        page_events = await _try_luma_url(url)
        events.extend(page_events)
    return events


async def _try_luma_url(url: str) -> list[dict]:
    """Try to fetch a Luma page with multiple header strategies."""
    import asyncio

    header_variants = [
        # Default (Mozilla baseline)
        None,
        # Browser-like with referer
        {
            "Referer": "https://www.google.com/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
        # luma.com instead of lu.ma (alternate domain)
    ]
    # Retry with luma.com if lu.ma 403s
    if "lu.ma/" in url:
        alt_url = url.replace("lu.ma/", "luma.com/")
    else:
        alt_url = None

    for headers in header_variants:
        try:
            html = (await fetch_text(url, headers=headers)) if headers else (await fetch_text(url))
            events = _parse_luma_page(html, url)
            return events
        except Exception as e:
            err_msg = str(e)
            if "403" in err_msg or "Forbidden" in err_msg:
                await asyncio.sleep(0.5)
                continue
            # Other errors (404, etc.) — try alt URL too
            break

    # Last resort: try alt domain
    if alt_url:
        try:
            html = await fetch_text(alt_url)
            return _parse_luma_page(html, url)
        except Exception as e:
            print(f"[luma] {url} (and {alt_url}): {e}")
            return []

    return []


def _parse_luma_page(html: str, source_url: str) -> list[dict]:
    events = []
    soup = BeautifulSoup(html, "lxml")

    script_tags = soup.find_all("script", type="application/ld+json")
    for script in script_tags:
        try:
            data = json.loads(script.string)
            if isinstance(data, list):
                for item in data:
                    result = _parse_ld_json(item, source_url)
                    if isinstance(result, list):
                        events.extend(result)
                    elif result:
                        events.append(result)
            elif isinstance(data, dict):
                result = _parse_ld_json(data, source_url)
                if isinstance(result, list):
                    events.extend(result)
                elif result:
                    events.append(result)
        except (json.JSONDecodeError, Exception):
            continue

    if not events:
        events.extend(_parse_luma_html(soup, source_url))

    return events


def _parse_ld_json(data: dict, source_url: str) -> dict | list | None:
    # Handle Organization schema with nested events array
    if data.get("@type") == "Organization":
        nested_events = data.get("events", data.get("event", []))
        if isinstance(nested_events, list):
            results = []
            for nested in nested_events:
                if isinstance(nested, dict):
                    ev = _parse_ld_json(nested, source_url)
                    if ev and isinstance(ev, dict):
                        results.append(ev)
            return results
        return None

    # Handle ItemList schema (Luma sometimes wraps events this way)
    if data.get("@type") == "ItemList":
        items = data.get("itemListElement", [])
        if isinstance(items, list):
            results = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                # ItemList items can be either bare Events or ListItem wrappers
                inner = item.get("item", item)
                if isinstance(inner, dict):
                    ev = _parse_ld_json(inner, source_url)
                    if ev and isinstance(ev, dict):
                        results.append(ev)
                    elif isinstance(ev, list):
                        results.extend(ev)
            return results
        return None

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
