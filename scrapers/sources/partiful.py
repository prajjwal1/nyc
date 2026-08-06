"""Partiful scraper — NYC-focused, robust.

Partiful has no public per-event index, but `partiful.com/explore/nyc` is a
server-rendered, NYC-scoped discovery page whose `__NEXT_DATA__` embeds ~60
events across a trending section, several curated sections, and a feed. That
is the primary source here (the old `/discover` page only exposed 5 NYC
"trending" events and also mixed in LA/SF). `/discover` is kept as a
NYC-filtered fallback in case the explore page's shape changes.

Robustness:
  - Header-variant retry on fetch.
  - Defensive per-event parsing (one bad item never sinks the run).
  - Proper UTC→America/New_York conversion (Partiful startDate is UTC; naive
    slicing mis-dated evening events by a day).
  - NYC gate via event timezone so a cross-listed non-NYC event can't leak.
  - Clear logging — never a silent zero.
"""
import json
import os
import asyncio
import re

import httpx

from bs4 import BeautifulSoup

from ..utils.http import fetch_text
from ..utils.event_parser import build_event, parse_date, parse_iso_to_local, infer_categories

EXPLORE_URL = "https://partiful.com/explore/nyc"
DISCOVER_URL = "https://partiful.com/discover"  # NYC-filtered fallback

# Individual partiful.com/e/<id> event URLs harvested from IG bios/captions +
# substack posts (e.g. Open Book Club's karaoke night) land in
# discovered_urls.json but partiful's explore/discover pages never list them,
# and the generic scraper can't parse partiful's __NEXT_DATA__. Resolve them
# here via the same _parse_event_obj path so a followed curator's actual dated
# event surfaces (fixes openbookclub — its Substack RSVP links to a Partiful).
_DISCOVERED_URLS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "discovered_urls.json"
)
_MAX_DISCOVERED = 60  # bound the per-run individual-page fetches

# Timezones we treat as NYC-area. Partiful tags each event with an IANA tz;
# everything on /explore/nyc should be America/New_York, but guard anyway so a
# cross-listed LA/SF event can never slip into the feed.
_NYC_TZS = {"America/New_York", ""}
_DISCOVER_API = "https://api.partiful.com"
_DISCOVER_TAGS = (
    "DISCOVER_HOME", "MUSIC", "COMMUNITY", "ARTS", "FITNESS", "FOOD",
    "NYC_BROOKLYN", "NYC_MANHATTAN",
)

_HEADER_VARIANTS = [
    {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
    },
    {"Referer": "https://www.google.com/", "Accept": "text/html,*/*;q=0.8"},
]


async def scrape() -> list[dict]:
    events: list[dict] = []
    seen: set[str] = set()

    explore = await _scrape_explore()
    _merge(events, seen, explore)

    # The server-rendered page contains only ~63 of the 147 events Partiful
    # reports for NYC. Full sweeps union the same public, bounded category and
    # borough feeds used by the Explore UI (currently ~111 unique events).
    # Quick runs retain the HTML path to stay comfortably inside CI budgets.
    if not os.environ.get("IG_SAVED_ONLY", "0") == "1":
        api_events = await _scrape_discover_api()
        before = len(events)
        _merge(events, seen, api_events)
        print(f"[partiful] +{len(events) - before} events from Discover API union")

    # Fallback only if the explore page yielded nothing (shape drift / block).
    if not events:
        print("[partiful] explore/nyc yielded 0 — falling back to /discover (NYC only)")
        _merge(events, seen, await _scrape_discover_nyc())

    # Resolve individual /e/<id> URLs harvested from bios/captions/substacks.
    disc = await _scrape_discovered_events(seen)
    _merge(events, seen, disc)
    if disc:
        print(f"[partiful] +{len(disc)} events from harvested /e/ URLs")

    detail_limit = 0 if os.environ.get("IG_SAVED_ONLY", "0") == "1" else 100
    events = await _hydrate_public_details(events, limit=detail_limit)
    print(f"[partiful] {len(events)} NYC events")
    return events


def _discovered_partiful_urls() -> list[str]:
    try:
        with open(_DISCOVERED_URLS_PATH) as f:
            d = json.load(f)
        items = d if isinstance(d, list) else d.get("urls", [])
        # New links are far more likely to point at future events. The old
        # first-N behavior permanently favored May links over fresh saves.
        items = sorted(
            items,
            key=lambda it: (it.get("discovered_at", "") if isinstance(it, dict) else ""),
            reverse=True,
        )
        urls = [(it["url"] if isinstance(it, dict) else it) for it in items]
        return [u for u in urls if "partiful.com/e/" in u]
    except Exception:
        return []


async def _scrape_discovered_events(seen: set[str]) -> list[dict]:
    """Fetch each harvested partiful.com/e/<id> page and parse its event via
    the same __NEXT_DATA__ path used for explore. Reuses _parse_event_obj so
    NYC-gating, tz conversion, and categorization stay consistent."""
    out: list[dict] = []
    max_discovered = 5 if os.environ.get("IG_SAVED_ONLY", "0") == "1" else _MAX_DISCOVERED
    urls = [u for u in _discovered_partiful_urls() if u not in seen][:max_discovered]
    for url in urls:
        html = await _fetch(url)
        if not html:
            continue
        data = _next_data(html)
        if not data:
            continue
        pp = data.get("props", {}).get("pageProps", {}) or {}
        ev = pp.get("event")
        if not isinstance(ev, dict):
            continue
        try:
            built = _parse_event_obj(ev, pp.get("hosts") or [])
        except Exception:  # noqa: BLE001
            continue
        if built and built != "non-nyc":
            out.append(built)
    return out


async def _hydrate_public_details(events: list[dict], limit: int = 100) -> list[dict]:
    """Hydrate public event pages for host identity and complete venue data."""
    sem = asyncio.Semaphore(5)

    async def one(existing: dict) -> dict:
        if existing.get("organizer"):
            return existing
        url = existing.get("sourceUrl") or ""
        if "/e/" not in url:
            return existing
        async with sem:
            html = await _fetch(url)
        data = _next_data(html) if html else None
        pp = (data or {}).get("props", {}).get("pageProps", {}) or {}
        raw = pp.get("event")
        if not isinstance(raw, dict):
            return existing
        try:
            hydrated = _parse_event_obj(raw, pp.get("hosts") or [])
            return hydrated if isinstance(hydrated, dict) else existing
        except Exception:
            return existing

    head = events[:limit]
    hydrated = await asyncio.gather(*(one(e) for e in head))
    return hydrated + events[limit:]


def _merge(events: list[dict], seen: set[str], new: list[dict]) -> None:
    for ev in new:
        key = ev.get("sourceUrl") or ev.get("title")
        if key in seen:
            continue
        seen.add(key)
        events.append(ev)


async def _fetch(url: str) -> str | None:
    """Fetch with header-variant retry. Returns None on total failure."""
    last = None
    for headers in _HEADER_VARIANTS:
        try:
            return await fetch_text(url, headers=headers)
        except Exception as e:  # noqa: BLE001
            last = e
            continue
    print(f"[partiful] fetch failed for {url}: {last}")
    return None


def _next_data(html: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")
    if not script or not script.string:
        return None
    try:
        return json.loads(script.string)
    except json.JSONDecodeError:
        return None


async def _scrape_explore() -> list[dict]:
    html = await _fetch(EXPLORE_URL)
    if not html:
        return []
    data = _next_data(html)
    if not data:
        print("[partiful] explore/nyc: no __NEXT_DATA__")
        return []
    pp = data.get("props", {}).get("pageProps", {})

    # Collect every event object across the page's containers, deduped by id.
    raw_by_id: dict[str, dict] = {}

    def collect_items(items):
        if not isinstance(items, list):
            return
        for it in items:
            ev = it.get("event") if isinstance(it, dict) else None
            if isinstance(ev, dict) and ev.get("id"):
                raw_by_id.setdefault(ev["id"], ev)

    collect_items((pp.get("trendingSection") or {}).get("items"))
    for section in pp.get("sections", []) or []:
        if isinstance(section, dict):
            collect_items(section.get("items"))
    collect_items(pp.get("feedItems"))

    events = []
    skipped_nonnyc = 0
    for ev in raw_by_id.values():
        try:
            built = _parse_event_obj(ev)
        except Exception as e:  # noqa: BLE001
            print(f"[partiful] skip event {ev.get('id','?')}: {e}")
            continue
        if built == "non-nyc":
            skipped_nonnyc += 1
            continue
        if built:
            events.append(built)
    if skipped_nonnyc:
        print(f"[partiful] explore/nyc: skipped {skipped_nonnyc} non-NYC cross-listed events")
    return events


async def _discover_api_call(function: str, tag: str) -> list[dict]:
    params = {"region": "NYC", "tagId": tag}
    if function == "getDiscoverFeed":
        params["allowedFeedPresentationStyles"] = ["rows"]
    else:
        params.update({
            "allowedSectionPresentationStyles": [
                "carousel-small", "carousel-medium", "carousel-large", "rows"
            ],
            "locale": "en-US",
        })
    payload = {"data": {"params": params, "paging": {"maxResults": 100}}}
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            response = await client.post(
                f"{_DISCOVER_API}/{function}",
                json=payload,
                headers={"Origin": "https://partiful.com", "Referer": EXPLORE_URL},
            )
            response.raise_for_status()
            data = (response.json().get("result") or {}).get("data") or {}
    except Exception as exc:
        print(f"[partiful] {function}/{tag} failed: {exc}")
        return []

    containers = data.get("sections") or [data]
    raw: dict[str, dict] = {}
    for container in containers:
        for item in (container.get("items") or []) if isinstance(container, dict) else []:
            event = item.get("event") if isinstance(item, dict) else None
            if isinstance(event, dict) and event.get("id"):
                raw.setdefault(event["id"], event)
    return list(raw.values())


async def _scrape_discover_api() -> list[dict]:
    calls = [
        _discover_api_call(function, tag)
        for tag in _DISCOVER_TAGS
        for function in ("getDiscoverSections", "getDiscoverFeed")
    ]
    pages = await asyncio.gather(*calls)
    raw_by_id: dict[str, dict] = {}
    for page in pages:
        for event in page:
            raw_by_id.setdefault(event["id"], event)

    events = []
    skipped_nonnyc = 0
    for raw in raw_by_id.values():
        try:
            built = _parse_event_obj(raw)
        except Exception as exc:
            print(f"[partiful] API skip event {raw.get('id', '?')}: {exc}")
            continue
        if built == "non-nyc":
            skipped_nonnyc += 1
        elif built:
            events.append(built)
    print(
        f"[partiful] Discover API: {len(raw_by_id)} unique, "
        f"{len(events)} NYC ({skipped_nonnyc} explicit non-NYC skipped)"
    )
    return events


async def _scrape_discover_nyc() -> list[dict]:
    """Fallback: the legacy /discover page, NYC region only."""
    html = await _fetch(DISCOVER_URL)
    if not html:
        return []
    data = _next_data(html)
    if not data:
        return []
    trending = data.get("props", {}).get("pageProps", {}).get("trendingSections", {})
    events = []
    if isinstance(trending, dict):
        nyc = trending.get("NYC") or {}
        for item in (nyc.get("items", []) if isinstance(nyc, dict) else []):
            ev = item.get("event") if isinstance(item, dict) else None
            if not isinstance(ev, dict):
                continue
            try:
                built = _parse_event_obj(ev)
            except Exception:  # noqa: BLE001
                continue
            if built and built != "non-nyc":
                events.append(built)
    return events


def _parse_event_obj(event: dict, hosts: list[dict] | None = None):
    """Build an event dict from a Partiful event object. Returns the event
    dict, the sentinel "non-nyc" to signal a cross-listed non-NYC event, or
    None when it isn't usable."""
    event_id = event.get("id", "")
    title = (event.get("title") or "").strip()
    start_raw = event.get("startDate", "") or ""
    if not title or not start_raw:
        return None

    # NYC gate: drop events explicitly tagged to another metro.
    tz = event.get("timezone", "") or ""
    if tz and tz not in _NYC_TZS:
        return "non-nyc"

    # UTC → America/New_York (naive slicing mis-dates evening events).
    date_str, start_time = parse_iso_to_local(start_raw)
    event_date = parse_date(date_str) if date_str else None
    if not event_date:
        return None
    _, end_time = parse_iso_to_local(event.get("endDate", "") or "")

    # Image: legacy coverPhotoUrl (str) OR image dict {url} / {upload:{url}}.
    cover = event.get("coverPhotoUrl") or ""
    if not cover:
        img = event.get("image") or {}
        if isinstance(img, dict):
            cover = img.get("url") or (img.get("upload") or {}).get("url") or ""

    # Location.
    loc_info = event.get("locationInfo", {})
    maps = loc_info.get("mapsInfo", {}) if isinstance(loc_info, dict) else {}
    loc_name = maps.get("name", "") if isinstance(maps, dict) else ""
    lines = []
    if isinstance(maps, dict):
        lines = maps.get("addressLines") or maps.get("displayAddressLines") or []
    if not lines and isinstance(loc_info, dict):
        lines = loc_info.get("displayAddressLines") or []
    address = ", ".join(lines) if isinstance(lines, list) else ""
    approximate = maps.get("approximateLocation", "") if isinstance(maps, dict) else ""
    location_blob = f"{address} {approximate}".lower()
    # America/New_York includes NJ/CT and is not by itself an NYC guarantee.
    # Keep hidden/approximate locations, but reject clearly out-of-city states
    # and common nearby cities when Partiful cross-lists them into NYC.
    if re.search(r"\b(?:nj|new jersey|ct|connecticut|pa|pennsylvania)\b", location_blob):
        return "non-nyc"
    if re.search(r"\b(?:edison|hoboken|jersey city|newark|yonkers|white plains)\b", location_blob):
        return "non-nyc"

    # Guest counts → description enrichment.
    description = event.get("description", "") or ""
    going = event.get("goingGuestCount", 0) or 0
    interested = event.get("interestedGuestCount", 0) or 0
    parts = []
    if going:
        parts.append(f"{going} going")
    if interested:
        parts.append(f"{interested} interested")
    guest = f" ({', '.join(parts)})" if parts else ""
    full_desc = (description[:450] + guest) if description else guest.strip()

    source_url = f"https://partiful.com/e/{event_id}" if event_id else EXPLORE_URL

    hosts = [h for h in (hosts or []) if isinstance(h, dict)]
    primary_host = next((h for h in hosts if h.get("isManaged")), hosts[0] if hosts else {})
    organizer = (primary_host.get("name") or "").strip()
    instagram = (((primary_host.get("socials") or {}).get("instagram") or {}).get("value") or "").strip()
    organizer_url = f"https://www.instagram.com/{instagram}/" if instagram else None
    organizer_refs = []
    host_by_id = {
        str(h.get("id") or h.get("userId") or h.get("api_id")): h
        for h in hosts
        if h.get("id") or h.get("userId") or h.get("api_id")
    }
    owner_ids = [str(owner_id) for owner_id in (event.get("ownerIds") or []) if owner_id]
    for index, owner_id in enumerate(owner_ids):
        host = host_by_id.get(owner_id, {})
        handle = (((host.get("socials") or {}).get("instagram") or {}).get("value") or "").strip()
        organizer_refs.append({
            "platform": "partiful",
            "externalId": owner_id,
            "name": (host.get("name") or "").strip(),
            "url": f"https://www.instagram.com/{handle}/" if handle else "",
            "handle": handle,
            "role": "host" if index == 0 else "cohost",
        })

    return build_event(
        title=title,
        description=full_desc,
        event_date=event_date,
        start_time=start_time,
        end_time=end_time,
        location_name=loc_name,
        address=address,
        source="partiful",
        source_url=source_url,
        image_url=cover or None,
        categories=infer_categories(title, description),
        organizer=organizer or None,
        organizer_url=organizer_url,
        organizer_refs=organizer_refs,
    )
