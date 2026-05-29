"""nycforfree.co — Squarespace eventlist scraper.

Iter 100 audit: README/KNOWLEDGE.md marked this scraper as `✗ "HTML
structure unclear"` but live probe finds 129 Squarespace eventlist
articles on /events. Same pattern as brooklyncomedy.py — each event has:
  - a.eventlist-title-link        (title + URL)
  - time.event-date[datetime=...] (date)
  - time.event-time-12hr-start    (display time)
  - .eventlist-description        (blurb)

Every event surfaced is free by definition (it's the "NYC for Free"
curator) so price="free" is stamped.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..utils.event_parser import build_event, parse_date, parse_time
from ..utils.http import fetch_text


BASE_URL = "https://www.nycforfree.co"
EVENTS_URL = f"{BASE_URL}/events"


async def scrape() -> list[dict]:
    events: list[dict] = []
    # /events is a ~2MB Squarespace page — bump the timeout from the
    # default 30s to 90s so flaky-network runs still succeed.
    try:
        html = await fetch_text(EVENTS_URL, timeout=90)
    except Exception as exc:
        print(f"[nycforfree] fetch failed: {exc}")
        return events

    soup = BeautifulSoup(html, "lxml")
    articles = soup.select("article.eventlist-event, article[class*='eventlist-event']")
    print(f"[nycforfree] found {len(articles)} eventlist articles")

    for art in articles:
        try:
            ev = _parse_article(art)
        except Exception as exc:
            print(f"[nycforfree] parse error: {exc}")
            continue
        if ev:
            events.append(ev)

    print(f"[nycforfree] built {len(events)} events")
    return events


def _parse_article(art) -> dict | None:
    title_el = art.select_one("a.eventlist-title-link, h1.eventlist-title a, h2.eventlist-title a")
    if not title_el:
        return None
    title = title_el.get_text(strip=True)
    href = title_el.get("href", "")
    url = href if href.startswith("http") else f"{BASE_URL}{href}"

    # Date — prefer the 24h datetime which Squarespace ships in ISO format
    date_el = (
        art.select_one("time.event-time-24hr-start[datetime]")
        or art.select_one("time.event-date[datetime]")
        or art.select_one("time[datetime]")
    )
    date_text = ""
    if date_el is not None:
        date_text = date_el.get("datetime") or date_el.get_text(strip=True)
    event_date = parse_date(date_text) if date_text else None
    if not event_date:
        return None

    # Time — separate element. 12h preferred for display parsing.
    time_el = art.select_one("time.event-time-12hr-start, time.event-time-12hr-end, time.event-time")
    time_text = time_el.get_text(strip=True) if time_el else ""
    start_time = parse_time(time_text or "") or None

    # Description
    desc_el = art.select_one(".eventlist-description, .eventlist-excerpt, .eventlist-content")
    desc = desc_el.get_text(" ", strip=True) if desc_el else ""

    # Image (poster thumbnail)
    img_el = art.select_one(".eventlist-column-thumbnail img, img.eventlist-thumbnail, img")
    image_url = None
    if img_el is not None:
        image_url = img_el.get("data-src") or img_el.get("src") or None

    # Location — sometimes inline in the description
    loc_el = art.select_one(".eventlist-meta-address, [class*='address']")
    loc_name = loc_el.get_text(" ", strip=True) if loc_el else ""

    return build_event(
        title=title,
        description=desc[:500],
        event_date=event_date,
        start_time=start_time,
        location_name=loc_name or None,
        source="nycforfree",
        source_url=url,
        image_url=image_url,
        price="free",
    )
