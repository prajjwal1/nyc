"""McNally Jackson bookstore events scraper.

mcnallyjackson.com/events lists ~33 monthly author events / book clubs
across their NYC locations (SoHo, Williamsburg, Seaport, Downtown
Brooklyn). High-curation literary content the user explicitly wants.

Page format: server-rendered HTML, no JSON-LD. Each event is a
.event-list__details div with title/date/time/location/body/image
sub-elements.
"""

import re
from datetime import date as _date
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..utils.event_parser import build_event
from ..utils.http import fetch_text


BASE_URL = "https://www.mcnallyjackson.com"
EVENTS_URL = f"{BASE_URL}/events"

_DATE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_TIME_RE = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", re.IGNORECASE)


def _parse_date(text: str) -> _date | None:
    m = _DATE_RE.search(text or "")
    if not m:
        return None
    try:
        month, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return _date(year, month, day)
    except ValueError:
        return None


def _parse_time(text: str) -> str | None:
    m = _TIME_RE.search(text or "")
    if not m:
        return None
    hour = int(m.group(1))
    minute = int(m.group(2) or 0)
    ampm = m.group(3).lower()
    if ampm == "pm" and hour < 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"


def _detail_value(details_div, label_text: str) -> str:
    """Extract the value from a .event-list__details--item by label."""
    for item in details_div.select(".event-list__details--item"):
        label = item.select_one(".event-list__details--label")
        if label and label_text.lower() in label.get_text(strip=True).lower():
            # Strip the label text from the item's text content
            full = item.get_text(separator=" ", strip=True)
            return full.replace(label.get_text(strip=True), "", 1).strip(": ").strip()
    return ""


def _parse_event(details_div) -> dict | None:
    title_link = details_div.select_one(".event-list__title a")
    if not title_link:
        return None
    title = title_link.get_text(strip=True)
    if not title or len(title) < 4:
        return None
    href = title_link.get("href") or ""
    source_url = urljoin(BASE_URL, href)

    date_text = _detail_value(details_div, "Date")
    event_date = _parse_date(date_text)
    if not event_date:
        return None

    time_text = _detail_value(details_div, "Time")
    start_time = _parse_time(time_text)

    # Description from body text
    body = details_div.select_one(".event-list__body")
    description = body.get_text(separator=" ", strip=True) if body else ""
    description = re.sub(r"\s+", " ", description).strip()[:500]

    # Image
    img_el = details_div.select_one(".event-list__image img")
    image_url = None
    if img_el and img_el.get("src"):
        image_url = urljoin(BASE_URL, img_el["src"])

    # Location (address)
    addr_el = details_div.select_one(".event-details__location--location")
    venue_name = "McNally Jackson"
    venue_addr = ""
    if addr_el:
        line1 = addr_el.select_one(".address-line1")
        line2 = addr_el.select_one(".address-line2")
        if line1:
            venue_name = line1.get_text(strip=True)
        if line2:
            venue_addr = line2.get_text(strip=True)

    # Tags → categories
    tags = [t.get_text(strip=True).lower() for t in details_div.select(".event-tag__term a")]
    categories = ["books"]  # always books for a bookstore
    if any("book club" in t for t in tags):
        categories.append("books")
    if any("music" in t for t in tags):
        categories.append("music")

    return build_event(
        title=title,
        description=description,
        event_date=event_date,
        start_time=start_time,
        location_name=venue_name,
        address=venue_addr,
        source="mcnallyjackson",
        source_url=source_url,
        image_url=image_url,
        categories=sorted(set(categories)),
    )


def _month_urls(months_ahead: int = 2) -> list[str]:
    """Generate /events/YYYY/MM URLs for the current + next N months.
    Iter 102 audit: bare /events only returns current-month events. The
    `/events/YYYY/MM` pattern returns 35 (June) + 11 (July) future
    events. Mirrors the iter-91 comedy-club dynamic-URL pattern."""
    from datetime import date as _date
    today = _date.today()
    urls = [EVENTS_URL]
    for offset in range(1, months_ahead + 1):
        y, m = today.year, today.month + offset
        while m > 12:
            m -= 12
            y += 1
        urls.append(f"{EVENTS_URL}/{y}/{m:02d}")
    return urls


async def scrape() -> list[dict]:
    events: list[dict] = []
    seen: set[str] = set()
    for url in _month_urls():
        try:
            html = await fetch_text(url)
        except Exception as exc:
            print(f"[mcnallyjackson] Failed to fetch {url}: {exc}")
            continue
        soup = BeautifulSoup(html, "html.parser")
        for details in soup.find_all("div", class_="event-list__details"):
            try:
                ev = _parse_event(details)
            except Exception as exc:
                print(f"[mcnallyjackson] Error parsing event: {exc}")
                continue
            if not ev:
                continue
            ev_key = (ev.get("title", ""), ev.get("date", ""))
            if ev_key in seen:
                continue
            seen.add(ev_key)
            events.append(ev)
    print(f"[mcnallyjackson] {len(events)} events (across {len(_month_urls())} month URLs)")
    return events
