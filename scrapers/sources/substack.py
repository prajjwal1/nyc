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
    # The Deli — independent NYC music venues
    "https://thedeli.substack.com/feed",
    # Eater NY — food/restaurant pop-ups, supper clubs, food events
    "https://ny.eater.com/rss/index.xml",
    # Bedford + Bowery — Brooklyn/East Village culture, art openings, shows
    "https://bedfordandbowery.com/feed/",
    # (Removed: hellgate.substack.com, gothamist.com — primarily news outlets
    # whose RSS items are news articles, not events. Occasional event
    # roundups exist but noise-to-signal ratio is too high.)
    # Untapped Cities — NYC tours, history, secret-spot/event coverage
    "https://untappedcities.com/feed/",
    # NYC for Free — free events curator, weekly roundups
    "https://nycforfree.substack.com/feed",
    # Brokelyn — Brooklyn-focused budget events (cheap/free)
    "https://www.brokelyn.com/feed/",
    # NYC Parks daily events feed (already covered via parks.py, but the
    # Substack version surfaces editorial picks + program highlights)
    "https://www.nycgovparks.org/news.rss",
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
    if channel is None:
        return events, 0

    items = channel.findall("item")
    # Process the most recent 8 posts (was 3) — captures more weekly guides
    for item in items[:8]:
        try:
            events.extend(_parse_item(item, ns))
            # Harvest authoritative event-platform URLs from post body —
            # newsletter posts often link to lu.ma/eventbrite/etc. directly.
            body = item.findtext("content:encoded", "", namespaces=ns) or item.findtext("description", "")
            urls_added += _harvest_and_save_post_urls(body)
        except Exception as e:
            title = item.findtext("title", "unknown")
            print(f"[substack] Error parsing item '{title}': {e}")
    return events, urls_added


def _parse_item(item, ns: dict) -> list[dict]:
    events = []
    post_title = item.findtext("title", "")
    post_link = item.findtext("link", "")
    pub_date_str = item.findtext("pubDate", "")

    # Get the full HTML content from content:encoded
    content_encoded = item.findtext("content:encoded", "", namespaces=ns)
    if not content_encoded:
        # Fallback to description
        content_encoded = item.findtext("description", "")

    if not content_encoded:
        return events

    # Parse the post publication date as fallback
    fallback_date = parse_date(pub_date_str) if pub_date_str else None

    soup = BeautifulSoup(content_encoded, "html.parser")

    # Strategy: find headings (h2, h3, strong, b) that likely denote event titles,
    # then gather the text and links that follow until the next heading.
    heading_tags = soup.find_all(["h2", "h3", "strong", "b"])

    if heading_tags:
        events.extend(_extract_from_headings(soup, heading_tags, fallback_date, post_link))
    else:
        # Fallback: treat the whole post as one event
        text = soup.get_text(separator=" ", strip=True)
        if (fallback_date and len(post_title) > 5
                and not _looks_like_news_title(post_title)):
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


def _extract_from_headings(soup, heading_tags, fallback_date, post_link: str) -> list[dict]:
    events = []
    seen_titles = set()

    for heading in heading_tags:
        title = heading.get_text(strip=True)
        # Skip very short or generic headings
        if len(title) < 4 or title.lower() in seen_titles:
            continue
        # Skip headings that are just generic section headers
        if title.lower() in ("events", "this week", "this weekend", "highlights", "more", "links"):
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

        # Extract time if present
        start_time = parse_time(combined_text)

        events.append(build_event(
            title=title,
            description=description,
            event_date=event_date,
            start_time=start_time,
            source="substack",
            source_url=source_url,
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
