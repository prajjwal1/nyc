import asyncio
import inspect
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.sources import luma, bookclubbar, lizsbookbar, nypl, nycforfree, eventbrite, museums, music_venues, parks, theskint, meetup, dice, instagram, substack, partiful, generic, reddit
from scrapers.normalize import process, _load_previous_events_index

ASYNC_SCRAPERS = [
    # Reddit returns 0 events but harvests event-platform URLs into
    # discovered_urls.json; the generic scraper picks them up next run.
    ("reddit", reddit.scrape),
    ("luma", luma.scrape),
    ("bookclubbar", bookclubbar.scrape),
    ("lizsbookbar", lizsbookbar.scrape),
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

    # Carry over existing IG events from the previous events.json on EVERY
    # run — full scrapes included. Reasons:
    #   (1) IG's incremental cursor + rate limiting + session expiry mean
    #       a fresh IG sweep can produce FEWER events than the previous
    #       run. Without carry-over we silently lose those events.
    #   (2) The partial-save below happens BEFORE the IG sweep finishes,
    #       so without carry-over the live events.json has ZERO IG events
    #       for the duration of every full scrape (~20-40 min window).
    # Dedup handles the merge: if the fresh IG run re-produces an event,
    # the old + new copies collapse to one via the existing dedup chain.
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

    # Run sanity check at the end of every full run so the per-account IG
    # diagnostic block lands in the workflow log. hard_fail=False keeps the
    # pipeline non-fatal but the breakdown is visible immediately.
    try:
        from scrapers import sanity_check
        sanity_check.main(OUTPUT_PATH, write_stats=True, hard_fail=False)
    except Exception as exc:
        print(f"[run_all] sanity_check failed: {exc}")


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

    Combines two signals:
      1. Accounts with future events in the current feed (in-feed events count)
      2. account_quality.json — historical yield across all runs (so high-yield
         accounts surface even when their events are filtered out of THIS run)

    Surfaces in the UI as a "Top Accounts" widget. Each entry marked with
    `userSaved` so UI can split "From accounts I save from" vs "Suggested".
    """
    from collections import defaultdict
    affinity = _load_user_affinity_set()
    quality = _load_account_quality()
    today = _today_iso()

    # Pass 1: per-account in-feed event count
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
        y = e.get("accountEventYield", 0) or 0
        if y and y > slot["yield"]:
            slot["yield"] = y
        if e.get("accountVerified"):
            slot["verified"] = True
        if not slot["image"] and e.get("imageUrl"):
            slot["image"] = e["imageUrl"]

    # Pass 2: enrich with account_quality.json for accounts that haven't
    # produced events in THIS feed but have strong historical yield.
    # Cap at 20 high-yield accounts not already in feed so the suggestion
    # surface stays meaningful even on sparse-IG runs.
    historical = []
    for acct, info in quality.items():
        if acct in per_acct:
            continue  # already counted
        posts = info.get("posts_scraped", 0)
        if posts < 5:
            continue
        ev = info.get("events_emitted", 0)
        y = ev / posts if posts else 0
        if y < 0.25:
            continue  # only meaningful yields
        historical.append((acct, y, ev, posts))
    historical.sort(key=lambda t: (-t[1], -t[3]))  # yield desc, posts desc

    for acct, y, _ev, _posts in historical[:20]:
        per_acct[acct] = {
            "events": 0,                  # 0 in current feed
            "yield": round(y, 3),
            "verified": False,
            "image": None,
        }

    out = []
    for acct, info in per_acct.items():
        # Drop entries with both 0 events AND 0 yield (no signal)
        if info["events"] == 0 and info["yield"] < 0.10:
            continue
        out.append({
            "username": acct,
            "events": info["events"],
            "yield": round(info["yield"], 3),
            "verified": info["verified"],
            "image": info["image"],
            "userSaved": acct in affinity,
        })
    # Rank by event count first (active accounts), then by yield, then by
    # affinity (saved-from accounts elevated).
    out.sort(key=lambda a: (
        -a["events"],
        -a["yield"],
        0 if a.get("userSaved") else 1,
    ))
    return out[:n]


def _load_account_quality() -> dict:
    """Load IG account_quality.json — lifetime per-account stats."""
    import json
    path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "data", "account_quality.json",
    )
    if not os.path.isfile(path):
        return {}
    try:
        with open(path) as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


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
