"""Brooklyn Comedy Collective shows scraper.

brooklyncomedycollective.com/show-schedule lists ~80+ upcoming comedy
shows at BCC's East Williamsburg theater (Eris Mainstage / Eris Deep
Space). High volume of indie comedy programming.

Page format: Squarespace eventlist. Each show is an
`<article class="eventlist-event eventlist-event--upcoming ...">` with:
  - h1.eventlist-title > a (title + URL)
  - time.event-date[datetime="YYYY-MM-DD"]
  - time.event-time-12hr-start (display time)
  - time.event-time-24hr-start[datetime="YYYY-MM-DD"] (used as fallback)
  - .eventlist-column-thumbnail img[data-src] (poster image)
  - .eventlist-cats a (category tag, e.g. "Eris Mainstage")
  - .eventlist-description (short blurb)
"""

from __future__ import annotations

import re
from datetime import date as _date
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..utils.event_parser import build_event
from ..utils.http import fetch_text


BASE_URL = "https://www.brooklyncomedycollective.com"
EVENTS_URL = f"{BASE_URL}/show-schedule"
DEFAULT_ADDRESS = "167 Graham Ave, Brooklyn, NY 11206"

_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")
_TIME_RE = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*(AM|PM)", re.IGNORECASE)


def _parse_date_iso(text: str) -> _date | None:
    m = _DATE_RE.match(text or "")
    if not m:
        return None
    try:
        return _date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _parse_time_24h(text: str) -> str | None:
    # 24-hour "HH:MM" — Squarespace renders this in <time class="...24hr">
    m = re.match(r"^(\d{1,2}):(\d{2})", (text or "").strip())
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        if 0 <= h < 24 and 0 <= mi < 60:
            return f"{h:02d}:{mi:02d}"
    # Fall back to 12-hour AM/PM
    m12 = _TIME_RE.search(text or "")
    if not m12:
        return None
    hour = int(m12.group(1))
    minute = int(m12.group(2) or 0)
    ampm = m12.group(3).upper()
    if ampm == "PM" and hour < 12:
        hour += 12
    if ampm == "AM" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"


def _text(el) -> str:
    return el.get_text(" ", strip=True) if el else ""


def _parse_event(article) -> dict | None:
    title_link = article.select_one("h1.eventlist-title a, .eventlist-title a")
    if not title_link:
        return None
    title = _text(title_link)
    if not title or len(title) < 2:
        return None
    # Skip private / closed events — these aren't open to the public.
    title_lower = title.lower()
    if "private event" in title_lower or "closed for" in title_lower:
        return None
    href = title_link.get("href") or ""
    source_url = href if href.startswith("http") else urljoin(BASE_URL, href)

    # Date: prefer the <time class="event-date" datetime="YYYY-MM-DD"> in meta
    date_el = article.select_one("time.event-date")
    event_date = None
    if date_el:
        dt_attr = date_el.get("datetime") or ""
        event_date = _parse_date_iso(dt_attr)
    if not event_date:
        # Fallback: 24hr-start time tag also carries datetime
        alt = article.select_one("time.event-time-24hr-start, time[datetime]")
        if alt:
            event_date = _parse_date_iso(alt.get("datetime") or "")
    if not event_date:
        return None

    # Start time: 24h variant is most precise
    start_time = None
    t24 = article.select_one("time.event-time-24hr-start")
    if t24:
        start_time = _parse_time_24h(_text(t24))
    if not start_time:
        t12 = article.select_one("time.event-time-12hr-start, .eventlist-datetag-time")
        if t12:
            start_time = _parse_time_24h(_text(t12))

    end_time = None
    e24 = article.select_one("time.event-time-24hr-end")
    if e24:
        end_time = _parse_time_24h(_text(e24))

    # Image — Squarespace lazyloads via data-src
    image_url = None
    img_el = article.select_one("img")
    if img_el:
        for attr in ("data-src", "data-image", "src"):
            val = img_el.get(attr) or ""
            if val and not val.startswith("data:"):
                # Squarespace CDN URLs are protocol-relative sometimes
                if val.startswith("//"):
                    val = "https:" + val
                image_url = val
                break

    # Category tag (e.g. "Eris Mainstage", "Eris Deep Space")
    cat_el = article.select_one(".eventlist-cats a")
    venue_subname = _text(cat_el)

    # Description (excerpt)
    desc_el = article.select_one(".eventlist-description, .eventlist-excerpt")
    description = _text(desc_el)

    location_name = "Brooklyn Comedy Collective"
    if venue_subname and venue_subname.lower() != "brooklyn comedy collective":
        location_name = f"Brooklyn Comedy Collective ({venue_subname})"

    return build_event(
        title=title,
        description=description[:500],
        event_date=event_date,
        start_time=start_time,
        end_time=end_time,
        location_name=location_name,
        address=DEFAULT_ADDRESS,
        source="brooklyncomedy",
        source_url=source_url,
        image_url=image_url,
        categories=["comedy"],
    )


async def scrape() -> list[dict]:
    try:
        html = await fetch_text(EVENTS_URL)
    except Exception as exc:
        print(f"[brooklyncomedy] Failed to fetch {EVENTS_URL}: {exc}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    events: list[dict] = []
    seen_urls: set[str] = set()

    for article in soup.select("article.eventlist-event--upcoming, article.eventlist-event"):
        try:
            ev = _parse_event(article)
            if not ev:
                continue
            if ev["sourceUrl"] in seen_urls:
                continue
            events.append(ev)
            seen_urls.add(ev["sourceUrl"])
        except Exception as exc:
            print(f"[brooklyncomedy] Error parsing event: {exc}")
    print(f"[brooklyncomedy] {len(events)} events")
    return events
