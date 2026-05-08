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
_FOLLOWING_ACCOUNTS_CACHE: set[str] = set()
_ACCOUNT_CURSORS_CACHE: dict = {}


def _load_following_accounts() -> set[str]:
    """Accounts the user directly follows (via discover.py harvest_following_list)."""
    import json, os
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data",
        "discovered_accounts.json",
    )
    if not os.path.isfile(path):
        return set()
    try:
        with open(path) as f:
            d = json.load(f)
        return {
            a["username"].lower()
            for a in d.get("accounts", [])
            if isinstance(a, dict) and a.get("discovered_via") == "user_following"
        }
    except Exception:
        return set()


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
    global _AFFINITY_ACCOUNTS_CACHE, _FOLLOWING_ACCOUNTS_CACHE, _ACCOUNT_CURSORS_CACHE, _ACCOUNT_QUALITY_CACHE
    _AFFINITY_ACCOUNTS_CACHE = _load_affinity_accounts()
    _FOLLOWING_ACCOUNTS_CACHE = _load_following_accounts()
    _ACCOUNT_CURSORS_CACHE = _load_account_cursors()
    _ACCOUNT_QUALITY_CACHE = _load_account_quality()
    print(f"[instagram] Cache: {len(_AFFINITY_ACCOUNTS_CACHE)} affinity, {len(_FOLLOWING_ACCOUNTS_CACHE)} following")

    loader = _get_authenticated_loader()
    if loader is None:
        return []

    all_events: list[dict] = []

    # 1. Saved posts — highest priority since user curated them
    saved_events, saved_accounts = _scrape_saved_posts(loader)
    all_events.extend(saved_events)
    # Saved posts update the affinity cache mid-run too
    _AFFINITY_ACCOUNTS_CACHE |= saved_accounts
    # Saved-post captions are gold — harvest authoritative URLs immediately
    for ev in saved_events:
        if ev.get("description"):
            saved_caption_urls = _extract_event_platform_urls(ev["description"])
            if saved_caption_urls:
                _save_caption_urls(saved_caption_urls)

    # 1b. Tagged posts — user was tagged, implicit invitation
    tagged_events, tagged_accounts = _scrape_tagged_posts(loader)
    all_events.extend(tagged_events)
    _AFFINITY_ACCOUNTS_CACHE |= tagged_accounts
    for ev in tagged_events:
        if ev.get("description"):
            tagged_caption_urls = _extract_event_platform_urls(ev["description"])
            if tagged_caption_urls:
                _save_caption_urls(tagged_caption_urls)

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

    # Skip dead accounts (404s, repeated failures) — auto-cleanup
    dead = _load_dead_accounts().get("accounts", {})
    dead_set = {u for u, info in dead.items() if info.get("reason") in ("not_exists", "repeated_failure", "stale_no_recent_posts")}
    before_dead = len(all_accounts)
    all_accounts = [a for a in all_accounts if a.lower() not in dead_set]
    if before_dead != len(all_accounts):
        print(f"[instagram] Skipped {before_dead - len(all_accounts)} dead accounts")

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

    # Track authoritative event-page URLs found inside captions (lu.ma,
    # eventbrite, partiful, posh.vip, ra.co, dice.fm). These let the generic
    # scraper fetch canonical structured data on the next run.
    caption_event_urls: set[str] = set()

    # Wall-clock budget for IG scraping — beyond this, stop and return what
    # we have so the rest of the pipeline (Eventbrite, Substack, etc.) can run.
    import time as _time
    ig_budget_seconds = float(os.environ.get("IG_TIME_BUDGET_SECONDS", "1500"))  # 25 min default
    started = _time.time()

    # Priority order so the most relevant accounts are guaranteed scraped
    # within the time budget. Tier (lower = higher priority):
    #   0 = saved-from (user explicitly bookmarked their posts)
    #   1 = directly followed by user
    #   2 = high-yield (>= 25% of recent posts produce events)
    #   3 = medium-yield (>= 10%)
    #   4 = unknown (newly discovered, not enough data)
    #   5 = low-yield (< 10% with >= 10 posts seen)
    # Inside each tier, sort by yield desc — best accounts of the tier first.
    def _priority(a: str) -> tuple[int, float]:
        al = a.lower()
        if al in _AFFINITY_ACCOUNTS_CACHE:
            base = 0
        elif al in _FOLLOWING_ACCOUNTS_CACHE:
            base = 1
        else:
            q = _ACCOUNT_QUALITY_CACHE.get(al, {})
            posts_seen = q.get("posts_scraped", 0)
            yield_ = (q.get("events_emitted", 0) / posts_seen) if posts_seen >= 10 else None
            if yield_ is None:
                base = 4  # unknown
            elif yield_ >= 0.25:
                base = 2
            elif yield_ >= 0.10:
                base = 3
            else:
                base = 5  # low-yield deprioritized
        # Negate yield so higher yield sorts FIRST inside each tier.
        q = _ACCOUNT_QUALITY_CACHE.get(al, {})
        posts_seen = q.get("posts_scraped", 0)
        y = (q.get("events_emitted", 0) / posts_seen) if posts_seen else 0.0
        return (base, -y)
    affinity_first = sorted(all_accounts, key=_priority)

    for idx, account in enumerate(affinity_first):
        elapsed = _time.time() - started
        if elapsed > ig_budget_seconds:
            print(f"[instagram] Time budget exhausted at {elapsed:.0f}s after {idx} accounts; stopping IG scrape")
            break
        try:
            posts = _fetch_posts(loader, account)
            account_event_count = 0
            # Is this account one the user saves-from? If so, every @-mention
            # in their event posts is a high-confidence recommendation.
            is_author_affinity = account.lower() in _AFFINITY_ACCOUNTS_CACHE
            for post in posts:
                # Capture bio URL once per account
                bio = post.get("bio_url", "")
                if bio and bio not in bio_urls_seen:
                    bio_urls_seen.add(bio)

                # Harvest authoritative event-page URLs from caption text.
                caption_event_urls |= _extract_event_platform_urls(post.get("caption", ""))

                extracted = _extract_events_from_caption(post, account)

                # If image analyzer is available, try to fill in gaps.
                if _HAS_IMAGE_ANALYZER:
                    extracted = _maybe_enrich_with_image(extracted, post)

                all_events.extend(extracted)
                account_event_count += len(extracted)

                # Affinity co-mention tracking: if this post is from an
                # account the user saves-from AND the post is about an event
                # (extracted >= 1), every @-mention in the caption is a
                # high-confidence recommendation. Bump per-mention counters.
                if is_author_affinity and extracted:
                    _record_affinity_comentions(account, post.get("caption", ""))
            # Record account-quality stats for this account this run.
            if posts:
                _record_account_activity(account, len(posts), account_event_count)
        except Exception as exc:
            print(f"[instagram] Failed @{account}: {exc}")

        # Rate-limit: sleep between accounts (skip after the last one).
        if idx < len(affinity_first) - 1:
            _time.sleep(IG_SLEEP_BETWEEN_ACCOUNTS)

    # 2b. IG's own 'Suggested for you' graph — for accounts the user saves
    # from, mine IG's related-profiles to surface accounts we don't yet
    # know about but IG's algorithm thinks are relevant. Bounded: only
    # affinity accounts (limit ~5 to bound API volume), only when full
    # hashtag-discovery is also enabled (so the budget is in full-sweep
    # territory, not quick-scrape).
    if os.environ.get("IG_HASHTAG_DISCOVERY", "0") == "1":
        related_total: set[str] = set()
        affinity_seeds = list(_AFFINITY_ACCOUNTS_CACHE)[:5]
        for seed in affinity_seeds:
            try:
                related = _harvest_related_profiles(loader, seed, max_related=8)
                related_total |= related
            except Exception:
                pass
        # Subtract dead + already-known
        dead_set = {u for u, info in _load_dead_accounts().get("accounts", {}).items()
                    if info.get("reason") in ("not_exists", "repeated_failure", "stale_no_recent_posts")}
        already_known = set(IG_ACCOUNTS) | set(load_discovered_accounts())
        new_related = related_total - dead_set - {a.lower() for a in already_known}
        if new_related:
            _add_to_discovered_accounts(new_related)
            print(f"[instagram-related] Added {len(new_related)} accounts via IG Suggested-for-you graph")

    # 3. Hashtag-driven discovery (opt-in via IG_HASHTAG_DISCOVERY=1).
    # Mines posts from NYC event hashtags — captures events from authors we
    # don't yet follow, AND registers those authors as discovered accounts
    # so future runs scrape them directly. Most expansive single channel.
    elapsed = _time.time() - started
    if elapsed < ig_budget_seconds:
        try:
            ht_events, ht_accounts = _scrape_hashtag_posts(loader)
            all_events.extend(ht_events)
            # Harvest caption URLs from hashtag posts too.
            for ev in ht_events:
                if ev.get("description"):
                    caption_event_urls |= _extract_event_platform_urls(ev["description"])
        except Exception as exc:
            print(f"[instagram-hashtag] Hashtag harvest failed: {exc}")

    # Persist bio URLs so the generic scraper can pick up event pages
    # (Linktree/Beacons/Eventbrite/lu.ma/etc.) on the next pipeline run.
    if bio_urls_seen:
        _save_bio_urls(bio_urls_seen)

    # Persist caption event URLs so the generic scraper grabs canonical
    # event data (lu.ma, eventbrite, partiful) on the next run.
    if caption_event_urls:
        _save_caption_urls(caption_event_urls)
        print(f"[instagram] Harvested {len(caption_event_urls)} event-platform URLs from captions")

    # Persist per-account cursors for incremental scraping next run
    if _ACCOUNT_CURSORS_CACHE:
        _save_account_cursors(_ACCOUNT_CURSORS_CACHE)

    # Persist per-account quality stats so future runs (and ranking) know
    # which accounts reliably produce events.
    if _ACCOUNT_QUALITY_CACHE:
        _save_account_quality(_ACCOUNT_QUALITY_CACHE)

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


_EVENT_PLATFORM_RE = re.compile(
    r"https?://(?:www\.)?(?:"
    r"lu\.ma/[A-Za-z0-9._-]+|"
    r"luma\.com/[A-Za-z0-9._-]+|"
    r"eventbrite\.com/(?:e|cc|o)/[^\s)>\]\"']+|"
    r"partiful\.com/e/[A-Za-z0-9._-]+|"
    r"posh\.vip/e/[^\s)>\]\"']+|"
    r"ra\.co/(?:events|promoters)/[^\s)>\]\"']+|"
    r"shotgun\.live/(?:[a-z]{2}/)?events/[^\s)>\]\"']+|"
    r"withtopography\.com/[^\s)>\]\"']+|"
    r"showtix4u\.com/[^\s)>\]\"']+|"
    r"tixr\.com/(?:groups|e)/[^\s)>\]\"']+"
    r")",
    re.IGNORECASE,
)


def _extract_event_platform_urls(caption: str) -> set[str]:
    """Pull authoritative event-page URLs from an IG caption.

    These platforms publish structured event data (JSON-LD or scrape-friendly
    HTML), so feeding them to the generic scraper turns a fragile caption
    parse into a reliable cross-source confirmation.
    """
    if not caption:
        return set()
    found = set()
    for m in _EVENT_PLATFORM_RE.finditer(caption):
        url = m.group(0).rstrip(".,;:!?)")
        # Drop trailing query-string fragments that are tracking-only.
        found.add(url)
    return found


def _harvest_post_comments(post, max_comments: int = 8) -> set[str]:
    """Pull event-platform URLs from top-level comments on an IG post.

    Reserved for HIGH-VALUE posts only (saved/tagged) so we don't multiply
    API volume across hundreds of curated-account posts. Top-level comments
    on event posts frequently contain ticket URLs from organizers and
    venue answers that aren't in the caption itself.
    """
    found: set[str] = set()
    try:
        comments = post.get_comments()
    except Exception:
        return found
    seen = 0
    for c in comments:
        if seen >= max_comments:
            break
        seen += 1
        text = getattr(c, "text", "") or ""
        if not text:
            continue
        found |= _extract_event_platform_urls(text)
    return found


def _save_caption_urls(urls: set[str]) -> None:
    """Append IG caption event-platform URLs to discovered_urls.json."""
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
                "discovered_via": "instagram_caption",
            })
            seen.add(url)
            added += 1

        if added:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                json.dump(existing, f, indent=2)
            print(f"[instagram] Added {added} caption event URLs to discovered_urls.json")
    except Exception as exc:
        print(f"[instagram] Failed to save caption URLs: {exc}")


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


_DEAD_ACCOUNTS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "dead_accounts.json",
)

_ACCOUNT_CURSORS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "account_cursors.json",
)

_ACCOUNT_QUALITY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "account_quality.json",
)


_ACCOUNT_QUALITY_CACHE: dict = {}


def _load_account_quality() -> dict:
    """Load per-account quality stats:
    {username: {posts_scraped, events_emitted, last_seen}}.

    Used to compute event-yield (events per post) so high-yield NYC event
    accounts get a small ranking boost. This is account-level memory that
    compounds across runs.
    """
    import json
    if not os.path.isfile(_ACCOUNT_QUALITY_PATH):
        return {}
    try:
        with open(_ACCOUNT_QUALITY_PATH) as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save_account_quality(quality: dict) -> None:
    import json
    os.makedirs(os.path.dirname(_ACCOUNT_QUALITY_PATH), exist_ok=True)
    tmp = _ACCOUNT_QUALITY_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(quality, f, indent=2)
    os.replace(tmp, _ACCOUNT_QUALITY_PATH)


def _record_account_activity(username: str, posts_count: int, events_count: int) -> None:
    """Update lifetime per-account counters for posts scraped and events emitted."""
    from datetime import datetime, timezone
    u = username.lower()
    entry = _ACCOUNT_QUALITY_CACHE.setdefault(u, {
        "posts_scraped": 0,
        "events_emitted": 0,
        "last_seen": "",
    })
    entry["posts_scraped"] = entry.get("posts_scraped", 0) + posts_count
    entry["events_emitted"] = entry.get("events_emitted", 0) + events_count
    entry["last_seen"] = datetime.now(timezone.utc).isoformat()


_AFFINITY_MENTION_RE = re.compile(r"@([a-z0-9_][a-z0-9._]{1,28}[a-z0-9_])", re.IGNORECASE)


def _harvest_related_profiles(loader, username: str, max_related: int = 10) -> set[str]:
    """Mine IG's own 'Suggested for you' graph for an account.

    When you visit a profile on IG, the 'Suggested for you' row shows
    related accounts in IG's recommendation algorithm. instaloader exposes
    this via Profile.get_related_profiles(). For high-signal accounts the
    user already saves from, the suggestions are highly relevant.

    Returns a set of usernames to add to discovered_accounts.
    """
    related: set[str] = set()
    try:
        profile = instaloader.Profile.from_username(loader.context, username)
    except Exception:
        return related
    try:
        rel_iter = profile.get_related_profiles()
    except Exception:
        return related
    count = 0
    try:
        for rp in rel_iter:
            if count >= max_related:
                break
            count += 1
            handle = (getattr(rp, "username", "") or "").lower()
            if not handle or handle == username.lower():
                continue
            related.add(handle)
    except Exception:
        # Iteration may fail mid-stream on rate limits — return what we got
        pass
    return related


def _record_affinity_comentions(author: str, caption: str) -> None:
    """Bump per-mention counters when an affinity-account event post mentions
    other accounts. Persisted in account_quality.json so high-co-mention
    accounts surface in ranking and discovery rotation.
    """
    if not caption:
        return
    author_l = author.lower()
    for m in _AFFINITY_MENTION_RE.finditer(caption):
        handle = m.group(1).lower()
        if handle == author_l or handle == IG_USERNAME.lower():
            continue
        # Skip obvious non-account mentions (emojis, generic terms)
        if len(handle) < 3:
            continue
        entry = _ACCOUNT_QUALITY_CACHE.setdefault(handle, {
            "posts_scraped": 0,
            "events_emitted": 0,
            "last_seen": "",
        })
        entry["affinity_comentions"] = entry.get("affinity_comentions", 0) + 1
        # Track WHICH affinity accounts mentioned this — useful for
        # surfacing "recommended by @theskint, @sipsandstoriesnyc"
        sources = entry.setdefault("affinity_comention_sources", [])
        if author_l not in sources:
            sources.append(author_l)
            # Cap to 10 most-recent contributors to bound payload
            if len(sources) > 10:
                entry["affinity_comention_sources"] = sources[-10:]


def _load_account_cursors() -> dict:
    """Load per-account cursors: {username: {last_shortcode: ..., last_seen: ...}}."""
    import json
    if not os.path.isfile(_ACCOUNT_CURSORS_PATH):
        return {}
    try:
        with open(_ACCOUNT_CURSORS_PATH) as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save_account_cursors(cursors: dict) -> None:
    import json
    os.makedirs(os.path.dirname(_ACCOUNT_CURSORS_PATH), exist_ok=True)
    tmp = _ACCOUNT_CURSORS_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cursors, f, indent=2)
    os.replace(tmp, _ACCOUNT_CURSORS_PATH)


def _load_dead_accounts() -> dict:
    """Load the dead-accounts ledger.  Format:

    {"accounts": {"username": {"reason": "...", "since": "...", "failure_count": N}}}
    """
    import json
    if not os.path.isfile(_DEAD_ACCOUNTS_PATH):
        return {"accounts": {}}
    try:
        with open(_DEAD_ACCOUNTS_PATH) as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {"accounts": {}}
    except Exception:
        return {"accounts": {}}


def _save_dead_accounts(data: dict) -> None:
    import json
    os.makedirs(os.path.dirname(_DEAD_ACCOUNTS_PATH), exist_ok=True)
    with open(_DEAD_ACCOUNTS_PATH, "w") as f:
        json.dump(data, f, indent=2)


def _mark_dead_account(username: str, reason: str) -> None:
    """Mark an account as dead — future scrape runs will skip it."""
    from datetime import datetime, timezone
    data = _load_dead_accounts()
    data.setdefault("accounts", {})[username.lower()] = {
        "reason": reason,
        "since": datetime.now(timezone.utc).isoformat(),
        "failure_count": data.get("accounts", {}).get(username.lower(), {}).get("failure_count", 0) + 1,
    }
    _save_dead_accounts(data)


def _record_account_failure(username: str, reason: str) -> None:
    """Record a transient failure. After 3 consecutive failures, mark dead."""
    data = _load_dead_accounts()
    entry = data.setdefault("accounts", {}).get(username.lower(), {"failure_count": 0})
    entry["failure_count"] = entry.get("failure_count", 0) + 1
    entry["last_reason"] = reason
    if entry["failure_count"] >= 3:
        from datetime import datetime, timezone
        entry["since"] = datetime.now(timezone.utc).isoformat()
        entry["reason"] = "repeated_failure"
        print(f"[instagram] @{username} hit 3 failures — marking dead")
    data["accounts"][username.lower()] = entry
    _save_dead_accounts(data)


def _is_dead_account(username: str) -> bool:
    """True if this account should be skipped because it's marked dead."""
    data = _load_dead_accounts()
    entry = data.get("accounts", {}).get(username.lower(), {})
    if entry.get("reason") in ("not_exists", "repeated_failure"):
        return True
    return False


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


# NYC hashtags consistently used to promote events. Order = priority since
# we'll cut off when the time budget is exhausted.
_IG_EVENT_HASHTAGS = [
    "nyceventsthisweek",
    "nycweekend",
    "brooklynevents",
    "whatsuptonyc",
    "nycnightlife",
    "williamsburgnyc",
    "nycdating",
    "nycbookclub",
    "nycrunclub",
    "thingstodonyc",
]


_USER_HASHTAGS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "user_hashtags.json",
)


def _harvest_user_hashtags(caption: str) -> set[str]:
    """Extract #hashtags from a caption (saved/tagged post). The user
    chose to save this — the hashtags they chose-to-save-with are a
    strong personalization signal for discovery."""
    if not caption:
        return set()
    out: set[str] = set()
    for m in re.finditer(r"#([a-z0-9_]{4,40})", caption, re.IGNORECASE):
        tag = m.group(1).lower()
        # Skip generic/non-NYC tags + likely-noise
        if tag in {"love", "fun", "vibes", "happy", "weekend", "monday", "friday",
                   "saturday", "sunday", "music", "art", "photography", "fashion"}:
            continue
        out.add(tag)
    return out


def _persist_user_hashtags(tags: set[str]) -> None:
    """Persist user-derived hashtag counters. Each save bumps the count;
    high-count tags get added to the hashtag-discovery rotation."""
    import json
    if not tags:
        return
    existing: dict = {}
    if os.path.isfile(_USER_HASHTAGS_PATH):
        try:
            with open(_USER_HASHTAGS_PATH) as f:
                existing = json.load(f) or {}
        except Exception:
            existing = {}
    counts: dict = existing.get("counts", {}) if isinstance(existing.get("counts"), dict) else {}
    for t in tags:
        counts[t] = counts.get(t, 0) + 1
    out = {
        "counts": counts,
        "last_updated": datetime.now().isoformat(),
    }
    try:
        os.makedirs(os.path.dirname(_USER_HASHTAGS_PATH), exist_ok=True)
        tmp = _USER_HASHTAGS_PATH + ".tmp"
        with open(tmp, "w") as f:
            json.dump(out, f, indent=2)
        os.replace(tmp, _USER_HASHTAGS_PATH)
    except Exception as exc:
        print(f"[instagram] Failed to save user hashtags: {exc}")


def _load_user_hashtag_rotation(min_count: int = 2, cap: int = 8) -> list[str]:
    """Return user-derived hashtags with at least `min_count` saves. These
    augment _IG_EVENT_HASHTAGS during the full-sweep hashtag mining."""
    import json
    if not os.path.isfile(_USER_HASHTAGS_PATH):
        return []
    try:
        with open(_USER_HASHTAGS_PATH) as f:
            d = json.load(f) or {}
    except Exception:
        return []
    counts = d.get("counts", {}) if isinstance(d.get("counts"), dict) else {}
    eligible = [(t, n) for t, n in counts.items() if n >= min_count]
    eligible.sort(key=lambda kv: -kv[1])
    return [t for t, _ in eligible[:cap]]


def _scrape_hashtag_posts(loader, max_posts_per_tag: int = 20) -> tuple[list[dict], set[str]]:
    """Mine NYC event hashtags for events + new author candidates.

    This is the biggest single expansion of the IG search space — we go from
    "scrape accounts we already know about" to "discover events from any
    NYC poster using these hashtags". Gated by env IG_HASHTAG_DISCOVERY=1
    because hashtag pulls are heavily rate-limited and can get sessions
    flagged.
    """
    if os.environ.get("IG_HASHTAG_DISCOVERY", "0") != "1":
        return [], set()

    events: list[dict] = []
    new_accounts: set[str] = set()
    started = time.time()
    budget_seconds = float(os.environ.get("IG_HASHTAG_BUDGET_SECONDS", "300"))  # 5 min
    dead_set = {u for u, info in _load_dead_accounts().get("accounts", {}).items()
                if info.get("reason") in ("not_exists", "repeated_failure", "stale_no_recent_posts")}

    # Mix in user-derived hashtags (from saved/tagged post captions) so the
    # discovery rotation reflects the user's actual interests, not just our
    # static seed list. User-derived tags get scraped FIRST since they're
    # the strongest personalization signal.
    user_tags = _load_user_hashtag_rotation(min_count=2, cap=8)
    rotation = list(dict.fromkeys(user_tags + _IG_EVENT_HASHTAGS))
    if user_tags:
        print(f"[instagram-hashtag] User-derived tags from saves: {user_tags}")

    for tag in rotation:
        if time.time() - started > budget_seconds:
            print(f"[instagram-hashtag] Budget exhausted; stopping after #{tag}")
            break
        try:
            hashtag = instaloader.Hashtag.from_name(loader.context, tag)
            count = 0
            for post in hashtag.get_posts():
                if count >= max_posts_per_tag:
                    break
                count += 1
                owner = (post.owner_username or "").lower()
                if not owner or owner in dead_set:
                    continue
                new_accounts.add(owner)

                # Build the same post-dict shape as _fetch_posts.
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
                # Carousel OCR for hashtag posts too — many hashtag-tagged
                # roundups are 10-slide carousels with per-slide events.
                if _HAS_IMAGE_ANALYZER and len(images) >= 3:
                    extracted = _maybe_enrich_with_image(extracted, post_dict)
                # Hashtag-discovered events: don't carry user-curation flags.
                # They get a smaller boost than saved/tagged but are still
                # candidates for ranking.
                events.extend(extracted)
            print(f"[instagram-hashtag] #{tag}: {count} posts scanned")
        except Exception as exc:
            print(f"[instagram-hashtag] #{tag} failed: {exc}")
            continue

    if new_accounts:
        # Persist new author candidates so they get scraped in regular runs.
        _add_to_discovered_accounts(new_accounts)
        print(f"[instagram-hashtag] Total: {len(events)} events, "
              f"{len(new_accounts)} new author candidates queued")
    return events, new_accounts


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
            # Carousel OCR fan-out — tagged posts may be 10-slide roundups
            # where each slide is a different event flyer. Without this we'd
            # miss 9/10 of those events.
            if _HAS_IMAGE_ANALYZER:
                extracted = _maybe_enrich_with_image(extracted, post_dict)
            events.extend(extracted)

            # Comments mining for tagged posts too — same value as saved.
            try:
                comment_urls = _harvest_post_comments(post, max_comments=8)
                if comment_urls:
                    _save_caption_urls(comment_urls)
            except Exception:
                pass
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
            # Carousel OCR fan-out — the user explicitly flagged that
            # carousel posts often have 10 different events, one per slide.
            # Saved posts are the user's highest-signal targets so apply
            # OCR fan-out unconditionally when image_analyzer is available.
            if _HAS_IMAGE_ANALYZER:
                extracted = _maybe_enrich_with_image(extracted, post_dict)
            events.extend(extracted)

            # Comments mining — saved posts are the highest-value targets.
            # Top-level comments on event posts often carry ticket URLs and
            # venue answers that the caption omits ("when's the next one?").
            # Bounded to saved posts only so we don't multiply API volume.
            try:
                comment_urls = _harvest_post_comments(post, max_comments=8)
                if comment_urls:
                    _save_caption_urls(comment_urls)
                    print(f"[instagram] @{owner} saved post: +{len(comment_urls)} URLs from comments")
            except Exception:
                # Comments may rate-limit; never block the scrape.
                pass

            # Hashtag personalization: extract #-tags from saved post
            # captions. These drive the hashtag-discovery rotation on
            # future runs — your saves shape what we mine.
            try:
                user_tags = _harvest_user_hashtags(post.caption or "")
                if user_tags:
                    _persist_user_hashtags(user_tags)
            except Exception:
                pass
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

    Dead accounts (consistent ProfileNotExists) get marked so future runs
    skip them automatically — keeps the scraper self-cleaning.
    """

    try:
        profile = instaloader.Profile.from_username(loader.context, username)
    except instaloader.exceptions.ProfileNotExistsException:
        print(f"[instagram] Profile @{username} does not exist, marking dead")
        _mark_dead_account(username, "not_exists")
        return []
    except Exception as exc:
        print(f"[instagram] Profile @{username} failed: {exc}")
        _record_account_failure(username, str(exc)[:200])
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

    # Incremental scraping: stop once we hit the most recent post we've
    # already seen (cursor lookup). Saves significant time on accounts
    # that haven't posted since last run.
    cursors = _ACCOUNT_CURSORS_CACHE
    last_seen = cursors.get(username.lower(), {}).get("last_shortcode")

    posts: list[dict] = []
    count = 0
    newest_shortcode = None
    newest_post_date = None

    for post in profile.get_posts():
        if count >= max_posts:
            break
        if newest_shortcode is None:
            newest_shortcode = post.shortcode
            newest_post_date = post.date_utc
        # Stop once we hit a post we've already processed (posts are
        # returned newest-first by instaloader).
        if last_seen and post.shortcode == last_seen:
            break

        # Collect all images from the post (carousel = sidecar). Crucially,
        # use display_url (always an image) rather than url (returns the
        # .mp4 for video posts / Reels — which won't render in <img>).
        images: list[str] = []
        try:
            if post.typename == "GraphSidecar":
                # Carousel: include EVERY slide's display image. Video slides
                # have valuable poster frames we'd previously discarded.
                for node in post.get_sidecar_nodes():
                    img = getattr(node, "display_url", None) or getattr(node, "url", None)
                    if img:
                        images.append(img)
            else:
                # Single-image OR video/Reel post: always use display_url so
                # Reels render their poster instead of a broken mp4 link.
                img = getattr(post, "display_url", None) or post.url
                images.append(img)
        except Exception:
            try:
                images.append(getattr(post, "display_url", post.url))
            except Exception:
                pass

        # Capture engagement signals (likes/comments) — high engagement
        # = real, popular event, not just any post.
        likes = 0
        comments = 0
        try:
            likes = int(getattr(post, "likes", 0) or 0)
            comments = int(getattr(post, "comments", 0) or 0)
        except Exception:
            pass

        # IG geo-tag: when a post is location-tagged, the venue name is
        # authoritative — much cleaner than parsing the caption's free text
        # for "@venue" mentions or "at X" patterns.
        geo_name = ""
        geo_lat = None
        geo_lng = None
        try:
            ig_loc = getattr(post, "location", None)
            if ig_loc is not None:
                geo_name = (getattr(ig_loc, "name", "") or "").strip()
                geo_lat = getattr(ig_loc, "lat", None)
                geo_lng = getattr(ig_loc, "lng", None)
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
            "geo_name": geo_name,
            "geo_lat": geo_lat,
            "geo_lng": geo_lng,
        })
        count += 1

    # Update cursor for this account so next run skips ahead
    if newest_shortcode:
        from datetime import datetime, timezone
        _ACCOUNT_CURSORS_CACHE[username.lower()] = {
            "last_shortcode": newest_shortcode,
            "last_seen": datetime.now(timezone.utc).isoformat(),
            "post_count": count,
        }

    # Stale-account auto-prune: if the newest post is >90 days old AND the
    # account isn't user-curated (saved/affinity/following), mark it stale.
    # Stale accounts don't post events — keeps the rotation tight.
    if newest_post_date is not None and username.lower() not in _AFFINITY_ACCOUNTS_CACHE \
            and username.lower() not in _FOLLOWING_ACCOUNTS_CACHE:
        from datetime import datetime, timezone, timedelta
        try:
            npd = newest_post_date if newest_post_date.tzinfo else newest_post_date.replace(tzinfo=timezone.utc)
            age_days = (datetime.now(timezone.utc) - npd).days
            if age_days >= 90:
                _mark_dead_account(username, "stale_no_recent_posts")
                print(f"[instagram] @{username} hasn't posted in {age_days}d — marked stale")
        except Exception:
            pass

    if last_seen and not posts:
        print(f"[instagram] @{username} has no new posts since last run — skipped")
    else:
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
    all_post_images = post.get("all_images") or []
    # extra_images is the carousel slides AFTER the cover image — used by
    # the EventModal to render an IG-style multi-image swiper.
    extra_imgs = [img for img in all_post_images if img and img != image_url][:9]
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

    # Location preference (most authoritative first):
    # 1. IG geo-tag (post.location.name) — venue confirmed by the poster
    # 2. Account default — known venue accounts (mapped statically)
    # 3. Caption text extraction (per-section)
    geo_name = (post.get("geo_name") or "").strip()
    default_location = geo_name or _account_default_location(account)
    geo_lat = post.get("geo_lat")
    geo_lng = post.get("geo_lng")

    sections = _split_caption(caption)
    # Detect if this post is clearly a multi-event roundup (many sections w/ dates).
    n_dated_sections = sum(1 for s in sections if _find_dates(s, post_date))
    # Threshold: 3+ dated sections (was 4) — better recall for shorter
    # roundups. Multi-image carousel posts where each slide is an event
    # flyer often have minimal captions but 3-4 inline-listed events.
    multi_event = n_dated_sections >= 3
    # Carousel posts with 4+ slides AND a short list of dated sections are
    # almost certainly per-slide-per-event roundups even if section count
    # is borderline.
    n_slides = len(post.get("all_images") or [])
    if not multi_event and n_slides >= 4 and n_dated_sections >= 2:
        multi_event = True

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
            extra_images=extra_imgs,
            lat=geo_lat,
            lng=geo_lng,
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
                extra_images=extra_imgs,
            lat=geo_lat,
            lng=geo_lng,
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
            extra_images=extra_imgs,
            lat=geo_lat,
            lng=geo_lng,
            categories=infer_categories(title, caption),
        ))

    # Tag every event with the IG account it came from + engagement + profile signals.
    likes = post.get("likes", 0)
    comments = post.get("comments", 0)
    followers = post.get("profile_followers", 0)
    verified = post.get("profile_is_verified", False)
    is_affinity = account.lower() in _AFFINITY_ACCOUNTS_CACHE
    is_following = account.lower() in _FOLLOWING_ACCOUNTS_CACHE
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
        if is_following:
            # User directly follows this account on IG.
            ev["userFollowing"] = True
        # Stamp lifetime account-quality stats so ranking can read them
        # without re-loading the JSON file per event.
        q = _ACCOUNT_QUALITY_CACHE.get(account.lower(), {})
        posts_seen = q.get("posts_scraped", 0)
        events_emitted = q.get("events_emitted", 0)
        if posts_seen >= 5:  # only meaningful with enough samples
            ev["accountEventYield"] = round(events_emitted / posts_seen, 3)
            ev["accountPostsSeen"] = posts_seen
        # Surface co-mention strength even when posts_seen is small —
        # accounts the user's saves-from accounts tag are high-confidence
        # even if we haven't directly scraped them many times.
        comentions = q.get("affinity_comentions", 0)
        if comentions > 0:
            ev["affinityComentions"] = comentions
            sources = q.get("affinity_comention_sources", [])
            if sources:
                ev["affinityComentionSources"] = sources[:5]

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
    # Photo/screenshot recap captions — these are content posts, not events
    r"\b(?:more|some|great) (?:pics|photos|shots) (?:from|of)\b",
    r"\bphotos?\s+(?:from|of)\s+(?:our|the|last)",
    r"\bscreenshot of\b",
    r"\bcourtesy of\s+@",
    r"^//\s*",  # photo-credit prefix like "// Screenshot of video"
    # Event was cancelled / rescheduled — date in caption is unreliable
    r"\brained out\b",
    r"\b(?:cancelled|canceled|postponed)\b",
    r"\bwill be rescheduled\b",
    # Past tense "we had" / "the night was"
    r"\b(?:we|the night) (?:had|was)\s+(?:a\s+)?(?:great|amazing|incredible|blast)",
    r"\bwe (?:had|enjoyed|loved)\s",
    # Promo/announcement only — no actual event being held
    r"\bpre-?orders? (?:are\s+)?(?:now\s+)?(?:open|available|live)\b",
    r"\bnew (?:single|album|book|product) (?:is\s+)?out\b",
    r"\bavailable (?:now|today)\s+(?:on|at)\b",
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
    r"|\n(?=📍|🎶|🎨|🎭|📚|🗓|🕐|👉|🎟|🎫|🎉|🍷|🍻|🎤)"  # event emoji
    # Number-emoji prefixes: 1️⃣ 2️⃣ 3️⃣ ... commonly used in carousel
    # roundups where each slide gets its own number marker
    r"|\n(?=[1-9]️⃣|\U0001f51f)"
    # Long-dash separators: ━━━━ ════ ═══ (split BEFORE the run only;
    # variable-width lookbehind isn't supported in stdlib re)
    r"|\n(?=[━═─]{3,})"
    # "Slide N" / "Photo N" / "Day N" / "Event N" / "Pic N" markers
    r"|\n(?=(?:Slide|Photo|Pic|Day|Event)\s*\d+\s*[:\.\)\-\—])"
    # Day-of-week prefixed roundup items
    r"|\n(?=(?:Mon(?:day)?|Tue(?:s|sday)?|Wed(?:nesday)?|Thu(?:rs(?:day)?)?|Fri(?:day)?|Sat(?:urday)?|Sun(?:day)?)[\s,:—–\-•·\.])"
    # Date-prefixed items: "5/12: ..." / "May 12: ..." / "5.12 ..."
    r"|\n(?=\d{1,2}/\d{1,2}[:\s\.,])"
    r"|\n(?=\d{1,2}\.\d{1,2}\.\d{2,4}[:\s])"
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


_FRAGMENT_TITLE_RE = re.compile(
    r"^(?:"
    # Lowercase function-word starters that signal a mid-sentence fragment
    r"we\s|to\s|from\s|in\s|on\s|at\s|of\s|the\s|and\s|but\s|or\s|that\s|this\s|"
    r"would\s|could\s|should\s|will\s|stills?\s|next\s|"
    # Image-credit / annotation prefixes
    r"//|@|#"
    r")",
    re.IGNORECASE,
)


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
        if _is_metadata_line(cleaned):
            continue
        # Skip caption-fragment starts ("we collage night", "to announce...",
        # "stills from Solaris", "// Screenshot of video"). Real event names
        # don't begin with lowercase function words or photo-credit prefixes.
        if _FRAGMENT_TITLE_RE.match(cleaned):
            continue
        # Skip lines whose first letter is lowercase AND first word is short:
        # almost always a sentence fragment, not an event name.
        first_word = cleaned.split(maxsplit=1)[0] if cleaned else ""
        if first_word and first_word[0].islower() and len(first_word) <= 4:
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

    # Carousel fan-out: posts with 3+ slides are typically multi-event roundups
    # (e.g., "10 events this week" with one flyer per slide). We've already
    # enriched slide 1; OCR the remaining slides and emit additional events
    # for slides that produce a distinct date/title signature.
    extras = _fan_out_carousel_slides(enriched, post)
    return enriched + extras


def _fan_out_carousel_slides(base_events: list[dict], post: dict) -> list[dict]:
    """OCR carousel slides 2..N and emit additional events when they produce
    a distinct (date, title) signature from the existing events.

    Inherits user-curation flags from the first base event so a saved-post
    carousel produces saved sub-events, etc.
    """
    if not _HAS_IMAGE_ANALYZER:
        return []
    all_images = post.get("all_images") or []
    if len(all_images) < 3:
        return []
    if not base_events:
        return []

    base = base_events[0]
    base_loc = base.get("location") or {}

    seen_signatures: set[tuple[str, str]] = set()
    for ev in base_events:
        sig = (
            ev.get("date") or "",
            (ev.get("title") or "")[:40].strip().lower(),
        )
        seen_signatures.add(sig)

    # Cap slides we OCR so a 20-slide carousel doesn't blow the wall clock.
    MAX_SLIDES = 8
    extras: list[dict] = []
    from datetime import date as _date

    for img_url in all_images[1:MAX_SLIDES]:
        try:
            info = analyze_event_image(img_url)
        except Exception:
            continue
        if not info or not info.get("date") or not info.get("title"):
            continue

        sig = (info["date"], info["title"][:40].strip().lower())
        if sig in seen_signatures:
            continue
        seen_signatures.add(sig)

        try:
            ev_date = _date.fromisoformat(info["date"])
        except Exception:
            continue

        new_ev = build_event(
            title=info["title"],
            description=(base.get("description") or "")[:300],
            event_date=ev_date,
            start_time=info.get("time"),
            location_name=info.get("location") or base_loc.get("name", ""),
            address=base_loc.get("address", ""),
            source="instagram",
            source_url=base.get("sourceUrl"),
            image_url=img_url,
            categories=base.get("categories", []),
        )
        # Inherit user-curation signals from the base event — a saved roundup
        # post should produce saved sub-events too.
        for flag in ("userSaved", "userTagged", "userAffinity", "userFollowing"):
            if base.get(flag):
                new_ev[flag] = True
        new_ev["ocrEnriched"] = True
        extras.append(new_ev)

    return extras
