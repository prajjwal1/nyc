import json
from bs4 import BeautifulSoup
from ..utils.http import fetch_text
from ..utils.event_parser import build_event, parse_date, parse_time

URL = "https://www.nycgovparks.org/events"


async def scrape() -> list[dict]:
    events = []
    try:
        html = await fetch_text(URL)
        soup = BeautifulSoup(html, "lxml")

        for card in soup.select(".card, .event_listing, tr.event, [class*='event-item'], article"):
            title_el = card.select_one("h3 a, h4 a, .event_title a, [class*='title'] a, h3, h4")
            date_el = card.select_one("time, .event_date, [class*='date'], td:first-child")

            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            link = ""
            if title_el.name == "a":
                href = title_el.get("href", "")
                link = href if href.startswith("http") else f"https://www.nycgovparks.org{href}"
            else:
                a = title_el.select_one("a")
                if a:
                    href = a.get("href", "")
                    link = href if href.startswith("http") else f"https://www.nycgovparks.org{href}"

            date_text = ""
            if date_el:
                date_text = date_el.get("datetime", date_el.get_text(strip=True))
            event_date = parse_date(date_text) if date_text else None
            if not event_date:
                continue

            loc_el = card.select_one("[class*='location'], [class*='park'], .event_location")
            loc_name = loc_el.get_text(strip=True) if loc_el else ""

            time_el = card.select_one("[class*='time']")
            start_time = parse_time(time_el.get_text(strip=True)) if time_el else parse_time(date_text)

            events.append(build_event(
                title=title,
                description="",
                event_date=event_date,
                start_time=start_time,
                location_name=loc_name,
                source="nyc_parks",
                source_url=link or URL,
                price="free",
                categories=["outdoors", "free"],
            ))
    except Exception as e:
        print(f"[parks] Failed: {e}")
    return events
