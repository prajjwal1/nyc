"""Instagram scraper using authenticated instaloader with session files.

Scrapes posts from curated NYC event accounts, parses captions to extract
event details (dates, times, locations, URLs), and handles multi-event posts.
"""

import os
import re
import time
from datetime import datetime

import instaloader

from ..config import (
    IG_ACCOUNTS,
    IG_MAX_POSTS_PER_ACCOUNT,
    IG_SESSION_FILE,
    IG_USERNAME,
)
from ..utils.event_parser import build_event, infer_categories, parse_date, parse_time

# Optional image analysis for posts with incomplete caption data.
try:
    from ..utils.image_analyzer import analyze_event_image

    _HAS_IMAGE_ANALYZER = True
except ImportError:
    _HAS_IMAGE_ANALYZER = False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scrape() -> list[dict]:
    """Scrape recent posts from curated IG accounts and return parsed events."""

    loader = _get_authenticated_loader()
    if loader is None:
        return []

    all_events: list[dict] = []

    for idx, account in enumerate(IG_ACCOUNTS):
        try:
            posts = _fetch_posts(loader, account)
            for post in posts:
                extracted = _extract_events_from_caption(post, account)

                # If image analyzer is available, try to fill in gaps.
                if _HAS_IMAGE_ANALYZER:
                    extracted = _maybe_enrich_with_image(extracted, post)

                all_events.extend(extracted)
        except Exception as exc:
            print(f"[instagram] Failed @{account}: {exc}")

        # Rate-limit: sleep between accounts (skip after the last one).
        if idx < len(IG_ACCOUNTS) - 1:
            time.sleep(1)

    print(f"[instagram] Scraped {len(all_events)} events from {len(IG_ACCOUNTS)} accounts")
    return all_events


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def _get_authenticated_loader() -> instaloader.Instaloader | None:
    """Return an authenticated Instaloader instance, or None if no session."""

    session_path = IG_SESSION_FILE

    if not os.path.isfile(session_path):
        print(
            f"[instagram] WARNING: No session file at {session_path}. "
            "Skipping Instagram scraping. "
            "Run `instaloader --login {username}` to create one."
        )
        return None

    loader = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
    )

    try:
        loader.load_session_from_file(IG_USERNAME, session_path)
        print(f"[instagram] Authenticated as @{IG_USERNAME}")
        return loader
    except Exception as exc:
        print(f"[instagram] WARNING: Failed to load session: {exc}. Skipping Instagram.")
        return None


# ---------------------------------------------------------------------------
# Fetching posts
# ---------------------------------------------------------------------------

def _fetch_posts(loader: instaloader.Instaloader, username: str) -> list[dict]:
    """Fetch the most recent posts for a given account."""

    try:
        profile = instaloader.Profile.from_username(loader.context, username)
    except instaloader.exceptions.ProfileNotExistsException:
        print(f"[instagram] Profile @{username} does not exist, skipping")
        return []

    posts: list[dict] = []
    count = 0

    for post in profile.get_posts():
        if count >= IG_MAX_POSTS_PER_ACCOUNT:
            break

        posts.append({
            "caption": post.caption or "",
            "date": post.date_utc,
            "url": f"https://www.instagram.com/p/{post.shortcode}/",
            "image": post.url,
        })
        count += 1

    print(f"[instagram] Fetched {len(posts)} posts from @{username}")
    return posts


# ---------------------------------------------------------------------------
# Caption parsing  — multi-event aware
# ---------------------------------------------------------------------------

def _extract_events_from_caption(post: dict, account: str) -> list[dict]:
    """Parse a post caption and return one or more event dicts.

    Many NYC event accounts list 5-10 events in a single caption, separated
    by double newlines, bullets, numbered items, or emoji markers.  We split
    on those boundaries and try to parse each section independently.
    """

    caption = post.get("caption", "")
    if not caption:
        return []

    post_date = post.get("date")
    post_url = post.get("url", "")
    image_url = post.get("image", "")

    # Try to find all URLs in the full caption (some appear only once at end).
    all_urls = re.findall(r"https?://[^\s)>\]\"']+", caption)

    sections = _split_caption(caption)

    events: list[dict] = []
    url_idx = 0  # walk through extracted URLs as we consume sections

    for section in sections:
        section = section.strip()
        if len(section) < 15:
            continue

        dates = _find_dates(section)
        time_str = parse_time(section)
        title = _extract_title(section)
        location = _extract_location(section)
        categories = infer_categories(title or section, section)

        # URLs within the section get priority; fall back to next global URL.
        section_urls = re.findall(r"https?://[^\s)>\]\"']+", section)
        if section_urls:
            source_url = section_urls[0]
        elif url_idx < len(all_urls):
            source_url = all_urls[url_idx]
            url_idx += 1
        else:
            source_url = post_url

        event_date = dates[0] if dates else (post_date.date() if post_date else None)
        if not event_date:
            continue

        events.append(build_event(
            title=title or section[:80],
            description=section[:400],
            event_date=event_date,
            start_time=time_str,
            location_name=location,
            source="instagram",
            source_url=source_url,
            image_url=image_url,
            categories=categories,
        ))

    # Fallback: if no sections produced events, treat the whole caption as one.
    if not events and post_date:
        title = _extract_title(caption) or caption[:80]
        events.append(build_event(
            title=title,
            description=caption[:400],
            event_date=post_date.date(),
            start_time=parse_time(caption),
            location_name=_extract_location(caption),
            source="instagram",
            source_url=all_urls[0] if all_urls else post_url,
            image_url=image_url,
            categories=infer_categories(title, caption),
        ))

    return events


# ---------------------------------------------------------------------------
# Caption splitting
# ---------------------------------------------------------------------------

_SPLIT_RE = re.compile(
    r"\n\n+"                              # double+ newlines
    r"|\n(?=[•●○‣◆▪︎★☆\-\*])"            # newline before bullet chars
    r"|\n(?=\d{1,2}[\.\)]\s)"            # newline before numbered list items
    r"|\n(?=📍|🎶|🎨|🎭|📚|🗓|🕐|👉)"   # newline before common event emoji
)


def _split_caption(caption: str) -> list[str]:
    """Split a caption into logical sections for multi-event posts."""

    parts = _SPLIT_RE.split(caption)

    # Merge very short fragments back into the previous section.
    merged: list[str] = []
    for part in parts:
        stripped = part.strip()
        if not stripped:
            continue
        if merged and len(stripped) < 15:
            merged[-1] += "\n" + stripped
        else:
            merged.append(stripped)

    return merged


# ---------------------------------------------------------------------------
# Date extraction
# ---------------------------------------------------------------------------

_DATE_PATTERNS = [
    # "May 5", "May 5th", "May 5, 2026", "May 5th 2026"
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:\s*,?\s*\d{4})?",
    # "5/5", "05/05/2026", "5/5/26"
    r"\d{1,2}/\d{1,2}(?:/\d{2,4})?",
    # "Saturday, May 5"
    r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+\d{1,2}",
    # "this Saturday", "next Friday"
    r"(?:this|next)\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)",
    # relative
    r"(?:tonight|today|tomorrow)",
]


def _find_dates(text: str) -> list:
    """Extract date objects from text using regex patterns + dateparser."""

    dates = []
    for pat in _DATE_PATTERNS:
        for match in re.finditer(pat, text, re.IGNORECASE):
            parsed = parse_date(match.group())
            if parsed:
                dates.append(parsed)
    return dates


# ---------------------------------------------------------------------------
# Title extraction
# ---------------------------------------------------------------------------

def _extract_title(text: str) -> str:
    """Pull the most likely event title from a caption section.

    Heuristic: the first non-trivial line that isn't just emoji or hashtags.
    """

    for line in text.strip().split("\n"):
        line = line.strip()
        # Strip emoji
        cleaned = re.sub(r"[\U0001F300-\U0001FAFF\U00002702-\U000027B0\U0000FE00-\U0000FE0F]", "", line).strip()
        # Skip lines that are just hashtags or handles
        if re.match(r"^[#@\s]+$", cleaned):
            continue
        if 5 < len(cleaned) < 120:
            return cleaned
    return ""


# ---------------------------------------------------------------------------
# Location extraction
# ---------------------------------------------------------------------------

_LOCATION_PATTERNS = [
    # "📍 Central Park" or "📍Central Park"
    r"📍\s*(.+?)(?:\n|$)",
    # "@VenueName" (Instagram mention style — uppercase start = likely venue)
    r"@([A-Z][A-Za-z0-9_&' ]+?)(?:\n|$|,|\.|!|\s{2})",
    # "at The Museum of..." / "at Brooklyn Mirage"
    r"\bat\s+([A-Z][A-Za-z\s&''\-]+?)(?:\n|$|,|\.|!)",
    # "Location: ..." or "Venue: ..." or "Where: ..."
    r"(?:Location|Venue|Where):\s*(.+?)(?:\n|$)",
    # Street addresses: "123 W 4th St"
    r"(\d{1,5}\s+[A-Z][A-Za-z]+(?:\s+[A-Za-z]+)?\s+(?:St|Ave|Blvd|Rd|Pl|Dr|Way|Ct|Ln)\.?)(?:\b|,)",
]


def _extract_location(text: str) -> str:
    """Try to pull a venue / location name from the text."""

    for pat in _LOCATION_PATTERNS:
        m = re.search(pat, text)
        if m:
            loc = m.group(1).strip()
            # Ignore very short or very long matches.
            if 2 < len(loc) < 100:
                return loc
    return ""


# ---------------------------------------------------------------------------
# Optional image enrichment
# ---------------------------------------------------------------------------

def _maybe_enrich_with_image(events: list[dict], post: dict) -> list[dict]:
    """If caption parsing left gaps, try to fill them from image analysis."""

    if not _HAS_IMAGE_ANALYZER:
        return events

    image_url = post.get("image", "")
    if not image_url:
        return events

    enriched: list[dict] = []
    for event in events:
        missing_title = not event.get("title") or event["title"] == event.get("description", "")[:80]
        missing_date = not event.get("date")

        if missing_title or missing_date:
            try:
                image_info = analyze_event_image(image_url)
                if image_info:
                    if missing_title and image_info.get("title"):
                        event["title"] = image_info["title"]
                    if missing_date and image_info.get("date"):
                        event["date"] = image_info["date"]
                    if not event["location"]["name"] and image_info.get("location"):
                        event["location"]["name"] = image_info["location"]
                    if image_info.get("time") and not event.get("startTime"):
                        event["startTime"] = image_info["time"]
            except Exception as exc:
                print(f"[instagram] Image analysis failed: {exc}")

        enriched.append(event)

    return enriched
