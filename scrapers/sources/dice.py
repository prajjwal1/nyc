"""DICE.fm browse-page scraper.

Iter 101 audit: the JSON-LD path was extracting 0 events because DICE
only ships site-metadata (Brand, WebSite) as JSON-LD. The actual events
live in `__NEXT_DATA__.pageProps.events` — 30 events per browse-page
fetch, with structured fields (`name`, `dates.event_start_date`,
`venues[].name/address`, `images.landscape`, `perm_name`).
"""
import json
import re

from bs4 import BeautifulSoup
from ..utils.event_parser import build_event, parse_date, parse_time, parse_iso_to_local
from ..utils.http import fetch_text


URL = "https://dice.fm/browse?location=new-york"


async def scrape() -> list[dict]:
    events: list[dict] = []
    try:
        html = await fetch_text(URL)
    except Exception as exc:
        print(f"[dice] fetch failed: {exc}")
        return events

    # Primary: __NEXT_DATA__ event list
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(1))
        except Exception as exc:
            print(f"[dice] __NEXT_DATA__ parse failed: {exc}")
            data = {}
        raw_events = (
            data.get("props", {}).get("pageProps", {}).get("events", []) or []
        )
        for raw in raw_events:
            try:
                ev = _from_next_data(raw)
            except Exception as exc:
                print(f"[dice] parse error: {exc}")
                continue
            if ev:
                events.append(ev)
        print(f"[dice] Parsed {len(events)} events from __NEXT_DATA__")
        if events:
            return events

    # Fallback: legacy JSON-LD + DOM-card paths (kept defensive in case
    # DICE swaps back to JSON-LD).
    soup = BeautifulSoup(html, "lxml")
    from .generic import EVENT_TYPES

    def _is_event(t) -> bool:
        if isinstance(t, str):
            return t in EVENT_TYPES
        if isinstance(t, list):
            return any(isinstance(x, str) and x in EVENT_TYPES for x in t)
        return False

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            items = data if isinstance(data, list) else [data]
            for item in items:
                if _is_event(item.get("@type")):
                    ev = _from_ld(item)
                    if ev:
                        events.append(ev)
        except (json.JSONDecodeError, Exception):
            continue
    return events


def _from_next_data(raw: dict) -> dict | None:
    name = (raw.get("name") or "").strip()
    if not name:
        return None
    dates = raw.get("dates") or {}
    start_iso = dates.get("event_start_date") or ""
    if not start_iso:
        return None
    date_str, start_time = parse_iso_to_local(start_iso)
    event_date = parse_date(date_str) if date_str else None
    if not event_date:
        return None

    venues = raw.get("venues") or []
    venue = venues[0] if isinstance(venues, list) and venues else {}
    venue_name = ""
    venue_addr = ""
    lat = lng = None
    if isinstance(venue, dict):
        venue_name = (venue.get("name") or "").strip()
        venue_addr = (venue.get("address") or "").strip()
        loc = venue.get("location") or {}
        if isinstance(loc, dict):
            lat = loc.get("lat")
            lng = loc.get("lng")

    images = raw.get("images") or {}
    image_url = None
    if isinstance(images, dict):
        # Preference: landscape > portrait > square
        for key in ("landscape", "portrait", "square"):
            v = images.get(key)
            if isinstance(v, str) and v.startswith("http"):
                image_url = v
                break
            if isinstance(v, dict):
                u = v.get("url")
                if isinstance(u, str) and u.startswith("http"):
                    image_url = u
                    break

    perm = raw.get("perm_name") or ""
    source_url = f"https://dice.fm/event/{perm}" if perm else URL

    # about is a dict { description, highlights }; summary_lineup is a string.
    about = raw.get("about")
    if isinstance(about, dict):
        summary = (about.get("description") or "").strip()
    else:
        summary = (about or raw.get("summary_lineup") or "").strip()

    return build_event(
        title=name[:300],
        description=summary[:500],
        event_date=event_date,
        start_time=start_time,
        location_name=venue_name or None,
        address=venue_addr or None,
        source="dice",
        source_url=source_url,
        image_url=image_url,
        lat=lat if isinstance(lat, (int, float)) else None,
        lng=lng if isinstance(lng, (int, float)) else None,
        categories=["music"],
    )


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
