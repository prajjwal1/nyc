import json
from bs4 import BeautifulSoup
from ..utils.http import fetch_text
from ..utils.event_parser import build_event, parse_date, parse_time, parse_iso_to_local, parse_offers_price

URL = "https://dice.fm/browse?location=new-york"


async def scrape() -> list[dict]:
    events = []
    try:
        html = await fetch_text(URL)
        soup = BeautifulSoup(html, "lxml")

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if item.get("@type") in ("Event", "MusicEvent"):
                        ev = _from_ld(item)
                        if ev:
                            events.append(ev)
            except (json.JSONDecodeError, Exception):
                continue

        if not events:
            for card in soup.select("[class*='EventCard'], [class*='event-card'], a[href*='/event/']"):
                title_el = card.select_one("h3, h4, [class*='title'], [class*='name']")
                date_el = card.select_one("[class*='date'], time")

                if not title_el:
                    continue

                title = title_el.get_text(strip=True)
                date_text = date_el.get_text(strip=True) if date_el else ""
                event_date = parse_date(date_text) if date_text else None
                if not event_date:
                    continue

                href = card.get("href", "") if card.name == "a" else ""
                link_el = card.select_one("a[href]")
                if not href and link_el:
                    href = link_el.get("href", "")
                if href and not href.startswith("http"):
                    href = f"https://dice.fm{href}"

                events.append(build_event(
                    title=title,
                    description="",
                    event_date=event_date,
                    start_time=parse_time(date_text),
                    source="dice",
                    source_url=href or URL,
                    categories=["music"],
                ))
    except Exception as e:
        print(f"[dice] Failed: {e}")
    return events


def _from_ld(data: dict) -> dict | None:
    title = data.get("name", "")
    start = data.get("startDate", "")
    location = data.get("location", {})

    loc_name = location.get("name", "") if isinstance(location, dict) else ""
    date_str, start_time = parse_iso_to_local(start)
    event_date = parse_date(date_str) if date_str else None
    if not event_date:
        return None
    url = data.get("url", URL)
    image = data.get("image", "")
    if isinstance(image, list) and image:
        image = image[0]

    price = parse_offers_price(data.get("offers"))

    return build_event(
        title=title,
        description=data.get("description", "")[:500],
        event_date=event_date,
        start_time=start_time,
        location_name=loc_name,
        source="dice",
        source_url=url,
        image_url=image if image else None,
        price=price,
        categories=["music"],
    )
