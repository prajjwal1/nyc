import json
import re
from bs4 import BeautifulSoup
from ..utils.http import fetch_text
from ..utils.event_parser import build_event, parse_date, parse_time, parse_iso_to_local, parse_offers_price

# Specific organizer pages the user has flagged as high-priority.
# These list ALL of an organizer's events in one place — useful for
# brand-curated event series the user follows. Add to user_curated_sources
# .json simultaneously so events from these get the +0.15 boost.
ORGANIZER_URLS = [
    # Lululemon — user added (fitness events priority)
    "https://www.eventbrite.com/o/14861961557",
]


# Topics that map cleanly onto Eventbrite's URL search slugs and are
# meaningful event categories (vs. location markers, demographics, or
# already-excluded categories). Auto-built into search URLs based on
# the user's interest profile — scalable: as the user's IG follows
# evolve, the topic counts change, and the search URLs change with them.
_SUPPORTED_INTEREST_TOPICS = {
    "yoga", "run", "book", "comedy", "wine", "park", "art",
    "music", "food", "dance", "running", "fitness", "literary",
    "queer", "social", "poetry", "pottery", "jazz", "vinyl",
}

# Special-case topic → eventbrite slug mapping where the literal topic
# word doesn't match the URL convention.
_TOPIC_URL_SLUG = {
    "run": "running",        # user's profile has "run", eventbrite slug is "running"
    "running": "running",
    "book": "books",
    "park": "outdoor",
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

    topics = (prof.get("topic_counts") or {})
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

SEARCH_URLS = [
    # Geographic + time (density)
    "https://www.eventbrite.com/d/ny--new-york/events--this-week/",
    "https://www.eventbrite.com/d/ny--new-york/events--this-weekend/",
    "https://www.eventbrite.com/d/ny--new-york/events--next-week/",
    "https://www.eventbrite.com/d/ny--new-york/events--this-month/",
    "https://www.eventbrite.com/d/ny--new-york/events--next-month/",
    "https://www.eventbrite.com/d/ny--brooklyn/events--this-week/",
    "https://www.eventbrite.com/d/ny--brooklyn/events--this-weekend/",
    "https://www.eventbrite.com/d/ny--brooklyn/events--this-month/",
    "https://www.eventbrite.com/d/ny--new-york/free--events/",
    # Category filters (NYC 20s-30s lifestyle)
    "https://www.eventbrite.com/d/ny--new-york/music--events/",
    "https://www.eventbrite.com/d/ny--new-york/comedy--events/",
    "https://www.eventbrite.com/d/ny--new-york/food-and-drink--events/",
    "https://www.eventbrite.com/d/ny--new-york/nightlife--events/",
    "https://www.eventbrite.com/d/ny--new-york/arts--events/",
    "https://www.eventbrite.com/d/ny--new-york/film-and-media--events/",
    "https://www.eventbrite.com/d/ny--new-york/dating--events/",
    "https://www.eventbrite.com/d/ny--new-york/performing-and-visual-arts--events/",
    "https://www.eventbrite.com/d/ny--new-york/holiday--events/",
    "https://www.eventbrite.com/d/ny--new-york/sports-and-fitness--events/",
    "https://www.eventbrite.com/d/ny--new-york/health-and-wellness--events/",
    "https://www.eventbrite.com/d/ny--brooklyn/music--events/",
    "https://www.eventbrite.com/d/ny--brooklyn/comedy--events/",
    "https://www.eventbrite.com/d/ny--brooklyn/nightlife--events/",
    "https://www.eventbrite.com/d/ny--brooklyn/food-and-drink--events/",
    # Williamsburg / specific neighborhoods
    "https://www.eventbrite.com/d/ny--williamsburg/events/",
    "https://www.eventbrite.com/d/ny--bushwick/events/",
    "https://www.eventbrite.com/d/ny--greenpoint/events/",
]


async def scrape() -> list[dict]:
    events = []
    # Pull search-density pages first
    for url in SEARCH_URLS:
        try:
            html = await fetch_text(url)
            events.extend(_parse_search_page(html, url))
        except Exception as e:
            print(f"[eventbrite] Failed {url}: {e}")
    # Topic search URLs built dynamically from the user's interest profile.
    # Auto-evolves with the IG follow graph — no per-topic config edits.
    interest_urls = _build_interest_topic_urls()
    if interest_urls:
        print(f"[eventbrite-interest] {len(interest_urls)} interest-driven URLs from profile")
        for url in interest_urls:
            try:
                html = await fetch_text(url)
                events.extend(_parse_search_page(html, url))
            except Exception as e:
                print(f"[eventbrite-interest] Failed {url}: {e}")
    # Then specific organizer pages (user-curated). Organizer pages don't
    # ship JSON-LD; they hydrate from a __NEXT_DATA__ blob. Use the
    # organizer-specific parser.
    for url in ORGANIZER_URLS:
        try:
            html = await fetch_text(url)
            org_events = _parse_organizer_page(html, url)
            events.extend(org_events)
            print(f"[eventbrite-organizer] {url}: {len(org_events)} events")
        except Exception as e:
            print(f"[eventbrite-organizer] Failed {url}: {e}")
    return events


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
    upcoming = (data.get("props", {}).get("pageProps", {}).get("upcomingEvents") or [])
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
    )
