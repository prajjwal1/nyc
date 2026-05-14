"""NYPL events scraper.

Two channels:
1. Refinery API (refinery.nypl.org) — returns ~13 generic events.
2. HTML calendar scraper (www.nypl.org/events/calendar?keyword=...) —
   returns search-filtered results for the things the user actually
   wants (book clubs, author talks, WNYC partnership events).
"""

import re
from html import unescape
from urllib.parse import urljoin

from ..utils.http import fetch_json, fetch_text
from ..utils.event_parser import build_event, parse_date

REFINERY_URL = "https://refinery.nypl.org/api/nypl/ndo/v0.1/site-data/events?limit=50"

# Search keywords the user has flagged as high-signal — these surface
# the specific event types worth attending at NYPL. Each query hits the
# public events calendar HTML and the results are merged.
SEARCH_QUERIES = [
    "wnyc book club",
    "book club",
    "author talks",
    "literary",
    "poetry",
]
CALENDAR_URL_TMPL = "https://www.nypl.org/events/calendar?keyword={query}"
BASE_URL = "https://www.nypl.org"

DEFAULT_IMAGE = "https://drupal.nypl.org/sites-drupal/default/files/2023-01/default_events_img_868x455.png"

_DATE_RE = re.compile(
    r"(?P<wday>Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s+"
    r"(?P<month>Jan|Feb|Mar|Apr|May|June|July|Aug|Sept?|Oct|Nov|Dec)[a-z]*\s+"
    r"(?P<day>\d{1,2})"
    r"(?:[^@]+@\s*(?P<hour>\d{1,2})(?::(?P<min>\d{2}))?\s*(?P<ampm>AM|PM)?)?",
    re.IGNORECASE,
)
_MONTH = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


async def scrape() -> list[dict]:
    events: list[dict] = []
    seen_urls: set[str] = set()

    try:
        data = await fetch_json(REFINERY_URL)
        for item in data.get("data", []):
            ev = _parse_refinery_event(item)
            if ev:
                events.append(ev)
                seen_urls.add(ev.get("sourceUrl", ""))
    except Exception as exc:
        print(f"[nypl] Refinery API failed: {exc}")

    for query in SEARCH_QUERIES:
        url = CALENDAR_URL_TMPL.format(query=query.replace(" ", "+"))
        try:
            html = await fetch_text(url)
        except Exception as exc:
            print(f"[nypl] HTML calendar failed for '{query}': {exc}")
            continue
        new = _parse_calendar_html(html, query_hint=query)
        added = 0
        for ev in new:
            if ev.get("sourceUrl") in seen_urls:
                continue
            seen_urls.add(ev.get("sourceUrl", ""))
            events.append(ev)
            added += 1
        if added:
            print(f"[nypl-html] '{query}': added {added} events")

    return events


def _parse_refinery_event(item: dict) -> dict | None:
    attrs = item.get("attributes", {})
    title = attrs.get("name", "")
    if not title:
        return None
    start = attrs.get("start-date", "")
    event_date = parse_date(start[:10]) if start else None
    if not event_date:
        return None
    start_time = start[11:16] if len(start) > 16 else None
    end = attrs.get("end-date", "")
    end_time = end[11:16] if len(end) > 16 else None

    desc_short = attrs.get("description-short", "")
    desc = re.sub(r"\s+", " ", desc_short).strip()[:400]
    uri = attrs.get("uri", {})
    url = uri.get("full-uri", "") if isinstance(uri, dict) else ""

    return build_event(
        title=title,
        description=desc,
        event_date=event_date,
        start_time=start_time,
        end_time=end_time,
        location_name="NYPL",
        source="nypl",
        source_url=url or "https://www.nypl.org/events",
        price="free",
        categories=["books", "free"],
    )


_ROW_RE = re.compile(r"<tr\s+class=\"col-4\">(.+?)</tr>", re.DOTALL)
_CELL_RES = {
    "time": re.compile(
        r'data-title="Date/Time"[^>]*>(.*?)</td>', re.DOTALL),
    "title_block": re.compile(
        r'data-title="Title/Description"[^>]*>(.*?)</td>', re.DOTALL),
    "location": re.compile(
        r'data-title="Location"[^>]*>(.*?)</td>', re.DOTALL),
}
_LINK_RE = re.compile(r'<a\s+href="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
_DESC_RE = re.compile(r'<div\s+class="description">(.*?)</div>', re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")


def _clean_html(s: str) -> str:
    s = _TAG_RE.sub(" ", s)
    s = unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def _parse_calendar_html(html: str, query_hint: str = "") -> list[dict]:
    """Extract event rows from the NYPL events calendar HTML table."""
    events: list[dict] = []
    for row in _ROW_RE.findall(html):
        time_cell = _CELL_RES["time"].search(row)
        title_cell = _CELL_RES["title_block"].search(row)
        loc_cell = _CELL_RES["location"].search(row)
        if not (time_cell and title_cell):
            continue

        time_text = _clean_html(time_cell.group(1))
        m = _DATE_RE.search(time_text)
        if not m:
            continue
        month_name = m.group("month").lower()[:3]
        month = _MONTH.get(month_name)
        if not month:
            continue
        day = int(m.group("day"))
        from datetime import date as _date, timedelta as _td
        today = _date.today()
        year = today.year
        # If the parsed month/day is before today, assume next year (NYPL
        # rolls events through but doesn't include the year in the table).
        candidate = _date(year, month, day)
        if candidate < today - _td(days=2):
            candidate = _date(year + 1, month, day)

        start_time = None
        if m.group("hour"):
            hh = int(m.group("hour"))
            mm = int(m.group("min")) if m.group("min") else 0
            ampm = (m.group("ampm") or "PM").upper()
            if ampm == "PM" and hh < 12:
                hh += 12
            if ampm == "AM" and hh == 12:
                hh = 0
            start_time = f"{hh:02d}:{mm:02d}"

        link_m = _LINK_RE.search(title_cell.group(1))
        if not link_m:
            continue
        href, title_raw = link_m.group(1), _clean_html(link_m.group(2))
        if not title_raw:
            continue
        source_url = urljoin(BASE_URL, href.split("#")[0])

        desc_m = _DESC_RE.search(title_cell.group(1))
        desc = _clean_html(desc_m.group(1))[:500] if desc_m else ""

        location = _clean_html(loc_cell.group(1)) if loc_cell else "NYPL"

        cats = ["books", "free"]
        if "author" in (title_raw + desc + query_hint).lower():
            cats.append("art")
        if "poetry" in (title_raw + desc + query_hint).lower():
            cats.append("art")

        events.append(build_event(
            title=title_raw,
            description=desc,
            event_date=candidate,
            start_time=start_time,
            location_name=location or "NYPL",
            source="nypl",
            source_url=source_url,
            image_url=DEFAULT_IMAGE,
            price="free",
            categories=sorted(set(cats)),
        ))
    return events
