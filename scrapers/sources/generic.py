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
from ..utils.event_parser import build_event, parse_date, parse_time, parse_iso_to_local, parse_offers_price

# High-value NYC venue/cultural URLs
# Calendar-style sources that expose `/calendar/YYYY-MM` (or `/events/YYYY-MM`)
# month-paginated views. The default listing page only shows the current
# month, so events past the 28th vanish unless we fetch next month too.
# Iter 91 audit: NYCC + East Ville Comedy were yielding ~250 May events
# combined but only 25 were future (after 2026-05-28). Adding next 2
# months' URLs at scrape time per `_dynamic_calendar_urls()`.
_CALENDAR_MONTH_URL_TEMPLATES = [
    "https://newyorkcomedyclub.com/calendar/{year}-{month:02d}",
    "https://www.eastvillecomedy.com/calendar/{year}-{month:02d}",
]


def _dynamic_calendar_urls() -> list[str]:
    """Generate next 3 months of calendar URLs at scrape time so we don't
    have to hardcode dates that go stale every month."""
    from datetime import date as _date
    today = _date.today()
    urls: list[str] = []
    for offset in (0, 1, 2):
        # Roll over to next year if needed
        y, m = today.year, today.month + offset
        while m > 12:
            m -= 12
            y += 1
        for tpl in _CALENDAR_MONTH_URL_TEMPLATES:
            urls.append(tpl.format(year=y, month=m))
    return urls


GENERIC_URLS = [
    # Music venues
    "https://www.92ny.org/calendar",
    "https://www.bricartsmedia.org/events",
    "https://thebellhouseny.com/calendar/",
    "https://www.brooklynbrewery.com/visit-the-brewery/events/",
    "https://lpr.com/calendar/",
    "https://elsewherebrooklyn.com/listings",
    "https://www.bowerypoetry.com/events",
    # Iter 103 audit: greenwoodcemetery.org redirects to green-wood.com which
    # returns 503 / Bad Gateway on the bare host. The direct events path
    # works: yields ~10 events including evening tours / After Hours.
    "https://www.green-wood.com/events",
    # Iter 113 audit: the Eventbrite venue-search URL pattern
    # `/d/<location>/<slug>/` is a KEYWORD search, NOT a strict venue
    # match. Generic slugs ("blue-note", "brooklyn-bowl", "mercury-lounge",
    # "comedy-cellar", "village-vanguard", "smoke-jazz-club") returned
    # 0/20 events at the target venue — Eventbrite was substring-matching
    # the slug across unrelated venues. Only sufficiently-unique slugs
    # work: elsewhere (18/20), littlefield (20/20), caveat (20/20),
    # pioneer-works (17/20).
    # The 11 false-positive URLs (HoY + KDC + the 9 generic-slug ones) were
    # removed from this list. Keeping the 4 verified.
    "https://www.eventbrite.com/d/ny--brooklyn/elsewhere/",
    "https://www.eventbrite.com/d/ny--brooklyn/littlefield/",
    "https://www.eventbrite.com/d/ny--manhattan/caveat/",
    "https://www.eventbrite.com/d/ny--brooklyn/pioneer-works/",
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
    # Eventbrite NYC category pages — JSON-LD structured listings, 18-20 events each.
    # Iter 90 audit: `?page=N` query param paginates correctly (each page returns
    # 20 distinct events). Added page 2 + 3 for the high-density all-events
    # URLs and page 2 for high-value categorical filters. Combined with the
    # new eventbrite=100 SOURCE_VOLUME_CAPS entry, this lets the top-100 best
    # events bubble up from a deeper pool without dominating the feed.
    "https://www.eventbrite.com/d/ny--new-york/all-events/",
    "https://www.eventbrite.com/d/ny--new-york/all-events/?page=2",
    "https://www.eventbrite.com/d/ny--new-york/all-events/?page=3",
    "https://www.eventbrite.com/d/ny--brooklyn/all-events/",
    "https://www.eventbrite.com/d/ny--brooklyn/all-events/?page=2",
    "https://www.eventbrite.com/d/ny--brooklyn/all-events/?page=3",
    "https://www.eventbrite.com/d/ny--brooklyn/free--events/",
    "https://www.eventbrite.com/d/ny--brooklyn/free--events--this-weekend/",
    "https://www.eventbrite.com/d/ny--queens/all-events/",
    "https://www.eventbrite.com/d/ny--queens/all-events/?page=2",
    "https://www.eventbrite.com/d/ny--new-york/music--events/",
    "https://www.eventbrite.com/d/ny--new-york/music--events/?page=2",
    "https://www.eventbrite.com/d/ny--new-york/comedy--events/",
    "https://www.eventbrite.com/d/ny--new-york/comedy--events/?page=2",
    "https://www.eventbrite.com/d/ny--new-york/food-and-drink--events/",
    "https://www.eventbrite.com/d/ny--new-york/free--events--this-weekend/",
    # Time-windowed + topic-targeted Eventbrite searches (~20 events each)
    "https://www.eventbrite.com/d/ny--new-york/events--this-weekend/",
    "https://www.eventbrite.com/d/ny--new-york/events--today/",
    "https://www.eventbrite.com/d/ny--new-york/events--this-week/",
    "https://www.eventbrite.com/d/ny--brooklyn/dating--events/",
    "https://www.eventbrite.com/d/ny--new-york/parties--events/",
    "https://www.eventbrite.com/d/ny--new-york/parties--events/?page=2",
    "https://www.eventbrite.com/d/ny--new-york/networking--events/",
    "https://www.eventbrite.com/d/ny--new-york/dating--events/",
    "https://www.eventbrite.com/d/ny--new-york/dating--events/?page=2",
    "https://www.eventbrite.com/d/ny--new-york/singles--events/",
    "https://www.eventbrite.com/d/ny--new-york/singles--events/?page=2",
    # Meetup search-result pages (structured JSON-LD listings)
    "https://www.meetup.com/find/?keywords=&source=EVENTS&location=us--ny--Brooklyn",
    "https://www.meetup.com/find/events/?source=EVENTS&location=us--ny--New%20York",
    # AllEvents.in — major aggregator with structured JSON-LD per borough.
    # Pagination is real — each page returns ~88-95 unique events.
    # AllEvents.in pagination: `?page=N` returns the same page-1 events.
    # Iter 89 audit: 6 of 12 borough URLs were duplicates wasting fetches.
    # The real pagination uses time-window paths (`/today`, `/tomorrow`,
    # `/this-weekend`, `/upcoming`, `/all`) which return distinct event
    # slices. Replaced the `?page=N` block with time-window URLs.
    "https://allevents.in/new-york",          # 65 events (default)
    "https://allevents.in/new-york/today",     # 15 distinct
    "https://allevents.in/new-york/tomorrow",  # 15 distinct
    "https://allevents.in/new-york/this-weekend",  # 15 distinct
    "https://allevents.in/new-york/upcoming",  # 15 distinct
    "https://allevents.in/new-york/all",       # 45 broader
    "https://allevents.in/brooklyn",          # 64 events
    "https://allevents.in/brooklyn/today",
    "https://allevents.in/brooklyn/this-weekend",
    "https://allevents.in/queens",
    "https://allevents.in/queens/this-weekend",
    "https://allevents.in/manhattan",
    "https://allevents.in/manhattan/this-weekend",
    "https://allevents.in/new-york/free",
    "https://allevents.in/new-york/music",
    "https://allevents.in/new-york/comedy",
    "https://allevents.in/new-york/food",
    "https://allevents.in/new-york/parties",
    "https://allevents.in/new-york/dating",
    "https://allevents.in/new-york/business",
    "https://allevents.in/new-york/art",
    "https://allevents.in/new-york/yoga",
    "https://allevents.in/new-york/running",
    "https://allevents.in/new-york/fitness",
    "https://allevents.in/brooklyn/yoga",
    "https://allevents.in/brooklyn/fitness",
    "https://allevents.in/new-york/coffee",          # 45 events confirmed
    "https://allevents.in/new-york/poetry",
    "https://allevents.in/brooklyn/books",
    # 2026-05-28 self-improve run: close the `bk` topic gap (S1).
    # Each probed live with yield ≥ 8; capped by SOURCE_VOLUME_CAPS["allevents"]=40.
    "https://allevents.in/brooklyn/free",
    "https://allevents.in/brooklyn/dating",
    "https://allevents.in/brooklyn/comedy",
    "https://allevents.in/brooklyn/literature",
    "https://allevents.in/brooklyn/running",
    "https://allevents.in/brooklyn/coffee",
    "https://allevents.in/brooklyn/poetry",
    "https://www.eventbrite.com/d/ny--brooklyn/parties--events/",
    "https://www.eventbrite.com/d/ny--brooklyn/comedy--events/",
    "https://allevents.in/new-york/art-exhibition",
    "https://allevents.in/new-york/gallery",
    # Eventbrite NYC categorical pages — running, yoga, fitness, books, art
    "https://www.eventbrite.com/d/ny--brooklyn/running--events/",
    "https://www.eventbrite.com/d/ny--new-york/running--events/",
    "https://www.eventbrite.com/d/ny--brooklyn/yoga--events/",
    "https://www.eventbrite.com/d/ny--new-york/yoga--events/",
    "https://www.eventbrite.com/d/ny--brooklyn/sports-and-fitness--events/",
    "https://www.eventbrite.com/d/ny--new-york/sports-and-fitness--events/",
    "https://www.eventbrite.com/d/ny--new-york/fitness--events/",
    "https://www.eventbrite.com/d/ny--brooklyn/book-club--events/",
    "https://www.eventbrite.com/d/ny--new-york/book-club--events/",
    "https://www.eventbrite.com/d/ny--brooklyn/literary--events/",
    "https://www.eventbrite.com/d/ny--new-york/literary--events/",
    "https://www.eventbrite.com/d/ny--manhattan/art-gallery--events/",
    "https://www.eventbrite.com/d/ny--brooklyn/art-gallery--events/",
    "https://www.eventbrite.com/d/ny--new-york/art-exhibits--events/",
    "https://www.eventbrite.com/d/ny--new-york/visual-arts--events/",
    "https://www.eventbrite.com/d/ny--new-york/jazz--events/",
    "https://www.eventbrite.com/d/ny--new-york/dance--events/",
    "https://www.eventbrite.com/d/ny--new-york/photography--events/",
    "https://www.eventbrite.com/d/ny--new-york/film--events/",
    "https://www.eventbrite.com/d/ny--new-york/theater--events/",
    "https://www.eventbrite.com/d/ny--new-york/wellness--events/",
    "https://www.eventbrite.com/d/ny--new-york/lgbtq--events/",
    "https://www.eventbrite.com/d/ny--new-york/wine-tasting--events/",
    # Meetup keyword searches: run clubs, yoga, book clubs, coffee meetups
    "https://www.meetup.com/find/?keywords=run+club&location=us--ny--Brooklyn",
    "https://www.meetup.com/find/?keywords=run+club&location=us--ny--New%20York",
    "https://www.meetup.com/find/?keywords=yoga&location=us--ny--Brooklyn",
    "https://www.meetup.com/find/?keywords=yoga&location=us--ny--New%20York",
    "https://www.meetup.com/find/?keywords=book+club&location=us--ny--New%20York",
    "https://www.meetup.com/find/?keywords=coffee&location=us--ny--New%20York",
    "https://www.meetup.com/topics/running/us/ny/new_york/",
    "https://www.meetup.com/topics/yoga/us/ny/new_york/",
    "https://allevents.in/new-york/film",
    "https://allevents.in/new-york/literature",
    "https://allevents.in/new-york/sports",
    "https://allevents.in/new-york/exhibition",
    # Songkick metro pages — major live-music coverage with JSON-LD.
    # Iter 88 audit: path-suffix pagination (`/2`, `/3`, ...) was broken —
    # all those URLs returned the same page-1 49 events, wasting 6 fetches.
    # The correct pagination is `?page=N` query param. Live-verified: each
    # `?page=N` returns ~48 distinct MusicEvent JSON-LD items. Confirmed
    # 1..7 reachable; estimated 337 total events vs 49 today.
    "https://www.songkick.com/metro-areas/7644-us-new-york",
    "https://www.songkick.com/metro-areas/7644-us-new-york?page=2",
    "https://www.songkick.com/metro-areas/7644-us-new-york?page=3",
    "https://www.songkick.com/metro-areas/7644-us-new-york?page=4",
    "https://www.songkick.com/metro-areas/7644-us-new-york?page=5",
    "https://www.songkick.com/metro-areas/7644-us-new-york?page=6",
    "https://www.songkick.com/metro-areas/7644-us-new-york?page=7",
    # Songkick venue pages — major NYC live-music venues (3-8 events each).
    # These compound with the metro page since metro shows top events while
    # venue pages give the full upcoming calendar per venue.
    "https://www.songkick.com/venues/22-brooklyn-bowl",
    "https://www.songkick.com/venues/8-elsewhere",
    "https://www.songkick.com/venues/5-mercury-lounge",
    # Additional NYC music venues discovered via Songkick metro page —
    # huge yield because Songkick reliably parses to JSON-LD MusicEvent
    # and these are the busiest NYC concert venues.
    "https://www.songkick.com/venues/16246-music-hall-of-williamsburg",
    "https://www.songkick.com/venues/316-bowery-ballroom",
    "https://www.songkick.com/venues/181873-irving-plaza",
    "https://www.songkick.com/venues/1025-beacon-theatre",
    "https://www.songkick.com/venues/10735-village-vanguard",
    "https://www.songkick.com/venues/120516-brooklyn-paramount",
    "https://www.songkick.com/venues/2445014-babys-all-right",
    "https://www.songkick.com/venues/28184-le-poisson-rouge",
    "https://www.songkick.com/venues/3457684-brooklyn-steel",
    "https://www.songkick.com/venues/3658119-elsewhere",
    "https://www.songkick.com/venues/3841499-sony-hall",
    "https://www.songkick.com/venues/3895789-rooftop-at-pier-17",
    "https://www.songkick.com/venues/4216319-public-records",
    "https://www.songkick.com/venues/4480562-racket-nyc",
    "https://www.songkick.com/venues/4429540-nebula",
    "https://www.songkick.com/venues/4424442-under-the-k-bridge-park",
    "https://www.songkick.com/venues/1656338-barclays-center",
    "https://www.songkick.com/venues/2470-hammerstein-ballroom-manhattan-center",
    # Universities — public lectures, readings, screenings, free concerts.
    # Most events listed are open to the public; the ones that aren't get
    # filtered by description content.
    "https://events.nyu.edu/",
    "https://events.columbia.edu/",
    "https://events.newschool.edu/",
    "https://www.juilliard.edu/calendar-performances",
    # Public libraries — readings, classes, kid events, talks. NYPL already
    # has a dedicated scraper; these add Brooklyn + Queens.
    "https://www.bklynlibrary.org/calendar",
    "https://www.queenslibrary.org/calendar",
    # Cultural institutions
    "https://www.bam.org/calendar",
    "https://www.lincolncenter.org/lincoln-center-at-home/calendar",
    "https://www.apollotheater.org/events/",
    "https://carnegiehall.org/Calendar",
    # Bookstores beyond McNally / Liz's — high quality literary events
    "https://www.strandbooks.com/events",
    "https://www.greenlightbookstore.com/event",
    "https://www.booksaremagic.net/event",
    "https://www.bookclubbar.com/events",
    "https://www.caveat.nyc/events",
    # Record-store / niche music venues with public events
    "https://www.roughtradenyc.com/events/",
    "https://www.publicrecords.nyc/calendar",
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


_SOURCE_LABEL_ALIASES = {
    # Same platform, different URL domains — normalize to one canonical label
    "lu.ma": "luma",
    "luma.com": "luma",
}


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
                label = f"{slug}.{parts[1]}"
            else:
                label = slug
        else:
            label = host or "generic"
        return _SOURCE_LABEL_ALIASES.get(label, label)
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


# Delegated to the shared helper in scrapers/utils/event_parser.py
_extract_price = parse_offers_price


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

    date_str, start_time = parse_iso_to_local(start)
    _, end_time = parse_iso_to_local(end)
    event_date = parse_date(date_str) if date_str else None
    if not event_date:
        return None

    loc_name, loc_addr = _extract_location(data.get("location"))
    image = _extract_image(data.get("image"))
    price = _extract_price(data.get("offers"))

    url = data.get("url", "") or fallback_url
    if isinstance(url, list) and url:
        url = url[0]
    if isinstance(url, str) and url and not url.startswith("http"):
        url = urljoin(fallback_url, url)

    ev = build_event(
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
    if ev is None:
        return None
    # Stamp organizer name + URL from JSON-LD organizer field if present.
    # Used downstream by normalize._enrich_provenance_from_url to attach
    # follow-graph signal to Eventbrite / Lu.ma events whose organizer is
    # a signal_account.
    org = data.get("organizer")
    if isinstance(org, list) and org:
        org = org[0]
    if isinstance(org, dict):
        org_name = (org.get("name") or "").strip()
        if isinstance(org_name, dict):
            org_name = (org_name.get("@value") or "").strip()
        if org_name:
            ev["organizer"] = org_name[:120]
        org_url = (org.get("url") or "").strip() if isinstance(org.get("url"), str) else ""
        if org_url and not ev.get("organizerUrl"):
            ev["organizerUrl"] = org_url
    return ev


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
        # Bookmanager SPA detection: if the page is a Bookmanager-powered
        # bookstore (Book Club Bar pattern), fetch the events via their
        # hidden API in the same run — no 2-cycle indirection.
        try:
            from ..utils.bookmanager import is_bookmanager, detect_san, scrape_san
            if is_bookmanager(html):
                san = detect_san(html)
                if san:
                    parsed = urlparse(url)
                    label = (parsed.netloc.lower().replace("www.", "").split(".")[0]
                             or "bookmanager")
                    public_tmpl = f"{parsed.scheme}://{parsed.netloc}/events/{{event_id}}"
                    bm_events = await scrape_san(
                        san=san,
                        source_label=label,
                        public_url_template=public_tmpl,
                    )
                    if bm_events:
                        events.extend(bm_events)
                        print(f"[generic] {url}: Bookmanager API → {len(bm_events)} events (SAN={san})")
        except Exception as exc:
            print(f"[generic] {url}: Bookmanager probe failed: {exc}")

    if not events:
        # Squarespace platform detection: many small venues are on
        # Squarespace, which exposes a reliable iCal feed at ?format=ical.
        # The React shell HTML returns 0 events to JSON-LD/OG, but the iCal
        # feed has the full event list. Same pattern as Bookmanager —
        # detect once, scrape any venue on the platform.
        try:
            from ..utils.squarespace import try_scrape_ical_for_squarespace
            parsed = urlparse(url)
            label = (parsed.netloc.lower().replace("www.", "").split(".")[0]
                     or "squarespace")
            ss_events = await try_scrape_ical_for_squarespace(url, html, label)
            if ss_events:
                events.extend(ss_events)
                print(f"[generic] {url}: Squarespace iCal → {len(ss_events)} events")
        except Exception as exc:
            print(f"[generic] {url}: Squarespace probe failed: {exc}")

    if not events:
        # Salvage pass: many venue sites are React/Next/Vue SPAs that return
        # JS-rendered content with 0 parseable JSON-LD/OG. BUT the raw HTML
        # almost always contains /events/<id> or /show/<id> links (nav,
        # hydration JSON, sitemap snippets) we can mine for canonical event
        # URLs. Each found URL gets queued to discovered_urls.json for
        # direct fetch on the next run — same pattern as Book Club Bar but
        # generalized for any venue. This is the difference between a
        # venue showing 0 events and showing all of them.
        salvaged = _salvage_event_urls_from_html(html, url)
        if salvaged:
            print(f"[generic] {url}: SPA salvage → +{salvaged} event URLs queued for next run")
            # Salvage counts as success — the URL DID surface event content,
            # we just need an extra hop. Reset the failure counter so the
            # URL doesn't get marked dead while it's actively producing
            # downstream discoveries.
            _record_url_success(url, event_count=0)
        else:
            _record_url_failure(url)
    else:
        _record_url_success(url, event_count=len(events))
        # Auto-discover Eventbrite organizer pages from event URLs.
        # An organizer typically hosts dozens of NYC events.
        if "eventbrite.com/e/" in url:
            organizer_url = _extract_eventbrite_organizer(soup)
            if organizer_url:
                _add_discovered_url(organizer_url, "eventbrite_organizer")

        # Auto-discover Lu.ma curator calendars via organizer URL in JSON-LD.
        # Each Lu.ma event JSON-LD includes organizer.url which is typically
        # lu.ma/<calendar-slug> — and those calendars often host 10-20+ NYC
        # events. Self-improving: each event we scrape can surface a new
        # curator we should follow directly.
        if "lu.ma/" in url or "luma.com/" in url:
            try:
                _harvest_luma_curator_urls(soup)
            except Exception:
                pass

        # Sitemap mining: try once per host (not every URL) to avoid spam.
        # When the host has /sitemap.xml, we can harvest every event URL on
        # the venue's site at once instead of crawling page-by-page.
        try:
            await _maybe_harvest_sitemap(url)
        except Exception as e:
            print(f"[generic] {url}: sitemap harvest failed: {e}")

        # Canonical event-path probe: enqueue /events, /events/, /calendar
        # for any new venue host. Generalizes the book-club-bar pattern so
        # we don't need per-venue scrapers. Idempotent + cheap (just adds
        # to discovery pool — actual fetches happen on next run, gated by
        # url_health pruning if the paths 404).
        try:
            _maybe_probe_event_paths(url)
        except Exception as e:
            print(f"[generic] {url}: event-path probe failed: {e}")

    return events


# Patterns that look like a venue's canonical event-detail URL inside the
# raw HTML of a SPA index page. We're conservative: numeric IDs (Bookmanager,
# Eventbrite-like), slug formats with hyphens, and common path segments.
# We deliberately AVOID matching arbitrary paths like /about or /contact.
_SALVAGE_PATH_RES = [
    # /events/<digits>      — Bookmanager (Book Club Bar style)
    re.compile(r'(?:href|"url"|"path")\s*[:=]\s*"(/events/\d{6,18})\b', re.IGNORECASE),
    # /events/<slug-with-hyphens>  — common WordPress-event style
    re.compile(r'href="(/events/[a-z0-9][a-z0-9\-]{4,80})"', re.IGNORECASE),
    # /event/<digits-or-slug>
    re.compile(r'href="(/event/[a-z0-9][a-z0-9\-]{2,80})"', re.IGNORECASE),
    # /show/<slug>  — common at small concert venues
    re.compile(r'href="(/shows?/[a-z0-9][a-z0-9\-]{4,80})"', re.IGNORECASE),
    # /e/<id>  — Eventbrite-style shortcodes
    re.compile(r'href="(/e/[a-z0-9\-]{4,80})"', re.IGNORECASE),
    # Absolute event URLs in any inline JSON/text — captures patterns
    # like {"url":"https://venue.com/events/123"} in hydration state.
    re.compile(r'"(https?://[^"]+/events?/(?:[a-z0-9][a-z0-9\-]{3,80}|\d{6,18}))"', re.IGNORECASE),
]

# Cap salvage output per page so a sitemap-style payload listing thousands
# of historical events doesn't explode discovered_urls.json.
_SALVAGE_CAP_PER_PAGE = 30


def _salvage_event_urls_from_html(html: str, base_url: str) -> int:
    """Extract canonical event URLs from a 0-event page's raw HTML and
    queue them as discovered URLs. Returns count of NEWLY queued URLs.

    This generalizes the Book Club Bar pattern: many venue sites are
    JS-rendered SPAs whose index page shows nothing to JSON-LD/OG
    parsers, but the raw HTML still contains nav links and hydration
    state with the actual event URLs. Mining those gives us the canonical
    event pages — which are server-side-rendered and have proper
    JSON-LD/OG, so the next-run generic fetch parses them cleanly.
    """
    if not html or len(html) < 200:
        return 0
    parsed = urlparse(base_url)
    if not parsed.netloc:
        return 0
    base = f"{parsed.scheme}://{parsed.netloc}"

    found: set[str] = set()
    for r in _SALVAGE_PATH_RES:
        for m in r.finditer(html):
            path = m.group(1)
            # Convert relative to absolute. Skip if path is identical to
            # base_url's path (don't add the index page back to itself).
            if path.startswith("http"):
                url = path
            else:
                url = base + path
            # Drop URL fragments / trailing punctuation
            url = url.split("#")[0].rstrip(".,;:!?)")
            # Skip self-references (index page linking to itself)
            if url.rstrip("/") == base_url.rstrip("/"):
                continue
            # Same-host only — don't accidentally harvest a CDN link
            try:
                if urlparse(url).netloc.lower() != parsed.netloc.lower():
                    continue
            except Exception:
                continue
            found.add(url)
            if len(found) >= _SALVAGE_CAP_PER_PAGE:
                break
        if len(found) >= _SALVAGE_CAP_PER_PAGE:
            break

    if not found:
        return 0

    added = 0
    bare_host = parsed.netloc.lower()
    if bare_host.startswith("www."):
        bare_host = bare_host[4:]
    src_label = f"spa-salvage:{bare_host}"
    for u in found:
        try:
            _add_discovered_url(u, src_label)
            added += 1
        except Exception:
            pass
    return added


_SITEMAP_TRIED_HOSTS: set[str] = set()
_EVENT_PATH_PROBED_HOSTS: set[str] = set()

# Hosts where probing /events makes no sense — they're aggregator platforms,
# IG/social, or hosts whose canonical event-listing URLs we already seed.
_PROBE_SKIP_HOSTS = {
    "instagram.com", "www.instagram.com",
    "facebook.com", "www.facebook.com", "m.facebook.com",
    "twitter.com", "x.com", "t.co",
    "lu.ma", "luma.com", "www.lu.ma",
    "eventbrite.com", "www.eventbrite.com",
    "meetup.com", "www.meetup.com",
    "partiful.com", "www.partiful.com",
    "allevents.in", "www.allevents.in",
    "songkick.com", "www.songkick.com",
    "dice.fm", "www.dice.fm",
    "ra.co", "www.ra.co",
    "ticketmaster.com", "www.ticketmaster.com",
    "ticketweb.com", "www.ticketweb.com",
    "youtube.com", "www.youtube.com", "youtu.be",
    "tiktok.com", "www.tiktok.com",
    "linktr.ee", "beacons.ai", "linkin.bio", "bio.link",
    "google.com", "maps.google.com",
    "substack.com",
}


def _maybe_probe_event_paths(url: str) -> None:
    """Once per venue host, register canonical event-listing paths
    (/events, /events/, /calendar) as discovered URLs.

    Generalizes the book-club-bar pattern: when we scrape a single event
    page like venue.com/events/1234, the venue almost certainly has a
    /events index page that lists everything else. Adding it to the
    discovery pool lets the next pipeline run pick it up automatically
    — no per-venue scraper needed.

    Cheap and idempotent: just enqueues paths. url_health prunes any
    that 404 after a few attempts.
    """
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if not host or host in _EVENT_PATH_PROBED_HOSTS:
        return
    _EVENT_PATH_PROBED_HOSTS.add(host)

    # Skip if the host is itself the aggregator (we already seed those).
    bare_host = host[4:] if host.startswith("www.") else host
    if host in _PROBE_SKIP_HOSTS or bare_host in _PROBE_SKIP_HOSTS:
        return
    # Don't probe if the URL already IS one of those canonical paths.
    path = (parsed.path or "/").rstrip("/").lower()
    if path in ("/events", "/calendar", "/events/calendar"):
        return

    base = f"{parsed.scheme}://{parsed.netloc}"
    candidates = [
        f"{base}/events",
        f"{base}/events/",
        f"{base}/calendar",
    ]
    added = 0
    for cand in candidates:
        # Stay idempotent — _add_discovered_url is no-op on duplicates.
        try:
            _add_discovered_url(cand, f"path-probe:{bare_host}")
            added += 1
        except Exception:
            pass
    if added:
        print(f"[generic] {host}: probed canonical event paths (+{added} URLs)")


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


_LUMA_CALENDAR_SLUG_RE = re.compile(
    r"^https?://(?:www\.)?(?:lu\.ma|luma\.com)/([a-z0-9][a-z0-9._-]{2,40})/?$",
    re.IGNORECASE,
)
_LUMA_EVENT_SHORTCODE_RE = re.compile(r"^[a-z0-9]{6,10}$", re.IGNORECASE)


def _harvest_luma_curator_urls(soup: BeautifulSoup) -> int:
    """Walk the page's JSON-LD scripts; whenever an event's organizer.url
    is a lu.ma calendar slug (not an event shortcode), add it to the
    discovered URL pool. Compounds: each event we scrape can surface a
    new high-yield curator calendar.
    """
    found: set[str] = set()
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text() or ""
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        _walk_for_organizer_urls(data, found)
    if not found:
        return 0
    added = 0
    for u in found:
        m = _LUMA_CALENDAR_SLUG_RE.match(u)
        if not m:
            continue
        slug = m.group(1)
        # Skip event shortcodes (8-10 alphanumeric, no hyphen) — those are
        # individual events, not calendars. Calendars typically have hyphens
        # or descriptive names.
        if _LUMA_EVENT_SHORTCODE_RE.match(slug) and "-" not in slug and "." not in slug and "_" not in slug:
            continue
        normalized = f"https://lu.ma/{slug}"
        _add_discovered_url(normalized, "luma_organizer_jsonld")
        added += 1
    return added


def _walk_for_organizer_urls(node, out: set[str], depth: int = 0) -> None:
    """Recursively find any organizer.url in JSON-LD."""
    if depth > 8 or node is None:
        return
    if isinstance(node, list):
        for item in node:
            _walk_for_organizer_urls(item, out, depth + 1)
        return
    if not isinstance(node, dict):
        return
    org = node.get("organizer")
    if isinstance(org, dict):
        u = org.get("url") or org.get("sameAs")
        if isinstance(u, str) and u.startswith("http"):
            out.add(u)
    elif isinstance(org, list):
        for o in org:
            if isinstance(o, dict):
                u = o.get("url") or o.get("sameAs")
                if isinstance(u, str) and u.startswith("http"):
                    out.add(u)
    # Recurse into common nested fields
    for key in ("@graph", "itemListElement", "events", "event"):
        if key in node:
            _walk_for_organizer_urls(node[key], out, depth + 1)


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


def _record_url_success(url: str, event_count: int = 0) -> None:
    from datetime import datetime, timezone
    data = _load_url_health()
    entry = data.setdefault(url, {"failures": 0, "successes": 0})
    entry["successes"] = entry.get("successes", 0) + 1
    entry["failures"] = 0  # reset on success
    entry["last_success_at"] = datetime.now(timezone.utc).isoformat()
    # Cumulative event yield — drives scrape rotation priority and lets us
    # spot URLs that "succeed" (return 200) but never produce events.
    entry["events_emitted_total"] = entry.get("events_emitted_total", 0) + event_count
    entry["last_event_count"] = event_count
    _save_url_health(data)


def _url_event_yield(url: str, health: dict | None = None) -> float:
    """Return mean events-per-successful-scrape for a URL, or 0 if no data."""
    if health is None:
        health = _load_url_health()
    entry = health.get(url, {})
    successes = entry.get("successes", 0)
    if successes < 2:
        return 0.0  # not enough data
    total = entry.get("events_emitted_total", 0)
    return total / successes


def _is_dead_url(url: str) -> bool:
    """A URL is dead if it has 5+ failures with no recent successes."""
    data = _load_url_health()
    entry = data.get(url, {})
    return entry.get("failures", 0) >= 5


_RETEST_COOLDOWN_DAYS = 7
_RETEST_PER_RUN = 5
# A URL with this many failures AND zero lifetime successes AND a stale
# last-failure timestamp is considered permanently dead. Prune it from
# both discovered_urls.json and url_health.json so the pool stays lean.
_PRUNE_FAILURE_THRESHOLD = 12
_PRUNE_AGE_DAYS = 30


def _prune_stale_urls() -> int:
    """Remove permanently-dead URLs from the discovery pool and url_health.

    Criteria (must meet ALL):
      - failures >= _PRUNE_FAILURE_THRESHOLD
      - successes == 0 (never emitted an event)
      - last_failure_at older than _PRUNE_AGE_DAYS

    Returns count of pruned URLs. Idempotent.
    """
    from datetime import datetime, timezone, timedelta
    health = _load_url_health()
    if not health:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=_PRUNE_AGE_DAYS)

    # Identify dead URLs to remove
    dead: set[str] = set()
    for url, entry in health.items():
        if entry.get("successes", 0) > 0:
            continue
        if entry.get("failures", 0) < _PRUNE_FAILURE_THRESHOLD:
            continue
        last_fail = entry.get("last_failure_at", "")
        try:
            ts = datetime.fromisoformat(last_fail)
        except Exception:
            # Legacy entry without timestamp — let it be eligible.
            dead.add(url)
            continue
        if ts < cutoff:
            dead.add(url)

    if not dead:
        return 0

    # Don't ever prune URLs from the seed list (GENERIC_URLS) — those are
    # editorial decisions; let them sit and be re-tested via the retest path.
    seed_urls = set(GENERIC_URLS)
    dead -= seed_urls
    if not dead:
        return 0

    # Drop from url_health
    for u in dead:
        health.pop(u, None)
    _save_url_health(health)

    # Drop from discovered_urls.json
    if os.path.isfile(DISCOVERED_URLS_PATH):
        try:
            with open(DISCOVERED_URLS_PATH) as f:
                data = json.load(f)
            items = data if isinstance(data, list) else data.get("urls", [])
            kept = [
                it for it in items
                if (it["url"] if isinstance(it, dict) else it) not in dead
            ]
            os.makedirs(os.path.dirname(DISCOVERED_URLS_PATH), exist_ok=True)
            tmp = DISCOVERED_URLS_PATH + ".tmp"
            with open(tmp, "w") as f:
                json.dump(kept, f, indent=2)
            os.replace(tmp, DISCOVERED_URLS_PATH)
        except Exception as exc:
            print(f"[generic] prune: failed to update discovered_urls: {exc}")

    return len(dead)


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
    # Pool hygiene first — drop URLs that are long-dead (12+ failures,
    # 0 successes, last failure 30+ days ago) so the pool doesn't grow
    # unboundedly. Seed URLs from GENERIC_URLS are never pruned.
    pruned = _prune_stale_urls()
    if pruned:
        print(f"[generic] Pruned {pruned} permanently-dead URLs from discovery pool")

    urls: list[str] = list(GENERIC_URLS)
    urls.extend(_dynamic_calendar_urls())

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

    # Order URLs by historical event yield so high-yield sources scrape first.
    # Untracked URLs (no successes yet) get a neutral middle priority so they
    # still get a fair shot. Tier scheme:
    #   tier 0: yield >= 5 events/scrape  (top performers)
    #   tier 1: yield >= 1 events/scrape  (steady contributors)
    #   tier 2: untracked / new           (give them a chance)
    #   tier 3: yield < 1 events/scrape   (consistently dry)
    # Within each tier, sort by yield desc.
    def _yield_priority(u: str) -> tuple[int, float]:
        y = _url_event_yield(u, health)
        successes = health.get(u, {}).get("successes", 0)
        if successes < 2:
            return (2, 0.0)
        if y >= 5:
            return (0, -y)
        if y >= 1:
            return (1, -y)
        return (3, -y)
    urls = sorted(urls, key=_yield_priority)

    all_events: list[dict] = []
    for url in urls:
        try:
            events = await scrape_url(url)
            all_events.extend(events)
        except Exception as e:
            print(f"[generic] {url}: ERROR {e}")
    return all_events
