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

from bs4 import BeautifulSoup

from ..utils.http import fetch_text
from ..utils.event_parser import build_event, parse_date, parse_iso_to_local, infer_categories

EXPLORE_URL = "https://partiful.com/explore/nyc"
DISCOVER_URL = "https://partiful.com/discover"  # NYC-filtered fallback

# Timezones we treat as NYC-area. Partiful tags each event with an IANA tz;
# everything on /explore/nyc should be America/New_York, but guard anyway so a
# cross-listed LA/SF event can never slip into the feed.
_NYC_TZS = {"America/New_York", ""}

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

    # Fallback only if the explore page yielded nothing (shape drift / block).
    if not events:
        print("[partiful] explore/nyc yielded 0 — falling back to /discover (NYC only)")
        _merge(events, seen, await _scrape_discover_nyc())

    print(f"[partiful] {len(events)} NYC events")
    return events


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


def _parse_event_obj(event: dict):
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
    )
