"""General-purpose event scraper.

Tries multiple universal extraction strategies (JSON-LD, OpenGraph, iCal)
to scrape events from arbitrary URLs without per-site code.
"""
import json
import os
import re
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup

from ..utils.http import fetch_text
from ..utils.event_parser import build_event, parse_date, parse_time

# High-value NYC venue/cultural URLs
GENERIC_URLS = [
    # Music venues
    "https://www.92ny.org/calendar",
    "https://www.bricartsmedia.org/events",
    "https://thebellhouseny.com/calendar/",
    "https://www.brooklynbrewery.com/visit-the-brewery/events/",
    "https://lpr.com/calendar/",
    "https://elsewherebrooklyn.com/listings",
    "https://www.bowerypoetry.com/events",
    "https://greenwoodcemetery.org/events/",
    "https://www.theinvisibledog.org/upcoming-events",
    "https://www.openhousenewyork.org/calendar/",
    "https://hudsonyards.com/discover/events/",
    "https://thehighline.org/events/",
    # Comedy venues
    "https://www.flophousecomedy.com/events",
    "https://www.flophousecomedy.com",
    "https://www.greenpointcomedyclub.com/events",
    "https://www.greenpointcomedyclub.com",
    "https://www.unioncomedyhall.com/events",
    "https://www.eastvillecomedy.com/events",
    "https://newyorkcomedyclub.com/calendar",
    "https://standupny.com/calendar",
    # Running clubs / outdoor fitness (weekly social runs)
    "https://www.brooklyntrack.club/events",
    "https://newyorkroad.com/events",
    "https://www.northbrooklynrunners.org/events",
    # Curated NYC event hubs
    "https://www.nyc.com/events/",
    "https://www.eventcombo.com/events/new-york",
    "https://www.timeout.com/newyork/things-to-do/things-to-do-in-nyc-this-weekend",
    "https://www.timeout.com/newyork/events",
    "https://www.timeout.com/newyork/things-to-do/best-things-to-do-in-nyc-this-week",
    # Bookstores / literary
    "https://www.mcnallyjackson.com/events",
    "https://www.barnesandnoble.com/h/events/store/2675",
    "https://www.bookcourt.com/calendar",
    "https://lizsbookbar.com/events",
    # Major concert venues with calendar pages (kept the working ones)
    "https://www.terminal5nyc.com/calendar/",       # Returns events ✓
    "https://www.boweryballroom.com/calendar/",
    "https://www.websterhall.com/events/",
    "https://www.brooklynsteel.com/calendar/",
    "https://www.warsawconcerts.com/events/",
    "https://www.brooklynbowl.com/new-york/events/",
    # Film venues
    "https://metrograph.com/calendar/",
    "https://www.filmforum.org/calendar",
    "https://www.anthologyfilmarchives.org/calendar",
    # Theater
    "https://www.thekitchen.org/calendar/",
    # Art / cultural
    "https://www.theshed.org/calendar",
    # Bell House comedy/music (works well)
    "https://thebellhouseny.com/calendar/",
    # Eventbrite NYC category pages — JSON-LD structured listings, 18-20 events each
    "https://www.eventbrite.com/d/ny--new-york/all-events/",
    "https://www.eventbrite.com/d/ny--brooklyn/all-events/",
    "https://www.eventbrite.com/d/ny--brooklyn/free--events/",
    "https://www.eventbrite.com/d/ny--brooklyn/free--events--this-weekend/",
    "https://www.eventbrite.com/d/ny--queens/all-events/",
    "https://www.eventbrite.com/d/ny--new-york/music--events/",
    "https://www.eventbrite.com/d/ny--new-york/comedy--events/",
    "https://www.eventbrite.com/d/ny--new-york/food-and-drink--events/",
    "https://www.eventbrite.com/d/ny--new-york/free--events--this-weekend/",
    # AllEvents.in — major aggregator with structured JSON-LD per borough.
    # Pagination is real — each page returns ~88-95 unique events.
    "https://allevents.in/new-york",
    "https://allevents.in/new-york?page=2",
    "https://allevents.in/new-york?page=3",
    "https://allevents.in/brooklyn",
    "https://allevents.in/brooklyn?page=2",
    "https://allevents.in/brooklyn?page=3",
    "https://allevents.in/queens",
    "https://allevents.in/queens?page=2",
    "https://allevents.in/manhattan",
    "https://allevents.in/manhattan?page=2",
    "https://allevents.in/new-york/free",
    "https://allevents.in/new-york/music",
    "https://allevents.in/new-york/comedy",
    "https://allevents.in/new-york/food",
    # Songkick metro pages — major live-music coverage with JSON-LD
    "https://www.songkick.com/metro-areas/7644-us-new-york",
    "https://www.songkick.com/metro-areas/7644-us-new-york/2",
    # Songkick venue pages — major NYC live-music venues (3-8 events each).
    # These compound with the metro page since metro shows top events while
    # venue pages give the full upcoming calendar per venue.
    "https://www.songkick.com/venues/22-brooklyn-bowl",
    "https://www.songkick.com/venues/8-elsewhere",
    "https://www.songkick.com/venues/5-mercury-lounge",
]

# JSON-LD event schema types we accept
EVENT_TYPES = {
    "Event",
    "MusicEvent",
    "TheaterEvent",
    "DanceEvent",
    "ComedyEvent",
    "FoodEvent",
    "SportsEvent",
    "BusinessEvent",
    "EducationEvent",
    "ExhibitionEvent",
    "FestivalEvent",
    "LiteraryEvent",
    "ScreeningEvent",
    "SocialEvent",
    "VisualArtsEvent",
    "ChildrensEvent",
    "PublicationEvent",
    "BroadcastEvent",
}

DISCOVERED_URLS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "discovered_urls.json",
)


def _domain_source(url: str) -> str:
    """Extract a clean source label from URL domain."""
    try:
        host = urlparse(url).hostname or ""
        host = host.lower()
        if host.startswith("www."):
            host = host[4:]
        parts = host.split(".")
        if len(parts) >= 2:
            # Use the registrable name; for short slugs (like "lu") keep the suffix too
            slug = parts[0]
            if len(slug) <= 3 and len(parts) >= 2:
                return f"{slug}.{parts[1]}"
            return slug
        return host or "generic"
    except Exception:
        return "generic"


def _coerce_list(val):
    if val is None:
        return []
    if isinstance(val, list):
        return val
    return [val]


def _matches_event_type(type_val) -> bool:
    """Check if a JSON-LD @type value indicates an event."""
    if not type_val:
        return False
    types = _coerce_list(type_val)
    return any(isinstance(t, str) and t in EVENT_TYPES for t in types)


def _extract_image(image_val) -> str | None:
    if not image_val:
        return None
    if isinstance(image_val, list):
        for item in image_val:
            url = _extract_image(item)
            if url:
                return url
        return None
    if isinstance(image_val, dict):
        return image_val.get("url") or image_val.get("contentUrl")
    if isinstance(image_val, str):
        return image_val
    return None


def _extract_location(location_val) -> tuple[str, str]:
    """Returns (location_name, address)."""
    if not location_val:
        return "", ""
    if isinstance(location_val, list):
        for item in location_val:
            name, addr = _extract_location(item)
            if name or addr:
                return name, addr
        return "", ""
    if isinstance(location_val, dict):
        loc_name = location_val.get("name", "") or ""
        addr = location_val.get("address", "")
        if isinstance(addr, dict):
            parts = [
                addr.get("streetAddress", ""),
                addr.get("addressLocality", ""),
                addr.get("addressRegion", ""),
            ]
            loc_addr = ", ".join(p for p in parts if p)
        elif isinstance(addr, str):
            loc_addr = addr
        else:
            loc_addr = ""
        return loc_name, loc_addr
    if isinstance(location_val, str):
        return location_val, ""
    return "", ""


def _extract_price(offers_val) -> str:
    if not offers_val:
        return "unknown"
    if isinstance(offers_val, list):
        if not offers_val:
            return "unknown"
        offers_val = offers_val[0]
    if isinstance(offers_val, dict):
        p = offers_val.get("price", offers_val.get("lowPrice", ""))
        if p == "0" or p == 0 or p == "0.00":
            return "free"
        if p:
            try:
                pf = float(p)
                if pf == 0:
                    return "free"
                return f"${pf:g}"
            except (ValueError, TypeError):
                return f"${p}"
    return "unknown"


def _ld_event_to_dict(data: dict, source: str, fallback_url: str) -> dict | None:
    """Convert a JSON-LD Event object to our event dict format."""
    title = data.get("name", "") or ""
    if not title:
        return None
    desc = data.get("description", "") or ""
    if isinstance(desc, dict):
        desc = desc.get("@value", "") or ""
    start = data.get("startDate", "") or ""
    end = data.get("endDate", "") or ""

    event_date = parse_date(start[:10]) if start else None
    if not event_date:
        return None

    start_time = start[11:16] if len(start) >= 16 else None
    end_time = end[11:16] if len(end) >= 16 else None

    loc_name, loc_addr = _extract_location(data.get("location"))
    image = _extract_image(data.get("image"))
    price = _extract_price(data.get("offers"))

    url = data.get("url", "") or fallback_url
    if isinstance(url, list) and url:
        url = url[0]
    if isinstance(url, str) and url and not url.startswith("http"):
        url = urljoin(fallback_url, url)

    return build_event(
        title=str(title)[:300],
        description=str(desc)[:500],
        event_date=event_date,
        start_time=start_time,
        end_time=end_time,
        location_name=loc_name,
        address=loc_addr,
        source=source,
        source_url=url or fallback_url,
        image_url=image,
        price=price,
    )


def _walk_jsonld(node, source: str, fallback_url: str, results: list[dict], _seen: set | None = None) -> None:
    """Recursively walk a JSON-LD structure, extracting any Event objects.

    Handles: direct Event, lists, @graph, Organization with nested events,
    ItemList with itemListElement, and other nested structures.
    """
    if _seen is None:
        _seen = set()
    if node is None:
        return
    # Cycles guard for dicts/lists by id
    nid = id(node)
    if nid in _seen:
        return
    _seen.add(nid)

    if isinstance(node, list):
        for item in node:
            _walk_jsonld(item, source, fallback_url, results, _seen)
        return

    if not isinstance(node, dict):
        return

    type_val = node.get("@type")

    # Direct event match
    if _matches_event_type(type_val):
        ev = _ld_event_to_dict(node, source, fallback_url)
        if ev:
            results.append(ev)
        # Some events have sub-events; keep walking
        for key in ("subEvent", "subEvents"):
            sub = node.get(key)
            if sub:
                _walk_jsonld(sub, source, fallback_url, results, _seen)
        return

    # @graph structure
    graph = node.get("@graph")
    if graph:
        _walk_jsonld(graph, source, fallback_url, results, _seen)

    # Organization or LocalBusiness or Place with nested events array
    for key in ("event", "events"):
        if key in node:
            _walk_jsonld(node[key], source, fallback_url, results, _seen)

    # ItemList with itemListElement
    if "itemListElement" in node:
        items = node["itemListElement"]
        if isinstance(items, list):
            for item in items:
                # Items can be ListItem wrappers around the actual entity
                if isinstance(item, dict):
                    inner = item.get("item", item)
                    _walk_jsonld(inner, source, fallback_url, results, _seen)


def _parse_jsonld_strategy(soup: BeautifulSoup, source: str, fallback_url: str) -> list[dict]:
    events: list[dict] = []
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text() or ""
        if not raw.strip():
            continue
        # Some sites embed multiple JSON objects or have stray characters
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Try to recover by grabbing the first parseable object
            try:
                data = json.loads(raw.strip().rstrip(";"))
            except Exception:
                continue
        _walk_jsonld(data, source, fallback_url, events)
    return events


def _meta(soup: BeautifulSoup, prop: str) -> str | None:
    """Read a meta tag by property or name."""
    el = soup.find("meta", attrs={"property": prop})
    if not el:
        el = soup.find("meta", attrs={"name": prop})
    if el:
        content = el.get("content")
        if content:
            return content.strip()
    return None


# Site-name suffixes to strip from <title>-derived event names
# (e.g., "Doppelgänger Crawfish Boil Tickets, ... | Eventbrite" → strip the suffix)
_TITLE_SUFFIXES = [
    r"\s*\|\s*Eventbrite\s*$",
    r"\s*\|\s*Lu\.ma\s*$",
    r"\s*\|\s*Luma\s*$",
    r"\s*\|\s*Partiful\s*$",
    r"\s*\|\s*Meetup\s*$",
    r"\s*\|\s*Substack\s*$",
    r"\s*\|\s*RA\s*$",
    r"\s*-\s*Eventbrite\s*$",
    # Ticket noise like "Tickets, Saturday, May 2 • 4 PM - 7 PM"
    r"\s+Tickets,\s+\w+,\s+\w+\s+\d+(?:\s*•[^|]*)?$",
    r"\s+Tickets\s*$",
]
_TITLE_SUFFIX_RE = re.compile(
    "|".join(_TITLE_SUFFIXES), re.IGNORECASE
)


def _clean_html_title(title: str) -> str:
    """Strip platform suffixes and ticket-listing noise from <title>-derived
    event names so they read like real event names.

    Examples:
      'Doppelgänger Crawfish Boil Tickets, Saturday, May 2 • 4 PM - 7 PM | Eventbrite'
      → 'Doppelgänger Crawfish Boil'
    """
    cleaned = title.strip()
    # Apply each suffix repeatedly until no further change
    for _ in range(3):
        new = _TITLE_SUFFIX_RE.sub("", cleaned).rstrip()
        if new == cleaned:
            break
        cleaned = new
    return cleaned


def _parse_opengraph_strategy(soup: BeautifulSoup, source: str, fallback_url: str) -> list[dict]:
    """Extract a single event from OpenGraph metadata.

    Robust to bot-stripped pages: falls back to <title> and meta name=description
    when og: tags are missing.  Tries to parse a date from the title or description.
    """
    og_type = (_meta(soup, "og:type") or "").lower()
    title = (
        _meta(soup, "og:title")
        or _meta(soup, "twitter:title")
        or (soup.title.get_text(strip=True) if soup.title else "")
    )
    if not title:
        return []
    title = _clean_html_title(title)

    start_raw = (
        _meta(soup, "event:start_time")
        or _meta(soup, "event:start_date")
        or _meta(soup, "article:published_time")
    )
    end_raw = _meta(soup, "event:end_time") or _meta(soup, "event:end_date")

    # If no explicit start time but we have an event-like URL, try parsing
    # date from title or description (e.g., "Tickets, Saturday, May 2 • 4 PM").
    desc_raw = _meta(soup, "og:description") or _meta(soup, "description") or ""
    is_eventbrite_or_event = (
        "event" in og_type
        or "eventbrite.com/e/" in fallback_url
        or "lu.ma/event/" in fallback_url
        or "partiful.com/e/" in fallback_url
    )

    event_date = None
    start_time = None
    if start_raw:
        event_date = parse_date(start_raw[:10]) or parse_date(start_raw)
        if len(start_raw) >= 16 and "T" in start_raw:
            start_time = start_raw[11:16]
    elif is_eventbrite_or_event:
        # Try parsing from title
        for src in (title, desc_raw):
            event_date = parse_date(src)
            if event_date:
                start_time = parse_time(src)
                break

    if not event_date:
        return []

    is_event = "event" in og_type or bool(start_raw) or is_eventbrite_or_event
    if not is_event:
        return []

    end_time = None
    if end_raw and len(end_raw) >= 16 and "T" in end_raw:
        end_time = end_raw[11:16]

    desc = desc_raw
    image = _meta(soup, "og:image") or _meta(soup, "twitter:image")
    canonical = _meta(soup, "og:url") or fallback_url
    location_name = _meta(soup, "event:location") or _meta(soup, "og:site_name") or ""

    return [
        build_event(
            title=str(title)[:300],
            description=str(desc)[:500],
            event_date=event_date,
            start_time=start_time,
            end_time=end_time,
            location_name=location_name,
            source=source,
            source_url=canonical,
            image_url=image,
        )
    ]


def _detect_ical_url(soup: BeautifulSoup, fallback_url: str) -> str | None:
    """Look for <link rel='alternate' type='text/calendar'> or common .ics paths."""
    link = soup.find("link", attrs={"rel": "alternate", "type": "text/calendar"})
    if link:
        href = link.get("href")
        if href:
            return urljoin(fallback_url, href)
    # Look for direct anchors to .ics files
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.endswith(".ics") or "format=ical" in href.lower():
            return urljoin(fallback_url, href)
    return None


_ICAL_FIELD_RE = re.compile(r"^([A-Z\-]+)(?:;[^:]*)?:(.*)$")


def _parse_ical(text: str, source: str, fallback_url: str) -> list[dict]:
    """Minimal iCal VEVENT parser — handles the common cases without a dep."""
    events: list[dict] = []
    # Unfold continuation lines (lines starting with space)
    unfolded_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith((" ", "\t")) and unfolded_lines:
            unfolded_lines[-1] += line[1:]
        else:
            unfolded_lines.append(line)

    in_event = False
    current: dict = {}
    for line in unfolded_lines:
        if line.strip() == "BEGIN:VEVENT":
            in_event = True
            current = {}
            continue
        if line.strip() == "END:VEVENT":
            in_event = False
            ev = _ical_record_to_event(current, source, fallback_url)
            if ev:
                events.append(ev)
            current = {}
            continue
        if not in_event:
            continue
        m = _ICAL_FIELD_RE.match(line)
        if not m:
            continue
        key, value = m.group(1), m.group(2)
        current[key] = value.replace("\\,", ",").replace("\\n", " ").replace("\\;", ";")
    return events


def _ical_date(value: str):
    """Parse an iCal date/datetime field into (date_obj, time_str_or_none)."""
    if not value:
        return None, None
    v = value.strip()
    # YYYYMMDDTHHMMSS or YYYYMMDDTHHMMSSZ
    m = re.match(r"^(\d{4})(\d{2})(\d{2})(?:T(\d{2})(\d{2}))?", v)
    if not m:
        return parse_date(v), None
    y, mo, d, h, mi = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
    date_obj = parse_date(f"{y}-{mo}-{d}")
    time_str = f"{h}:{mi}" if h and mi else None
    return date_obj, time_str


def _ical_record_to_event(rec: dict, source: str, fallback_url: str) -> dict | None:
    title = rec.get("SUMMARY", "")
    if not title:
        return None
    start = rec.get("DTSTART", "")
    end = rec.get("DTEND", "")
    desc = rec.get("DESCRIPTION", "")
    location = rec.get("LOCATION", "")
    url = rec.get("URL", fallback_url) or fallback_url

    event_date, start_time = _ical_date(start)
    if not event_date:
        return None
    _, end_time = _ical_date(end)

    return build_event(
        title=title[:300],
        description=desc[:500],
        event_date=event_date,
        start_time=start_time,
        end_time=end_time,
        location_name=location,
        source=source,
        source_url=url,
    )


async def _try_ical(soup: BeautifulSoup, source: str, fallback_url: str) -> list[dict]:
    ical_url = _detect_ical_url(soup, fallback_url)
    candidates = []
    if ical_url:
        candidates.append(ical_url)
    # Common conventional paths
    parsed = urlparse(fallback_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    for path in ("/events.ics", "/calendar.ics", "/events/feed.ics"):
        candidates.append(base + path)

    for cand in candidates:
        try:
            text = await fetch_text(cand)
            if "BEGIN:VCALENDAR" in text:
                events = _parse_ical(text, source, fallback_url)
                if events:
                    return events
        except Exception:
            continue
    return []


def _dedupe(events: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for ev in events:
        key = ev.get("id") or f"{ev.get('title')}::{ev.get('date')}"
        if key in seen:
            continue
        seen.add(key)
        out.append(ev)
    return out


_LINK_AGGREGATOR_HOSTS = (
    "linktr.ee",
    "beacons.ai",
    "linkin.bio",
    "stan.store",
    "withkoji.com",
    "koji.to",
    "allmylinks.com",
    "lnk.bio",
    "snipfeed.co",
    "tap.bio",
    "msha.ke",  # milkshake
    "campsite.bio",
    "withfriends.co",
)

_EVENT_PLATFORM_HOSTS_RE = re.compile(
    r"(?:lu\.ma|luma\.com|eventbrite\.com|partiful\.com|posh\.vip|"
    r"ra\.co|shotgun\.live|withtopography\.com|tixr\.com|dice\.fm|"
    r"meetup\.com)",
    re.IGNORECASE,
)


def _is_link_aggregator(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower().lstrip("www.")
        return any(host == h or host.endswith("." + h) for h in _LINK_AGGREGATOR_HOSTS)
    except Exception:
        return False


def _expand_link_aggregator(soup: BeautifulSoup, source_url: str) -> int:
    """For Linktree/Beacons-style URLs, harvest outbound event-platform URLs
    and add them to discovered_urls.json. Returns count of newly-added URLs.

    These pages don't have event JSON-LD themselves but each links to one.
    """
    found: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href.startswith("http"):
            continue
        if _EVENT_PLATFORM_HOSTS_RE.search(href):
            found.add(href.split("?")[0].split("#")[0])
    if not found:
        return 0
    # Compute additions before writing so the count is accurate.
    existing = set()
    if os.path.isfile(DISCOVERED_URLS_PATH):
        try:
            with open(DISCOVERED_URLS_PATH) as f:
                d = json.load(f)
            items = d if isinstance(d, list) else d.get("urls", [])
            existing = {it["url"] if isinstance(it, dict) else it for it in items}
        except Exception:
            pass
    new_urls = found - existing
    via = f"link_aggregator:{_domain_source(source_url)}"
    for href in new_urls:
        _add_discovered_url(href, via)
    return len(new_urls)


async def scrape_url(url: str, default_source: str = "generic") -> list[dict]:
    """Scrape events from a single URL using universal extraction strategies."""
    source = default_source if default_source != "generic" else _domain_source(url)
    try:
        html = await fetch_text(url)
    except Exception as e:
        print(f"[generic] {url}: fetch failed: {e}")
        _record_url_failure(url)
        return []

    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception as e:
        print(f"[generic] {url}: parse failed: {e}")
        return []

    # Link-aggregator fan-out: Linktree/Beacons/etc. don't host events but link
    # to event pages. Harvest those outbound URLs and bail — the event pages
    # themselves get scraped on the next pipeline run.
    if _is_link_aggregator(url):
        added = _expand_link_aggregator(soup, url)
        if added:
            print(f"[generic] {url}: aggregator → harvested {added} event-platform URLs")
        # Treat as successful so we don't mark it dead.
        _record_url_success(url)
        return []

    # Strategy 1: JSON-LD Schema.org Event extraction
    events = _parse_jsonld_strategy(soup, source, url)

    # Strategy 2: OpenGraph metadata fallback for single-event pages
    if not events:
        events = _parse_opengraph_strategy(soup, source, url)

    # Strategy 3: iCal feed detection
    if not events:
        try:
            events = await _try_ical(soup, source, url)
        except Exception as e:
            print(f"[generic] {url}: ical attempt failed: {e}")

    events = _dedupe(events)
    print(f"[generic] {url}: {len(events)} events")

    # Self-improvement: track URLs that consistently return 0 events.
    # After 5 consecutive empty pulls, URL is marked dead and skipped.
    if not events:
        _record_url_failure(url)
    else:
        _record_url_success(url)
        # Auto-discover Eventbrite organizer pages from event URLs.
        # An organizer typically hosts dozens of NYC events.
        if "eventbrite.com/e/" in url:
            organizer_url = _extract_eventbrite_organizer(soup)
            if organizer_url:
                _add_discovered_url(organizer_url, "eventbrite_organizer")

        # Sitemap mining: try once per host (not every URL) to avoid spam.
        # When the host has /sitemap.xml, we can harvest every event URL on
        # the venue's site at once instead of crawling page-by-page.
        try:
            await _maybe_harvest_sitemap(url)
        except Exception as e:
            print(f"[generic] {url}: sitemap harvest failed: {e}")

    return events


_SITEMAP_TRIED_HOSTS: set[str] = set()


async def _maybe_harvest_sitemap(url: str) -> None:
    """Once per host, fetch /sitemap.xml and harvest event-looking URLs.

    Many venue/listing sites publish a sitemap with hundreds of event pages.
    We're conservative — only harvest URLs whose path contains common event
    markers (event, show, calendar, gig, performance) so we don't add the
    entire site.
    """
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if not host or host in _SITEMAP_TRIED_HOSTS:
        return
    _SITEMAP_TRIED_HOSTS.add(host)

    base = f"{parsed.scheme}://{parsed.netloc}"
    candidates = [
        f"{base}/sitemap.xml",
        f"{base}/sitemap_index.xml",
        f"{base}/events-sitemap.xml",
    ]
    for cand in candidates:
        try:
            xml = await fetch_text(cand)
        except Exception:
            continue
        if "<urlset" not in xml and "<sitemapindex" not in xml:
            continue
        urls = _extract_event_urls_from_sitemap(xml, base)
        if not urls:
            return
        # Dedup against existing discovered_urls
        existing = set()
        if os.path.isfile(DISCOVERED_URLS_PATH):
            try:
                with open(DISCOVERED_URLS_PATH) as f:
                    d = json.load(f)
                items = d if isinstance(d, list) else d.get("urls", [])
                existing = {it["url"] if isinstance(it, dict) else it for it in items}
            except Exception:
                pass
        new_urls = [u for u in urls if u not in existing][:50]  # cap per host
        for u in new_urls:
            _add_discovered_url(u, f"sitemap:{_domain_source(url)}")
        if new_urls:
            print(f"[generic] {host}: sitemap → harvested {len(new_urls)} event URLs")
        return


_SITEMAP_EVENT_MARKERS_RE = re.compile(
    r"/(?:event|events|show|shows|calendar|gig|gigs|performance|performances|"
    r"concert|concerts|exhibit|exhibits|exhibition|exhibitions|tour|tours|"
    r"screening|screenings|class|classes|workshop|workshops|book|reading)/",
    re.IGNORECASE,
)


def _extract_event_urls_from_sitemap(xml: str, base: str) -> list[str]:
    """Pull <loc> URLs from a sitemap and keep only event-looking ones."""
    # Sitemaps may be a sitemap index pointing to other sitemaps; we only
    # follow one level deep to bound cost.
    locs = re.findall(r"<loc>\s*([^<]+?)\s*</loc>", xml)
    out: list[str] = []
    for loc in locs:
        loc = loc.strip()
        if not loc.startswith("http"):
            continue
        if _SITEMAP_EVENT_MARKERS_RE.search(urlparse(loc).path or ""):
            out.append(loc.split("#")[0])
    # Dedup, preserve order
    seen: set[str] = set()
    result: list[str] = []
    for u in out:
        if u not in seen:
            seen.add(u)
            result.append(u)
    return result


def _extract_eventbrite_organizer(soup: BeautifulSoup) -> str | None:
    """Find the organizer page URL on an Eventbrite event page."""
    # Eventbrite organizer links usually look like /o/{slug}-{id}
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if "eventbrite.com/o/" in href and "-" in href:
            # Make sure we only get organizer profile URLs
            if "/o/" in href and not href.endswith("/follow"):
                return href.split("?")[0]
    return None


_URL_HEALTH_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "url_health.json",
)


def _load_url_health() -> dict:
    if not os.path.isfile(_URL_HEALTH_PATH):
        return {}
    try:
        with open(_URL_HEALTH_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_url_health(data: dict) -> None:
    os.makedirs(os.path.dirname(_URL_HEALTH_PATH), exist_ok=True)
    tmp = _URL_HEALTH_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, _URL_HEALTH_PATH)


def _record_url_failure(url: str) -> None:
    from datetime import datetime, timezone
    data = _load_url_health()
    entry = data.setdefault(url, {"failures": 0, "successes": 0})
    entry["failures"] = entry.get("failures", 0) + 1
    entry["last_failure_at"] = datetime.now(timezone.utc).isoformat()
    _save_url_health(data)


def _record_url_success(url: str) -> None:
    from datetime import datetime, timezone
    data = _load_url_health()
    entry = data.setdefault(url, {"failures": 0, "successes": 0})
    entry["successes"] = entry.get("successes", 0) + 1
    entry["failures"] = 0  # reset on success
    entry["last_success_at"] = datetime.now(timezone.utc).isoformat()
    _save_url_health(data)


def _is_dead_url(url: str) -> bool:
    """A URL is dead if it has 5+ failures with no recent successes."""
    data = _load_url_health()
    entry = data.get(url, {})
    return entry.get("failures", 0) >= 5


_RETEST_COOLDOWN_DAYS = 7
_RETEST_PER_RUN = 5


def _select_dead_urls_for_retest(health: dict, all_urls: list[str]) -> list[str]:
    """Pick a small set of dead URLs to retry this run (self-healing).

    A dead URL is eligible after _RETEST_COOLDOWN_DAYS since last failure.
    Cap at _RETEST_PER_RUN to bound wasted requests.
    """
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=_RETEST_COOLDOWN_DAYS)

    candidates = []
    for u in all_urls:
        entry = health.get(u, {})
        if entry.get("failures", 0) < 5:
            continue
        last_fail = entry.get("last_failure_at", "")
        try:
            ts = datetime.fromisoformat(last_fail)
        except Exception:
            # No timestamp on legacy entries — treat as eligible for retest.
            candidates.append(u)
            continue
        if ts < cutoff:
            candidates.append(u)
    # Prefer URLs with the longest dead time first (most overdue).
    candidates.sort(
        key=lambda u: health.get(u, {}).get("last_failure_at", ""),
    )
    return candidates[:_RETEST_PER_RUN]


def _add_discovered_url(url: str, source: str) -> None:
    """Add a URL to discovered_urls.json (deduped)."""
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data",
        "discovered_urls.json",
    )
    try:
        existing = []
        if os.path.isfile(path):
            with open(path) as f:
                d = json.load(f)
            existing = d if isinstance(d, list) else d.get("urls", [])
        seen = {item["url"] if isinstance(item, dict) else item for item in existing}
        if url in seen:
            return
        from datetime import datetime, timezone
        existing.append({
            "url": url,
            "discovered_at": datetime.now(timezone.utc).isoformat(),
            "discovered_via": source,
        })
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(existing, f, indent=2)
    except Exception as exc:
        print(f"[generic] add_discovered_url failed: {exc}")


def _load_discovered_urls() -> list[str]:
    """Load additional URLs from a JSON file (created by IG bio link discovery).

    Accepts multiple shapes:
      - ["url1", "url2", ...]
      - {"urls": [...]}
      - [{"url": "...", ...}, ...]   ← format used by discover.py + instagram.py
    """
    if not os.path.exists(DISCOVERED_URLS_PATH):
        return []
    try:
        with open(DISCOVERED_URLS_PATH) as f:
            data = json.load(f)
    except Exception as e:
        print(f"[generic] Failed to read {DISCOVERED_URLS_PATH}: {e}")
        return []

    def _extract(item):
        if isinstance(item, str):
            return item
        if isinstance(item, dict):
            return item.get("url")
        return None

    items: list = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("urls", [])

    urls = []
    for item in items:
        u = _extract(item)
        if u and isinstance(u, str) and u.startswith("http"):
            urls.append(u)
    return urls


async def scrape() -> list[dict]:
    """Scrape all URLs from GENERIC_URLS plus any discovered URLs.

    URLs that consistently return 0 events are skipped after 5 failures.
    """
    urls: list[str] = list(GENERIC_URLS)

    # Append discovered URLs while preserving order and deduping
    seen = set(urls)
    for u in _load_discovered_urls():
        if u not in seen:
            urls.append(u)
            seen.add(u)

    # Skip dead URLs (5+ consecutive failures), but pick a few to retest
    # so the URL pool is self-healing — if a venue's calendar comes back
    # online or its URL was momentarily 5xx, we'll find it again.
    health = _load_url_health()
    retest_urls = _select_dead_urls_for_retest(health, urls)
    before = len(urls)
    urls = [u for u in urls if health.get(u, {}).get("failures", 0) < 5 or u in set(retest_urls)]
    skipped = before - len(urls)
    if skipped:
        print(f"[generic] Skipping {skipped} dead URLs (5+ failures)")
    if retest_urls:
        print(f"[generic] Re-testing {len(retest_urls)} previously-dead URLs after {_RETEST_COOLDOWN_DAYS}d cooldown")

    all_events: list[dict] = []
    for url in urls:
        try:
            events = await scrape_url(url)
            all_events.extend(events)
        except Exception as e:
            print(f"[generic] {url}: ERROR {e}")
    return all_events
