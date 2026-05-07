"""Reddit URL harvester.

Recent posts in r/AskNYC, r/nyc, r/Brooklyn, r/Queens routinely link to
event-platform URLs (lu.ma, eventbrite, partiful, posh, ra.co, dice.fm)
in selftext or top-level comments — especially in weekly "what's
happening this weekend" megathreads.

This scraper does NOT directly parse events from Reddit posts (the text
is too conversational). Instead it harvests event-platform URLs from
selftext and top comments, feeding them to discovered_urls.json so the
generic scraper picks them up on the next pipeline run. Pure URL
discovery — returns 0 events itself.
"""
import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from ..utils.http import fetch_text

SUBREDDITS = ["AskNYC", "nyc", "Brooklyn", "Queens", "AskNYC"]

# Direct platform-name searches catch posts that explicitly link to event pages.
# These are higher-yield than topic searches because the query matches the URL.
SEARCH_QUERIES = [
    "lu.ma",
    "eventbrite",
    "partiful",
    "posh.vip",
    "events this weekend",
    "things to do",
    "happening this week",
]

# Match the same authoritative event platforms as the IG harvester.
_EVENT_URL_RE = re.compile(
    r"https?://(?:www\.)?(?:"
    r"lu\.ma/[A-Za-z0-9._-]+|"
    r"luma\.com/[A-Za-z0-9._-]+|"
    r"eventbrite\.com/(?:e|cc|o)/[^\s)>\]\"']+|"
    r"partiful\.com/e/[A-Za-z0-9._-]+|"
    r"posh\.vip/e/[^\s)>\]\"']+|"
    r"ra\.co/(?:events|promoters)/[^\s)>\]\"']+|"
    r"shotgun\.live/(?:[a-z]{2}/)?events/[^\s)>\]\"']+|"
    r"dice\.fm/event/[^\s)>\]\"']+|"
    r"tixr\.com/(?:groups|e)/[^\s)>\]\"']+|"
    r"withfriends\.co/event/[^\s)>\]\"']+"
    r")",
    re.IGNORECASE,
)

DISCOVERED_URLS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "discovered_urls.json",
)


async def scrape() -> list[dict]:
    """Harvest event-platform URLs from NYC subreddits."""
    found: set[str] = set()

    # Strategy 1: latest /new posts per subreddit
    for sub in set(SUBREDDITS):
        try:
            urls = await _harvest_subreddit_new(sub, limit=30)
            found.update(urls)
        except Exception as e:
            print(f"[reddit] /r/{sub}/new failed: {e}")

    # Strategy 2: search-based mining for high-signal queries
    permalinks_to_mine: list[str] = []
    for sub in ("AskNYC", "nyc"):
        for query in SEARCH_QUERIES:
            try:
                urls = await _harvest_subreddit_search(sub, query, limit=15)
                found.update(urls)
                # Capture permalinks from this query for comment mining
                pls = getattr(_extract_urls_from_listing, "_last_permalinks", []) or []
                permalinks_to_mine.extend(pls[:5])  # cap per query
            except Exception as e:
                print(f"[reddit] /r/{sub}/search '{query}' failed: {e}")

    # Strategy 3: mine comments on high-comment posts surfaced by search.
    # Cap total comment fetches per run to bound rate-limit risk.
    seen_permalinks = set()
    comment_urls = 0
    for pl in permalinks_to_mine:
        if pl in seen_permalinks:
            continue
        seen_permalinks.add(pl)
        if len(seen_permalinks) > 12:
            break
        try:
            cu = await _harvest_post_comments(pl)
            new_from_comments = cu - found
            comment_urls += len(new_from_comments)
            found.update(cu)
        except Exception as e:
            print(f"[reddit] comments on {pl} failed: {e}")
    if comment_urls:
        print(f"[reddit] +{comment_urls} URLs from comment mining ({len(seen_permalinks)} posts)")

    if not found:
        print(f"[reddit] No event-platform URLs found")
        return []

    # Dedup against existing discovered_urls
    existing = _load_existing_urls()
    new_urls = found - existing

    if new_urls:
        _persist_urls(new_urls)
        print(f"[reddit] Harvested {len(new_urls)} new event URLs (skipped {len(found) - len(new_urls)} dupes)")
    else:
        print(f"[reddit] All {len(found)} URLs already known")

    # Return empty — next pipeline run picks up the URLs via the generic scraper.
    return []


async def _harvest_subreddit_new(subreddit: str, limit: int = 25) -> set[str]:
    url = f"https://www.reddit.com/r/{subreddit}/new.json?limit={limit}"
    headers = {"User-Agent": "nyc-events-scraper/0.1 (+https://github.com/prajjwal1/nyc)"}
    try:
        text = await fetch_text(url, headers=headers)
    except Exception:
        return set()
    return _extract_urls_from_listing(text)


async def _harvest_subreddit_search(subreddit: str, query: str, limit: int = 15) -> set[str]:
    from urllib.parse import quote_plus
    url = (
        f"https://www.reddit.com/r/{subreddit}/search.json"
        f"?q={quote_plus(query)}&restrict_sr=1&sort=relevance&limit={limit}"
    )
    headers = {"User-Agent": "nyc-events-scraper/0.1 (+https://github.com/prajjwal1/nyc)"}
    try:
        text = await fetch_text(url, headers=headers)
    except Exception:
        return set()
    return _extract_urls_from_listing(text)


def _extract_urls_from_listing(text: str) -> set[str]:
    """Parse a Reddit listing JSON and extract event-platform URLs from
    each post's selftext + the post URL itself.
    """
    found: set[str] = set()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return found

    posts = data.get("data", {}).get("children", []) if isinstance(data, dict) else []
    permalinks: list[str] = []
    for child in posts:
        if not isinstance(child, dict):
            continue
        post = child.get("data", {})
        if not isinstance(post, dict):
            continue
        # External link posts: post.url is the linked URL itself
        post_url = post.get("url_overridden_by_dest") or post.get("url") or ""
        if isinstance(post_url, str) and _EVENT_URL_RE.match(post_url):
            found.add(post_url.split("#")[0])
        # Self-text: scan body for event URLs
        selftext = post.get("selftext", "")
        if isinstance(selftext, str) and selftext:
            for m in _EVENT_URL_RE.finditer(selftext):
                found.add(m.group(0).rstrip(".,;:!?)").split("#")[0])
        # Save permalinks of high-comment posts for later comment mining
        permalink = post.get("permalink", "")
        num_comments = post.get("num_comments", 0)
        if permalink and num_comments and num_comments >= 5:
            permalinks.append(permalink)
    # Stash permalinks on the function (return only URLs but expose for caller)
    _extract_urls_from_listing._last_permalinks = permalinks  # type: ignore[attr-defined]
    return found


async def _harvest_post_comments(permalink: str, limit: int = 30) -> set[str]:
    """Fetch top-level comments on a Reddit post and harvest event URLs.

    Many "events this weekend" megathreads have ticket URLs in comments
    rather than the original post body. This pulls the JSON comments tree
    and scans top comments for event-platform URLs.
    """
    url = f"https://www.reddit.com{permalink}.json?limit={limit}&depth=1"
    headers = {"User-Agent": "nyc-events-scraper/0.1 (+https://github.com/prajjwal1/nyc)"}
    try:
        text = await fetch_text(url, headers=headers)
    except Exception:
        return set()
    found: set[str] = set()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return found
    # Reddit comments JSON returns [post_listing, comments_listing]
    if not isinstance(data, list) or len(data) < 2:
        return found
    comments = data[1].get("data", {}).get("children", []) if isinstance(data[1], dict) else []
    for child in comments:
        if not isinstance(child, dict):
            continue
        c = child.get("data", {})
        if not isinstance(c, dict):
            continue
        body = c.get("body", "")
        if isinstance(body, str) and body:
            for m in _EVENT_URL_RE.finditer(body):
                found.add(m.group(0).rstrip(".,;:!?)").split("#")[0])
    return found


def _load_existing_urls() -> set[str]:
    if not os.path.isfile(DISCOVERED_URLS_PATH):
        return set()
    try:
        with open(DISCOVERED_URLS_PATH) as f:
            d = json.load(f)
        items = d if isinstance(d, list) else d.get("urls", [])
        return {it["url"] if isinstance(it, dict) else it for it in items}
    except Exception:
        return set()


def _persist_urls(urls: set[str]) -> None:
    if not urls:
        return
    existing: list = []
    if os.path.isfile(DISCOVERED_URLS_PATH):
        try:
            with open(DISCOVERED_URLS_PATH) as f:
                d = json.load(f)
            existing = d if isinstance(d, list) else d.get("urls", [])
        except Exception:
            existing = []
    seen = {it["url"] if isinstance(it, dict) else it for it in existing}
    now = datetime.now(timezone.utc).isoformat()
    for u in urls:
        if u in seen:
            continue
        existing.append({"url": u, "discovered_at": now, "discovered_via": "reddit"})
        seen.add(u)
    os.makedirs(os.path.dirname(DISCOVERED_URLS_PATH), exist_ok=True)
    tmp = DISCOVERED_URLS_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(existing, f, indent=2)
    os.replace(tmp, DISCOVERED_URLS_PATH)
