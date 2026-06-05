import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from bs4 import BeautifulSoup
from ..utils.http import fetch_text
from ..utils.event_parser import build_event, parse_date, parse_time, infer_categories

# Authoritative event-platform URLs that appear in newsletter post bodies.
# Substack newsletter posts like "10 NYC events this weekend" link directly
# to canonical event pages — harvesting those URLs feeds the generic scraper
# on the next pipeline run for full structured data.
_EVENT_PLATFORM_RE = re.compile(
    r"https?://(?:www\.)?(?:"
    r"lu\.ma/[A-Za-z0-9._-]+|"
    r"luma\.com/[A-Za-z0-9._-]+|"
    r"eventbrite\.com/(?:e|cc|o)/[^\s)>\]\"'<]+|"
    r"partiful\.com/e/[A-Za-z0-9._-]+|"
    r"posh\.vip/e/[^\s)>\]\"'<]+|"
    r"ra\.co/(?:events|promoters)/[^\s)>\]\"'<]+|"
    r"dice\.fm/event/[^\s)>\]\"'<]+|"
    r"shotgun\.live/(?:[a-z]{2}/)?events/[^\s)>\]\"'<]+|"
    r"tixr\.com/(?:groups|e)/[^\s)>\]\"'<]+|"
    r"meetup\.com/[^\s)>\]\"'<]+/events/[^\s)>\]\"'<]+"
    r")",
    re.IGNORECASE,
)

_DISCOVERED_URLS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "discovered_urls.json",
)


def _harvest_and_save_post_urls(html_or_text: str) -> int:
    """Harvest event-platform URLs from a post body and add to discovered_urls.

    Returns count of NEWLY-added URLs (existing ones are deduped silently).
    """
    if not html_or_text:
        return 0
    found = set()
    for m in _EVENT_PLATFORM_RE.finditer(html_or_text):
        url = m.group(0).rstrip(".,;:!?)").split("#")[0]
        found.add(url)
    if not found:
        return 0
    # Load existing
    existing: list = []
    if os.path.isfile(_DISCOVERED_URLS_PATH):
        try:
            with open(_DISCOVERED_URLS_PATH) as f:
                d = json.load(f)
            existing = d if isinstance(d, list) else d.get("urls", [])
        except Exception:
            existing = []
    seen = {it["url"] if isinstance(it, dict) else it for it in existing}
    added = 0
    now = datetime.now(timezone.utc).isoformat()
    for url in found:
        if url in seen:
            continue
        existing.append({"url": url, "discovered_at": now, "discovered_via": "substack_body"})
        seen.add(url)
        added += 1
    if added:
        try:
            os.makedirs(os.path.dirname(_DISCOVERED_URLS_PATH), exist_ok=True)
            tmp = _DISCOVERED_URLS_PATH + ".tmp"
            with open(tmp, "w") as f:
                json.dump(existing, f, indent=2)
            os.replace(tmp, _DISCOVERED_URLS_PATH)
        except Exception as e:
            print(f"[substack] Failed to save discovered URLs: {e}")
    return added

FEEDS = [
    "https://onefinedaynyc.substack.com/feed",
    # The Skint — daily curated free/cheap NYC events newsletter (legendary)
    "https://www.theskint.com/feed/",
    # Brooklyn Vegan — extensive concert / live music NY listings
    "https://www.brooklynvegan.com/feed/",
    # (Removed: hyperallergic.com — mostly art news/commentary, not events.
    # Posts like 'Getty Awards $1.8M for Archives' or 'What Does a Booth
    # Cost at an Art Fair?' are news articles. We get art-opening coverage
    # through bedfordandbowery, the venue sources, and IG instead.)
    # (Removed iter 124: thedeli.substack.com — STALE per audit_urls.py:
    # 4 events, 0 future, 0 URL harvest. Music venues already covered by
    # Songkick + per-venue scrapers.)
    # Eater NY — food/restaurant pop-ups, supper clubs, food events
    "https://ny.eater.com/rss/index.xml",
    # (Removed iter 114: bedfordandbowery.com — confirmed dead since 2021.)
    # (Removed: hellgate.substack.com, gothamist.com — news outlets.)
    # (Removed iter 87: untappedcities.com/feed/ + nycgovparks.org/news.rss
    # — both 404.)
    # (Removed iter 124: nycforfree.substack.com — STALE per audit_urls.py:
    # 3 events, 0 future, 0 URL harvest. The .co site is covered by the
    # iter-100 nycforfree.py Squarespace scraper.)
    # (Removed iter 124: brokelyn.com/feed/ — STALE: 8 events, 0 future,
    # 0 URL harvest. Site appears to have stopped publishing events.)
]

# Patterns that look like dates within event text
DATE_PATTERNS = [
    # "May 10" / "May 10th" / "May 10, 2026"
    r"((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?(?:[,\s]+\d{4})?)",
    # "1/15" / "01/15/2026"
    r"(\d{1,2}/\d{1,2}(?:/\d{2,4})?)",
]


async def scrape() -> list[dict]:
    events = []
    total_url_added = 0
    for feed_url in FEEDS:
        try:
            xml_text = await fetch_text(feed_url)
            feed_events, urls_added = _parse_feed(xml_text)
            events.extend(feed_events)
            total_url_added += urls_added
        except Exception as e:
            print(f"[substack] Failed to fetch {feed_url}: {e}")
    if total_url_added:
        print(f"[substack] Harvested {total_url_added} event-platform URLs from post bodies")
    return events


def _parse_feed(xml_text: str) -> tuple[list[dict], int]:
    events = []
    urls_added = 0
    root = ET.fromstring(xml_text)

    # RSS feeds use <channel><item> structure
    ns = {"content": "http://purl.org/rss/1.0/modules/content/"}
    channel = root.find("channel")
    items: list = []
    if channel is not None:
        items = list(channel.findall("item"))
    else:
        # Atom feeds use <feed><entry> with a default xmlns (iter 96 audit:
        # eaterny ships Atom not RSS and was extracting 0 events).
        atom_ns = {"a": "http://www.w3.org/2005/Atom"}
        items = list(root.findall("a:entry", atom_ns))

    if not items:
        return events, 0

    # Process the most recent 8 posts (was 3) — captures more weekly guides
    for item in items[:8]:
        try:
            events.extend(_parse_item(item, ns))
            # Harvest authoritative event-platform URLs from post body —
            # newsletter posts often link to lu.ma/eventbrite/etc. directly.
            body = (
                item.findtext("content:encoded", "", namespaces=ns)
                or item.findtext("description", "")
                or item.findtext("{http://www.w3.org/2005/Atom}content", "")
                or item.findtext("{http://www.w3.org/2005/Atom}summary", "")
            )
            urls_added += _harvest_and_save_post_urls(body)
        except Exception as e:
            title = item.findtext("title", "unknown")
            print(f"[substack] Error parsing item '{title}': {e}")
    return events, urls_added


def _parse_item(item, ns: dict) -> list[dict]:
    events = []
    # RSS first, then Atom-namespaced fallback (iter 96).
    post_title = (
        item.findtext("title", "")
        or item.findtext("{http://www.w3.org/2005/Atom}title", "")
        or ""
    )
    post_link = item.findtext("link", "") or ""
    pub_date_str = item.findtext("pubDate", "") or ""

    # Atom fallback (iter 96): <link rel="alternate" href="...">, <published>
    if not post_link:
        for link_el in item.findall("{http://www.w3.org/2005/Atom}link"):
            rel = link_el.get("rel", "alternate")
            if rel == "alternate":
                post_link = link_el.get("href", "")
                break
    if not pub_date_str:
        pub_date_str = (
            item.findtext("{http://www.w3.org/2005/Atom}published", "")
            or item.findtext("{http://www.w3.org/2005/Atom}updated", "")
            or ""
        )

    # Get the full HTML content from content:encoded
    content_encoded = item.findtext("content:encoded", "", namespaces=ns)
    if not content_encoded:
        # Fallback to description, then Atom summary/content
        content_encoded = (
            item.findtext("description", "")
            or item.findtext("{http://www.w3.org/2005/Atom}content", "")
            or item.findtext("{http://www.w3.org/2005/Atom}summary", "")
        )

    if not content_encoded:
        return events

    # Parse the post publication date as fallback
    fallback_date = parse_date(pub_date_str) if pub_date_str else None

    soup = BeautifulSoup(content_encoded, "html.parser")

    # One Fine Day NYC-style posts mark each curated event with a 📍 pin +
    # ☁️ date. When present, parse those precisely — the structure is clean
    # and deterministic, unlike the heading-fragment heuristic which mangles
    # these posts into duplicate / mis-dated / mis-linked fragments.
    # (The pin arrives HTML-encoded as &#128205; in the raw XML, so test the
    # DECODED soup text, not content_encoded.)
    if _PIN in soup.get_text():
        pin_events = _extract_pin_marker_events(
            soup, fallback_date, post_link, fallback_date
        )
        if pin_events:
            return pin_events

    # Iter 94: roundup vs single-event detection. Newsletters like theskint
    # mix two post shapes — multi-event roundups whose titles start with a
    # day-pair like "WEDS-THURS, 5/27-28: ..." AND single-event posts like
    # "CELEBRATE THE MODERN AMERICAN THEATER AT HB STUDIO'S FESTIVAL".
    # The default heading-fragmentation path produces 100+ fragments from a
    # single non-roundup post (button text, paragraph subheads).
    is_roundup_title = _looks_like_roundup(post_title)

    # Strategy: find headings (h2, h3, strong, b) that likely denote event titles,
    # then gather the text and links that follow until the next heading.
    heading_tags = soup.find_all(["h2", "h3", "strong", "b"]) if is_roundup_title else []

    if heading_tags:
        events.extend(_extract_from_headings(soup, heading_tags, fallback_date, post_link))
    else:
        # Fallback: treat the whole post as one event. But a roundup/guide
        # title ("Your June Guide to NYC", "NYC This Week | …", "May Calendar")
        # is a CONTAINER of events, never itself a single event — emitting it
        # produces a junk promo card (especially for now-paywalled monthly
        # guides that ship only an intro + "Read more").
        text = soup.get_text(separator=" ", strip=True)
        if (fallback_date and len(post_title) > 5
                and not _looks_like_news_title(post_title)
                and not _looks_like_roundup(post_title)
                and not _re.search(r"\b(guide|calendar)\b", post_title, _re.IGNORECASE)):
            events.append(build_event(
                title=post_title,
                description=text[:500],
                event_date=fallback_date,
                source="substack",
                source_url=post_link,
                categories=infer_categories(post_title, text[:500]),
            ))

    return events


# News-headline detection. Substack feeds (especially gothamist, hellgate-
# style outlets that slip through) emit news articles as RSS posts. These
# get parsed as 'events' even though they're commentary on past events
# or general news. Patterns: passive voice, "X-year-old shot", question
# titles like "What is...", "How can...", etc.
import re as _re

_NEWS_TITLE_PATTERNS = [
    _re.compile(r"\b\d+[-\s]?year[-\s]?old\b", _re.IGNORECASE),
    _re.compile(r"\b(shot|killed|stabbed|attacked|arrested|sentenced|indicted|fired|"
                r"resigned|injured|hospitalized) (in|near|at|by|after)\b", _re.IGNORECASE),
    _re.compile(r"\b(police|nypd|fdny|mta|fbi|doj) (say|seek|search|investigate|"
                r"arrest|charge|release)", _re.IGNORECASE),
    _re.compile(r"\b(governor|mayor|senator|congressman|councilman|hochul|adams|"
                r"cuomo|trump|biden) (says|endorses|announces|signs|vetoes|denies)",
                _re.IGNORECASE),
    _re.compile(r"^(what|why|how|is|are|do|does|can|will|should) ", _re.IGNORECASE),
    _re.compile(r"\b(early addition|morning briefing|news briefing|daily digest)\b",
                _re.IGNORECASE),
    _re.compile(r"\b(idf|israel|gaza|palestin|hamas) ", _re.IGNORECASE),
    _re.compile(r"\b(fire (breaks|broke) out|breaks? out at|service (disrupted|suspended))\b",
                _re.IGNORECASE),
    _re.compile(r"\b(remembering|in memoriam|tribute to) [A-Z]", _re.IGNORECASE),
    _re.compile(r"\b(awarded?|wins?|named|appointed|hired|gets?\s+new) (chief|director|"
                r"curator|president|ceo|head)\b", _re.IGNORECASE),
    _re.compile(r"\b(essential\s+\w+\s+to\s+know|things?\s+to\s+know|"
                r"rights\s+to\s+know)", _re.IGNORECASE),
]


def _looks_like_news_title(title: str) -> bool:
    """Detect news-article titles that aren't events.

    Substack fallback path emits the whole RSS post as an event when there
    are no h2/h3 headings. For news outlets this means every news article
    becomes a fake event. Filter those out.
    """
    if not title:
        return False
    for pat in _NEWS_TITLE_PATTERNS:
        if pat.search(title):
            return True
    return False


# Retail / non-event hosts that newsletter authors link to for affiliate
# revenue. An "event" sourceUrl pointing to one of these is a product pick,
# not an event.
_AFFILIATE_HOSTS = (
    "amazon.com", "amzn.to",
    "jcrew.com", "macys.com", "apple.com", "llbean.com",
    "shopstyle.com", "rewardstyle.com", "ltk.com", "shopmy.us",
    "distrokid.com", "mirror.xyz", "audius.co", "spotify.com",
    "variety.com", "gofundme.com",
    "twitter.com", "x.com",  # social-link spam in newsletter footers
)


# Roundup-title detection (iter 94). Theskint and similar newsletters use
# weekday-pair prefixes for multi-event roundups: "WEDS-THURS, 5/27-28:",
# "FRI-TUES, 5/22-26:", "MON, 6/3:". Posts WITHOUT this shape are typically
# single-event sponsored posts and should be parsed as one event each.
_ROUNDUP_TITLE_RE = _re.compile(
    r"^\s*"
    r"(?:mon|tue|tues|wed|weds|thu|thur|thurs|fri|sat|sun)s?"
    r"\s*[-,/&]\s*"  # separator
    r"(?:mon|tue|tues|wed|weds|thu|thur|thurs|fri|sat|sun)s?"
    r"\s*[,:]",
    _re.IGNORECASE,
)
# Also: "MON, 6/3:" or "WEDS, 5/27:" — single day + date + colon
_SINGLE_DAY_ROUNDUP_RE = _re.compile(
    r"^\s*"
    r"(?:mon|tue|tues|wed|weds|thu|thur|thurs|fri|sat|sun)s?"
    r"\s*,\s*\d{1,2}/\d{1,2}\s*:",
    _re.IGNORECASE,
)
# Weekly-digest titles like "NYC This Week | May 27 - 31",
# "Your May Guide to NYC", "NYC Weekend Guide: ...". Different shape from
# theskint's weekday-prefix posts but same structure inside — proper h2/h3 +
# strong tags listing the actual events. Trigger the heading-extraction
# path so the embedded events surface (instead of dropping the whole post
# as one un-actionable event titled "NYC This Week | ...").
_WEEKLY_DIGEST_TITLE_RE = _re.compile(
    r"(?:"
    r"\bNYC\s+(?:this\s+)?(?:week|weekend)\b"     # "NYC This Week", "NYC Weekend"
    r"|\bweekend\s+(?:guide|picks?|edit|roundup)\b"
    r"|\bguide\s+to\s+NYC\b"                       # "Your May Guide to NYC"
    r"|\bweekly\s+(?:digest|roundup|picks?)\b"
    r")",
    _re.IGNORECASE,
)


def _looks_like_roundup(title: str) -> bool:
    if not title:
        return False
    return bool(
        _ROUNDUP_TITLE_RE.match(title)
        or _SINGLE_DAY_ROUNDUP_RE.match(title)
        or _WEEKLY_DIGEST_TITLE_RE.search(title)
    )


def _is_affiliate_noise(title: str, source_url: str) -> bool:
    """True if the heading is a product affiliate / non-event link, not an
    actual event. Pattern: title ending in `(link)` OR sourceUrl pointing to
    a retail / non-NYC-event host."""
    t = (title or "").strip().lower()
    if t.endswith("(link)") or t.endswith("[link]"):
        return True
    try:
        from urllib.parse import urlparse
        host = (urlparse(source_url or "").hostname or "").replace("www.", "").lower()
    except Exception:
        return False
    return any(h in host for h in _AFFILIATE_HOSTS)


def _extract_from_headings(soup, heading_tags, fallback_date, post_link: str) -> list[dict]:
    events = []
    seen_titles = set()

    for heading in heading_tags:
        title = heading.get_text(strip=True)
        # Skip very short or generic headings
        if len(title) < 4 or title.lower() in seen_titles:
            continue
        # Skip headings that are just generic section headers. Both literal
        # strings AND structural patterns — onefinedaynyc uses h2s like
        # "NYC Local Events I'm Excited About This Week" / "Taylor's Top
        # Picks" / "NYC Small Businesses / Local Finds" to organize the
        # newsletter. They aren't events themselves; treating them as
        # event titles produces dateless garbage that needs to be filtered
        # downstream.
        t_lower = title.lower()
        if t_lower in ("events", "this week", "this weekend", "highlights", "more", "links"):
            continue
        if _re.search(
            r"\b(nyc\s+local\s+events|top\s+picks?|small\s+businesses|local\s+finds|"
            r"i'?m\s+excited|excited\s+about|this\s+(week|weekend)\s*$)",
            t_lower,
        ):
            continue

        seen_titles.add(title.lower())

        # Gather subsequent text until the next heading
        description_parts = []
        source_url = post_link
        event_date = None

        # Collect siblings after this heading
        sibling = heading.find_next_sibling()
        while sibling and sibling.name not in ("h2", "h3"):
            # If this sibling is or contains a strong/b that is also in our heading list, stop
            if sibling.name in ("strong", "b") and sibling in heading_tags:
                break
            text = sibling.get_text(strip=True)
            if text:
                description_parts.append(text)
            # Look for links
            links = sibling.find_all("a", href=True) if hasattr(sibling, "find_all") else []
            for link in links:
                href = link.get("href", "")
                if href and href.startswith("http") and "substack" not in href:
                    source_url = href
                    break
            sibling = sibling.find_next_sibling()

        # Also check parent's next siblings if heading was inside a <p>
        if not description_parts and heading.parent and heading.parent.name == "p":
            parent_text = heading.parent.get_text(strip=True)
            # Remove the heading text itself
            remaining = parent_text.replace(title, "", 1).strip()
            if remaining:
                description_parts.append(remaining)
            # Check for links in parent
            for link in heading.parent.find_all("a", href=True):
                href = link.get("href", "")
                if href and href.startswith("http") and "substack" not in href:
                    source_url = href
                    break
            # Continue with parent's siblings
            sibling = heading.parent.find_next_sibling()
            while sibling and sibling.name not in ("h2", "h3"):
                if sibling.find(["strong", "b"]):
                    # Check if this strong/b is another heading
                    inner = sibling.find(["strong", "b"])
                    if inner and inner in heading_tags:
                        break
                text = sibling.get_text(strip=True)
                if text:
                    description_parts.append(text)
                sibling = sibling.find_next_sibling()

        description = " ".join(description_parts)[:500]
        combined_text = f"{title} {description}"

        # Try to extract a date from the title or description
        event_date = _extract_date(combined_text)
        if not event_date:
            event_date = fallback_date

        if not event_date:
            continue

        # If the title is just a date like "May 16" or "May 16th", promote the
        # first meaningful sentence from the description as the actual title.
        if _is_date_only_title(title):
            real_title = _extract_real_title_from_desc(description)
            if real_title:
                title = real_title

        # Skip if we still have a low-quality title
        if _is_date_only_title(title) or len(title) < 8:
            continue

        # Skip product-affiliate noise (iter 87, fb-128). Substack newsletters
        # often embed product picks alongside events: "J.Crew Cosmo pant in
        # luster charmeuse (link)", "Apple Wired Ear Pods (link)". Trailing
        # "(link)" + retail/shopping host on source_url = noise.
        if _is_affiliate_noise(title, source_url):
            continue

        # Extract time if present
        start_time = parse_time(combined_text)

        # Substack RSS often bakes the venue into the title:
        #   "Pet Adoption Day (@ Elizabeth Street Garden)"
        #   "High Line Plant Sale (@ High Line - 14th Street)"
        # Pull the venue into location.name so the event isn't dropped by
        # the shell-event filter (no desc + no img + no loc → shell).
        # Iter 86 audit: ~235 substack events were getting shell-filtered
        # for exactly this reason.
        loc_name = ""
        m = _re.search(r"\((?:@|at)\s+([^)]+)\)\s*$", title)
        if m:
            loc_name = m.group(1).strip()
            title = title[:m.start()].strip()

        events.append(build_event(
            title=title,
            description=description,
            event_date=event_date,
            start_time=start_time,
            location_name=loc_name or None,
            source="substack",
            source_url=source_url,
            categories=infer_categories(title, description),
        ))

    return events


# --- Pin-marker event extraction (One Fine Day NYC newsletter style) -------
# Posts like "NYC This Week | May 27-31" mark each curated event with a 📍
# pin, then encode date/time/ticket inline with emoji delimiters:
#   📍<Title> (@ <Venue>)☁️ <Date> | <Time>🎟️ <Price><Description…>
# Shops are marked 🛍️/🍀/☕ and product picks 👖/📱, so the 📍 pin + ☁️ date
# pair is a clean event discriminator. This structured parse replaces the
# heading-fragment heuristic for these posts (which mangles them into
# duplicate/mis-dated/mis-linked fragments). Content-pattern driven, so any
# newsletter using this convention benefits — not hardcoded to one host.
_PIN = "\U0001F4CD"          # 📍
_CLOUD_RE = _re.compile(r"☁️?")        # ☁ (+ optional VS16)
_TICKET_RE = _re.compile(r"\U0001F39F️?")   # 🎟 (+ optional VS16)
_MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
           "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
_MONTH_DAY_RE = _re.compile(
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})",
    _re.IGNORECASE,
)


def _parse_marker_date(date_text: str, ref_date):
    """Parse a 'Month Day' from the inline date text, anchored to the post's
    publication YEAR (ref_date). dateparser's PREFER_DATES_FROM=future pushes a
    bare 'May 29' to next year when it's already past — anchoring to the post
    year fixes that. Handles ranges ('May 28-31' → start) by taking the first
    match. Returns None for dateless text ('Open daily')."""
    from datetime import date as _date
    if not date_text:
        return None
    m = _MONTH_DAY_RE.search(date_text)
    if not m:
        return None
    month = _MONTHS[m.group(1)[:3].lower()]
    day = int(m.group(2))
    year = ref_date.year if ref_date else _date.today().year
    try:
        d = _date(year, month, day)
    except ValueError:
        return None
    # Year rollover: a post published in late December linking a January event
    # should land next year. Only bump when the event is well before the post.
    if ref_date and (d - ref_date).days < -90:
        try:
            d = _date(year + 1, month, day)
        except ValueError:
            pass
    return d


def _extract_pin_marker_events(soup, fallback_date, post_link, ref_date) -> list[dict]:
    events = []
    seen = set()
    for p in soup.find_all(["p", "li"]):
        text = p.get_text(" ", strip=True)
        if _PIN not in text:
            continue
        # Each event is its own paragraph; take everything after the pin.
        after = text.split(_PIN, 1)[1].strip()
        if not after:
            continue
        # Layout: 📍<Title> (@ Venue)☁️ <Date> | <Time>🎟️ <Price><Desc…>
        # Split on the 🎟️ ticket marker FIRST (always present) so price/desc
        # never bleed into the title — the ☁️ date marker is absent on the
        # dateless monthly-guide items. Then split the left side on ☁️.
        head, tail = (_TICKET_RE.split(after, maxsplit=1) + [""])[:2]
        tv, dt_text = (_CLOUD_RE.split(head, maxsplit=1) + [""])[:2]

        # Title + venue: "Title (@ Venue)" — venue may itself contain parens.
        title_venue = tv.strip()
        loc_name = ""
        if "(@" in title_venue:
            title, venue = title_venue.split("(@", 1)
            title = title.strip()
            loc_name = venue.strip().rstrip(")").strip()
        else:
            title = title_venue.strip()
        title = _re.sub(r"\s+", " ", title).strip(" .,:;-")
        if len(title) < 4:
            continue

        # Date + time.
        date_part, time_part = (dt_text.split("|", 1) + [""])[:2]
        event_date = _parse_marker_date(date_part, ref_date) or fallback_date
        if not event_date:
            continue
        start_time = parse_time(time_part) or parse_time(dt_text)

        # Per-event URL: first non-substack http link in this paragraph.
        source_url = post_link
        for link in p.find_all("a", href=True):
            href = link.get("href", "")
            if href.startswith("http") and "substack.com" not in href:
                source_url = href
                break

        # Price hint + description from the tail (after 🎟️). The tail leads
        # with a ticket phrase glued to the description; capture price, then
        # strip the phrase so the description reads cleanly. Monthly-guide
        # items use a ✨ separator between the price line and the description.
        tail = tail.strip()
        price = "free" if _re.match(r"free\b", tail, _re.IGNORECASE) else None
        if "✨" in tail:
            description = tail.split("✨", 1)[1].strip()
        else:
            description = _re.sub(
                r"^(free to attend|free entry|ticketed event|ticketed|free|"
                r"rsvp required|scheduled event|pay[- ]what[- ]you[- ]wish)\b[\s:./-]*",
                "", tail, flags=_re.IGNORECASE,
            ).strip()
        description = description[:500]

        key = (title.lower(), event_date.isoformat())
        if key in seen:
            continue
        seen.add(key)

        events.append(build_event(
            title=title,
            description=description,
            event_date=event_date,
            start_time=start_time,
            location_name=loc_name or None,
            source="substack",
            source_url=source_url,
            price=price,
            categories=infer_categories(title, description),
        ))
    return events


def _is_date_only_title(title: str) -> bool:
    """True if the title is just a date like 'May 16' or '5/16'."""
    if not title:
        return True
    stripped = title.strip().rstrip(".:,;")
    # Match "May 16", "May 16th", "May 16, 2026"
    if re.match(r"^(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?(?:[,\s]+\d{4})?$", stripped, re.IGNORECASE):
        return True
    if re.match(r"^\d{1,2}/\d{1,2}(?:/\d{2,4})?$", stripped):
        return True
    # Iter 94: roundup posts leak day-name fragments ("wednesday", "monday")
    # as if they were event titles. The day-of-week appears as a paragraph
    # subhead in theskint posts. Treat as date-only.
    if re.match(r"^(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)$", stripped, re.IGNORECASE):
        return True
    if re.match(r"^(?:may|june|july|august|september|october|november|december)\s+\d{1,2}\s*(?:to|-|–|—)\s*(?:may|june|july|august|september|october|november|december)?\s*\d{1,2}$", stripped, re.IGNORECASE):
        return True  # date range like "May 30 to June 5"
    return False


def _extract_real_title_from_desc(desc: str) -> str:
    """Extract the actual event title from description text.

    Substack guides format like: '📍 Watch the 5 Boro Bike Tour🎟️ ...'
    The title is between the location pin and the ticket emoji.
    """
    if not desc:
        return ""

    # Strip leading 📍 and any emoji
    text = re.sub(r"^[📍🎟️✨🗓️🕐]+\s*", "", desc).strip()

    # Cut at the ticket emoji 🎟️ (separates title from details)
    title = re.split(r"🎟️", text, 1)[0].strip()

    # Also try other common separators
    if not title or len(title) < 5:
        title = re.split(r"[•·|]", text, 1)[0].strip()

    # Trim trailing junk
    title = re.sub(r"\s+", " ", title)
    title = title.strip(" .,:;!?-")

    if 5 < len(title) < 120:
        return title
    return ""


def _extract_date(text: str):
    """Try to find a date in the given text using regex patterns and dateparser."""
    for pattern in DATE_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            date_str = m.group(1)
            parsed = parse_date(date_str)
            if parsed:
                return parsed
    return None
