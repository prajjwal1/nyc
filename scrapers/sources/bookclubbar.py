from bs4 import BeautifulSoup
from ..utils.http import fetch_text
from ..utils.event_parser import build_event, parse_date, parse_time

URL = "https://www.bookclubbar.com/events"


async def scrape() -> list[dict]:
    events = []
    try:
        html = await fetch_text(URL)
        soup = BeautifulSoup(html, "lxml")

        for item in soup.select(".eventlist-event, .summary-item, article, [data-type='event']"):
            title_el = item.select_one("h1 a, h2 a, h3 a, .eventlist-title a, .summary-title a, .eventlist-title, .summary-title")
            date_el = item.select_one("time, .eventlist-meta-date, .summary-metadata-container, .event-date")
            desc_el = item.select_one(".eventlist-description, .summary-excerpt, p")

            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            link = title_el.get("href", "")
            if link and not link.startswith("http"):
                link = f"https://www.bookclubbar.com{link}"

            date_text = date_el.get("datetime", "") if date_el and date_el.get("datetime") else (date_el.get_text(strip=True) if date_el else "")
            event_date = parse_date(date_text)
            if not event_date:
                continue

            time_el = item.select_one(".eventlist-meta-time, .event-time-12hr, .event-time")
            start_time = parse_time(time_el.get_text(strip=True)) if time_el else None

            desc = desc_el.get_text(strip=True) if desc_el else ""

            events.append(build_event(
                title=title,
                description=desc,
                event_date=event_date,
                start_time=start_time,
                location_name="Book Club Bar",
                address="197 E 3rd St, New York, NY 10009",
                source="bookclubbar",
                source_url=link or URL,
                categories=["books", "social"],
            ))
    except Exception as e:
        print(f"[bookclubbar] Failed: {e}")
    return events
