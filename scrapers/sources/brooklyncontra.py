"""Brooklyn Contra — recurring contra-dance series scraper.

Brooklyn Contra (brooklyncontra.org) runs live-music contra dances roughly
every other weekend, plus the occasional special (Pride Techno Contra,
Harvest Ball, touring-band nights). User asked for it specifically as a
dance/fitness social event.

The /tickets page is a Squarespace **commerce store** — one product per
dance date, NOT a Squarespace event collection. So there's no Event
JSON-LD; the generic scraper can't parse it. Each product anchor under
`[data-controller="ProductList"]` carries:
  - a title with the date embedded ("May 17 with Cozy Socks",
    "September 26th Harvest Ball Evening Dance", "Oct. 4th Raven & Goose")
  - the price appended as a trailing "US$15.00"

The product-page slugs are stale clones (most read "dec-7th-with-paper-
plane-…"), so the DATE MUST come from the title text, not the href.
parse_date() only handles a leading date, so we extract month+day with a
dedicated regex here and infer the year. Workshop products
("Contra Connections: An Intermediate Workshop") have no date in the
title and are skipped naturally.
"""

from __future__ import annotations

import re
from datetime import date as _date

from bs4 import BeautifulSoup

from ..utils.http import fetch_text
from ..utils.event_parser import build_event


SOURCE = "brooklyncontra"
URL = "https://www.brooklyncontra.org/tickets"

# Default venue (from the site's LocalBusiness JSON-LD). Some dates list a
# "special location" in the title (kept in the title so it's visible), but
# the regular hall is the sensible default.
VENUE = "Brooklyn Contra (385 East 18th Street)"
ADDRESS = "385 East 18th Street, Brooklyn, NY 11226"
# Contra dances run in the evening; surfacing a sensible default lets the
# event land in the user's 5pm-11pm window and the "Tonight" rail.
START_TIME = "19:00"
END_TIME = "22:00"

_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}
_MONTH_ALT = "|".join(sorted(_MONTHS, key=len, reverse=True))
# "June 27th", "Oct. 4th", "May 17", "September 26th" — month then 1-2 digit
# day with an optional ordinal suffix. Matches anywhere in the title.
_DATE_RE = re.compile(
    rf"\b({_MONTH_ALT})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\b", re.IGNORECASE
)
_PRICE_RE = re.compile(r"US?\$\s*([\d,.]+)")


def _parse_date_from_title(title: str, today: _date) -> _date | None:
    m = _DATE_RE.search(title)
    if not m:
        return None
    month = _MONTHS.get(m.group(1).lower())
    day = int(m.group(2))
    if not month or not (1 <= day <= 31):
        return None
    # No year in titles. Assume current year, roll to next year if the date
    # is well in the past (store keeps recently-passed dates listed).
    year = today.year
    try:
        d = _date(year, month, day)
    except ValueError:
        return None
    if (today - d).days > 60:
        try:
            d = _date(year + 1, month, day)
        except ValueError:
            return None
    return d


def _clean_title(raw: str) -> str:
    """Strip the trailing price and the bare date token, prefix the series.

    "May 17 with Cozy Socks"            -> "Brooklyn Contra Dance with Cozy Socks"
    "July 11th"                         -> "Brooklyn Contra Dance — Live Music & Caller"
    "September 26th Harvest Ball ..."   -> "Brooklyn Contra Dance — Harvest Ball ..."

    The bare-date listings (just "July 11th") get a descriptive suffix
    rather than a bare "Brooklyn Contra Dance" — the quality filter nukes
    short titles ending in "dance" as caption fragments, and the suffix
    also reads better in the feed.
    """
    text = _PRICE_RE.sub("", raw).strip()
    # Remove the leading date token so the descriptor reads cleanly.
    remainder = _DATE_RE.sub("", text, count=1).strip(" -–—:,")
    # Drop a dangling leading "with"/"w/" connective when nothing precedes it.
    remainder = re.sub(r"^(w/|with)\s+", "with ", remainder, flags=re.IGNORECASE)
    if not remainder:
        return "Brooklyn Contra Dance — Live Music & Caller"
    if remainder.lower().startswith("with "):
        return f"Brooklyn Contra Dance {remainder}"
    return f"Brooklyn Contra Dance — {remainder}"


async def scrape() -> list[dict]:
    events: list[dict] = []
    today = _date.today()
    try:
        html = await fetch_text(URL)
    except Exception as e:
        print(f"[brooklyncontra] Failed to fetch: {e}")
        return events

    soup = BeautifulSoup(html, "lxml")
    container = soup.select_one('[data-controller="ProductList"]') or soup
    seen: set[str] = set()
    for a in container.find_all("a", href=True):
        if "/tickets/p/" not in a["href"]:
            continue
        raw = a.get_text(" ", strip=True)
        if not raw:
            continue
        event_date = _parse_date_from_title(raw, today)
        if not event_date or event_date < today:
            continue  # workshops (no date) and past dates are skipped

        title = _clean_title(raw)
        price_m = _PRICE_RE.search(raw)
        price = f"${price_m.group(1)}" if price_m else None
        # Dedupe by (date, title) — the store occasionally lists two products
        # for one night (e.g. Harvest Ball Advanced + Evening); keep both
        # since the titles differ, but drop exact repeats.
        key = f"{event_date.isoformat()}|{title.lower()}"
        if key in seen:
            continue
        seen.add(key)

        ev = build_event(
            title=title,
            description=(
                "Live-music contra dance from Brooklyn Contra — a friendly, "
                "all-levels social folk dance with a caller who teaches every "
                "dance, so no partner or experience needed. A great low-key "
                "way to move and meet people."
            ),
            event_date=event_date,
            start_time=START_TIME,
            end_time=END_TIME,
            location_name=VENUE,
            address=ADDRESS,
            source=SOURCE,
            source_url=URL,
            price=price,
            categories=["dance", "music"],
        )
        if ev:
            events.append(ev)

    print(f"[brooklyncontra] Generated {len(events)} contra-dance events")
    return events
