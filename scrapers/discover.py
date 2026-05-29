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
MAX_NEW_ACCOUNTS_PER_RUN = 120
# Cap how many candidates a single suggested-for-you sweep can persist —
# prevents one noisy seed from dominating a discovery run.
MAX_NEW_PER_SUGGESTED_BATCH = 8
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


from scrapers.utils.user_excluded import load_excluded_account_set as _load_user_excluded_account_set  # noqa: E402


def load_discovered_accounts() -> list[str]:
    """Return the list of usernames previously discovered (empty if none)."""

    data = _read_json(DISCOVERED_PATH, {"accounts": []})
    return [entry["username"] for entry in data.get("accounts", []) if entry.get("username")]


def _load_discovered_state() -> dict:
    return _read_json(DISCOVERED_PATH, {"accounts": [], "lastDiscovery": None})


def _save_discovered_state(state: dict) -> None:
    _write_json(DISCOVERED_PATH, state)


def _load_discovered_urls_state() -> dict:
    raw = _read_json(DISCOVERED_URLS_PATH, {"urls": [], "lastDiscovery": None})
    # Legacy format on disk is a flat list of url-entries; new format is
    # {"urls": [...], "lastDiscovery": ...}. Normalize on read.
    if isinstance(raw, list):
        return {"urls": raw, "lastDiscovery": None}
    return raw


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

def harvest_related_profiles(loader, username: str, max_related: int = 10) -> set[str]:
    """Mine IG's related-account graph for a seed.

    IG's official 'Suggested for you' endpoint was removed from public
    APIs years ago, so instaloader no longer exposes `get_related_profiles`.
    The closest replacement is `get_followees()` — the accounts the seed
    itself follows. For a high-yield event account, who they follow is a
    much stronger endorsement signal than IG's algorithmic suggestion
    anyway (the seed manually chose those accounts).

    Returns a set of lowercased usernames to feed into the discovery pipeline.
    """
    related: set[str] = set()
    try:
        profile = instaloader.Profile.from_username(loader.context, username)
    except Exception:
        return related
    if getattr(profile, "is_private", False):
        return related
    # Skip mega-accounts: their followees are full of random brands/friends
    # and the signal-to-noise ratio drops sharply.
    if (getattr(profile, "followees", 0) or 0) > 5000:
        return related
    try:
        for i, followee in enumerate(profile.get_followees()):
            if i >= max_related:
                break
            handle = (getattr(followee, "username", "") or "").lower()
            if not handle or handle == username.lower():
                continue
            related.add(handle)
    except Exception:
        # Iteration may fail mid-stream on rate limits — return what we got
        pass
    return related


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


def _evaluate_and_save_candidates(
    loader,
    handles,
    origin: str,
    threshold: float,
    already_known: set[str],
    max_to_accept: int = MAX_NEW_PER_SUGGESTED_BATCH,
    sleep_between: float = SLEEP_BETWEEN_PROFILES_SEC,
) -> list[dict]:
    """Score each candidate handle, persist those above `threshold`, return
    the accepted entries. Mutates `already_known` so the same handle isn't
    re-evaluated. Persists to discovered_accounts.json after the batch.

    Used by both the @-mention BFS path and the suggested-for-you sweep —
    single source of truth for candidate evaluation.
    """
    new: list[dict] = []
    for handle in handles:
        handle = handle.lower()
        if handle in already_known:
            continue
        if len(new) >= max_to_accept:
            break
        score, profile = _evaluate_candidate(loader, handle)
        time.sleep(sleep_between)
        if profile is None or score < threshold:
            continue
        already_known.add(handle)
        new.append({
            "username": handle,
            "score": round(score, 3),
            "discovered_at": _now_iso(),
            "discovered_via": origin,
        })
        try:
            bio_urls = extract_bio_links(profile)
            _save_discovered_urls(bio_urls, discovered_via=handle)
        except Exception as exc:
            print(f"[discover]   bio link expansion failed for @{handle}: {exc}")
    if new:
        state = _load_discovered_state()
        state.setdefault("accounts", []).extend(new)
        state["lastDiscovery"] = _now_iso()
        _save_discovered_state(state)
    return new


def _top_yield_accounts(seed_pool, n: int = 20, min_posts: int = 10) -> list[str]:
    """Return up to N highest-yield usernames from seed_pool by
    events_emitted/posts_scraped, gated on posts_scraped >= min_posts.
    Reads scrapers/data/account_quality.json.
    """
    quality_path = os.path.join(DATA_DIR, "account_quality.json")
    if not os.path.isfile(quality_path):
        return []
    try:
        with open(quality_path) as f:
            quality = json.load(f)
    except Exception:
        return []
    pool = {a.lower() for a in seed_pool}
    ranked: list[tuple[float, str]] = []
    for acct, info in (quality.items() if isinstance(quality, dict) else []):
        if not isinstance(info, dict):
            continue
        if acct.lower() not in pool:
            continue
        posts = info.get("posts_scraped", 0) or 0
        if posts < min_posts:
            continue
        ev = info.get("events_emitted", 0) or 0
        y = ev / posts if posts else 0.0
        ranked.append((y, acct))
    ranked.sort(reverse=True)
    return [acct for _y, acct in ranked[:n]]


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

    frontier: list[tuple[str, str]] = [(s.lower(), s.lower()) for s in seed_accounts]
    # tuple is (username_to_explore, origin_seed)

    all_new: list[dict] = []
    explored: set[str] = set()

    for depth in range(max_depth):
        if not frontier:
            break
        next_frontier: list[tuple[str, str]] = []

        for username, origin in frontier:
            if username in explored:
                continue
            explored.add(username)

            if len(all_new) >= MAX_NEW_ACCOUNTS_PER_RUN:
                print(f"[discover] Hit MAX_NEW_ACCOUNTS_PER_RUN ({MAX_NEW_ACCOUNTS_PER_RUN}); stopping")
                break

            mentions = extract_mentions_from_posts(loader, username, N_POSTS_TO_SCAN)
            time.sleep(SLEEP_BETWEEN_PROFILES_SEC)

            candidates = [m for m in mentions[: max_per_seed * 4]
                          if m not in already_known and m not in explored]
            new_entries = _evaluate_and_save_candidates(
                loader,
                candidates,
                origin=origin,
                threshold=SCORE_THRESHOLD,
                already_known=already_known,
                max_to_accept=max_per_seed,
            )
            all_new.extend(new_entries)

            print(
                f"[discover] Exploring @{username}... found {len(mentions)} mentions, "
                f"{len(new_entries)} promising"
            )

            if depth + 1 < max_depth:
                for entry in new_entries:
                    next_frontier.append((entry["username"], origin))

        if len(all_new) >= MAX_NEW_ACCOUNTS_PER_RUN:
            break
        frontier = next_frontier

    print(f"[discover] Run complete: {len(all_new)} new accounts saved")
    return [entry["username"] for entry in all_new]


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

    # Pre-load user-excluded accounts so they never enter the discovered
    # set in the first place — saves the per-followee scoring call and
    # keeps discovered_accounts.json from constantly churning excluded
    # handles back in on every harvest pass.
    excluded = _load_user_excluded_account_set()

    relevant: list[dict] = []
    count = 0
    try:
        for followee in my_profile.get_followees():
            if count >= max_to_evaluate:
                break
            count += 1
            if followee.username.lower() in excluded:
                continue
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


def _suggested_for_you_sweep(
    loader,
    seeds: list[str],
    threshold: float,
    max_related_per_seed: int,
    max_seeds: int,
) -> int:
    """For each seed, mine IG's 'Suggested for you' graph and persist
    high-scoring candidates with discovered_via=f"suggested_for:{seed}".
    Returns total new accounts saved.
    """
    if not seeds:
        return 0
    state = _load_discovered_state()
    already_known = set(IG_ACCOUNTS) | {
        e["username"].lower() for e in state.get("accounts", [])
    }
    total_new = 0
    for seed in seeds[:max_seeds]:
        related = harvest_related_profiles(loader, seed, max_related=max_related_per_seed)
        new_candidates = [h for h in related if h not in already_known]
        if not new_candidates:
            time.sleep(SLEEP_BETWEEN_PROFILES_SEC)
            continue
        new_entries = _evaluate_and_save_candidates(
            loader,
            new_candidates,
            origin=f"suggested_for:{seed}",
            threshold=threshold,
            already_known=already_known,
            max_to_accept=MAX_NEW_PER_SUGGESTED_BATCH,
        )
        total_new += len(new_entries)
        time.sleep(SLEEP_BETWEEN_PROFILES_SEC)
    return total_new


async def run_discovery() -> list[str]:
    """Tiered IG discovery that mirrors how a curious user would explore IG:

    Tier 1 — accounts the USER follows (highest trust signal):
      a. Harvest the user's following list, score each.
      b. BFS one level through @mentions in their recent posts (max_per_seed=6).
      c. For up to 30 user-follows, mine IG's 'Suggested for you' graph and
         add high-scoring candidates with discovered_via='suggested_for:<seed>'.

    Tier 2 — curated IG_ACCOUNTS (broad NYC event-account seed):
      a. BFS one level (max_per_seed=4).
      b. Suggested-for-you sweep on the top-20 highest-yield curated accounts
         (yield = events_emitted / posts_scraped from account_quality.json).

    Returns the merged account list (curated + all discovered) for the
    scrape pipeline.
    """

    loader = _get_authenticated_loader()
    if loader is None:
        return sorted(set(IG_ACCOUNTS))

    # Tier 1 — user follows
    following_seeds: list[str] = []
    try:
        following_seeds = harvest_following_list(loader, max_to_evaluate=300)
    except Exception as exc:
        print(f"[discover] Following list harvest failed: {exc}")
    print(f"[discover] Tier 1: {len(following_seeds)} user-followed accounts")

    if following_seeds:
        discover_accounts(
            seed_accounts=following_seeds,
            max_depth=1,
            max_per_seed=6,
        )
        added = _suggested_for_you_sweep(
            loader,
            seeds=following_seeds,
            threshold=USER_FOLLOWING_THRESHOLD,
            max_related_per_seed=8,
            max_seeds=30,
        )
        print(f"[discover] Tier 1 suggested-for-you added {added} accounts")

    # Tier 2 — curated IG_ACCOUNTS
    print(f"[discover] Tier 2: {len(IG_ACCOUNTS)} curated accounts")
    discover_accounts(
        seed_accounts=list(IG_ACCOUNTS),
        max_depth=1,
        max_per_seed=4,
    )
    curated_top = _top_yield_accounts(IG_ACCOUNTS, n=20)
    print(f"[discover] Tier 2 suggested-for-you on top-{len(curated_top)} yield accounts")
    added = _suggested_for_you_sweep(
        loader,
        seeds=curated_top,
        threshold=SCORE_THRESHOLD,
        max_related_per_seed=6,
        max_seeds=20,
    )
    print(f"[discover] Tier 2 suggested-for-you added {added} accounts")

    discovered = load_discovered_accounts()
    merged = sorted(set(IG_ACCOUNTS) | set(discovered))
    print(f"[discover] Merged account list: {len(merged)} total "
          f"({len(IG_ACCOUNTS)} seed + {len(discovered)} discovered)")
    return merged
