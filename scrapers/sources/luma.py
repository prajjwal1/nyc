import json
import os
import re
from bs4 import BeautifulSoup
from ..utils.http import fetch_text
from ..utils.event_parser import build_event, parse_date, parse_time, parse_iso_to_local
from ..utils.platform_discovery import FrontierItem, platform_frontier, rotating_luma_probes

LUMA_DISCOVER_URL = "https://lu.ma/nyc"
# Compatibility for maintenance/tests. Runtime coverage comes from
# _calendar_plan(), not from appending URLs to this constant.
LUMA_PAGES = [LUMA_DISCOVER_URL]


def _calendar_plan() -> list[FrontierItem]:
    """Return learned calendars, harvested events, and rotating probes."""
    quick = os.environ.get("IG_SAVED_ONLY", "0") == "1"
    learned_calendars = platform_frontier(
        "luma", kinds={"calendar"}, limit=5 if quick else 14
    )
    direct_events = platform_frontier(
        "luma", kinds={"event"}, limit=4 if quick else 16
    )
    probes = [] if quick else rotating_luma_probes(limit=4)
    items = [
        FrontierItem(
            url=LUMA_DISCOVER_URL,
            kind="discover",
            lane="explore",
            score=1.0,
            via="city_discover",
        ),
        *learned_calendars,
        *direct_events,
        *probes,
    ]
    out: list[FrontierItem] = []
    seen: set[str] = set()
    for item in items:
        if item.url in seen:
            continue
        seen.add(item.url)
        out.append(item)
    return out


async def scrape() -> list[dict]:
    """Scrape a learned Luma frontier. Retries with browser-like headers."""
    import asyncio

    plan = _calendar_plan()
    print(
        f"[luma] dynamic frontier: {len(plan)} targets "
        f"({sum(item.kind == 'calendar' for item in plan)} calendars, "
        f"{sum(item.kind == 'event' for item in plan)} direct events)"
    )
    sem = asyncio.Semaphore(4)

    async def calendar(item: FrontierItem) -> tuple[FrontierItem, list[dict]]:
        async with sem:
            page_events = await _try_luma_url(item.url)
        for event in page_events:
            event["discoveryLane"] = item.lane
            if item.kind == "discover":
                event["_lumaNeedsHydration"] = True
        return item, page_events

    results = await asyncio.gather(*(calendar(item) for item in plan))
    events = [event for _item, page_events in results for event in page_events]

    # Organizer URLs exposed by the city listing are new calendar candidates.
    # Fetch a bounded set immediately instead of waiting for a code/config edit.
    planned = {item.url.rstrip("/") for item in plan}
    promoted = _promoted_calendars(events, planned, limit=8 if not os.environ.get("IG_SAVED_ONLY") == "1" else 2)
    if promoted:
        promoted_results = await asyncio.gather(*(calendar(item) for item in promoted))
        events.extend(event for _item, page_events in promoted_results for event in page_events)
        print(f"[luma] promoted {len(promoted)} organizers from current results")

    # The discover listing intentionally omits descriptions. Hydrate its
    # canonical event URLs before normalization; otherwise the description
    # shell filter discards the entire broad Luma discovery lane.
    quick = os.environ.get("IG_SAVED_ONLY", "0") == "1"
    canonical = {}
    for event in events:
        url = event.get("sourceUrl") or ""
        if not quick and event.get("_lumaNeedsHydration") and re.match(
            r"https?://(?:lu\.ma|luma\.com)/[a-z0-9-]{6,}/?$", url, re.I
        ):
            canonical[url] = event
    sem = asyncio.Semaphore(4)

    async def hydrate(url: str) -> dict:
        async with sem:
            detailed = await _try_luma_url(url)
        if detailed:
            return detailed[0]
        return canonical[url]

    hydrated = await asyncio.gather(*(hydrate(url) for url in canonical)) if canonical else []
    by_url = {e.get("sourceUrl"): e for e in hydrated}
    out = [by_url.get(e.get("sourceUrl"), e) for e in events]
    for event in out:
        event.pop("_lumaNeedsHydration", None)
    return out


def _promoted_calendars(
    events: list[dict],
    excluded: set[str],
    *,
    limit: int = 8,
) -> list[FrontierItem]:
    by_url: dict[str, dict] = {}
    for event in events:
        raw = (event.get("organizerUrl") or "").strip().rstrip("/")
        match = re.match(r"https?://(?:www\.)?(?:lu\.ma|luma\.com)/([a-z0-9._-]+)$", raw, re.I)
        if not match:
            continue
        url = f"https://lu.ma/{match.group(1)}"
        if url in excluded or match.group(1).lower() == "nyc":
            continue
        rec = by_url.setdefault(url, {"score": 0.0, "personal": False})
        rec["score"] += 1.0
        if event.get("discoveryLane") == "personal" or any(
            event.get(flag) for flag in ("userSaved", "userFollowing", "userAffinity")
        ):
            rec["score"] += 3.0
            rec["personal"] = True
    ranked = sorted(by_url.items(), key=lambda row: (-row[1]["score"], row[0]))
    return [
        FrontierItem(
            url=url,
            kind="calendar",
            lane="personal" if rec["personal"] else "explore",
            score=rec["score"],
            via="current_discover_results",
        )
        for url, rec in ranked[:limit]
    ]


async def _try_luma_url(url: str) -> list[dict]:
    """Try to fetch a Luma page with multiple header strategies."""
    import asyncio

    header_variants = [
        # Default (Mozilla baseline)
        None,
        # Browser-like with referer
        {
            "Referer": "https://www.google.com/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
        # luma.com instead of lu.ma (alternate domain)
    ]
    # Retry with luma.com if lu.ma 403s
    if "lu.ma/" in url:
        alt_url = url.replace("lu.ma/", "luma.com/")
    else:
        alt_url = None

    for headers in header_variants:
        try:
            html = (await fetch_text(url, headers=headers)) if headers else (await fetch_text(url))
            events = _parse_luma_page(html, url)
            return events
        except Exception as e:
            err_msg = str(e)
            if "403" in err_msg or "Forbidden" in err_msg:
                await asyncio.sleep(0.5)
                continue
            # Other errors (404, etc.) — try alt URL too
            break

    # Last resort: try alt domain
    if alt_url:
        try:
            html = await fetch_text(alt_url)
            return _parse_luma_page(html, url)
        except Exception as e:
            print(f"[luma] {url} (and {alt_url}): {e}")
            return []

    return []


def _parse_luma_page(html: str, source_url: str) -> list[dict]:
    events = []
    soup = BeautifulSoup(html, "lxml")

    script_tags = soup.find_all("script", type="application/ld+json")
    for script in script_tags:
        try:
            data = json.loads(script.string)
            if isinstance(data, list):
                for item in data:
                    result = _parse_ld_json(item, source_url)
                    if isinstance(result, list):
                        events.extend(result)
                    elif result:
                        events.append(result)
            elif isinstance(data, dict):
                result = _parse_ld_json(data, source_url)
                if isinstance(result, list):
                    events.extend(result)
                elif result:
                    events.append(result)
        except (json.JSONDecodeError, Exception):
            continue

    # Curator calendars (lu.ma/<handle>) are SPAs that embed their event
    # roster in <script id="__NEXT_DATA__"> rather than ld+json — so the
    # ld+json loop above silently yields 0 for them (e.g. nycbackgammonclub
    # had 6 live events but extracted none). Source-agnostic NEXT_DATA path.
    if not events:
        m = re.search(
            r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S
        )
        if m:
            try:
                data = json.loads(m.group(1))
            except Exception:
                data = None
            if data:
                events.extend(_parse_luma_next_data(data, source_url))

    if not events:
        events.extend(_parse_luma_html(soup, source_url))

    return events


_NYC_CITIES = {"new york", "brooklyn", "queens", "bronx", "staten island",
               "long island city", "williamsburg", "astoria"}


def _is_nyc_address(geo: dict) -> bool:
    """Broad NYC gate (not strict city=='New York' — keeps Brooklyn-labeled
    events). Rejects events with no parseable NYC address so a curator's
    out-of-town events aren't pulled in."""
    if not isinstance(geo, dict):
        return False
    city = (geo.get("city") or "").strip().lower()
    if city in _NYC_CITIES:
        return True
    blob = " ".join(str(geo.get(k) or "") for k in
                    ("full_address", "address", "region", "city_state")).lower()
    if "new york" in blob:
        return True
    # ", NY" with a NY-zip / state token (avoid matching "NYE party" etc.)
    if re.search(r",\s*ny\b", blob):
        return True
    return False


def _parse_luma_next_data(data, source_url: str) -> list[dict]:
    """Walk a lu.ma __NEXT_DATA__ blob for event dicts (name + start_at) and
    build NYC events. Defensive: never throws, requires name + parseable
    start, dedupes by api_id, gates on a NYC address."""
    found = []
    seen_ids = set()

    def walk(node):
        if isinstance(node, dict):
            if isinstance(node.get("name"), str) and isinstance(node.get("start_at"), str):
                found.append(node)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    try:
        walk(data)
    except Exception:
        return []

    events = []
    for ev in found:
        try:
            api_id = ev.get("api_id") or ""
            if api_id and api_id in seen_ids:
                continue
            geo = ev.get("geo_address_info") or {}
            if not _is_nyc_address(geo):
                continue
            title = (ev.get("name") or "").strip()
            if not title:
                continue
            date_str, start_time = parse_iso_to_local(ev.get("start_at") or "")
            event_date = parse_date(date_str) if date_str else None
            if not event_date:
                continue
            _, end_time = parse_iso_to_local(ev.get("end_at") or "")
            loc_name = (geo.get("name") or "").strip()
            loc_addr = (geo.get("full_address") or geo.get("address") or "").strip()
            image = ev.get("cover_url") or None
            if api_id:
                seen_ids.add(api_id)
            desc = ev.get("description_mirror") or ev.get("description") or ""
            calendar_handle = source_url.rstrip("/").rsplit("/", 1)[-1]
            events.append(build_event(
                title=title,
                description=desc[:1000] if isinstance(desc, str) else "",
                event_date=event_date,
                start_time=start_time,
                end_time=end_time,
                location_name=loc_name,
                address=loc_addr,
                source="luma",
                # Keep the curator/page URL (not a per-event slug) so the
                # normalize.py curator-handle enrichment (lu.ma/<handle>)
                # can fire and tag userFollowing — the point of this path.
                source_url=source_url,
                image_url=image,
                organizer_refs=[{
                    "platform": "luma",
                    "externalId": calendar_handle,
                    "name": calendar_handle.replace("-", " ").replace(".", " ").strip().title(),
                    "url": source_url,
                    "role": "host",
                }] if calendar_handle != "nyc" else None,
            ))
        except Exception:
            continue
    return events


def _parse_ld_json(data: dict, source_url: str) -> dict | list | None:
    # Handle Organization schema with nested events array
    if data.get("@type") == "Organization":
        nested_events = data.get("events", data.get("event", []))
        if isinstance(nested_events, list):
            results = []
            for nested in nested_events:
                if isinstance(nested, dict):
                    ev = _parse_ld_json(nested, source_url)
                    if ev and isinstance(ev, dict):
                        results.append(ev)
            return results
        return None

    # Handle ItemList schema (Luma sometimes wraps events this way)
    if data.get("@type") == "ItemList":
        items = data.get("itemListElement", [])
        if isinstance(items, list):
            results = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                # ItemList items can be either bare Events or ListItem wrappers
                inner = item.get("item", item)
                if isinstance(inner, dict):
                    ev = _parse_ld_json(inner, source_url)
                    if ev and isinstance(ev, dict):
                        results.append(ev)
                    elif isinstance(ev, list):
                        results.extend(ev)
            return results
        return None

    # Accept Schema.org Event subtypes (MusicEvent, EducationEvent, etc.)
    # — same set as generic.py. Iter 84 audit: strict "Event"-only check
    # was identical to the bug Meetup had in iter 83.
    from .generic import EVENT_TYPES
    t = data.get("@type")
    if isinstance(t, str):
        if t not in EVENT_TYPES:
            return None
    elif isinstance(t, list):
        if not any(isinstance(x, str) and x in EVENT_TYPES for x in t):
            return None
    else:
        return None
    title = data.get("name", "")
    desc = data.get("description", "")
    start = data.get("startDate", "")
    end = data.get("endDate", "")
    location = data.get("location", {})
    loc_name = ""
    loc_addr = ""
    if isinstance(location, dict):
        loc_name = location.get("name", "")
        addr = location.get("address", {})
        if isinstance(addr, dict):
            loc_addr = addr.get("streetAddress", "")
        elif isinstance(addr, str):
            loc_addr = addr

    image = data.get("image", "")
    if isinstance(image, list) and image:
        image = image[0]

    date_str, start_time = parse_iso_to_local(start)
    _, end_time = parse_iso_to_local(end)
    event_date = parse_date(date_str) if date_str else None
    if not event_date:
        return None

    offers = data.get("offers", {})
    price = "free"
    if isinstance(offers, dict):
        p = offers.get("price", 0)
        if p and float(p) > 0:
            price = f"${p}"

    canonical_url = data.get("url") or data.get("@id") or source_url
    organizer = data.get("organizer") or {}
    if isinstance(organizer, list):
        organizer = organizer[0] if organizer else {}
    organizer_name = organizer.get("name", "") if isinstance(organizer, dict) else ""
    organizer_url = organizer.get("url", "") if isinstance(organizer, dict) else ""

    return build_event(
        title=title,
        description=desc,
        event_date=event_date,
        start_time=start_time,
        end_time=end_time,
        location_name=loc_name,
        address=loc_addr,
        source="luma",
        source_url=canonical_url,
        image_url=image if image else None,
        price=price,
        organizer=organizer_name or None,
        organizer_url=organizer_url or None,
        organizer_refs=[{
            "platform": "luma",
            "externalId": (organizer_url or canonical_url).rstrip("/").rsplit("/", 1)[-1],
            "name": organizer_name,
            "url": organizer_url or canonical_url,
            "role": "host",
        }] if organizer_name or organizer_url else None,
    )


def _parse_luma_html(soup: BeautifulSoup, source_url: str) -> list[dict]:
    events = []
    for card in soup.select("[class*='event-card'], [class*='EventCard'], .event-link, a[href*='/event/']"):
        title_el = card.select_one("h2, h3, [class*='title'], [class*='name']")
        date_el = card.select_one("[class*='date'], [class*='time'], time")
        if title_el:
            title = title_el.get_text(strip=True)
            date_text = date_el.get_text(strip=True) if date_el else ""
            event_date = parse_date(date_text)
            if event_date:
                events.append(build_event(
                    title=title,
                    description="",
                    event_date=event_date,
                    source="luma",
                    source_url=source_url,
                ))
    return events
