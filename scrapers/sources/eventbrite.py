import json
import re
import asyncio
import os
from bs4 import BeautifulSoup
from ..utils.http import fetch_text
from ..utils.event_parser import build_event, parse_date, parse_time, parse_iso_to_local, parse_offers_price

# Specific organizer pages the user has flagged as high-priority.
# These list ALL of an organizer's events in one place — useful for
# brand-curated event series the user follows. Add to user_curated_sources
# .json simultaneously so events from these get the +0.15 boost.
# Seed organizer pages. NOTE: prefer NOT hardcoding organizers here — the
# canonical way to add a vetted organizer is to put its host in
# scrapers/data/user_curated_sources.json (the learned preference layer),
# which _curated_organizer_urls() reads at scrape time. That way vetting a
# source is a data/preference signal, not a code edit, and the same entry
# also drives the curation boost + score-floor bypass. This list is just a
# cold-start seed for anything not yet represented in the preference layer.
ORGANIZER_URLS = [
    # Lululemon — legacy seed (also in user_curated_sources).
    "https://www.eventbrite.com/o/14861961557",
]


def _curated_organizer_urls() -> list[str]:
    """Derive Eventbrite organizer scrape targets from the user's LEARNED
    preference layer (user_curated_sources.json), rather than hardcoding
    them. Any curated host shaped `eventbrite.com/o/<id>` becomes an
    organizer page we scrape — so when the user vets a top organizer, it is
    picked up automatically (and, being curated, its events get the boost +
    the lower score floor). Generalizes 'learn my preferences' to sources.
    """
    import os as _os

    path = _os.path.join(
        _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
        "data",
        "user_curated_sources.json",
    )
    urls: list[str] = []
    try:
        with open(path) as f:
            hosts = (json.load(f).get("hosts") or {})
        for host in hosts:
            m = re.search(r"eventbrite\.com/o/(\d+)", host)
            if m:
                urls.append(f"https://www.eventbrite.com/o/{m.group(1)}")
    except Exception:
        pass
    return urls


# Topics that map cleanly onto Eventbrite's URL search slugs and are
# meaningful event categories (vs. location markers, demographics, or
# already-excluded categories). Auto-built into search URLs based on
# the user's interest profile — scalable: as the user's IG follows
# evolve, the topic counts change, and the search URLs change with them.
_SUPPORTED_INTEREST_TOPICS = {
    "yoga", "run", "book", "comedy", "wine", "park", "art",
    "music", "food", "dance", "running", "fitness", "literary",
    "queer", "social", "poetry", "pottery", "jazz", "vinyl",
    "read",        # iter 145: maps to books slug
    "outdoor",
}

# Special-case topic → eventbrite slug mapping where the literal topic
# word doesn't match the URL convention.
_TOPIC_URL_SLUG = {
    "run": "running",        # user's profile has "run", eventbrite slug is "running"
    "running": "running",
    "book": "books",
    "read": "books",         # iter 145: same target as 'book'
    "park": "outdoor",
    "outdoor": "outdoor",
    "literary": "books",
    "vinyl": "music",
    "jazz": "music",
}


def _build_interest_topic_urls() -> list[str]:
    """Read the user interest profile and construct eventbrite search URLs
    for topics the user's IG follow graph has surfaced.

    No hardcoded per-topic URL list — the function generates URLs at
    runtime based on the live profile. New topics that appear in the
    profile automatically get searched.
    """
    import os, json as _json
    profile_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "user_interest_profile.json",
    )
    if not os.path.isfile(profile_path):
        return []
    try:
        with open(profile_path) as f:
            prof = _json.load(f)
    except Exception:
        return []

    topics = dict(prof.get("topic_counts") or {})
    # Explicit in-app behavior is more authoritative than username
    # substrings. Fold category weights into the same URL planner.
    engagement_path = os.path.join(os.path.dirname(profile_path), "user_engagement.json")
    try:
        with open(engagement_path) as f:
            engagement = _json.load(f)
        category_topics = {
            "books": "book", "fitness": "fitness", "wellness": "wellness",
            "music": "music", "comedy": "comedy", "food": "food",
            "art": "art", "dance": "dance", "singles": "social",
            "games": "gaming", "outdoors": "outdoor",
        }
        negative = engagement.get("negCategories") or {}
        for category, weight in (engagement.get("categories") or {}).items():
            if (negative.get(category, 0) or 0) >= (weight or 0):
                continue
            topic = category_topics.get(category)
            if topic:
                topics[topic] = topics.get(topic, 0) + max(1, weight or 0)
    except Exception:
        pass
    urls: list[str] = []
    seen_slugs: set[str] = set()
    for topic, count in sorted(topics.items(), key=lambda kv: -kv[1]):
        if topic not in _SUPPORTED_INTEREST_TOPICS:
            continue
        if count < 1:
            continue
        slug = _TOPIC_URL_SLUG.get(topic, topic)
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)
        urls.append(f"https://www.eventbrite.com/d/ny--new-york/{slug}--events/")
        urls.append(f"https://www.eventbrite.com/d/ny--brooklyn/{slug}--events/")
    return urls

# Broad searches are intentionally bounded. The previous implementation hit
# 40+ overlapping pages every run and routinely triggered Eventbrite 429s.
_EXPLORATION_URLS = [
    "https://www.eventbrite.com/d/ny--new-york/events--this-week/",
    "https://www.eventbrite.com/d/ny--new-york/events--this-weekend/",
    "https://www.eventbrite.com/d/ny--brooklyn/events--this-week/",
    "https://www.eventbrite.com/d/ny--brooklyn/events--this-weekend/",
    "https://www.eventbrite.com/d/ny--new-york/free--events/",
    "https://www.eventbrite.com/d/ny--williamsburg/events/",
]


def _search_plan() -> list[tuple[str, str]]:
    """Twelve taste-driven queries plus six bounded exploration queries."""
    personal = _build_interest_topic_urls()[:12]
    # Cold-start fallback uses the highest-value categories, not all legacy
    # URLs. Engagement/profile-driven URLs replace these as soon as available.
    if not personal:
        preferred = ("books", "music", "comedy", "sports-and-fitness", "arts", "food-and-drink")
        personal = [
            f"https://www.eventbrite.com/d/ny--new-york/{slug}--events/"
            for slug in preferred
        ]
    quick = os.environ.get("IG_SAVED_ONLY", "0") == "1"
    personal_limit, total_limit = (4, 6) if quick else (12, 18)
    out = [(u, "personal") for u in personal[:personal_limit]]
    out.extend((u, "explore") for u in _EXPLORATION_URLS if u not in personal)
    return out[:total_limit]


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
    events = []
    # Personalized, bounded search pages first.
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
    detail_limit = 0 if os.environ.get("IG_SAVED_ONLY", "0") == "1" else 40
    events = await _hydrate_shortlist(events, limit=detail_limit)
    # Then organizer pages — the seed list PLUS any organizer the user has
    # vetted in the preference layer (user_curated_sources.json). Organizer
    # pages don't ship JSON-LD; they hydrate from a __NEXT_DATA__ blob. Use
    # the organizer-specific parser.
    organizer_urls = list(dict.fromkeys(ORGANIZER_URLS + _curated_organizer_urls()))
    if len(organizer_urls) > len(ORGANIZER_URLS):
        print(f"[eventbrite-organizer] {len(organizer_urls)} organizers ({len(organizer_urls)-len(ORGANIZER_URLS)} from preference layer)")
    for url in organizer_urls:
        try:
            html = await _fetch_with_backoff(url)
            org_events = _parse_organizer_page(html, url)
            events.extend(org_events)
            print(f"[eventbrite-organizer] {url}: {len(org_events)} events")
        except Exception as e:
            print(f"[eventbrite-organizer] Failed {url}: {e}")
    return events


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
    """Parse an Eventbrite organizer page (/o/<id>) via __NEXT_DATA__.
    Organizer pages don't include JSON-LD — they hydrate from a Next.js
    data blob. Extracts upcoming events with full venue + ticket info.
    """
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except Exception:
        return []
    page_props = data.get("props", {}).get("pageProps", {})
    upcoming = page_props.get("upcomingEvents") or []
    organizer_obj = page_props.get("organizer") or {}
    organizer_name = organizer_obj.get("name", "") if isinstance(organizer_obj, dict) else ""
    events: list[dict] = []
    for raw in upcoming:
        if not isinstance(raw, dict):
            continue
        title = raw.get("name") or ""
        if isinstance(title, dict):
            title = title.get("text") or ""
        if not title:
            continue
        date_str = raw.get("start_date") or ""
        event_date = parse_date(date_str)
        if not event_date:
            continue
        start_time = (raw.get("start_time") or "")[:5] or None
        end_time = (raw.get("end_time") or "")[:5] or None
        url = raw.get("url") or source_url
        image = ((raw.get("image") or {}).get("url") or None)
        venue = raw.get("primary_venue") or {}
        venue_name = venue.get("name") or ""
        addr_obj = venue.get("address") or {}
        venue_addr = addr_obj.get("localized_address_display") or ""
        is_free = ((raw.get("ticket_availability") or {}).get("is_free"))
        price = "free" if is_free else None
        summary = raw.get("summary") or ""
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
            organizer=(raw.get("organizer", {}).get("name") if isinstance(raw.get("organizer"), dict) else None) or organizer_name or None,
            organizer_url=source_url,
            organizer_refs=[{
                "platform": "eventbrite",
                "externalId": (re.search(r"/o/(\d+)", source_url).group(1) if re.search(r"/o/(\d+)", source_url) else source_url),
                "name": (raw.get("organizer", {}).get("name") if isinstance(raw.get("organizer"), dict) else None) or organizer_name or "",
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
            "externalId": (re.search(r"/o/(\d+)", organizer_url).group(1) if organizer_url and re.search(r"/o/(\d+)", organizer_url) else organizer_url),
            "name": organizer_name,
            "url": organizer_url,
            "role": "host",
        }] if organizer_name or organizer_url else None,
    )
