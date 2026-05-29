"""Powerhouse Arena bookstore events scraper.

powerhousearena.com/events lists ~10-15 monthly book launches, author
talks, and signings at the DUMBO independent bookstore. High-curation
literary events targeting NYC readers.

Page format: WordPress events-manager plugin, server-rendered. Each
event is a `<div class="row event-row">` with structured sub-elements:
  - h4 > a (title + URL)
  - h4.dates (date string, e.g. "Monday Jun 01, 2026")
  - h4.times (time string, e.g. "7:00 PM")
  - .event-image > a > img (image URL)
  - .event-location (venue name)
  - last <div> sibling (description paragraph)
"""

from __future__ import annotations

import re
from datetime import date as _date
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..utils.event_parser import build_event
from ..utils.http import fetch_text


BASE_URL = "https://powerhousearena.com"
EVENTS_URL = f"{BASE_URL}/events/"
DEFAULT_ADDRESS = "28 Adams St, Brooklyn, NY 11201"

# Powerhouse renders dates as "Monday Jun 01, 2026" (Weekday Mon DD, YYYY).
_DATE_RE = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{1,2}),?\s+(\d{4})\b"
)
_TIME_RE = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*(AM|PM)", re.IGNORECASE)
_MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


def _parse_date(text: str) -> _date | None:
    m = _DATE_RE.search(text or "")
    if not m:
        return None
    try:
        month = _MONTHS[m.group(1)[:3]]
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
    ampm = m.group(3).upper()
    if ampm == "PM" and hour < 12:
        hour += 12
    if ampm == "AM" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"


def _text(el) -> str:
    return el.get_text(" ", strip=True) if el else ""


def _parse_event(row) -> dict | None:
    # Title comes from the FIRST h4 > a in .info-wrap (not the .dates/.times h4s)
    info_wrap = row.select_one(".info-wrap")
    if not info_wrap:
        return None
    # The first h4 > a is the title; subsequent h4.dates / h4.times are date/time
    title_anchor = None
    for h4 in info_wrap.find_all("h4"):
        cls = h4.get("class") or []
        if "dates" in cls or "times" in cls:
            continue
        a = h4.find("a")
        if a:
            title_anchor = a
            break
    if not title_anchor:
        return None
    title = _text(title_anchor)
    if not title or len(title) < 4:
        return None
    href = title_anchor.get("href") or ""
    source_url = urljoin(BASE_URL, href) if href else EVENTS_URL

    date_el = row.select_one("h4.dates")
    event_date = _parse_date(_text(date_el))
    if not event_date:
        return None

    time_el = row.select_one("h4.times")
    start_time = _parse_time(_text(time_el))

    # Image lives in .event-image > a > img
    img_el = row.select_one(".event-image img")
    image_url = None
    if img_el:
        src = img_el.get("src") or img_el.get("data-src") or ""
        if src:
            image_url = urljoin(BASE_URL, src)

    # Venue name from .event-location
    venue_el = row.select_one(".event-location")
    venue_name = _text(venue_el) or "POWERHOUSE Arena"

    # Description — the last <div> in .info-wrap that isn't date-wrap, contains
    # a paragraph with the book/event blurb.
    description = ""
    for div in info_wrap.find_all("div", recursive=False):
        cls = div.get("class") or []
        # Skip wrappers — we want the un-classed div with the <p>
        if "date-wrap" in " ".join(cls):
            continue
        p = div.find("p")
        if p:
            description = _text(p)
            break

    return build_event(
        title=title,
        description=description[:500],
        event_date=event_date,
        start_time=start_time,
        location_name=venue_name,
        address=DEFAULT_ADDRESS,
        source="powerhousearena",
        source_url=source_url,
        image_url=image_url,
        categories=["books"],
    )


async def scrape() -> list[dict]:
    try:
        html = await fetch_text(EVENTS_URL)
    except Exception as exc:
        print(f"[powerhousearena] Failed to fetch {EVENTS_URL}: {exc}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    events: list[dict] = []
    for row in soup.select("div.row.event-row"):
        try:
            ev = _parse_event(row)
            if ev:
                events.append(ev)
        except Exception as exc:
            print(f"[powerhousearena] Error parsing event: {exc}")
    print(f"[powerhousearena] {len(events)} events")
    return events
