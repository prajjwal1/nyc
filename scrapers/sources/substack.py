import re
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from ..utils.http import fetch_text
from ..utils.event_parser import build_event, parse_date, parse_time, infer_categories

FEEDS = [
    "https://onefinedaynyc.substack.com/feed",
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
    for feed_url in FEEDS:
        try:
            xml_text = await fetch_text(feed_url)
            events.extend(_parse_feed(xml_text))
        except Exception as e:
            print(f"[substack] Failed to fetch {feed_url}: {e}")
    return events


def _parse_feed(xml_text: str) -> list[dict]:
    events = []
    root = ET.fromstring(xml_text)

    # RSS feeds use <channel><item> structure
    ns = {"content": "http://purl.org/rss/1.0/modules/content/"}
    channel = root.find("channel")
    if channel is None:
        return events

    items = channel.findall("item")
    # Only process the most recent 3 posts
    for item in items[:3]:
        try:
            events.extend(_parse_item(item, ns))
        except Exception as e:
            title = item.findtext("title", "unknown")
            print(f"[substack] Error parsing item '{title}': {e}")
    return events


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
        if fallback_date and len(post_title) > 5:
            events.append(build_event(
                title=post_title,
                description=text[:500],
                event_date=fallback_date,
                source="substack",
                source_url=post_link,
                categories=infer_categories(post_title, text[:500]),
            ))

    return events


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
