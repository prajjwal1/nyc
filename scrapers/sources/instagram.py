import re
import asyncio
from datetime import datetime
from ..utils.event_parser import build_event, parse_date, parse_time

ACCOUNTS = [
    "nycforfree.co",
    "onefinedaynyc_",
]

MAX_POSTS = 20


async def scrape() -> list[dict]:
    events = []
    for account in ACCOUNTS:
        try:
            posts = await _fetch_posts(account)
            for post in posts:
                extracted = _extract_events_from_caption(post, account)
                events.extend(extracted)
        except Exception as e:
            print(f"[instagram] Failed @{account}: {e}")
    return events


async def _fetch_posts(username: str) -> list[dict]:
    try:
        import instaloader
        L = instaloader.Instaloader()
        profile = instaloader.Profile.from_username(L.context, username)

        posts = []
        count = 0
        for post in profile.get_posts():
            if count >= MAX_POSTS:
                break
            posts.append({
                "caption": post.caption or "",
                "date": post.date_utc,
                "url": f"https://www.instagram.com/p/{post.shortcode}/",
                "image": post.url,
            })
            count += 1
            await asyncio.sleep(0.5)
        return posts
    except Exception as e:
        print(f"[instagram] instaloader failed for {username}: {e}")
        return []


def _extract_events_from_caption(post: dict, account: str) -> list[dict]:
    caption = post.get("caption", "")
    if not caption:
        return []

    events = []
    post_date = post.get("date")
    post_url = post.get("url", "")
    image = post.get("image", "")

    sections = re.split(r"\n\n+|\n(?=[•●○‣•\-\*\d+\.])", caption)

    for section in sections:
        section = section.strip()
        if len(section) < 15:
            continue

        dates = _find_dates(section)
        times = parse_time(section)
        title = _extract_title(section)
        location = _extract_location(section)
        urls = re.findall(r"https?://\S+", section)

        event_date = dates[0] if dates else (post_date.date() if post_date else None)
        if not event_date:
            continue

        events.append(build_event(
            title=title or section[:80],
            description=section[:400],
            event_date=event_date,
            start_time=times,
            location_name=location,
            source="instagram",
            source_url=urls[0] if urls else post_url,
            image_url=image,
        ))

    if not events and post_date:
        title = _extract_title(caption) or caption[:80]
        events.append(build_event(
            title=title,
            description=caption[:400],
            event_date=post_date.date(),
            start_time=parse_time(caption),
            source="instagram",
            source_url=post_url,
            image_url=image,
        ))

    return events


def _find_dates(text: str) -> list:
    patterns = [
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:\s*,?\s*\d{4})?",
        r"\d{1,2}/\d{1,2}(?:/\d{2,4})?",
        r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}",
        r"(?:this|next)\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)",
        r"(?:tonight|today|tomorrow)",
    ]
    dates = []
    for pat in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            d = parse_date(m.group())
            if d:
                dates.append(d)
    return dates


def _extract_title(text: str) -> str:
    lines = text.strip().split("\n")
    first_line = lines[0].strip()
    first_line = re.sub(r"[\U0001F300-\U0001F9FF]", "", first_line).strip()
    if len(first_line) > 5 and len(first_line) < 120:
        return first_line
    return ""


def _extract_location(text: str) -> str:
    patterns = [
        r"(?:at|@)\s+([A-Z][A-Za-z\s&']+?)(?:\n|$|,|\.|!)",
        r"📍\s*(.+?)(?:\n|$)",
        r"(?:Location|Venue|Where):\s*(.+?)(?:\n|$)",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(1).strip()
    return ""
