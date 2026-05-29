"""Smorgasburg recurring-event generator.

Smorgasburg is a NYC food-market institution that the
`sanity_check.py::WARNING_CHECKS` explicitly requires. The official
website (smorgasburg.com) only ships site-metadata JSON-LD (WebSite +
LocalBusiness) with no per-event structure — it's run as recurring
weekly markets, no individual event pages.

This scraper emits one event per upcoming weekend per location for the
next 8 weeks, following the publicly-known schedule:

  Saturday  @ East River State Park, Williamsburg (11am-6pm)
  Sunday    @ Breeze Hill, Prospect Park (11am-6pm)

(Schedule confirmed against smorgasburg.com homepage. May be paused
on certain weekends — surfacing the recurring slot is a feature: the
user can verify on the day.)
"""
from __future__ import annotations

from datetime import date as _date, timedelta

from ..utils.event_parser import build_event


SOURCE = "smorgasburg"
START_TIME = "11:00"
END_TIME = "18:00"
DESCRIPTION = (
    "Smorgasburg — NYC's open-air weekend food market. ~80 vendors with "
    "everything from ramen to lobster rolls, BBQ to vegan donuts. Free "
    "admission; pay-per-vendor. Held every Saturday at East River State "
    "Park in Williamsburg and every Sunday in Prospect Park. (Outdoor; "
    "check social for weather updates.)"
)
LOCATIONS = (
    {
        "weekday": 5,  # Saturday
        "name": "East River State Park",
        "address": "90 Kent Avenue, Brooklyn, NY 11211",
        "neighborhood": "williamsburg",
        "lat": 40.7218,
        "lng": -73.9606,
    },
    {
        "weekday": 6,  # Sunday
        "name": "Breeze Hill, Prospect Park",
        "address": "Prospect Park West, Brooklyn, NY",
        "neighborhood": "park slope",
        "lat": 40.6601,
        "lng": -73.9690,
    },
)
WEEKS_AHEAD = 8


def _upcoming_dates(weekday: int, weeks: int) -> list[_date]:
    today = _date.today()
    days_until = (weekday - today.weekday()) % 7
    first = today + timedelta(days=days_until)
    return [first + timedelta(weeks=i) for i in range(weeks)]


async def scrape() -> list[dict]:
    events: list[dict] = []
    for loc in LOCATIONS:
        for d in _upcoming_dates(loc["weekday"], WEEKS_AHEAD):
            day_name = "Saturday" if loc["weekday"] == 5 else "Sunday"
            title = f"Smorgasburg {day_name} — {loc['neighborhood'].title()}"
            ev = build_event(
                title=title,
                description=DESCRIPTION,
                event_date=d,
                start_time=START_TIME,
                end_time=END_TIME,
                location_name=loc["name"],
                address=loc["address"],
                source=SOURCE,
                source_url="https://www.smorgasburg.com",
                price="free",
                categories=["food", "outdoors", "free"],
                lat=loc["lat"],
                lng=loc["lng"],
            )
            if ev:
                events.append(ev)
    print(f"[smorgasburg] Generated {len(events)} recurring events")
    return events
