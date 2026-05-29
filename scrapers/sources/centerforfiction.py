"""Center for Fiction events scraper.

centerforfiction.org/events/ lists the Brooklyn nonprofit's upcoming
literary programming — author talks, panels, novel discussions, member
events. ~7-10 events visible at a time. High-curation literary content
in Fort Greene.

Page format: server-rendered HTML, no JSON-LD on the listing page.
Each event is wrapped in a `<li class="content-list-query-item">`
containing:
  - <a href="/event/..."> — the event URL
  - <h2 class="heading-5"> — title (may include italics for book names)
  - <div class="event-details-info"> with two spans:
      - "<weekday>, <time> EDT"  (e.g. "Friday, 6:00 pm EDT")
      - "<Month> <day>, <year>"  (e.g. "June 5, 2026")
  - <p class="body-3 margin-t"> — short description
  - <img data-src="..."> — featured image (lazyloaded, so prefer data-src)
"""

from __future__ import annotations

import re
from datetime import date as _date
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..utils.event_parser import build_event
from ..utils.http import fetch_text


BASE_URL = "https://centerforfiction.org"
EVENTS_URL = f"{BASE_URL}/events/"
DEFAULT_ADDRESS = "15 Lafayette Ave, Brooklyn, NY 11217"

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5,
    "june": 6, "july": 7, "august": 8, "september": 9, "october": 10,
    "november": 11, "december": 12,
}

# "June 5, 2026" or "June 5 2026"
_DATE_RE = re.compile(
    r"(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2}),?\s+(\d{4})",
    re.IGNORECASE,
)
_TIME_RE = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", re.IGNORECASE)


def _parse_date(text: str) -> _date | None:
    m = _DATE_RE.search(text or "")
    if not m:
        return None
    try:
        month = _MONTHS[m.group(1).lower()]
        day, year = int(m.group(2)), int(m.group(3))
        return _date(year, month, day)
    except (KeyError, ValueError):
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


def _text(el) -> str:
    return el.get_text(" ", strip=True) if el else ""


def _parse_event(item) -> dict | None:
    title_el = item.select_one("h2")
    if not title_el:
        return None
    title = _text(title_el)
    if not title or len(title) < 4:
        return None

    link_el = item.select_one('a[href*="/event/"]')
    href = link_el.get("href") if link_el else ""
    source_url = href if href.startswith("http") else urljoin(BASE_URL, href or EVENTS_URL)

    details = item.select_one(".event-details-info")
    if not details:
        return None
    details_text = _text(details)
    event_date = _parse_date(details_text)
    if not event_date:
        return None
    start_time = _parse_time(details_text)

    # Description in <p class="body-3 ...">
    desc_el = item.select_one("p.body-3")
    description = _text(desc_el)

    # Image — Center for Fiction lazyloads with a base64 placeholder src and
    # the real URL in data-src.
    image_url = None
    img_el = item.select_one("img")
    if img_el:
        for attr in ("data-src", "src"):
            val = img_el.get(attr) or ""
            if val and not val.startswith("data:"):
                image_url = val if val.startswith("http") else urljoin(BASE_URL, val)
                break

    return build_event(
        title=title,
        description=description[:500],
        event_date=event_date,
        start_time=start_time,
        location_name="Center for Fiction",
        address=DEFAULT_ADDRESS,
        source="centerforfiction",
        source_url=source_url,
        image_url=image_url,
        categories=["books"],
    )


async def scrape() -> list[dict]:
    try:
        html = await fetch_text(EVENTS_URL)
    except Exception as exc:
        print(f"[centerforfiction] Failed to fetch {EVENTS_URL}: {exc}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    events: list[dict] = []
    seen_urls: set[str] = set()

    for item in soup.select("li.content-list-query-item"):
        try:
            ev = _parse_event(item)
            if ev and ev["sourceUrl"] not in seen_urls:
                events.append(ev)
                seen_urls.add(ev["sourceUrl"])
        except Exception as exc:
            print(f"[centerforfiction] Error parsing event: {exc}")
    print(f"[centerforfiction] {len(events)} events")
    return events
