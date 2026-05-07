import asyncio
import inspect
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.sources import luma, bookclubbar, nypl, nycforfree, eventbrite, museums, music_venues, parks, theskint, meetup, dice, instagram, substack, partiful, generic, reddit
from scrapers.normalize import process, _load_previous_events_index

ASYNC_SCRAPERS = [
    # Reddit returns 0 events but harvests event-platform URLs into
    # discovered_urls.json; the generic scraper picks them up next run.
    ("reddit", reddit.scrape),
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

# Allow CI to skip slow sources for fast partial scrapes.
SKIP_INSTAGRAM = os.environ.get("SKIP_INSTAGRAM", "0") == "1"
IG_SAVED_ONLY = os.environ.get("IG_SAVED_ONLY", "0") == "1"

if SKIP_INSTAGRAM:
    SYNC_SCRAPERS = []
elif IG_SAVED_ONLY:
    # Quick-scrape mode: only user's saved posts (30s-2min).
    SYNC_SCRAPERS = [("instagram-saved", instagram.scrape_saved_only)]

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

    # Snapshot previous events to preserve firstSeenAt across runs.
    previous_index = _load_previous_events_index(OUTPUT_PATH)
    print(f"[run_all] Previous events.json: {len(previous_index)} events")

    # When skipping the full IG sweep, carry over existing IG events from
    # the previous events.json (so quick scrapes don't lose all the IG data
    # the full scrape gathered). These are merged with the fresh non-IG
    # events from this run, then re-processed.
    if SKIP_INSTAGRAM or IG_SAVED_ONLY:
        carryover = [e for e in previous_index.values() if e.get("source") == "instagram"]
        if carryover:
            all_events.extend(carryover)
            print(f"[run_all] Carrying over {len(carryover)} IG events from previous run")

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
        _write_events(process(all_events, previous_index), OUTPUT_PATH)
        print(f"[run_all] Partial save after async scrapers: {len(all_events)} raw events")

    for name, fn in SYNC_SCRAPERS:
        result = run_sync_scraper(name, fn)
        all_events.extend(result)

    print(f"\nTotal raw events: {len(all_events)}")
    processed = process(all_events, previous_index)
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
    payload = {
        "events": events,
        "lastUpdated": _dt.datetime.now().isoformat(),
        "topAccounts": _top_ig_accounts(events, n=12),
    }
    for path in (primary_path, SITE_PUBLIC_PATH):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp, path)


def _top_ig_accounts(events: list[dict], n: int = 12) -> list[dict]:
    """Compute the top IG accounts by yield + future event count.

    Surfaces in the UI as a "Top Accounts" widget so the user can quickly
    browse events from the most reliable NYC event-emitting accounts.
    Each account is marked with `userSaved: bool` so the UI can split
    into "From accounts I save from" vs "Suggested for you".
    """
    from collections import defaultdict
    affinity = _load_user_affinity_set()
    today = _today_iso()
    per_acct: dict[str, dict] = defaultdict(lambda: {
        "events": 0,
        "yield": 0.0,
        "verified": False,
        "image": None,
    })
    for e in events:
        acct = (e.get("instagramAccount") or "").lower()
        if not acct:
            continue
        if (e.get("date") or "") < today:
            continue
        slot = per_acct[acct]
        slot["events"] += 1
        # accountEventYield is stamped onto events; take max seen.
        y = e.get("accountEventYield", 0) or 0
        if y and y > slot["yield"]:
            slot["yield"] = y
        if e.get("accountVerified"):
            slot["verified"] = True
        if not slot["image"] and e.get("imageUrl"):
            slot["image"] = e["imageUrl"]
    out = []
    for acct, info in per_acct.items():
        if info["events"] < 1:
            continue
        out.append({
            "username": acct,
            "events": info["events"],
            "yield": round(info["yield"], 3),
            "verified": info["verified"],
            "image": info["image"],
            "userSaved": acct in affinity,
        })
    # Rank by upcoming event count, then by yield (high-quality accounts win).
    out.sort(key=lambda a: (-a["events"], -a["yield"]))
    return out[:n]


def _load_user_affinity_set() -> set:
    """Load user-affinity (saved-from) account usernames lowercased."""
    import json
    path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "data", "user_affinity_accounts.json",
    )
    if not os.path.isfile(path):
        return set()
    try:
        with open(path) as f:
            d = json.load(f)
        accts = d.get("accounts", []) if isinstance(d, dict) else d
        return {str(a).lower() for a in accts}
    except Exception:
        return set()


def _today_iso() -> str:
    import datetime as _dt
    return _dt.date.today().isoformat()


if __name__ == "__main__":
    asyncio.run(main())
