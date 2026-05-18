"""NYC Parks event scraper.

nycgovparks.org/events publishes ~50 events per page with consistent
HTML structure. Events are server-side rendered with date encoded in
both the URL path (/events/YYYY/MM/DD/slug) AND inline `.date_graphic`
elements. The previous selector-based parser missed all 50 because the
HTML uses `.event` / `.event-title` / `.location`, not the legacy
`.event_listing` / `.event_title` patterns the scraper was looking for.

Strategy:
  1. Iterate every `<div class="event">` (one per event on the page).
  2. Extract title from `.event-title`, location from `.location`,
     description from `.description`.
  3. Parse the date from the event's anchor href (URL contains
     /YYYY/MM/DD/) — the most reliable signal.
  4. Mark all events as free (NYC Parks programming is overwhelmingly
     free public events).
"""

from __future__ import annotations

import re
from datetime import date as _date

from bs4 import BeautifulSoup

from ..utils.event_parser import build_event, parse_date, parse_time, infer_categories
from ..utils.http import fetch_text


URL = "https://www.nycgovparks.org/events"
_DATE_PATH_RE = re.compile(r"/events/(\d{4})/(\d{1,2})/(\d{1,2})/")


def _parse_date_from_href(href: str) -> _date | None:
    m = _DATE_PATH_RE.search(href or "")
    if not m:
        return None
    try:
        y, mth, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return _date(y, mth, d)
    except ValueError:
        return None


def _text(el) -> str:
    return el.get_text(" ", strip=True) if el else ""


async def scrape() -> list[dict]:
    try:
        html = await fetch_text(URL)
    except Exception as e:
        print(f"[parks] Index fetch failed: {e}")
        return []

    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception as e:
        print(f"[parks] Parse failed: {e}")
        return []

    events: list[dict] = []
    seen_urls: set[str] = set()

    # The page renders each event in a `<div class="event">` block.
    for block in soup.select("div.event"):
        # Title + canonical URL
        title_anchor = block.select_one(".event-title a, h3 a, h4 a")
        if title_anchor is None:
            continue
        title = _text(title_anchor)
        href = title_anchor.get("href") or ""
        if not href:
            continue
        url = href if href.startswith("http") else f"https://www.nycgovparks.org{href}"
        if url in seen_urls:
            continue
        seen_urls.add(url)

        # Date comes from the URL path — most reliable
        event_date = _parse_date_from_href(href)
        if not event_date:
            # Fallback: look for .date_graphic with month + day text
            dg = block.select_one(".date_graphic, time")
            if dg:
                event_date = parse_date(_text(dg))
        if not event_date:
            continue

        # Location and description (when present)
        loc_name = _text(block.select_one(".location"))
        description = _text(block.select_one(".description, .event_body p"))

        # Time: NYC Parks events embed start times in various spots —
        # the description often has "Time: 10:00 AM", or there's a
        # `.time` element.
        time_text = _text(block.select_one(".time, .event_time"))
        start_time = parse_time(time_text) if time_text else parse_time(description)

        cats = infer_categories(title, description)
        # NYC Parks programming skews outdoors — always include it.
        if "outdoors" not in cats:
            cats = sorted(set(list(cats) + ["outdoors"]))

        events.append(
            build_event(
                title=title,
                description=description[:600],
                event_date=event_date,
                start_time=start_time,
                location_name=loc_name or "NYC Parks",
                source="nyc_parks",
                source_url=url,
                image_url="https://www.nycgovparks.org/pagefiles/180/Bryant-Park.jpg",
                price="free",
                categories=cats,
            )
        )

    print(f"[parks] Parsed {len(events)} events from nycgovparks.org/events")
    return events
