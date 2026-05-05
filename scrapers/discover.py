"""Instagram BFS-based account discovery.

Mimics how a curious user finds new event accounts: starting from a seed list,
fetch recent posts, extract @mentions from captions, score each mentioned
account for "is this a NYC event-focused account?", keep promising ones, and
optionally recurse one level deeper.

Discovered accounts are persisted to JSON so they can be merged into the
Instagram scraper's account list on subsequent runs.

This module reuses the authenticated instaloader session pattern from
``scrapers.sources.instagram`` (see ``_get_authenticated_loader``).
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
import instaloader

from .config import IG_ACCOUNTS, IG_SESSION_FILE, IG_USERNAME

# ---------------------------------------------------------------------------
# Constants & configuration
# ---------------------------------------------------------------------------

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DISCOVERED_PATH = os.path.join(DATA_DIR, "discovered_accounts.json")
DISCOVERED_URLS_PATH = os.path.join(DATA_DIR, "discovered_urls.json")

# Score threshold for accounts discovered via @mentions in captions
# (BFS).  Lower threshold here = more permissive but more noise.
SCORE_THRESHOLD = 0.40

# Threshold for accounts the user themselves follows. Be permissive — even
# if a follow doesn't have explicit "event" keywords, the user's manual
# decision to follow is signal in itself.
USER_FOLLOWING_THRESHOLD = 0.30

# Hard caps to keep IG happy.
MAX_NEW_ACCOUNTS_PER_RUN = 50
SLEEP_BETWEEN_PROFILES_SEC = 1.0
N_POSTS_TO_SCAN = 8

# Mention extraction: @ followed by IG-valid username chars.
# IG usernames: 1-30 chars, alphanum + . + _.
_MENTION_RE = re.compile(r"@([A-Za-z0-9_.]{2,30})")

# Linktree-style aggregator hosts whose pages we'll follow to harvest URLs.
_LINK_AGGREGATORS = (
    "linktr.ee",
    "beacons.ai",
    "lnk.bio",
    "bio.link",
    "linkin.bio",
    "later.com",
    "campsite.bio",
    "msha.ke",
    "withkoji.com",
    "stan.store",
)

# Event-platform domains we want to harvest from bios + linktrees.
_EVENT_URL_HINTS = (
    "lu.ma",
    "luma.com",
    "partiful.com",
    "eventbrite.com",
    "eventbrite.co",
    "dice.fm",
    "ra.co",
    "shotgun.live",
    "tixr.com",
    "withfriends.co",
    "posh.vip",
    "fever.com",
    "sosh.com",
    "withfriends.co",
)

# Bio scoring keyword groups. Each group contributes once (max one hit per
# group) so a bio dense in one category doesn't dominate.
_NYC_KEYWORDS = (
    "nyc", "new york", "new york city", "manhattan", "brooklyn", "queens",
    "bronx", "harlem", "williamsburg", "bushwick", "lower east side",
    "lower east", "uptown", "downtown", "the village", "soho", "tribeca",
    "ny", "nyny",
)
_EVENT_KEYWORDS = (
    "event", "events", "things to do", "happening", "happenings", "party",
    "parties", "tickets", "rsvp", "what's on", "whats on", "guide",
    "calendar", "lineup", "show", "shows", "concert", "rave", "dance",
    "nightlife", "afterhours",
)
_VENUE_KEYWORDS = (
    "venue", "rooftop", "club", "bar", "lounge", "loft", "warehouse",
    "speakeasy", "supper club", "music hall", "live music", "diy",
    "underground",
)
_CULTURE_KEYWORDS = (
    "art", "gallery", "curator", "curated", "museum", "exhibition",
    "literary", "books", "bookstore", "poetry", "film", "screening",
    "festival", "open mic", "comedy", "improv",
)
_LOCATION_MARKERS = ("📍", "🗽", "🌆", "🌃")
_PLATFORM_HINTS = (
    "lu.ma", "luma", "partiful", "eventbrite", "linktr.ee", "beacons.ai",
    "dice.fm", "ra.co", "shotgun",
)


# ---------------------------------------------------------------------------
# Authentication (mirrors scrapers.sources.instagram)
# ---------------------------------------------------------------------------

def _get_authenticated_loader() -> instaloader.Instaloader | None:
    """Return an authenticated Instaloader instance, or None if no session."""

    session_path = IG_SESSION_FILE

    if not os.path.isfile(session_path):
        print(
            f"[discover] WARNING: No session file at {session_path}. "
            "Skipping discovery. Run `instaloader --login {username}`."
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
        print(f"[discover] Authenticated as @{IG_USERNAME}")
        return loader
    except Exception as exc:
        print(f"[discover] WARNING: Failed to load session: {exc}.")
        return None


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: str, default: dict) -> dict:
    if not os.path.isfile(path):
        return default
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load_discovered_accounts() -> list[str]:
    """Return the list of usernames previously discovered (empty if none)."""

    data = _read_json(DISCOVERED_PATH, {"accounts": []})
    return [entry["username"] for entry in data.get("accounts", []) if entry.get("username")]


def _load_discovered_state() -> dict:
    return _read_json(DISCOVERED_PATH, {"accounts": [], "lastDiscovery": None})


def _save_discovered_state(state: dict) -> None:
    _write_json(DISCOVERED_PATH, state)


def _load_discovered_urls_state() -> dict:
    return _read_json(DISCOVERED_URLS_PATH, {"urls": [], "lastDiscovery": None})


def _save_discovered_urls_state(state: dict) -> None:
    _write_json(DISCOVERED_URLS_PATH, state)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score_event_account(profile) -> float:
    """Return a 0-1 score: is this likely a NYC event/lifestyle account?

    Looks at bio text, external URL, follower/post counts, and emoji
    location markers. Each signal contributes a small amount; we cap at 1.0.
    """

    score = 0.0

    bio = (getattr(profile, "biography", "") or "").lower()
    external_url = (getattr(profile, "external_url", "") or "").lower()
    full_name = (getattr(profile, "full_name", "") or "").lower()
    haystack = " ".join([bio, full_name])

    # NYC signal — required-ish; weighted heavy.
    if any(kw in haystack for kw in _NYC_KEYWORDS):
        score += 0.30

    # Event-language signal.
    if any(kw in haystack for kw in _EVENT_KEYWORDS):
        score += 0.20

    # Venue / nightlife signal.
    if any(kw in haystack for kw in _VENUE_KEYWORDS):
        score += 0.10

    # Culture signal.
    if any(kw in haystack for kw in _CULTURE_KEYWORDS):
        score += 0.10

    # Bio location emoji markers.
    if any(marker in bio for marker in _LOCATION_MARKERS):
        score += 0.05

    # Bio mentions a known event platform name (textually).
    if any(p in bio for p in _PLATFORM_HINTS):
        score += 0.10

    # External URL points to a known event platform OR aggregator (which
    # often hosts links to event platforms).
    if external_url:
        url_host = urlparse(external_url).netloc.lower()
        if any(host in url_host for host in _EVENT_URL_HINTS):
            score += 0.20
        elif any(host in url_host for host in _LINK_AGGREGATORS):
            score += 0.10

    # Activity signal: enough posts to be real.
    post_count = getattr(profile, "mediacount", 0) or 0
    if post_count >= 50:
        score += 0.05

    # Follower band: real but not mega-influencer.
    followers = getattr(profile, "followers", 0) or 0
    if 1_000 <= followers <= 500_000:
        score += 0.05
    elif followers > 500_000:
        # Big celebrity/brand accounts almost never deliver actionable events.
        score -= 0.20

    return max(0.0, min(1.0, score))


# ---------------------------------------------------------------------------
# Mention extraction
# ---------------------------------------------------------------------------

def extract_mentions_from_posts(
    loader: instaloader.Instaloader,
    username: str,
    n_posts: int = N_POSTS_TO_SCAN,
) -> list[str]:
    """Pull unique @mentions from the most recent N posts of an account."""

    try:
        profile = instaloader.Profile.from_username(loader.context, username)
    except instaloader.exceptions.ProfileNotExistsException:
        print(f"[discover] @{username} does not exist, skipping")
        return []
    except Exception as exc:
        print(f"[discover] Failed to load @{username}: {exc}")
        return []

    if getattr(profile, "is_private", False):
        print(f"[discover] @{username} is private, skipping")
        return []

    mentions: list[str] = []
    seen: set[str] = set()
    count = 0

    try:
        for post in profile.get_posts():
            if count >= n_posts:
                break
            count += 1
            caption = post.caption or ""
            for match in _MENTION_RE.finditer(caption):
                handle = match.group(1).lower().rstrip(".")
                if handle and handle not in seen and handle != username.lower():
                    seen.add(handle)
                    mentions.append(handle)
    except Exception as exc:
        print(f"[discover] Error iterating posts for @{username}: {exc}")

    return mentions


# ---------------------------------------------------------------------------
# Bio link extraction & Linktree expansion
# ---------------------------------------------------------------------------

def extract_bio_links(profile) -> list[str]:
    """Return a list of external URLs from a profile's bio.

    If the bio link is a Linktree / Beacons / similar aggregator, fetch the
    aggregator page and harvest any event-platform URLs we find on it.
    """

    urls: list[str] = []
    external_url = (getattr(profile, "external_url", "") or "").strip()
    if not external_url:
        return urls

    urls.append(external_url)

    host = urlparse(external_url).netloc.lower()
    if not any(agg in host for agg in _LINK_AGGREGATORS):
        return urls

    # Aggregator: fetch and harvest.
    try:
        with httpx.Client(follow_redirects=True, timeout=15.0,
                          headers={"User-Agent": "Mozilla/5.0"}) as client:
            resp = client.get(external_url)
            if resp.status_code != 200:
                return urls
            text = resp.text
    except Exception as exc:
        print(f"[discover] Failed to fetch aggregator {external_url}: {exc}")
        return urls

    found = re.findall(r'https?://[^\s"\'<>)]+', text)
    for url in found:
        url_host = urlparse(url).netloc.lower()
        if any(hint in url_host for hint in _EVENT_URL_HINTS):
            if url not in urls:
                urls.append(url)

    return urls


def _save_discovered_urls(urls: list[str], discovered_via: str) -> None:
    """Append harvested event URLs to the discovered_urls JSON store."""

    if not urls:
        return

    state = _load_discovered_urls_state()
    existing = {entry["url"] for entry in state.get("urls", [])}
    added = 0

    for url in urls:
        if url in existing:
            continue
        # Skip the aggregator landing pages themselves; only keep concrete
        # event-platform URLs.
        host = urlparse(url).netloc.lower()
        if not any(hint in host for hint in _EVENT_URL_HINTS):
            continue
        state.setdefault("urls", []).append({
            "url": url,
            "discovered_at": _now_iso(),
            "discovered_via": discovered_via,
        })
        existing.add(url)
        added += 1

    if added:
        state["lastDiscovery"] = _now_iso()
        _save_discovered_urls_state(state)
        print(f"[discover]   harvested {added} event URLs from @{discovered_via}'s bio links")


# ---------------------------------------------------------------------------
# BFS discovery
# ---------------------------------------------------------------------------

def _evaluate_candidate(
    loader: instaloader.Instaloader,
    handle: str,
) -> tuple[float, instaloader.Profile | None]:
    """Load a candidate's profile and score it. Returns (score, profile)."""

    try:
        profile = instaloader.Profile.from_username(loader.context, handle)
    except instaloader.exceptions.ProfileNotExistsException:
        return (0.0, None)
    except Exception as exc:
        print(f"[discover] Could not evaluate @{handle}: {exc}")
        return (0.0, None)

    if getattr(profile, "is_private", False):
        return (0.0, profile)

    score = score_event_account(profile)
    return (score, profile)


def discover_accounts(
    seed_accounts: list[str],
    max_depth: int = 1,
    max_per_seed: int = 5,
) -> list[str]:
    """BFS through Instagram from ``seed_accounts`` to find new event accounts.

    Strategy:
      1. For each account in the current frontier, fetch recent posts.
      2. Extract @mentions from captions.
      3. Score each mentioned account; keep those above SCORE_THRESHOLD.
      4. Persist accepted accounts and add them to the next frontier.
      5. Stop when depth is exhausted or we've added MAX_NEW_ACCOUNTS_PER_RUN.

    Returns the list of newly-discovered usernames added this run.
    """

    loader = _get_authenticated_loader()
    if loader is None:
        return []

    state = _load_discovered_state()
    already_known: set[str] = set(IG_ACCOUNTS) | {
        entry["username"].lower() for entry in state.get("accounts", [])
    }

    # Normalise seeds.
    frontier: list[tuple[str, str]] = [(s.lower(), s.lower()) for s in seed_accounts]
    # tuple is (username_to_explore, origin_seed)

    newly_discovered: list[dict] = []
    explored: set[str] = set()

    for depth in range(max_depth):
        if not frontier:
            break
        next_frontier: list[tuple[str, str]] = []

        for username, origin in frontier:
            if username in explored:
                continue
            explored.add(username)

            if len(newly_discovered) >= MAX_NEW_ACCOUNTS_PER_RUN:
                print(f"[discover] Hit MAX_NEW_ACCOUNTS_PER_RUN ({MAX_NEW_ACCOUNTS_PER_RUN}); stopping")
                break

            mentions = extract_mentions_from_posts(loader, username, N_POSTS_TO_SCAN)
            time.sleep(SLEEP_BETWEEN_PROFILES_SEC)

            promising_count = 0
            kept_for_next: list[str] = []

            # Cap how many candidates from each seed we actually evaluate to
            # avoid hammering IG. Process the most-frequent first by keeping
            # insertion order (already deduped).
            for handle in mentions[: max_per_seed * 4]:
                if handle in already_known or handle in explored:
                    continue
                if len(newly_discovered) >= MAX_NEW_ACCOUNTS_PER_RUN:
                    break
                if promising_count >= max_per_seed:
                    break

                score, profile = _evaluate_candidate(loader, handle)
                time.sleep(SLEEP_BETWEEN_PROFILES_SEC)

                if profile is None:
                    continue
                if score < SCORE_THRESHOLD:
                    continue

                # Accept!
                already_known.add(handle)
                newly_discovered.append({
                    "username": handle,
                    "score": round(score, 3),
                    "discovered_at": _now_iso(),
                    "discovered_via": origin,
                })
                promising_count += 1
                kept_for_next.append(handle)

                # Harvest any event URLs from the bio (incl. linktree).
                try:
                    bio_urls = extract_bio_links(profile)
                    _save_discovered_urls(bio_urls, discovered_via=handle)
                except Exception as exc:
                    print(f"[discover]   bio link expansion failed for @{handle}: {exc}")

            print(
                f"[discover] Exploring @{username}... found {len(mentions)} mentions, "
                f"{promising_count} promising"
            )

            # Queue accepted accounts for next BFS level.
            if depth + 1 < max_depth:
                for handle in kept_for_next:
                    next_frontier.append((handle, origin))

        if len(newly_discovered) >= MAX_NEW_ACCOUNTS_PER_RUN:
            break
        frontier = next_frontier

    # Persist results.
    if newly_discovered:
        state.setdefault("accounts", []).extend(newly_discovered)
    state["lastDiscovery"] = _now_iso()
    _save_discovered_state(state)

    print(f"[discover] Run complete: {len(newly_discovered)} new accounts saved")
    return [entry["username"] for entry in newly_discovered]


# ---------------------------------------------------------------------------
# Public API for the scrape pipeline
# ---------------------------------------------------------------------------

def harvest_following_list(loader, max_to_evaluate: int = 200) -> list[str]:
    """Pull the authenticated user's following list and score each for
    event-likelihood. Returns usernames whose profiles look event-focused.

    This is a powerful signal: if the user manually follows an account, it's
    much more likely to be relevant to their interests than a random discovery.
    """
    try:
        my_profile = instaloader.Profile.from_username(loader.context, IG_USERNAME)
    except Exception as exc:
        print(f"[discover] Could not load @{IG_USERNAME} profile: {exc}")
        return []

    relevant: list[dict] = []
    count = 0
    try:
        for followee in my_profile.get_followees():
            if count >= max_to_evaluate:
                break
            count += 1
            try:
                score = score_event_account(followee)
                # Be more permissive for user's own follows
                if score >= USER_FOLLOWING_THRESHOLD:
                    relevant.append({
                        "username": followee.username,
                        "score": round(score, 3),
                        "discovered_via": "user_following",
                        "discovered_at": _now_iso(),
                    })
                time.sleep(0.5)
            except Exception as exc:
                print(f"[discover]   skipping followee @{followee.username}: {exc}")
                continue
    except Exception as exc:
        print(f"[discover] Failed to iterate followees: {exc}")
        return []

    # Save them
    if relevant:
        state = _load_discovered_state()
        already = {a["username"].lower() for a in state.get("accounts", [])}
        new_relevant = [a for a in relevant if a["username"].lower() not in already]
        if new_relevant:
            state.setdefault("accounts", []).extend(new_relevant)
            state["lastDiscovery"] = _now_iso()
            _save_discovered_state(state)
            print(f"[discover] Harvested {len(new_relevant)} relevant accounts from your following list")
        else:
            print(f"[discover] No new accounts from following list (all {len(relevant)} already known)")

    return [a["username"] for a in relevant]


async def run_discovery() -> list[str]:
    """Run BFS discovery and return seed + discovered accounts (deduped).

    Strategy:
      1. Harvest the user's IG following list — score each followee, keep relevant ones
      2. Use both the seed accounts AND user's relevant follows as BFS seeds
      3. BFS one level through @mentions in their captions
      4. Persist everything for the scraper to use

    This is intended to be called from an orchestration script (e.g.
    ``run_discovery.py``) on a less-frequent schedule than the main scrape.
    """

    # 1. Harvest the user's following list (powerful signal)
    loader = _get_authenticated_loader()
    following_seeds: list[str] = []
    if loader is not None:
        try:
            following_seeds = harvest_following_list(loader, max_to_evaluate=200)
        except Exception as exc:
            print(f"[discover] Following list harvest failed: {exc}")

    # 2. BFS from seed accounts AND from relevant follows.
    # Depth 2: find accounts that user's network mentions, AND accounts
    # those secondary accounts mention.  This casts a much wider net.
    seed_set = sorted(set(IG_ACCOUNTS) | set(following_seeds))
    print(f"[discover] BFS starting from {len(seed_set)} seeds ({len(IG_ACCOUNTS)} configured + {len(following_seeds)} from your follows)")

    discover_accounts(
        seed_accounts=seed_set,
        max_depth=2,
        max_per_seed=4,
    )

    discovered = load_discovered_accounts()
    merged = sorted(set(IG_ACCOUNTS) | set(discovered))
    print(f"[discover] Merged account list: {len(merged)} total "
          f"({len(IG_ACCOUNTS)} seed + {len(discovered)} discovered)")
    return merged
