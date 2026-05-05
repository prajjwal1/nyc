import asyncio
import inspect
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.sources import luma, bookclubbar, nypl, nycforfree, eventbrite, museums, music_venues, parks, theskint, meetup, dice, instagram, substack, partiful, generic
from scrapers.normalize import process

ASYNC_SCRAPERS = [
    ("luma", luma.scrape),
    ("bookclubbar", bookclubbar.scrape),
    ("nypl", nypl.scrape),
    ("nycforfree", nycforfree.scrape),
    ("eventbrite", eventbrite.scrape),
    ("museums", museums.scrape),
    ("music_venues", music_venues.scrape),
    ("parks", parks.scrape),
    ("theskint", theskint.scrape),
    ("meetup", meetup.scrape),
    ("dice", dice.scrape),
    ("substack", substack.scrape),
    ("partiful", partiful.scrape),
    ("generic", generic.scrape),
]

SYNC_SCRAPERS = [
    ("instagram", instagram.scrape),
]

OUTPUT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "events.json")


async def run_scraper(name: str, scrape_fn) -> list[dict]:
    try:
        print(f"[{name}] Scraping...")
        events = await scrape_fn()
        print(f"[{name}] Found {len(events)} events")
        return events
    except Exception as e:
        print(f"[{name}] ERROR: {e}")
        return []


def run_sync_scraper(name: str, scrape_fn) -> list[dict]:
    try:
        print(f"[{name}] Scraping...")
        events = scrape_fn()
        print(f"[{name}] Found {len(events)} events")
        return events
    except Exception as e:
        print(f"[{name}] ERROR: {e}")
        return []


async def main():
    all_events = []

    results = await asyncio.gather(
        *[run_scraper(name, fn) for name, fn in ASYNC_SCRAPERS],
        return_exceptions=True,
    )

    for i, result in enumerate(results):
        name = ASYNC_SCRAPERS[i][0]
        if isinstance(result, Exception):
            print(f"[{name}] Failed with exception: {result}")
        elif isinstance(result, list):
            all_events.extend(result)

    # Save partial result after async scrapers — protects against IG hanging
    # the whole pipeline. We'll overwrite once IG completes (or doesn't).
    if all_events:
        _write_events(process(all_events), OUTPUT_PATH)
        print(f"[run_all] Partial save after async scrapers: {len(all_events)} raw events")

    for name, fn in SYNC_SCRAPERS:
        result = run_sync_scraper(name, fn)
        all_events.extend(result)

    print(f"\nTotal raw events: {len(all_events)}")
    processed = process(all_events)
    print(f"After processing: {len(processed)} events")

    _write_events(processed, OUTPUT_PATH)
    print(f"Written to {OUTPUT_PATH}")


SITE_PUBLIC_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "site", "public", "events.json",
)


def _write_events(events: list[dict], primary_path: str = OUTPUT_PATH) -> None:
    """Write events.json to both data/ and site/public/ atomically."""
    import datetime as _dt
    payload = {"events": events, "lastUpdated": _dt.datetime.now().isoformat()}
    for path in (primary_path, SITE_PUBLIC_PATH):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp, path)


if __name__ == "__main__":
    asyncio.run(main())
