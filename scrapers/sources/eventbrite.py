import json
import re
import asyncio
import os
from bs4 import BeautifulSoup
from ..utils.http import fetch_text
from ..utils.event_parser import build_event, parse_date, parse_time, parse_iso_to_local, parse_offers_price
from ..utils.platform_discovery import FrontierItem, platform_frontier, ranked_topics


# Platform vocabulary, not a source list. Coverage is generated from the
# shared interest taxonomy and always includes a floor for categories that a
# narrow historical profile could otherwise hide forever.
_TOPIC_SEARCH_SLUG = {
    "fitness": "sports-and-fitness",
    "music": "music",
    "books": "books",
    "wellness": "health-and-wellness",
    "movies": "film-and-media",
    "art": "performing-and-visual-arts",
    "food": "food-and-drink",
    "comedy": "comedy",
    "games": "hobbies",
    "outdoors": "outdoor",
    "social": "community",
    "dance": "dance",
}
_SEARCH_LOCATIONS = ("new-york", "brooklyn", "queens")


def _eventbrite_organizer_id(url: str) -> str:
    """Return an organizer id from numeric or slugged Eventbrite URLs."""
    match = re.search(r"/o/(?:[^/?#]*-)?(\d+)(?:[/?#]|$)", url or "", re.I)
    return match.group(1) if match else ""


def _build_interest_topic_urls() -> list[str]:
    """Compatibility helper: return the generated topic frontier URLs."""
    return [url for url, _lane in _generated_search_candidates()]


def _generated_search_candidates() -> list[tuple[str, str]]:
    """Generate category searches with breadth before pagination/geography.

    Every canonical category gets a city-wide page before a second borough
    page is scheduled. This specifically prevents the old `[:12]` truncation
    from spending the entire budget on the first six interests.
    """
    topics = ranked_topics()
    candidates: list[tuple[str, str]] = []
    primary: list[tuple[str, str]] = []
    for topic, _score, lane in topics:
        slug = _TOPIC_SEARCH_SLUG.get(topic)
        if not slug:
            continue
        primary.append((
            f"https://www.eventbrite.com/d/ny--new-york/{slug}--events/",
            lane,
        ))
    candidates.extend(primary)
    # Page two is usually 20 new events and costs less overlap than repeating
    # the city-wide query for a borough. It is therefore the first depth lane.
    candidates.extend((f"{url}?page=2", lane) for url, lane in primary if lane == "personal")
    # If a future/full budget grows, continue into borough-specific discovery.
    for location in _SEARCH_LOCATIONS[1:]:
        for topic, _score, lane in topics:
            if lane != "personal":
                continue
            slug = _TOPIC_SEARCH_SLUG.get(topic)
            if slug:
                candidates.append((
                    f"https://www.eventbrite.com/d/ny--{location}/{slug}--events/",
                    lane,
                ))
    return candidates


def _search_plan() -> list[tuple[str, str]]:
    """Bounded, generated search frontier with category coverage."""
    quick = os.environ.get("IG_SAVED_ONLY", "0") == "1"
    total_limit = 8 if quick else 24
    candidates = _generated_search_candidates()
    if quick:
        candidates = [item for item in candidates if item[1] == "personal"] or candidates
    return candidates[:total_limit]


async def _fetch_with_backoff(url: str, attempts: int = 3) -> str:
    last = None
    for attempt in range(attempts):
        try:
            return await fetch_text(url)
        except Exception as exc:  # Eventbrite exposes 429 through httpx text
            last = exc
            msg = str(exc).lower()
            if "429" not in msg and "too many requests" not in msg:
                raise
            if attempt < attempts - 1:
                await asyncio.sleep(1.0 * (2**attempt))
    raise last  # type: ignore[misc]


async def scrape() -> list[dict]:
    events: list[dict] = []
    quick = os.environ.get("IG_SAVED_ONLY", "0") == "1"

    # Protect learned organizers from broad-search rate limiting. The frontier
    # is rebuilt from harvested links, curated hosts, and prior event yield;
    # no organizer needs to be added to source code.
    organizer_limit = 8 if quick else 20
    known_organizers = platform_frontier(
        "eventbrite", kinds={"organizer"}, limit=organizer_limit
    )
    fetched_organizers: set[str] = set()
    if known_organizers:
        print(f"[eventbrite] learned organizer frontier: {len(known_organizers)}")
    for item in known_organizers:
        try:
            html = await _fetch_with_backoff(item.url)
            parsed = _parse_organizer_page(html, item.url)
            for event in parsed:
                event["discoveryLane"] = item.lane
            events.extend(parsed)
            fetched_organizers.add(item.url)
            print(f"[eventbrite-organizer] {item.url}: {len(parsed)} events")
        except Exception as exc:
            print(f"[eventbrite-organizer] Failed {item.url}: {exc}")

    # Canonical event links harvested from followed accounts/newsletters are
    # higher-signal than anonymous search results and often never rank on a
    # broad Eventbrite page.
    direct_limit = 5 if quick else 14
    direct_items = platform_frontier("eventbrite", kinds={"event"}, limit=direct_limit)
    for item in direct_items:
        try:
            html = await _fetch_with_backoff(item.url, attempts=2)
            parsed = _parse_search_page(html, item.url)
            for event in parsed:
                event["discoveryLane"] = item.lane
            events.extend(parsed)
        except Exception as exc:
            print(f"[eventbrite-direct] Failed {item.url}: {exc}")

    # Generated category × geography coverage comes after high-signal lanes.
    plan = _search_plan()
    print(f"[eventbrite] bounded search plan: {len(plan)} pages")
    consecutive_rate_limits = 0
    for url, lane in plan:
        try:
            html = await _fetch_with_backoff(url)
            consecutive_rate_limits = 0
            parsed = _parse_search_page(html, url)
            for event in parsed:
                event["discoveryLane"] = lane
            events.extend(parsed)
            await asyncio.sleep(0.25)
        except Exception as e:
            print(f"[eventbrite] Failed {url}: {e}")
            if "429" in str(e) or "too many requests" in str(e).lower():
                consecutive_rate_limits += 1
                if consecutive_rate_limits >= 2:
                    print("[eventbrite] search circuit open after repeated 429s; preserving organizer lane/carryover")
                    break
    detail_limit = 0 if quick else 18
    events = await _hydrate_shortlist(events, limit=detail_limit)

    # Search/detail results teach the engine new organizers immediately. A
    # small frequency- and preference-ranked promotion lane turns a single
    # matching event into the organizer's complete upcoming calendar.
    promoted = _promoted_organizers(events, fetched_organizers, limit=4 if quick else 8)
    for item in promoted:
        try:
            html = await _fetch_with_backoff(item.url)
            org_events = _parse_organizer_page(html, item.url)
            for event in org_events:
                event["discoveryLane"] = item.lane
            events.extend(org_events)
            print(f"[eventbrite-organizer:new] {item.url}: {len(org_events)} events")
        except Exception as e:
            print(f"[eventbrite-organizer:new] Failed {item.url}: {e}")
    return events


def _promoted_organizers(
    events: list[dict],
    excluded: set[str] | None = None,
    *,
    limit: int = 10,
) -> list[FrontierItem]:
    """Promote useful organizers found in this run into calendar fetches."""
    excluded = excluded or set()
    by_url: dict[str, dict] = {}
    for event in events:
        raw_url = event.get("organizerUrl") or ""
        organizer_id = _eventbrite_organizer_id(raw_url)
        if not organizer_id:
            continue
        url = f"https://eventbrite.com/o/{organizer_id}"
        if url in excluded or url.replace("https://", "https://www.") in excluded:
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
            kind="organizer",
            lane="personal" if rec["personal"] else "explore",
            score=rec["score"],
            via="current_search_results",
        )
        for url, rec in ranked[:limit]
    ]


async def _hydrate_shortlist(events: list[dict], limit: int = 40) -> list[dict]:
    """Hydrate unique personal candidates missing organizer/detail fields."""
    if limit <= 0:
        return events
    targets: list[str] = []
    for event in events:
        url = event.get("sourceUrl") or ""
        if event.get("discoveryLane") != "personal" or "/e/" not in url:
            continue
        if url not in targets and not event.get("organizer"):
            targets.append(url)
        if len(targets) >= limit:
            break
    sem = asyncio.Semaphore(2)

    async def hydrate(url: str):
        async with sem:
            try:
                html = await _fetch_with_backoff(url, attempts=2)
                parsed = _parse_search_page(html, url)
                return parsed[0] if parsed else None
            except Exception:
                return None

    details = await asyncio.gather(*(hydrate(url) for url in targets)) if targets else []
    by_url = {url: event for url, event in zip(targets, details) if event}
    if by_url:
        print(f"[eventbrite] hydrated {len(by_url)}/{len(targets)} personalized event pages")
    out = []
    for event in events:
        detail = by_url.get(event.get("sourceUrl"))
        if detail:
            detail["discoveryLane"] = event.get("discoveryLane", "personal")
            out.append(detail)
        else:
            out.append(event)
    return out


def _parse_organizer_page(html: str, source_url: str) -> list[dict]:
    """Parse an Eventbrite organizer page across old/new hydration shapes."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    data = None
    if m:
        try:
            data = json.loads(m.group(1))
        except Exception:
            data = None

    upcoming: list[dict] = []
    organizer_name = ""

    def walk(node, parent_key: str = "", depth: int = 0) -> None:
        nonlocal organizer_name
        if depth > 14:
            return
        if isinstance(node, list):
            for child in node:
                walk(child, parent_key, depth + 1)
            return
        if not isinstance(node, dict):
            return
        if parent_key.lower().startswith("organizer") and not organizer_name:
            name = node.get("name")
            if isinstance(name, str):
                organizer_name = name
        title = node.get("name")
        if isinstance(title, dict):
            title = title.get("text")
        has_start = any(node.get(key) for key in ("start_date", "startDate", "start_time"))
        has_event_identity = node.get("url") or node.get("id") or node.get("event_id")
        if isinstance(title, str) and title.strip() and has_start and has_event_identity:
            upcoming.append(node)
            return
        for key, child in node.items():
            walk(child, str(key), depth + 1)

    if data:
        walk(data)

    # Some organizer pages now include JSON-LD even when their private Next.js
    # object changes. Keep that standards-based path as a durable fallback.
    if not upcoming:
        fallback = _parse_search_page(html, source_url)
        for event in fallback:
            event["organizerUrl"] = source_url
            organizer_id = _eventbrite_organizer_id(source_url) or source_url
            if not event.get("organizerRefs"):
                event["organizerRefs"] = [{
                    "platform": "eventbrite",
                    "externalId": organizer_id,
                    "name": event.get("organizer") or "",
                    "url": source_url,
                    "role": "host",
                }]
        return fallback

    events: list[dict] = []
    seen: set[str] = set()
    for raw in upcoming:
        if not isinstance(raw, dict):
            continue
        title = raw.get("name") or ""
        if isinstance(title, dict):
            title = title.get("text") or ""
        if not title:
            continue
        start_obj = raw.get("start") or {}
        date_str = raw.get("start_date") or raw.get("startDate") or (
            start_obj.get("utc") if isinstance(start_obj, dict) else ""
        ) or ""
        local_date, iso_time = parse_iso_to_local(date_str)
        event_date = parse_date(local_date or date_str)
        if not event_date:
            continue
        start_time = (raw.get("start_time") or "")[:5] or iso_time or None
        end_raw = raw.get("end_date") or raw.get("endDate") or ""
        _end_date, iso_end_time = parse_iso_to_local(end_raw)
        end_time = (raw.get("end_time") or "")[:5] or iso_end_time or None
        url = raw.get("url") or source_url
        if url in seen:
            continue
        seen.add(url)
        image_obj = raw.get("image") or {}
        image = image_obj.get("url") if isinstance(image_obj, dict) else image_obj or None
        venue = raw.get("primary_venue") or raw.get("venue") or {}
        venue_name = venue.get("name") or ""
        addr_obj = venue.get("address") or {}
        venue_addr = (
            addr_obj.get("localized_address_display")
            or addr_obj.get("localized_area_display")
            or addr_obj.get("address_1")
            or ""
        ) if isinstance(addr_obj, dict) else str(addr_obj or "")
        is_free = ((raw.get("ticket_availability") or {}).get("is_free"))
        price = "free" if is_free else None
        summary = raw.get("summary") or raw.get("description") or ""
        if isinstance(summary, dict):
            summary = summary.get("text") or ""
        raw_organizer = raw.get("organizer") or {}
        raw_organizer_name = raw_organizer.get("name") if isinstance(raw_organizer, dict) else ""
        organizer_id = _eventbrite_organizer_id(source_url) or source_url
        ev = build_event(
            title=title,
            description=summary[:500],
            event_date=event_date,
            start_time=start_time,
            end_time=end_time,
            location_name=venue_name,
            address=venue_addr,
            source="eventbrite",
            source_url=url,
            image_url=image,
            price=price,
            organizer=raw_organizer_name or organizer_name or None,
            organizer_url=source_url,
            organizer_refs=[{
                "platform": "eventbrite",
                "externalId": organizer_id,
                "name": raw_organizer_name or organizer_name or "",
                "url": source_url,
                "role": "host",
            }],
        )
        # Stamp the organizer-page URL so downstream filters can match
        # it against user_curated_sources.json (the per-event sourceUrl
        # is the specific /e/<slug> URL which doesn't contain the
        # organizer ID).
        ev["organizerUrl"] = source_url
        events.append(ev)
    return events


def _parse_search_page(html: str, source_url: str) -> list[dict]:
    events = []
    soup = BeautifulSoup(html, "lxml")

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            events.extend(_walk_jsonld(data))
        except (json.JSONDecodeError, Exception):
            continue

    if not events:
        for card in soup.select("[class*='event-card'], [class*='SearchResultCard'], article"):
            title_el = card.select_one("h2, h3, [class*='title']")
            date_el = card.select_one("p[class*='date'], [class*='date'], time")
            link_el = card.select_one("a[href*='eventbrite.com/e/']")

            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            date_text = date_el.get_text(strip=True) if date_el else ""
            link = link_el.get("href", "") if link_el else source_url

            event_date = parse_date(date_text)
            if not event_date:
                continue

            price_el = card.select_one("[class*='price'], [class*='Price']")
            price = price_el.get_text(strip=True) if price_el else "unknown"
            if "free" in price.lower():
                price = "free"

            loc_el = card.select_one("[class*='location'], [class*='venue']")
            loc_name = loc_el.get_text(strip=True) if loc_el else ""

            events.append(build_event(
                title=title,
                description="",
                event_date=event_date,
                start_time=parse_time(date_text),
                location_name=loc_name,
                source="eventbrite",
                source_url=link,
                price=price,
            ))

    return events


_EVENT_TYPES = {
    "Event", "MusicEvent", "TheaterEvent", "DanceEvent", "ComedyEvent",
    "FoodEvent", "SportsEvent", "BusinessEvent", "EducationEvent",
    "ExhibitionEvent", "FestivalEvent", "LiteraryEvent", "ScreeningEvent",
    "SocialEvent", "ChildrensEvent",
}


def _walk_jsonld(data) -> list[dict]:
    """Recursively walk JSON-LD looking for Event objects.

    Handles: direct Event, list, ItemList.itemListElement, @graph arrays,
    Organization with nested events, etc.
    """
    found = []
    if isinstance(data, list):
        for item in data:
            found.extend(_walk_jsonld(item))
        return found
    if not isinstance(data, dict):
        return found

    t = data.get("@type", "")
    if isinstance(t, list):
        types = set(t)
    else:
        types = {t}

    if types & _EVENT_TYPES:
        ev = _parse_ld_event(data)
        if ev:
            found.append(ev)
        return found

    if "ItemList" in types:
        for el in data.get("itemListElement", []) or []:
            if isinstance(el, dict):
                # ListItem wrapper
                inner = el.get("item", el)
                found.extend(_walk_jsonld(inner))
        return found

    if "@graph" in data:
        found.extend(_walk_jsonld(data["@graph"]))

    if "Organization" in types or "LocalBusiness" in types:
        for key in ("event", "events"):
            nested = data.get(key)
            if nested:
                found.extend(_walk_jsonld(nested))

    return found


def _parse_ld_event(data: dict) -> dict | None:
    title = data.get("name", "")
    desc = data.get("description", "")
    start = data.get("startDate", "")
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

    date_str, start_time = parse_iso_to_local(start)
    event_date = parse_date(date_str) if date_str else None
    if not event_date:
        return None
    url = data.get("url", "")

    organizer = data.get("organizer") or {}
    if isinstance(organizer, list):
        organizer = organizer[0] if organizer else {}
    organizer_name = organizer.get("name", "") if isinstance(organizer, dict) else ""
    organizer_url = organizer.get("url", "") if isinstance(organizer, dict) else ""

    price = parse_offers_price(data.get("offers"))

    image = data.get("image", "")
    if isinstance(image, list) and image:
        image = image[0]

    return build_event(
        title=title,
        description=desc[:500],
        event_date=event_date,
        start_time=start_time,
        location_name=loc_name,
        address=loc_addr,
        source="eventbrite",
        source_url=url,
        image_url=image if image else None,
        price=price,
        organizer=organizer_name or None,
        organizer_url=organizer_url or None,
        organizer_refs=[{
            "platform": "eventbrite",
            "externalId": _eventbrite_organizer_id(organizer_url) or organizer_url,
            "name": organizer_name,
            "url": organizer_url,
            "role": "host",
        }] if organizer_name or organizer_url else None,
    )
