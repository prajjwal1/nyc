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
    IG_MAX_ACCOUNTS,
    IG_SESSION_FILE,
    IG_SLEEP_BETWEEN_ACCOUNTS,
    IG_USERNAME,
)
from ..discover import load_discovered_accounts
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

_AFFINITY_ACCOUNTS_CACHE: set[str] = set()


def scrape_saved_only() -> list[dict]:
    """Light-weight scrape: user's saved posts AND tagged posts.

    Both are direct user-curated signals — saved (explicit bookmark)
    and tagged (someone invited the user). Runs in 30s-2min.

    Used by the quick-scrape workflow to keep the user's most relevant
    events fresh on every cron tick.
    """
    global _AFFINITY_ACCOUNTS_CACHE
    _AFFINITY_ACCOUNTS_CACHE = _load_affinity_accounts()

    loader = _get_authenticated_loader()
    if loader is None:
        return []

    saved_events, _ = _scrape_saved_posts(loader)
    tagged_events, _ = _scrape_tagged_posts(loader)
    return saved_events + tagged_events


def scrape() -> list[dict]:
    """Scrape recent posts from curated IG accounts and return parsed events.

    Priority order:
    1. User's SAVED posts — highest signal (user explicitly bookmarked these)
    2. Curated IG_ACCOUNTS + BFS-discovered accounts
    """
    global _AFFINITY_ACCOUNTS_CACHE
    _AFFINITY_ACCOUNTS_CACHE = _load_affinity_accounts()

    loader = _get_authenticated_loader()
    if loader is None:
        return []

    all_events: list[dict] = []

    # 1. Saved posts — highest priority since user curated them
    saved_events, saved_accounts = _scrape_saved_posts(loader)
    all_events.extend(saved_events)
    # Saved posts update the affinity cache mid-run too
    _AFFINITY_ACCOUNTS_CACHE |= saved_accounts

    # 1b. Tagged posts — user was tagged, implicit invitation
    tagged_events, tagged_accounts = _scrape_tagged_posts(loader)
    all_events.extend(tagged_events)
    _AFFINITY_ACCOUNTS_CACHE |= tagged_accounts

    # If saved posts surfaced new accounts not in our seed/discovered list,
    # add them so we scrape MORE posts from them in this same run.
    discovered_now = set(load_discovered_accounts())
    seed_set = {a.lower() for a in IG_ACCOUNTS}
    new_from_saves = saved_accounts - seed_set - discovered_now
    if new_from_saves:
        _add_to_discovered_accounts(new_from_saves)
        print(f"[instagram] Added {len(new_from_saves)} new accounts from saved posts: {sorted(new_from_saves)}")

    # 2. Curated + discovered accounts (skip ones we just covered via saved)
    all_accounts = sorted(set(IG_ACCOUNTS) | set(load_discovered_accounts()))

    # Cap account count for time-bounded CI runs.
    if IG_MAX_ACCOUNTS > 0 and len(all_accounts) > IG_MAX_ACCOUNTS:
        # Always include the curated seeds + a sample of discovered.
        seeds = list(set(IG_ACCOUNTS) & set(all_accounts))
        discovered = [a for a in all_accounts if a not in seeds]
        slot = max(0, IG_MAX_ACCOUNTS - len(seeds))
        all_accounts = sorted(set(seeds) | set(discovered[:slot]))
        print(f"[instagram] Capped to {len(all_accounts)} accounts for time budget")

    # Track bio URLs from accounts that have "link in bio" pattern — these
    # often link to Linktree/Beacons/lu.ma etc. with full event lists.
    bio_urls_seen: set[str] = set()

    # Wall-clock budget for IG scraping — beyond this, stop and return what
    # we have so the rest of the pipeline (Eventbrite, Substack, etc.) can run.
    import time as _time
    ig_budget_seconds = float(os.environ.get("IG_TIME_BUDGET_SECONDS", "1500"))  # 25 min default
    started = _time.time()

    # Order accounts: high-affinity first (so they always get scraped even
    # if budget runs out), then everything else.
    affinity_first = sorted(
        all_accounts,
        key=lambda a: 0 if a.lower() in _AFFINITY_ACCOUNTS_CACHE else 1,
    )

    for idx, account in enumerate(affinity_first):
        elapsed = _time.time() - started
        if elapsed > ig_budget_seconds:
            print(f"[instagram] Time budget exhausted at {elapsed:.0f}s after {idx} accounts; stopping IG scrape")
            break
        try:
            posts = _fetch_posts(loader, account)
            for post in posts:
                # Capture bio URL once per account
                bio = post.get("bio_url", "")
                if bio and bio not in bio_urls_seen:
                    bio_urls_seen.add(bio)

                extracted = _extract_events_from_caption(post, account)

                # If image analyzer is available, try to fill in gaps.
                if _HAS_IMAGE_ANALYZER:
                    extracted = _maybe_enrich_with_image(extracted, post)

                all_events.extend(extracted)
        except Exception as exc:
            print(f"[instagram] Failed @{account}: {exc}")

        # Rate-limit: sleep between accounts (skip after the last one).
        if idx < len(affinity_first) - 1:
            _time.sleep(IG_SLEEP_BETWEEN_ACCOUNTS)

    # Persist bio URLs so the generic scraper can pick up event pages
    # (Linktree/Beacons/Eventbrite/lu.ma/etc.) on the next pipeline run.
    if bio_urls_seen:
        _save_bio_urls(bio_urls_seen)

    print(f"[instagram] Scraped {len(all_events)} events from {len(all_accounts)} accounts + saved")
    return all_events


def _save_bio_urls(urls: set[str]) -> None:
    """Append IG bio URLs to discovered_urls.json (for the generic scraper)."""
    import json
    from datetime import datetime, timezone

    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data",
        "discovered_urls.json",
    )
    try:
        existing: list[dict] = []
        if os.path.isfile(path):
            with open(path) as f:
                data = json.load(f)
                if isinstance(data, list):
                    existing = data
                elif isinstance(data, dict):
                    existing = data.get("urls", [])

        seen = {item["url"] if isinstance(item, dict) else item for item in existing}
        added = 0
        now = datetime.now(timezone.utc).isoformat()
        for url in urls:
            if url in seen:
                continue
            existing.append({
                "url": url,
                "discovered_at": now,
                "discovered_via": "instagram_bio",
            })
            seen.add(url)
            added += 1

        if added:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                json.dump(existing, f, indent=2)
            print(f"[instagram] Added {added} bio URLs to discovered_urls.json")
    except Exception as exc:
        print(f"[instagram] Failed to save bio URLs: {exc}")


_AFFINITY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "user_affinity_accounts.json",
)


def _load_affinity_accounts() -> set[str]:
    """Load accounts the user has historically saved from."""
    import json
    if not os.path.isfile(_AFFINITY_PATH):
        return set()
    try:
        with open(_AFFINITY_PATH) as f:
            d = json.load(f)
        return {a.lower() for a in d.get("accounts", []) if isinstance(a, str)}
    except Exception:
        return set()


def _add_to_discovered_accounts(usernames: set[str]) -> None:
    """Append accounts to discovered_accounts.json so they get scraped in
    the same run (and persisted for future runs)."""
    import json
    from datetime import datetime, timezone
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data",
        "discovered_accounts.json",
    )
    try:
        existing = []
        if os.path.isfile(path):
            with open(path) as f:
                d = json.load(f)
            existing = d.get("accounts", []) if isinstance(d, dict) else []
        seen = {a.get("username", "").lower() for a in existing if isinstance(a, dict)}
        now = datetime.now(timezone.utc).isoformat()
        for u in usernames:
            if u.lower() not in seen:
                existing.append({
                    "username": u,
                    "score": 0.7,  # high — user explicitly saved a post
                    "discovered_at": now,
                    "discovered_via": "user_saved_post",
                })
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump({"accounts": existing, "lastDiscovery": now}, f, indent=2)
    except Exception as exc:
        print(f"[instagram] Failed to add discovered accounts: {exc}")


def _save_affinity_accounts(accounts: set[str]) -> None:
    """Persist the union of past + current saved-from accounts."""
    import json
    existing = _load_affinity_accounts()
    merged = existing | {a.lower() for a in accounts}
    if merged == existing:
        return
    try:
        os.makedirs(os.path.dirname(_AFFINITY_PATH), exist_ok=True)
        with open(_AFFINITY_PATH, "w") as f:
            json.dump({"accounts": sorted(merged)}, f, indent=2)
    except Exception as exc:
        print(f"[instagram] Failed to save affinity accounts: {exc}")


def _scrape_tagged_posts(loader, max_tagged: int = 30) -> tuple[list[dict], set[str]]:
    """Scrape posts where the user is tagged.

    These are typically friends/venues calling the user out — events where
    the user is implicitly invited. Highest semantic signal per post.
    """
    events: list[dict] = []
    accounts_seen: set[str] = set()
    try:
        my_profile = instaloader.Profile.from_username(loader.context, IG_USERNAME)
    except Exception as exc:
        print(f"[instagram] Could not load profile for tagged posts: {exc}")
        return events, accounts_seen

    try:
        count = 0
        for post in my_profile.get_tagged_posts():
            if count >= max_tagged:
                break
            count += 1
            owner = post.owner_username or "unknown"
            accounts_seen.add(owner.lower())

            images: list[str] = []
            try:
                if post.typename == "GraphSidecar":
                    for node in post.get_sidecar_nodes():
                        if not getattr(node, "is_video", False):
                            images.append(node.display_url)
                else:
                    images.append(post.url)
            except Exception:
                images.append(post.url)

            post_dict = {
                "caption": post.caption or "",
                "date": post.date_utc,
                "url": f"https://www.instagram.com/p/{post.shortcode}/",
                "image": images[0] if images else "",
                "all_images": images,
                "owner": owner,
                "bio_url": "",
            }
            extracted = _extract_events_from_caption(post_dict, owner)
            for ev in extracted:
                # Tagged posts are nearly as strong a signal as saved posts.
                ev["userTagged"] = True
            events.extend(extracted)
        print(f"[instagram] Scraped {len(events)} events from {count} TAGGED posts ({len(accounts_seen)} unique accounts)")
    except Exception as exc:
        print(f"[instagram] Tagged posts failed: {exc}")
    return events, accounts_seen


def _scrape_saved_posts(loader, max_saved: int = 50) -> tuple[list[dict], set[str]]:
    """Scrape the user's IG saved posts. These are the highest-signal events
    since the user explicitly bookmarked them — likely things they want to attend.

    Also persists the accounts user has saved from (cumulative across runs)
    so future scrapes can boost ALL events from those accounts, not just
    the saved post itself.
    """
    events: list[dict] = []
    accounts_seen: set[str] = set()
    try:
        my_profile = instaloader.Profile.from_username(loader.context, IG_USERNAME)
    except Exception as exc:
        print(f"[instagram] Could not load own profile @{IG_USERNAME}: {exc}")
        return events, accounts_seen

    try:
        count = 0
        for post in my_profile.get_saved_posts():
            if count >= max_saved:
                break
            count += 1
            owner = post.owner_username or "unknown"
            accounts_seen.add(owner.lower())

            # Build the post dict (same shape as _fetch_posts)
            images: list[str] = []
            try:
                if post.typename == "GraphSidecar":
                    for node in post.get_sidecar_nodes():
                        if not getattr(node, "is_video", False):
                            images.append(node.display_url)
                else:
                    images.append(post.url)
            except Exception:
                images.append(post.url)

            post_dict = {
                "caption": post.caption or "",
                "date": post.date_utc,
                "url": f"https://www.instagram.com/p/{post.shortcode}/",
                "image": images[0] if images else "",
                "all_images": images,
                "owner": owner,
                "bio_url": "",
            }

            # Saved posts get their owner as the IG account.
            extracted = _extract_events_from_caption(post_dict, owner)
            # Mark these as user-saved so we can boost in ranking
            for ev in extracted:
                ev["userSaved"] = True
            events.extend(extracted)
        print(f"[instagram] Scraped {len(events)} events from {count} SAVED posts ({len(accounts_seen)} unique accounts)")
    except Exception as exc:
        print(f"[instagram] Saved posts failed: {exc}")

    # Persist accounts as user-affinity signal for future runs.
    if accounts_seen:
        _save_affinity_accounts(accounts_seen)

    return events, accounts_seen


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
    """Fetch the most recent posts for a given account.

    High-affinity accounts (user has saved from them) get more posts pulled.

    Carousel posts (sidecar) yield ALL their images so the OCR pipeline can
    extract event details from flyer-style multi-image posts.
    """

    try:
        profile = instaloader.Profile.from_username(loader.context, username)
    except instaloader.exceptions.ProfileNotExistsException:
        print(f"[instagram] Profile @{username} does not exist, skipping")
        return []
    except Exception as exc:
        print(f"[instagram] Profile @{username} failed: {exc}")
        return []

    # High-affinity accounts get up to 1.5x posts (capped at 30)
    max_posts = IG_MAX_POSTS_PER_ACCOUNT
    if username.lower() in _AFFINITY_ACCOUNTS_CACHE:
        max_posts = min(30, int(IG_MAX_POSTS_PER_ACCOUNT * 1.5))

    # Capture the profile's external URL — many event accounts say "link in bio"
    # and the actual ticket page is at this URL.
    bio_url = getattr(profile, "external_url", "") or ""

    # Capture profile-level quality signals (affects ranking).
    profile_followers = int(getattr(profile, "followers", 0) or 0)
    profile_is_verified = bool(getattr(profile, "is_verified", False))

    posts: list[dict] = []
    count = 0

    for post in profile.get_posts():
        if count >= max_posts:
            break

        # Collect all images from the post (carousel = sidecar)
        images: list[str] = []
        try:
            if post.typename == "GraphSidecar":
                for node in post.get_sidecar_nodes():
                    if not getattr(node, "is_video", False):
                        images.append(node.display_url)
            else:
                images.append(post.url)
        except Exception:
            images.append(post.url)

        # Capture engagement signals (likes/comments) — high engagement
        # = real, popular event, not just any post.
        likes = 0
        comments = 0
        try:
            likes = int(getattr(post, "likes", 0) or 0)
            comments = int(getattr(post, "comments", 0) or 0)
        except Exception:
            pass

        posts.append({
            "caption": post.caption or "",
            "date": post.date_utc,
            "url": f"https://www.instagram.com/p/{post.shortcode}/",
            "image": images[0] if images else "",
            "all_images": images,
            "owner": post.owner_username,
            "bio_url": bio_url,
            "likes": likes,
            "comments": comments,
            "profile_followers": profile_followers,
            "profile_is_verified": profile_is_verified,
        })
        count += 1

    print(f"[instagram] Fetched {len(posts)} posts from @{username}")
    return posts


# ---------------------------------------------------------------------------
# Caption parsing  — multi-event aware
# ---------------------------------------------------------------------------

def _account_default_location(account: str) -> str:
    """Map well-known IG accounts to their default venue/location name.

    Used when the caption doesn't have a location — e.g. a post from
    @brooklynbowl is almost certainly happening AT Brooklyn Bowl.
    """
    mapping = {
        "brooklynbowl": "Brooklyn Bowl",
        "brooklynmuseum": "Brooklyn Museum",
        "metmuseum": "The Met",
        "whitneymuseum": "Whitney Museum",
        "newmuseum": "New Museum",
        "moma": "MoMA",
        "themorganlibrary": "Morgan Library",
        "houseofyesnyc": "House of Yes",
        "knockdowncenter": "Knockdown Center",
        "elsewherebrooklyn": "Elsewhere",
        "publicrecords": "Public Records",
        "rockwoodmusichall": "Rockwood Music Hall",
        "littlefieldnyc": "Littlefield",
        "mercurylounge": "Mercury Lounge",
        "thebellhouseny": "The Bell House",
        "bookclubbar": "Book Club Bar",
        "powerhousearena": "POWERHOUSE Arena",
        "lizsbookbar": "Liz's Book Bar",
        "recessgrove": "Recess Grove",
        "smallsjazzclub": "Smalls Jazz Club",
        "villagevanguard": "Village Vanguard",
        "bluenote.nyc": "Blue Note",
        "smokejazzclub": "Smoke Jazz Club",
        "ucbtheatre": "UCB Theatre",
        "thecaveatnyc": "Caveat",
        "thecomedycellar": "Comedy Cellar",
        "qedastoria": "Q.E.D. Astoria",
        "smorgasburg": "Smorgasburg",
        "thehighlinenyc": "The High Line",
        "centralparknyc": "Central Park",
        "domino_park": "Domino Park",
        "brooklynbridgepark": "Brooklyn Bridge Park",
        "bryantparknyc": "Bryant Park",
        "nycparks": "NYC Parks",
    }
    return mapping.get(account.lower(), "")


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
    bio_url = post.get("bio_url", "")

    # Try to find all URLs in the full caption (some appear only once at end).
    all_urls = re.findall(r"https?://[^\s)>\]\"']+", caption)

    # If caption mentions "link in bio" / "tickets in bio" but no URL is in
    # the caption itself, prepend the bio URL — that's where the user goes
    # for actual ticket info.
    has_link_in_bio = bool(re.search(
        r"\b(?:link|tickets?|info|details?|RSVP|sign\s*up)\s+in\s+bio\b",
        caption, re.IGNORECASE,
    )) or "🔗" in caption
    if has_link_in_bio and bio_url and bio_url not in all_urls:
        all_urls.insert(0, bio_url)

    # First check: is this post even about an event?
    # Posts with images get more leeway (we may OCR the image for details).
    if not _looks_like_event_post(caption, has_image=bool(image_url)):
        return []

    # Drop very old posts unless they reference an explicit future date.
    # Posts older than 60 days are usually retrospective.
    if post_date:
        from datetime import datetime, timezone, timedelta
        post_d = post_date if isinstance(post_date, datetime) else datetime.combine(post_date, datetime.min.time())
        if post_d.tzinfo is None:
            post_d = post_d.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - post_d).days
        if age_days > 60:
            # Only keep if caption has an explicit month-day or numeric date
            has_explicit_date = bool(re.search(
                r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}",
                caption, re.IGNORECASE,
            )) or bool(re.search(r"\b\d{1,2}/\d{1,2}", caption))
            if not has_explicit_date:
                return []

    # If account is a known venue, use it as default location.
    default_location = _account_default_location(account)

    sections = _split_caption(caption)
    # Detect if this post is clearly a multi-event roundup (many sections w/ dates).
    n_dated_sections = sum(1 for s in sections if _find_dates(s, post_date))
    multi_event = n_dated_sections >= 4

    events: list[dict] = []
    url_idx = 0  # walk through extracted URLs as we consume sections

    for section in sections:
        section = section.strip()
        if len(section) < 15:
            continue

        dates = _find_dates(section, post_date)

        # If this is a multi-event roundup, ONLY accept sections that contain
        # an explicit date. Otherwise we get caption fragments masquerading as events.
        if multi_event and not dates:
            continue

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

        loc_name = location or default_location
        events.append(build_event(
            title=title or section[:80],
            description=section[:400],
            event_date=event_date,
            start_time=time_str,
            location_name=loc_name,
            source="instagram",
            source_url=source_url,
            image_url=image_url,
            categories=categories,
        ))

    # If single-event post: treat the whole caption as one event with the post's
    # main date. This is more accurate than splitting captions that aren't roundups.
    if not multi_event:
        events = []  # discard the per-section attempts
        if post_date:
            full_caption = caption
            title = _extract_title(full_caption) or full_caption.split("\n")[0][:80]
            event_date = _find_dates(full_caption, post_date)
            event_date = event_date[0] if event_date else post_date.date()
            extracted_loc = _extract_location(full_caption)
            events.append(build_event(
                title=title,
                description=full_caption[:400],
                event_date=event_date,
                start_time=parse_time(full_caption),
                location_name=extracted_loc or default_location,
                source="instagram",
                source_url=all_urls[0] if all_urls else post_url,
                image_url=image_url,
                categories=infer_categories(title, full_caption),
            ))

    # Fallback: if no events at all, build one from the whole post
    if not events and post_date:
        title = _extract_title(caption) or caption[:80]
        extracted_loc = _extract_location(caption)
        events.append(build_event(
            title=title,
            description=caption[:400],
            event_date=post_date.date(),
            start_time=parse_time(caption),
            location_name=extracted_loc or default_location,
            source="instagram",
            source_url=all_urls[0] if all_urls else post_url,
            image_url=image_url,
            categories=infer_categories(title, caption),
        ))

    # Tag every event with the IG account it came from + engagement + profile signals.
    likes = post.get("likes", 0)
    comments = post.get("comments", 0)
    followers = post.get("profile_followers", 0)
    verified = post.get("profile_is_verified", False)
    is_affinity = account.lower() in _AFFINITY_ACCOUNTS_CACHE
    for ev in events:
        ev["instagramAccount"] = account
        if likes:
            ev["likes"] = likes
        if comments:
            ev["comments"] = comments
        if followers:
            ev["accountFollowers"] = followers
        if verified:
            ev["accountVerified"] = True
        if is_affinity:
            # User has previously saved from this account — they're high-affinity.
            ev["userAffinity"] = True

    return events


# ---------------------------------------------------------------------------
# Event-post detection — most IG posts are NOT events
# ---------------------------------------------------------------------------

# Words/phrases that strongly suggest the post is about a specific event.
_EVENT_POST_SIGNALS = [
    # Time / date markers
    r"\bdoors?\s*(?:open|at)?\s*\d",  # "doors at 8"
    r"\b\d+\s*(?:pm|am)\b",  # "8pm"
    r"\b\d+:\d+\s*(?:pm|am)?\b",  # "8:30pm"
    r"\btickets?\b",
    r"\brsvp\b",
    r"\b(?:link|tickets|info)\s+in\s+bio\b",
    r"\bbuy\s+tickets\b",
    r"\bget\s+tickets\b",
    r"\bjoin\s+us\b",
    r"\blu\.ma/",
    r"\bpartiful\.com/",
    r"\beventbrite\.com/",
    r"\bdice\.fm/",
    # Direct event language
    r"\b(?:concert|show|gig|set|festival|party|gala|premiere|opening|launch|screening|reading|workshop|class|tour|mixer|meetup|happy hour|brunch|dinner)\b",
    r"\b(?:performing|performance|playing|presents|hosts)\b",
    # Date patterns
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d+",
    r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)",
    r"\b(?:tonight|tomorrow|this\s+(?:weekend|friday|saturday|sunday|thursday))\b",
    # Venue markers
    r"\bat\s+@\w+",  # "at @venue_name"
    r"📍",
    r"🎟",
    r"🎫",
    r"🎤",
]
_EVENT_POST_SIGNAL_RES = [re.compile(p, re.IGNORECASE) for p in _EVENT_POST_SIGNALS]

# Phrases that strongly suggest the post is NOT an event (just content/art piece
# or recap of a past event).
_NON_EVENT_SIGNALS = [
    "throughout (?:his|her|their) career",
    "the artist (?:created|made|designed)",
    "this (?:work|piece|painting|sculpture)",
    "currently on view",
    "now on view",
    "have been featured",
    "have been shown",
    "has been featured",
    "in (?:our|the) (?:permanent )?collection",
    "from (?:our|the) collection",
    "🌹|🌷|💐",  # flower emoji posts are usually content
    "did you know",
    "fun fact",
    "happy birthday",
    "happy anniversary",
    "happy mother",
    "happy father",
    "happy holidays",
    # Past-tense recaps (these are NOT future events, they happened already)
    r"\b(?:throwback|tbt|flashback)\b",
    r"\bthroughback\b",
    r"\bone year ago\b",
    r"\blast (?:night|weekend|week|month) was\b",
    r"\bwhat a (?:night|weekend|show|crowd)\b",
    r"\bthank you (?:to|so much) (?:everyone|all|to those)",
    r"\b(?:thank|thanks) for coming",
    r"\bsold out (?:our|the) (?:show|night|event)",
    r"\bsuch a (?:great|amazing|incredible) (?:night|crowd|show)",
    r"\bwhat an (?:amazing|incredible|epic|unforgettable)",
    r"\brecap (?:of|from)",
    r"\bin case you missed",
    r"\bicymi\b",
]
_NON_EVENT_SIGNAL_RES = [re.compile(p, re.IGNORECASE) for p in _NON_EVENT_SIGNALS]


def _looks_like_event_post(caption: str, has_image: bool = False) -> bool:
    """Decide if an Instagram post is actually about an event.

    Most IG posts are NOT events — they're announcements, art descriptions,
    hype, behind-the-scenes content. We only emit an event if the post has
    sufficient positive signals AND no strong negative signals.

    If the post has an image (which we may OCR), we accept just 1 signal
    since image flyers often have generic captions like "May calendar 🩵".
    """
    if not caption or len(caption) < 20:
        return False

    # Strong negative signals = not an event
    if any(r.search(caption) for r in _NON_EVENT_SIGNAL_RES):
        return False

    # Posts with images get more leeway since the actual event details may
    # live in the image (calendar flyer, poster, etc.). Image OCR will
    # extract dates from those.
    threshold = 1 if has_image else 2
    signal_count = sum(1 for r in _EVENT_POST_SIGNAL_RES if r.search(caption))
    return signal_count >= threshold


# ---------------------------------------------------------------------------
# Caption splitting
# ---------------------------------------------------------------------------

_SPLIT_RE = re.compile(
    r"\n\n+"                              # double+ newlines
    r"|\n(?=[•●○‣◆▪︎★☆\-\*])"            # newline before bullet chars
    r"|\n(?=\d{1,2}[\.\)]\s)"            # newline before numbered list items
    r"|\n(?=📍|🎶|🎨|🎭|📚|🗓|🕐|👉)"   # newline before common event emoji
    # Day-of-week prefixed roundup items: "Monday: ..." / "MON 5/12: ..." / "Friday — ..."
    r"|\n(?=(?:Mon(?:day)?|Tue(?:s|sday)?|Wed(?:nesday)?|Thu(?:rs(?:day)?)?|Fri(?:day)?|Sat(?:urday)?|Sun(?:day)?)[\s,:—–\-•·\.])"
    # Date-prefixed items: "5/12: ..." / "May 12: ..."
    r"|\n(?=\d{1,2}/\d{1,2}[:\s\.,])"
    r"|\n(?=(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}[:\s\.,])"
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
    # MM.DD.YYYY (run club style: "05.09.2026")
    r"\d{1,2}\.\d{1,2}\.\d{4}",
    # "Saturday, May 5"
    r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+\d{1,2}",
    # "this Saturday", "next Friday"
    r"(?:this|next)\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)",
    # "this weekend", "next weekend"
    r"(?:this|next)\s+weekend",
    # relative
    r"(?:tonight|today|tomorrow)",
]


_WEEKDAY_NAMES = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


def _resolve_relative(phrase: str, base_date) -> "date | None":
    """Resolve relative phrases like 'tonight', 'this Saturday', 'next Fri'.

    base_date is the anchor (post date for IG posts).  Returns a date or None.
    """
    from datetime import timedelta
    p = phrase.lower().strip()

    if p in ("tonight", "today"):
        return base_date
    if p == "tomorrow":
        return base_date + timedelta(days=1)

    # "this Saturday" → next Saturday on or after base_date
    m = re.match(r"this\s+(\w+)", p)
    if m:
        wd = _WEEKDAY_NAMES.get(m.group(1))
        if wd is not None:
            days_ahead = (wd - base_date.weekday()) % 7
            return base_date + timedelta(days=days_ahead)

    # "next Saturday" → Saturday strictly AFTER this week
    m = re.match(r"next\s+(\w+)", p)
    if m:
        wd = _WEEKDAY_NAMES.get(m.group(1))
        if wd is not None:
            days_ahead = (wd - base_date.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            # "next" usually means the week after — add another 7
            return base_date + timedelta(days=days_ahead + 7)

    # "this weekend" → next Saturday on or after base_date
    if p in ("this weekend", "weekend"):
        days_ahead = (5 - base_date.weekday()) % 7
        return base_date + timedelta(days=days_ahead)
    if p == "next weekend":
        days_ahead = (5 - base_date.weekday()) % 7
        if days_ahead < 7:
            days_ahead += 7
        return base_date + timedelta(days=days_ahead)

    return None


def _find_dates(text: str, post_date=None) -> list:
    """Extract date objects from text using regex patterns + dateparser.

    If post_date is given, relative phrases like "tonight" / "tomorrow" /
    "this Friday" are anchored to the post's date instead of the scraper's
    "now".  This is critical because we scrape posts from days/weeks ago
    that mention "tomorrow" — meaning the day AFTER the post, not the day
    after we ran the scraper.
    """
    dates = []
    base_date = None
    if post_date is not None:
        base_date = post_date.date() if hasattr(post_date, "date") else post_date

    for pat in _DATE_PATTERNS:
        for match in re.finditer(pat, text, re.IGNORECASE):
            phrase = match.group()
            resolved = None
            if base_date is not None:
                resolved = _resolve_relative(phrase, base_date)
            if resolved is None:
                # Fall back to dateparser (handles "May 5", "5/5", etc.)
                resolved = parse_date(phrase)
            if resolved:
                dates.append(resolved)
    return dates


# ---------------------------------------------------------------------------
# Title extraction
# ---------------------------------------------------------------------------

_HYPE_PREFIX_RE = re.compile(
    r"^(?:just announced|announcing|newly announced|big news|huge news|"
    r"exciting news|great news|psa|hey [a-z]+|yo [a-z]+|"
    r"presale begins|tickets on sale|tickets are live|"
    r"now showing|now open|back by popular|last chance|"
    r"don[''`]?t miss|save the date|calling all|coming up|coming soon|"
    r"we[''`]?(?:ve got| got| are loving| are thrilled| are excited)|"
    r"shoutout|thank you|thanks to|photo by|video by|captured by|"
    r"got some \S+ gigs|real dancers|catch (?:his|her|their)|"
    r"clear your schedules)\s*[:!\-—,\s]*",
    re.IGNORECASE,
)


_METADATA_LINE_RES = [
    # "05.09.2026 / SAT / 11AM" — date/day/time line, no event content
    re.compile(r"^\d{1,2}[./]\d{1,2}[./]\d{2,4}(?:\s*[/|\-—]\s*[\w\s]+)*$"),
    # "Saturday May 5 - 7pm"
    re.compile(r"^(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*[,\s]+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d+(?:\s*[\-—|]\s*\d+\s*(?:am|pm))?$", re.IGNORECASE),
    # Pure month-day "May 5" or "May 5, 2026"
    re.compile(r"^(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?(?:\s*,?\s*\d{4})?$", re.IGNORECASE),
    # "5/9 - 11AM"
    re.compile(r"^\d{1,2}/\d{1,2}(?:/\d{2,4})?\s*[\-—|]?\s*\d*\s*(?:am|pm)?$", re.IGNORECASE),
]


def _is_metadata_line(line: str) -> bool:
    """True if line is just date/time metadata, not the event name."""
    return any(r.match(line) for r in _METADATA_LINE_RES)


def _extract_title(text: str) -> str:
    """Pull the most likely event title from a caption section.

    Heuristic: skip hype/announcement prefixes, find the first non-trivial
    line that looks like an event name.
    """

    if not text:
        return ""

    # Strip leading hype prefix
    cleaned_text = _HYPE_PREFIX_RE.sub("", text.strip(), count=1)

    for line in cleaned_text.strip().split("\n"):
        line = line.strip()
        # Strip emoji at start/end
        cleaned = re.sub(
            r"[\U0001F300-\U0001FAFF\U00002702-\U000027B0\U0000FE00-\U0000FE0F]",
            "",
            line,
        ).strip()
        # Strip leading punctuation
        cleaned = cleaned.lstrip(":;,.!? -—")
        # Skip lines that are just hashtags, handles, or punctuation
        if re.match(r"^[#@\s\W]+$", cleaned):
            continue
        # Skip if line is mostly hashtags
        if cleaned.count("#") >= 3 and len(cleaned) < 60:
            continue
        # Skip lines that are just date/time metadata
        # ("05.09.2026 / SAT / 11AM", "Saturday, May 5", "5/9 - 11AM")
        if _is_metadata_line(cleaned):
            continue
        if 8 < len(cleaned) < 120:
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
    # "meet @ Letish Cafe (171 S 4th St, ...)" — explicit venue + parenthesized address
    r"meet\s+@\s+([A-Z][\w\s&'\-]+?)\s*\(",
    # "at The Museum of..." / "at Brooklyn Mirage"
    r"\bat\s+([A-Z][A-Za-z\s&''\-]+?)(?:\n|$|,|\.|!)",
    # "Location: ..." or "Venue: ..." or "Where: ..."
    r"(?:Location|Venue|Where):\s*(.+?)(?:\n|$)",
    # Street addresses: "123 W 4th St"
    r"(\d{1,5}\s+[A-Z][A-Za-z]+(?:\s+[A-Za-z]+)?\s+(?:St|Ave|Blvd|Rd|Pl|Dr|Way|Ct|Ln)\.?)(?:\b|,)",
]


def _extract_location(text: str) -> str:
    """Try to pull a venue / location name from the text.

    Special-case @mentions of known venues — e.g., '@brooklynbowl' →
    'Brooklyn Bowl' (uses the same mapping as _account_default_location).
    """
    # Look for @account mentions first; if any maps to a known venue, use it.
    for handle_match in re.finditer(r"@([a-z0-9._]{2,30})", text, re.IGNORECASE):
        handle = handle_match.group(1).lower()
        venue = _account_default_location(handle)
        if venue:
            return venue

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
    """Run image OCR on event posts to fill in / enhance event details.

    OCR is expensive (~2-5s/image), so we only run it when the post is
    likely image-driven (short caption, calendar/flyer style).
    """

    if not _HAS_IMAGE_ANALYZER:
        return events

    image_url = post.get("image", "")
    if not image_url:
        return events

    caption = post.get("caption", "") or ""
    # Trigger OCR when:
    #  - caption is short (image likely contains the event details), or
    #  - any event from this post is missing critical data
    short_caption = len(caption) < 150
    needs_enrichment = any(
        not e.get("startTime") or not e.get("location", {}).get("name") or
        not e.get("title") or len(e.get("title", "")) < 10
        for e in events
    )

    if not (short_caption or needs_enrichment):
        return events

    try:
        image_info = analyze_event_image(image_url)
    except Exception as exc:
        print(f"[instagram] Image analysis failed: {exc}")
        return events

    if not image_info:
        return events

    enriched: list[dict] = []
    for event in events:
        if image_info.get("title") and (
            not event.get("title") or len(event["title"]) < 10
        ):
            event["title"] = image_info["title"]
        if image_info.get("date") and not event.get("date"):
            event["date"] = image_info["date"]
        if image_info.get("location") and not event["location"]["name"]:
            event["location"]["name"] = image_info["location"]
        if image_info.get("time") and not event.get("startTime"):
            event["startTime"] = image_info["time"]
        # Mark that this event was OCR-enriched
        event["ocrEnriched"] = True
        enriched.append(event)

    return enriched
