import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.sources import luma, bookclubbar, nypl, nycforfree, eventbrite, museums, music_venues, parks, theskint, meetup, dice, instagram
from scrapers.normalize import process

SCRAPERS = [
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


async def main():
    all_events = []

    results = await asyncio.gather(
        *[run_scraper(name, fn) for name, fn in SCRAPERS],
        return_exceptions=True,
    )

    for i, result in enumerate(results):
        name = SCRAPERS[i][0]
        if isinstance(result, Exception):
            print(f"[{name}] Failed with exception: {result}")
        elif isinstance(result, list):
            all_events.extend(result)

    print(f"\nTotal raw events: {len(all_events)}")
    processed = process(all_events)
    print(f"After processing: {len(processed)} events")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump({"events": processed, "lastUpdated": __import__("datetime").datetime.now().isoformat()}, f, indent=2)

    print(f"Written to {OUTPUT_PATH}")

    site_public = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site", "public", "events.json")
    os.makedirs(os.path.dirname(site_public), exist_ok=True)
    with open(site_public, "w") as f:
        json.dump({"events": processed, "lastUpdated": __import__("datetime").datetime.now().isoformat()}, f, indent=2)
    print(f"Copied to {site_public}")


if __name__ == "__main__":
    asyncio.run(main())
