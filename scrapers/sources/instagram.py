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
    IG_SPOTS_ACCOUNTS,
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

# Number of most-recent posts to re-process on EVERY scrape, regardless of
# whether their shortcode matches the stored cursor. Picks up caption edits
# (curators frequently fix dates / add ticket links after posting), engagement
# growth (velocity), and accumulating comment attendance signals. 3 strikes
# the balance between freshness and rate-limit cost.
_MIN_FRESH_REFETCH = 3


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
    # GUARD: only add accounts whose saved post ACTUALLY PARSED AS AN EVENT.
    # Without this, every random save (a cute-dog video, a news post, a
    # brand promo) added its account to discovered_accounts — crowding the
    # discovery pool with @nba, @sephora, @wellsfargo etc. that have nothing
    # to do with NYC events. We only want accounts where the user saved
    # actual-event content.
    discovered_now = set(load_discovered_accounts())
    seed_set = {a.lower() for a in IG_ACCOUNTS}
    accounts_that_yielded_events = {
        (ev.get("instagramAccount") or "").lower()
        for ev in saved_events
        if ev.get("instagramAccount")
    }
    new_from_saves = (saved_accounts & accounts_that_yielded_events) - seed_set - discovered_now
    if new_from_saves:
        _add_to_discovered_accounts(new_from_saves)
        print(f"[instagram] Added {len(new_from_saves)} event-producing accounts from saved posts: {sorted(new_from_saves)}")
    skipped_non_event = (saved_accounts - accounts_that_yielded_events) - seed_set - discovered_now
    if skipped_non_event:
        print(f"[instagram] Skipped {len(skipped_non_event)} saved-from accounts (no event yielded): {sorted(skipped_non_event)[:5]}")

    # 2. Curated + discovered accounts (skip ones we just covered via saved)
    all_accounts = sorted(set(IG_ACCOUNTS) | set(load_discovered_accounts()))

    # Skip dead accounts (404s, repeated failures) — auto-cleanup. Curated
    # accounts (IG_ACCOUNTS) get a 21-day cooldown-then-retest, so transient
    # IG outages, rate-limits, and brief privacy toggles don't permanently
    # kill the curated set. Discovered (non-curated) accounts stay dead since
    # the discovery pool is large and fast-replenishing.
    from datetime import datetime, timezone, timedelta
    dead = _load_dead_accounts().get("accounts", {})
    curated_lower = {a.lower() for a in IG_ACCOUNTS}
    cooldown_cutoff = datetime.now(timezone.utc) - timedelta(days=21)
    dead_set: set[str] = set()
    retested_curated = 0
    for u, info in dead.items():
        if info.get("reason") not in ("not_exists", "repeated_failure", "stale_no_recent_posts"):
            continue
        # Curated retest: if the dead-marker is older than 21 days, give it
        # another shot this run.
        if u.lower() in curated_lower:
            since = info.get("since", "")
            try:
                ts = datetime.fromisoformat(since)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts < cooldown_cutoff:
                    retested_curated += 1
                    continue  # don't add to dead_set — let it run
            except Exception:
                # Legacy/missing timestamp → assume eligible.
                retested_curated += 1
                continue
        dead_set.add(u.lower())
    before_dead = len(all_accounts)
    all_accounts = [a for a in all_accounts if a.lower() not in dead_set]
    if before_dead != len(all_accounts):
        print(f"[instagram] Skipped {before_dead - len(all_accounts)} dead accounts")
    if retested_curated:
        print(f"[instagram] Re-testing {retested_curated} curated accounts after 21d cooldown")

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
    ig_budget_seconds = float(os.environ.get("IG_TIME_BUDGET_SECONDS", "2400"))  # 40 min default
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
    # Curated seed list (IG_ACCOUNTS) is protected from tier-5 demotion —
    # these are accounts the user explicitly chose. Same protection as
    # stale-prune. Without this, a curated account that switches to non-
    # event content for a stretch (seasonal, hiatus, batch posting)
    # gets permanently demoted because yield never recovers.
    curated_set = {a.lower() for a in IG_ACCOUNTS}

    def _priority(a: str) -> tuple[int, float]:
        al = a.lower()
        if al in _AFFINITY_ACCOUNTS_CACHE:
            base = 0
        elif al in _FOLLOWING_ACCOUNTS_CACHE:
            base = 1
        elif al in curated_set:
            # Curated accounts always get tier 2 minimum — they earn their
            # spot through user choice, not yield. Rolling-window yield
            # would be better long-term but tier protection is cheap.
            base = 2
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

    # Split the iteration into PROTECTED (tier 0 affinity + tier 1 user-follows)
    # and BUDGETED (everyone else). Protected accounts run regardless of the
    # time budget so user-followed accounts NEVER get starved by a long tail
    # of low-yield seeds. Same per-account body for both.
    protected = [a for a in affinity_first if _priority(a)[0] <= 1]
    budgeted = [a for a in affinity_first if _priority(a)[0] > 1]

    # Priority-only mode (set by scrape-priority.yml cron): scrape only the
    # protected pass, skip budgeted accounts and the downstream hashtag /
    # venue-tag / story / highlight passes. Lets the priority cron run on
    # a tight schedule without competing with the full sweep.
    protected_only = os.environ.get("IG_PROTECTED_ONLY", "0") == "1"
    if protected_only:
        budgeted = []
    print(f"[instagram] {len(protected)} protected + {len(budgeted)} budgeted accounts"
          + (" [PROTECTED_ONLY]" if protected_only else ""))

    def _scrape_one_account(account: str) -> None:
        try:
            posts = _fetch_posts(loader, account)
            account_event_count = 0
            is_author_affinity = account.lower() in _AFFINITY_ACCOUNTS_CACHE
            for post in posts:
                bio = post.get("bio_url", "")
                if bio and bio not in bio_urls_seen:
                    bio_urls_seen.add(bio)
                caption_event_urls.update(
                    _extract_event_platform_urls(post.get("caption", ""))
                )
                extracted = _extract_events_from_caption(post, account)
                if _HAS_IMAGE_ANALYZER:
                    extracted = _maybe_enrich_with_image(extracted, post)
                all_events.extend(extracted)
                account_event_count += len(extracted)
                if is_author_affinity and extracted:
                    _record_affinity_comentions(account, post.get("caption", ""))
                if extracted:
                    tagged = post.get("tagged_users", [])
                    if tagged:
                        _record_tagged_user_discovery(account, tagged, is_author_affinity)
            if posts:
                _record_account_activity(account, len(posts), account_event_count)
        except Exception as exc:
            print(f"[instagram] Failed @{account}: {exc}")

    # Pass 1: protected (no budget check)
    for idx, account in enumerate(protected):
        _scrape_one_account(account)
        if idx < len(protected) - 1:
            _time.sleep(IG_SLEEP_BETWEEN_ACCOUNTS)

    # Pass 2: budgeted
    for idx, account in enumerate(budgeted):
        elapsed = _time.time() - started
        if elapsed > ig_budget_seconds:
            print(f"[instagram] Budget exhausted after {len(protected)} protected + {idx} budgeted accounts ({elapsed:.0f}s)")
            break
        _scrape_one_account(account)
        if idx < len(budgeted) - 1:
            _time.sleep(IG_SLEEP_BETWEEN_ACCOUNTS)

    # 2b. IG's 'Suggested for you' graph mining moved to scrapers/discover.py
    # (`harvest_related_profiles`) so it runs in the discovery cron, not the
    # scrape cron — frees scrape budget for actual event extraction.

    # 3. Hashtag-driven discovery (opt-in via IG_HASHTAG_DISCOVERY=1).
    # Mines posts from NYC event hashtags — captures events from authors we
    # don't yet follow, AND registers those authors as discovered accounts
    # so future runs scrape them directly. Most expansive single channel.
    elapsed = _time.time() - started
    if elapsed < ig_budget_seconds and not protected_only:
        try:
            ht_events, ht_accounts = _scrape_hashtag_posts(loader)
            all_events.extend(ht_events)
            # Harvest caption URLs from hashtag posts too.
            for ev in ht_events:
                if ev.get("description"):
                    caption_event_urls |= _extract_event_platform_urls(ev["description"])
        except Exception as exc:
            print(f"[instagram-hashtag] Hashtag harvest failed: {exc}")

    # 4. Venue-tagged-posts mining. For each known venue account, fetch
    # posts where THIRD parties (DJs, promoters, fans) tagged the venue.
    # The venue's own feed is curated marketing; the tagged-posts surface
    # event flyers from organizers, opening acts, and fans — gold for
    # comprehensive event coverage at NYC venues. Time-budgeted, can be
    # disabled via IG_VENUE_TAGGED=0.
    elapsed = _time.time() - started
    if elapsed < ig_budget_seconds and not protected_only and os.environ.get("IG_VENUE_TAGGED", "1") != "0":
        try:
            vt_events, vt_owners = _scrape_venue_tagged_posts(loader)
            all_events.extend(vt_events)
            for ev in vt_events:
                if ev.get("description"):
                    caption_event_urls |= _extract_event_platform_urls(ev["description"])
            # Discovered owners (third-party promoters) → discovery pool
            if vt_owners:
                seed_set = {a.lower() for a in IG_ACCOUNTS}
                discovered_now = {a.lower() for a in load_discovered_accounts()}
                fresh = vt_owners - seed_set - discovered_now
                if fresh:
                    _add_to_discovered_accounts(fresh)
                    print(f"[instagram-venue-tagged] Surfaced {len(fresh)} new promoter accounts from venue tags")
        except Exception as exc:
            print(f"[instagram-venue-tagged] Venue tagged-posts harvest failed: {exc}")

    # 5. IG Stories — 24h ephemeral content where event flyers go FIRST.
    # This is THE channel the user has to manually scroll IG to see, since
    # stories don't appear in feed and disappear after a day. Capturing
    # them is the highest-leverage move for "user doesn't want to scroll IG".
    # Time-budgeted (3 min default), gated by IG_STORIES=0 to disable.
    # Only auth-user-followed accounts are accessible (instaloader limit).
    elapsed = _time.time() - started
    if elapsed < ig_budget_seconds and os.environ.get("IG_STORIES", "1") != "0":
        try:
            story_events = _scrape_stories(loader)
            all_events.extend(story_events)
            for ev in story_events:
                if ev.get("description"):
                    caption_event_urls |= _extract_event_platform_urls(ev["description"])
        except Exception as exc:
            print(f"[instagram-stories] Stories harvest failed: {exc}")

    # 6. Story HIGHLIGHTS — pinned story collections on venue/curated accounts.
    # Unlike 24h stories, highlights PERSIST. Venues curate them as
    # "Upcoming Shows", "This Week", "Events" — effectively their own
    # editorial best-of. Capturing them is a major unlock: every venue
    # we mine surfaces a hand-curated event roster the venue itself
    # decided was worth pinning. Time-budgeted, IG_HIGHLIGHTS=0 to disable.
    elapsed = _time.time() - started
    if elapsed < ig_budget_seconds and not protected_only and os.environ.get("IG_HIGHLIGHTS", "1") != "0":
        try:
            hl_events = _scrape_account_highlights(loader)
            all_events.extend(hl_events)
            for ev in hl_events:
                if ev.get("description"):
                    caption_event_urls |= _extract_event_platform_urls(ev["description"])
        except Exception as exc:
            print(f"[instagram-highlights] Highlights harvest failed: {exc}")

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
    # Known event ticketing platforms — these have structured JSON-LD
    r"lu\.ma/[A-Za-z0-9._-]+|"
    r"luma\.com/[A-Za-z0-9._-]+|"
    r"eventbrite\.com/(?:e|cc|o)/[^\s)>\]\"']+|"
    r"partiful\.com/e/[A-Za-z0-9._-]+|"
    r"posh\.vip/e/[^\s)>\]\"']+|"
    r"ra\.co/(?:events|promoters)/[^\s)>\]\"']+|"
    r"shotgun\.live/(?:[a-z]{2}/)?events/[^\s)>\]\"']+|"
    r"withtopography\.com/[^\s)>\]\"']+|"
    r"showtix4u\.com/[^\s)>\]\"']+|"
    r"tixr\.com/(?:groups|e)/[^\s)>\]\"']+|"
    # Generic venue-website pattern: ANY domain with /events/<id> or
    # /event/<id> or /e/<slug> path. Covers bookclubbar.com, museum
    # sites, venue calendars, etc. Generic scraper falls back to OG
    # metadata when JSON-LD isn't present, so even if the venue's
    # site is JS-rendered the individual event URL will produce a
    # title + image + description.
    r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9-]+)+/(?:events?|e|tickets?)/[A-Za-z0-9][A-Za-z0-9._-]+"
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


# Attendance-intent phrases — comments containing these are high-effort
# signals that real people are RSVPing, distinct from passive likes.
_ATTENDANCE_INTENT_RE = re.compile(
    r"\b(?:"
    r"going!?|i'?m going|i'?ll be there|count me in|i'?m in|"
    r"see you there|see u there|saving (?:my )?seat|"
    r"rsvp(?:'?ed| in)?|signed up|just rsvp|"
    r"can'?t wait|so excited|excited for this|"
    r"\+\d+|"  # "+1", "+2 friends"
    r"bringing (?:my|a) (?:friend|crew|date)|"
    r"will (?:try to )?(?:be there|come|attend)"
    r")\b",
    re.IGNORECASE,
)
# A comment with multiple @-tagged friends is an "inviting friends" signal.
_FRIEND_INVITE_RE = re.compile(r"@[a-z0-9._]{2,30}", re.IGNORECASE)


def _harvest_post_comments(post, max_comments: int = 8) -> tuple[set[str], int]:
    """Pull event-platform URLs AND attendance signals from top-level comments.

    Returns (urls, attendance_score). The attendance score is the count of
    comments expressing attendance intent or tagging friends — a stronger
    popularity proxy than likes since it requires effort.

    Reserved for HIGH-VALUE posts only (saved/tagged) so we don't multiply
    API volume across hundreds of curated-account posts. Top-level comments
    on event posts frequently contain ticket URLs from organizers and
    venue answers that aren't in the caption itself.
    """
    found: set[str] = set()
    attendance_score = 0
    try:
        comments = post.get_comments()
    except Exception:
        return found, 0
    seen = 0
    for c in comments:
        if seen >= max_comments:
            break
        seen += 1
        text = getattr(c, "text", "") or ""
        if not text:
            continue
        found |= _extract_event_platform_urls(text)
        # Attendance intent: explicit "going!" / "rsvp'd" type phrases.
        if _ATTENDANCE_INTENT_RE.search(text):
            attendance_score += 2
        # Friend invitation: 2+ @-tags in one comment is a near-sure signal
        # this person is inviting friends to attend.
        mentions = _FRIEND_INVITE_RE.findall(text)
        if len(mentions) >= 2:
            attendance_score += 1
    return found, attendance_score


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


_DEAD_ACCOUNT_RETEST_DAYS = 21


def _is_dead_account(username: str) -> bool:
    """True if this account should be skipped because it's marked dead.

    Curated IG_ACCOUNTS get a 21-day cooldown-then-retest pass: even if
    they got marked dead (transient IG rate-limit, network blip, brief
    privacy toggle), we re-attempt periodically so the curated set is
    self-healing — analogous to the dead-URL retest path in generic.py.
    """
    data = _load_dead_accounts()
    entry = data.get("accounts", {}).get(username.lower(), {})
    if entry.get("reason") not in ("not_exists", "repeated_failure"):
        return False

    # Curated accounts: allow a periodic retest. Discovered accounts stay
    # dead — they were never explicitly chosen and the pool is large.
    if username.lower() in {a.lower() for a in IG_ACCOUNTS}:
        from datetime import datetime, timezone, timedelta
        since = entry.get("since", "")
        try:
            ts = datetime.fromisoformat(since)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except Exception:
            return False  # missing/legacy timestamp → eligible
        cooldown = datetime.now(timezone.utc) - timedelta(days=_DEAD_ACCOUNT_RETEST_DAYS)
        if ts < cooldown:
            return False  # cooled down — give it another chance
    return True


def _record_tagged_user_discovery(author: str, tagged: list[str], is_author_affinity: bool) -> None:
    """Treat tagged_users on event posts as a high-confidence discovery
    signal. Skip self-tags and known-aggregator accounts.

    When the post author is in the user's affinity set, additionally bump
    affinity-comention counters so these accounts surface in the comention
    boost path during ranking.
    """
    if not tagged:
        return
    # Skip self-tags and accounts that just clutter (e.g., big platforms).
    SKIP = {
        author.lower(),
        IG_USERNAME.lower() if IG_USERNAME else "",
        "instagram", "explore", "reels",
    }
    new_tags: set[str] = set()
    for u in tagged:
        u = (u or "").lstrip("@").lower()
        if not u or u in SKIP:
            continue
        if not re.match(r"^[a-z0-9._]{2,40}$", u):
            continue
        new_tags.add(u)
    if not new_tags:
        return

    # Skip ones we already know about — _add_to_discovered_accounts is a
    # no-op for duplicates, but doing the filter here avoids reading the
    # whole file on every post.
    seed = {a.lower() for a in IG_ACCOUNTS}
    discovered_now = {a.lower() for a in load_discovered_accounts()}
    fresh = new_tags - seed - discovered_now
    if fresh:
        _add_to_discovered_accounts(fresh)
        print(f"[instagram] @{author} tagged {len(fresh)} new accounts in event post: {sorted(fresh)[:5]}")

    # Affinity comention: if author is affinity, every tagged account
    # gets a comention bump (stronger signal than a caption mention since
    # tagged_users requires explicit author choice, not a regex match).
    if is_author_affinity:
        author_l = author.lower()
        for u in new_tags:
            entry = _ACCOUNT_QUALITY_CACHE.setdefault(u, {
                "posts_scraped": 0,
                "events_emitted": 0,
                "last_seen": "",
            })
            # Weight 2: tagged_users is more authoritative than caption regex.
            entry["affinity_comentions"] = entry.get("affinity_comentions", 0) + 2
            sources = entry.setdefault("affinity_comention_sources", [])
            if author_l not in sources:
                sources.append(author_l)
                if len(sources) > 10:
                    entry["affinity_comention_sources"] = sources[-10:]


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
# we'll cut off when the time budget is exhausted. Curated for the user's
# vibe (books / art / fitness / social / cultural — not nightclub-heavy).
_IG_EVENT_HASHTAGS = [
    # Tier 1: weekly-curation tags (broadest event surface area)
    "nyceventsthisweek",
    "nycweekend",
    "thingstodonyc",
    "freenyc",                 # free events — high signal for budget-aware
    # Tier 2: vibe-aligned themed tags
    "nycbookclub",
    "nycrunclub",
    "nyccomedy",               # comedy is a great social non-drinking option
    "nycart",                  # gallery openings, art events
    "nycgallery",
    "nycyoga",                 # wellness / morning fitness
    "nycworkshop",             # classes, ceramics, painting, etc.
    "bookwormsofny",
    # Tier 3: neighborhood-specific (close to user's home)
    "williamsburgnyc",
    "brooklynevents",
    "brooklynnight",           # broader than nightclub — covers concerts/dinner
    # Tier 4: catch-alls (fall back when above are exhausted)
    "whatsuptonyc",
    "nycdating",
    "nycnightlife",            # last — soft-penalty + hard-block filter trims
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
                # OCR-first helper handles sparse-caption posts (common in
                # hashtag-tagged flyer reposts) AND folds in carousel OCR
                # for multi-slide roundups.
                extracted = _try_ocr_first_then_caption(post_dict, owner)
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


def _venue_accounts_for_tagged_mining() -> list[str]:
    """Venues we should mine for third-party tagged posts. Pulled from the
    `_account_default_location()` mapping — those are the accounts we
    recognize as physical NYC venues with their own location.

    Returns a deduped, lowercased list ordered by curation priority
    (curated venues that appear in IG_ACCOUNTS go first since their
    third-party flyers are most aligned with the user's interests).
    """
    # Re-extract the keys from _account_default_location's mapping by
    # passing each curated/discovered account through it. This avoids
    # duplicating the venue list.
    venues: list[str] = []
    seen: set[str] = set()
    # Curated set first
    for a in IG_ACCOUNTS:
        if _account_default_location(a) and a.lower() not in seen:
            venues.append(a.lower())
            seen.add(a.lower())
    # Then discovered venues (e.g., bookclubbar surfaced via discovery)
    for a in load_discovered_accounts():
        al = a.lower()
        if _account_default_location(al) and al not in seen:
            venues.append(al)
            seen.add(al)
    return venues


def _scrape_venue_tagged_posts(
    loader, max_per_venue: int = 8
) -> tuple[list[dict], set[str]]:
    """For each known venue account, scrape posts tagging the venue.

    The venue's own feed is curated marketing; tagged posts capture event
    flyers from third parties (DJs, opening acts, promoters, fans, food
    pop-ups). These are events HAPPENING AT the venue that the venue's
    own posts may not cover. Generalizes the value of `get_tagged_posts`
    beyond just the user's own tags.

    Returns (events, owner_accounts) — owner accounts are surfaced for
    discovery (they're third-party event organizers who tag NYC venues).
    """
    events: list[dict] = []
    owners: set[str] = set()
    started = time.time()
    budget = float(os.environ.get("IG_VENUE_TAGGED_BUDGET_SECONDS", "300"))
    venues = _venue_accounts_for_tagged_mining()
    if not venues:
        return events, owners

    dead_set = {
        u for u, info in _load_dead_accounts().get("accounts", {}).items()
        if info.get("reason") in ("not_exists", "repeated_failure", "stale_no_recent_posts")
    }

    for venue in venues:
        if time.time() - started > budget:
            print(f"[instagram-venue-tagged] Budget exhausted at @{venue}")
            break
        if venue in dead_set:
            continue
        try:
            profile = instaloader.Profile.from_username(loader.context, venue)
        except Exception as exc:
            # Don't mark venue dead from this path — _fetch_posts is the
            # canonical authority for that.
            continue

        venue_loc = _account_default_location(venue)
        count = 0
        try:
            for post in profile.get_tagged_posts():
                if count >= max_per_venue:
                    break
                count += 1
                owner = (post.owner_username or "").lower()
                if not owner or owner == venue or owner in dead_set:
                    continue
                # Skip the user's own tagged posts — already handled by
                # `_scrape_tagged_posts`.
                if IG_USERNAME and owner == IG_USERNAME.lower():
                    continue
                owners.add(owner)

                images: list[str] = []
                try:
                    if post.typename == "GraphSidecar":
                        for node in post.get_sidecar_nodes():
                            img = getattr(node, "display_url", None) or getattr(node, "url", None)
                            if img:
                                images.append(img)
                    else:
                        img = getattr(post, "display_url", None) or post.url
                        if img:
                            images.append(img)
                except Exception:
                    pass

                # Pre-populate venue location since the third-party caption
                # may not say where the event is — but it's tagged AT this
                # venue, so we know.
                post_dict = {
                    "caption": post.caption or "",
                    "date": post.date_utc,
                    "url": f"https://www.instagram.com/p/{post.shortcode}/",
                    "image": images[0] if images else "",
                    "all_images": images,
                    "owner": owner,
                    "bio_url": "",
                    "geo_name": venue_loc,
                    "likes": int(getattr(post, "likes", 0) or 0),
                    "comments": int(getattr(post, "comments", 0) or 0),
                }
                # OCR-first for venue-tagged: third-party event flyers
                # often have minimal text ("tonight!" + image of date/time)
                # and the venue tag is what tells us WHERE it's happening.
                extracted = _try_ocr_first_then_caption(post_dict, owner)
                if not extracted:
                    continue
                # Tag every event with the venue we found it via, so the
                # ranking can credit this discovery channel.
                for ev in extracted:
                    ev.setdefault("discoveredVia", "venue_tagged")
                    ev["venueTaggedFrom"] = venue
                events.extend(extracted)
        except Exception as exc:
            print(f"[instagram-venue-tagged] @{venue}: {exc}")
            continue
        # Brief sleep between venues to be polite.
        time.sleep(IG_SLEEP_BETWEEN_ACCOUNTS)

    if events or owners:
        print(f"[instagram-venue-tagged] {len(events)} events from "
              f"{len(venues)} venues, {len(owners)} third-party promoters")
    return events, owners


# Highlight titles that signal event content — used to filter which
# highlight collections to scrape. Skipping "Food", "Drinks", "Vibes"
# etc. preserves the rate-limit budget for the highlights worth mining.
_EVENT_HIGHLIGHT_TITLES_RE = re.compile(
    r"\b(?:events?|shows?|upcoming|calendar|this week|this weekend|weekend|"
    r"weekly|tonight|today|tomorrow|next|coming|lineups?|line[- ]?ups?|"
    r"performances?|concerts?|gigs?|sets?|show\s*time|on\s*sale|tickets?|"
    r"presale|premiere|openings?|readings?|workshops?|classes|class|clinic|"
    r"now\s*showing|now\s*open|book\s*now|happenings?)\b",
    re.IGNORECASE,
)


def _highlights_target_accounts(max_accounts: int) -> list[str]:
    """Pick accounts to mine highlights from. Priority:
       1. High-affinity (saved-from) — the user's strongest signal
       2. Curated venues from `_account_default_location()` — most
          likely to pin event flyers
       3. Curated IG_ACCOUNTS generally

    Highlights are heavily rate-limited so we spend the budget on accounts
    most likely to surface curated event content (venues, event-curators).
    """
    seen: set[str] = set()
    out: list[str] = []
    # Affinity first
    for a in _AFFINITY_ACCOUNTS_CACHE:
        al = (a or "").lower()
        if al and al not in seen:
            seen.add(al)
            out.append(al)
            if len(out) >= max_accounts:
                return out
    # Then curated venues
    for v in _venue_accounts_for_tagged_mining():
        if v not in seen:
            seen.add(v)
            out.append(v)
            if len(out) >= max_accounts:
                return out
    # Then other curated accounts
    for a in IG_ACCOUNTS:
        al = a.lower()
        if al not in seen:
            seen.add(al)
            out.append(al)
            if len(out) >= max_accounts:
                return out
    return out


def _scrape_account_highlights(loader, max_accounts: int = 12, max_items_per_hl: int = 20) -> list[dict]:
    """Mine pinned story highlights from venue + affinity accounts.

    Highlights are curated story collections that PERSIST (unlike 24h
    stories). Venues pin event flyers to highlights named "Events",
    "Upcoming Shows", "This Week" etc. — capturing them surfaces the
    venue's own editorial event roster, including future events not
    yet on their main feed.

    Defensive: every instaloader call wrapped, missing attributes
    handled, schema changes won't break the run. Time-budgeted at 5
    minutes default. Skip-listed highlights (food/vibes/about) avoid
    burning budget on non-event collections.
    """
    events: list[dict] = []
    started = time.time()
    budget = float(os.environ.get("IG_HIGHLIGHTS_BUDGET_SECONDS", "300"))
    targets = _highlights_target_accounts(max_accounts)
    if not targets:
        return events

    dead_set = {
        u for u, info in _load_dead_accounts().get("accounts", {}).items()
        if info.get("reason") in ("not_exists", "repeated_failure", "stale_no_recent_posts")
    }

    accounts_scanned = 0
    highlights_scanned = 0
    items_scanned = 0
    extracted_total = 0

    for username in targets:
        if time.time() - started > budget:
            print(f"[instagram-highlights] Budget exhausted at @{username}")
            break
        if username in dead_set:
            continue

        try:
            profile = instaloader.Profile.from_username(loader.context, username)
        except Exception:
            # Don't mark dead from this path; _fetch_posts is authoritative.
            continue

        try:
            hl_iter = loader.get_highlights(user=profile)
        except Exception as exc:
            # Some accounts have no highlights at all — silent skip.
            continue

        accounts_scanned += 1
        try:
            for highlight in hl_iter:
                if time.time() - started > budget:
                    break
                title = ""
                try:
                    title = (getattr(highlight, "title", "") or "").strip()
                except Exception:
                    pass
                # Only mine highlights whose title suggests event content.
                # Saves the rate-limit budget — "Food", "Drinks", "Vibes",
                # "About us" highlights almost never contain event flyers.
                if not title or not _EVENT_HIGHLIGHT_TITLES_RE.search(title):
                    continue
                highlights_scanned += 1

                try:
                    items = list(highlight.get_items())
                except Exception:
                    continue

                for item in items[:max_items_per_hl]:
                    if time.time() - started > budget:
                        break
                    items_scanned += 1
                    caption = ""
                    image_url = ""
                    date_local = None
                    shortcode = ""
                    try:
                        caption = (getattr(item, "caption", "") or "")
                    except Exception:
                        pass
                    try:
                        image_url = (
                            getattr(item, "display_url", None)
                            or getattr(item, "url", "")
                            or ""
                        )
                    except Exception:
                        pass
                    try:
                        date_local = (
                            getattr(item, "date_local", None)
                            or getattr(item, "date_utc", None)
                        )
                    except Exception:
                        pass
                    try:
                        shortcode = getattr(item, "shortcode", "") or ""
                    except Exception:
                        pass

                    if not caption and not image_url:
                        continue

                    # Build a post-shaped dict and run through the
                    # OCR-first pipeline — highlights are mostly visual,
                    # so OCR is where most of the value comes from.
                    venue_loc = _account_default_location(username)
                    post_dict = {
                        "caption": caption,
                        "date": date_local,
                        "url": (
                            f"https://www.instagram.com/stories/highlights/{shortcode}/"
                            if shortcode else
                            f"https://www.instagram.com/{username}/"
                        ),
                        "image": image_url,
                        "all_images": [image_url] if image_url else [],
                        "owner": username,
                        "bio_url": "",
                        "geo_name": venue_loc,
                        "likes": 0,
                        "comments": 0,
                    }
                    extracted = _try_ocr_first_then_caption(post_dict, username)
                    if not extracted:
                        continue
                    # Tag for transparency + downstream ranking.
                    for ev in extracted:
                        ev["discoveredVia"] = "ig_highlight"
                        ev["isHighlight"] = True
                        ev["highlightTitle"] = title
                    events.extend(extracted)
                    extracted_total += len(extracted)
        except Exception as exc:
            print(f"[instagram-highlights] @{username}: {exc}")
            continue
        # Brief sleep between accounts to be polite.
        try:
            time.sleep(IG_SLEEP_BETWEEN_ACCOUNTS)
        except Exception:
            pass

    print(
        f"[instagram-highlights] {accounts_scanned} accounts, "
        f"{highlights_scanned} event-titled highlights, "
        f"{items_scanned} items, {extracted_total} events extracted"
    )
    return events


def _try_ocr_first_then_caption(post: dict, owner: str) -> list[dict]:
    """Run caption-extraction, then OCR-fallback for sparse-caption posts.

    Three-stage flow:
      1. Normal caption pipeline — handles the typical post with text
         describing the event.
      2. If that yielded nothing AND we have an image AND caption < 30
         chars AND OCR is available: run OCR, use raw OCR text as a
         synthetic caption, re-run the caption pipeline. Mark resulting
         events ocrOnly=True so we know provenance.
      3. If we DID get events from caption (or OCR-only), let
         _maybe_enrich_with_image fill in missing fields from the image
         (date/time/title/location).

    Used by stories (where most posts are image-only), hashtag posts
    (often terse), and venue-tagged posts (third-party flyers often
    have minimal text). Stage 2 is the big unlock — without it, ~80%
    of image-only event posts get silently dropped.
    """
    image_url = post.get("image", "") or ""
    caption = post.get("caption", "") or ""

    extracted = _extract_events_from_caption(post, owner)

    if not extracted and image_url and _HAS_IMAGE_ANALYZER and len(caption) < 30:
        try:
            ocr_result = analyze_event_image(image_url)
        except Exception:
            ocr_result = None
        ocr_text = (ocr_result or {}).get("text") or ""
        if ocr_text and len(ocr_text) >= 20:
            post_ocr = dict(post)
            post_ocr["caption"] = ocr_text
            extracted = _extract_events_from_caption(post_ocr, owner)
            for ev in extracted:
                ev["ocrEnriched"] = True
                ev["ocrOnly"] = True

    # Whether we got events from caption or OCR-only, still let the
    # image-enrich pass fill in missing fields.
    if _HAS_IMAGE_ANALYZER and extracted:
        try:
            extracted = _maybe_enrich_with_image(extracted, post)
        except Exception:
            pass

    return extracted


def _stories_target_accounts(max_accounts: int) -> list[str]:
    """Pick which accounts to scrape stories for. Priority order:
       1. High-affinity (user has saved from them) — highest signal
       2. User-followed (explicit choice on IG)
       3. High-yield event accounts (lifetime ≥10 events) — these post
          time-sensitive flyers to stories often.
       4. Curated venue accounts (likely to post event flyers as stories)

    Capped at max_accounts to bound API volume. Stories rate-limit harshly,
    so we only spend our budget on accounts most likely to surface valuable
    time-sensitive flyers.
    """
    seen: set[str] = set()
    out: list[str] = []
    # Affinity first
    for a in _AFFINITY_ACCOUNTS_CACHE:
        al = (a or "").lower()
        if al and al not in seen:
            seen.add(al)
            out.append(al)
            if len(out) >= max_accounts:
                return out
    # Then following
    for a in _FOLLOWING_ACCOUNTS_CACHE:
        al = (a or "").lower()
        if al and al not in seen:
            seen.add(al)
            out.append(al)
            if len(out) >= max_accounts:
                return out
    # Then top-yield event accounts (lifetime ≥10 events) — these post
    # event flyers to stories regularly. Surfaces high-value content from
    # accounts the user may not follow on IG but our system has identified
    # as productive event sources.
    quality = _ACCOUNT_QUALITY_CACHE if isinstance(_ACCOUNT_QUALITY_CACHE, dict) else {}
    top_yield = sorted(
        ((a, q.get("events_emitted", 0)) for a, q in quality.items()
         if q.get("events_emitted", 0) >= 10),
        key=lambda x: -x[1],
    )
    for acct, _ in top_yield:
        if acct not in seen:
            seen.add(acct)
            out.append(acct)
            if len(out) >= max_accounts:
                return out
    # Then curated venues (where stories most often have event flyers)
    venues = _venue_accounts_for_tagged_mining()
    for v in venues:
        if v not in seen:
            seen.add(v)
            out.append(v)
            if len(out) >= max_accounts:
                return out
    return out


def _scrape_stories(loader, max_accounts: int = 25) -> list[dict]:
    """Scrape recent IG stories from high-priority accounts.

    Stories are 24-hour ephemeral content where event flyers commonly go
    FIRST — the venue posts a flyer to story for tonight's show before
    (or instead of) putting it on their feed. This is THE channel the
    user has to manually scroll IG to see, so capturing it is the highest-
    leverage move for the website's core goal (replace IG scrolling).

    instaloader limitation: only stories from accounts the AUTH user
    follows are accessible. We respect that by prioritizing affinity +
    following + curated-venues we know the user follows.

    Returns a list of event dicts. Stories without parseable date stamp
    onto today + post_date so they sort with current content. Stories
    without parseable text (image-only) are silently skipped unless the
    optional OCR analyzer is wired in.
    """
    events: list[dict] = []
    started = time.time()
    budget = float(os.environ.get("IG_STORIES_BUDGET_SECONDS", "180"))

    target_usernames = _stories_target_accounts(max_accounts)
    if not target_usernames:
        return events

    # Resolve usernames to userids — instaloader's get_stories needs IDs.
    # Skip accounts that fail to resolve (private/dead/missing) silently.
    userids: list[int] = []
    for username in target_usernames:
        if time.time() - started > budget:
            break
        try:
            profile = instaloader.Profile.from_username(loader.context, username)
            uid = getattr(profile, "userid", None)
            if uid is not None:
                userids.append(int(uid))
        except Exception:
            continue

    if not userids:
        return events

    story_count = 0
    item_count = 0
    extracted_count = 0
    try:
        for story in loader.get_stories(userids=userids):
            if time.time() - started > budget:
                print("[instagram-stories] Budget exhausted while iterating stories")
                break
            owner = ""
            try:
                owner = (getattr(story, "owner_username", "") or "").lower()
            except Exception:
                continue
            if not owner:
                continue
            story_count += 1

            try:
                items = list(story.get_items())
            except Exception:
                continue

            for item in items:
                item_count += 1
                # StoryItem fields vary by instaloader version. Defensive reads.
                caption = ""
                image_url = ""
                date_local = None
                shortcode = ""
                try:
                    caption = (getattr(item, "caption", "") or "")
                except Exception:
                    pass
                try:
                    # Prefer display_url (always image), fall back to url
                    image_url = (
                        getattr(item, "display_url", None)
                        or getattr(item, "url", "")
                        or ""
                    )
                except Exception:
                    pass
                try:
                    date_local = getattr(item, "date_local", None) or getattr(
                        item, "date_utc", None
                    )
                except Exception:
                    pass
                try:
                    shortcode = getattr(item, "shortcode", "") or ""
                except Exception:
                    pass

                # Skip items with neither caption nor image — nothing to parse.
                if not caption and not image_url:
                    continue

                # Build a post-shaped dict for the existing caption pipeline.
                # Stories don't have permalinks the way posts do — we link to
                # the account's stories page (best-effort) so the user can
                # tap-through within the 24h window.
                post_dict = {
                    "caption": caption,
                    "date": date_local,
                    "url": (
                        f"https://www.instagram.com/stories/{owner}/{shortcode}/"
                        if shortcode else
                        f"https://www.instagram.com/{owner}/"
                    ),
                    "image": image_url,
                    "all_images": [image_url] if image_url else [],
                    "owner": owner,
                    "bio_url": "",
                    # Stories don't expose like/comment counts
                    "likes": 0,
                    "comments": 0,
                }

                extracted = _try_ocr_first_then_caption(post_dict, owner)

                if not extracted:
                    continue

                # Tag for transparency — the user may want a "from stories"
                # filter, and ranking can apply a small urgency boost since
                # stories are inherently time-sensitive.
                for ev in extracted:
                    ev["discoveredVia"] = "ig_story"
                    ev["isStory"] = True
                events.extend(extracted)
                extracted_count += len(extracted)
    except Exception as exc:
        print(f"[instagram-stories] Iteration failed: {exc}")

    print(
        f"[instagram-stories] {len(userids)} accounts → "
        f"{story_count} stories, {item_count} items, "
        f"{extracted_count} events extracted"
    )
    return events


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
            # OCR-first helper: tagged posts from friends/venues may have
            # minimal text + a full event flyer. Recovers events we'd
            # otherwise drop.
            extracted = _try_ocr_first_then_caption(post_dict, owner)
            for ev in extracted:
                # Tagged posts are nearly as strong a signal as saved posts.
                ev["userTagged"] = True
            events.extend(extracted)

            # Comments mining for tagged posts too — same value as saved.
            try:
                comment_urls, attendance = _harvest_post_comments(post, max_comments=8)
                if comment_urls:
                    _save_caption_urls(comment_urls)
                if attendance and extracted:
                    for ev in extracted:
                        ev["attendanceSignal"] = attendance
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

            # Saved posts: the user's explicit bookmark. OCR-first helper
            # handles posts where the user saved a story-style image with
            # minimal caption — without OCR, we'd lose the user's own
            # explicit signal.
            extracted = _try_ocr_first_then_caption(post_dict, owner)
            # Mark these as user-saved so we can boost in ranking
            for ev in extracted:
                ev["userSaved"] = True
            events.extend(extracted)

            # Comments mining — saved posts are the highest-value targets.
            # Top-level comments on event posts often carry ticket URLs and
            # venue answers that the caption omits ("when's the next one?").
            # Also harvest attendance-intent signals ("going!", "rsvp'd",
            # "+5 friends") which are stronger popularity proxies than likes.
            try:
                comment_urls, attendance = _harvest_post_comments(post, max_comments=8)
                if comment_urls:
                    _save_caption_urls(comment_urls)
                    print(f"[instagram] @{owner} saved post: +{len(comment_urls)} URLs from comments")
                if attendance and extracted:
                    for ev in extracted:
                        ev["attendanceSignal"] = attendance
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
        # Cap connection retries so one deprecated/broken IG endpoint
        # (e.g., /explore/locations/<id>/?__a=1 currently returns HTTP 201)
        # doesn't hang the entire scrape with exponential-backoff retries.
        # Three attempts is enough to absorb transient blips while still
        # bailing fast on a permanently-broken endpoint.
        max_connection_attempts=3,
        request_timeout=20.0,
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
        # ProfileNotExistsException is UNRELIABLE — instaloader returns it for
        # genuinely-deleted accounts BUT also for rate-limited fetches, stale
        # session state, login-required private profiles, and username drift
        # (e.g. @bluenote.nyc renamed to @bluenotenyc). Only mark a curated
        # account dead after multiple consecutive 'not_exists' hits. For non-
        # curated discovered accounts, the old fast-fail path is fine.
        is_curated = username.lower() in {a.lower() for a in IG_ACCOUNTS}
        if is_curated:
            print(f"[instagram] Profile @{username} reported not_exists (curated — treating as transient)")
            _record_account_failure(username, "profile_not_exists_transient")
        else:
            print(f"[instagram] Profile @{username} does not exist, marking dead")
            _mark_dead_account(username, "not_exists")
        return []
    except Exception as exc:
        print(f"[instagram] Profile @{username} failed: {exc}")
        _record_account_failure(username, str(exc)[:200])
        return []

    # Yield-scaled post depth: high-yield accounts deserve deeper crawls
    # because each post is more likely to be a real event. Low-yield accounts
    # get a shallower crawl to save the IG time budget. The cap (40) protects
    # against single-account starvation when the budget is tight.
    base_cap = IG_MAX_POSTS_PER_ACCOUNT
    max_posts = base_cap
    quality = _ACCOUNT_QUALITY_CACHE.get(username.lower(), {}) if isinstance(_ACCOUNT_QUALITY_CACHE, dict) else {}
    posts_seen_lifetime = quality.get("posts_scraped", 0)
    events_emitted_lifetime = quality.get("events_emitted", 0)
    if posts_seen_lifetime >= 10:
        yield_ = events_emitted_lifetime / max(1, posts_seen_lifetime)
        if yield_ >= 0.50:                # daily-event accounts (e.g. @theskint, @nycforfree.co)
            max_posts = min(40, int(base_cap * 2.0))
        elif yield_ >= 0.25:              # frequent-event venues
            max_posts = min(35, int(base_cap * 1.6))
        elif yield_ < 0.05:               # mostly non-event content
            max_posts = max(8, int(base_cap * 0.5))
    # User-affinity (saves-from) trumps yield — give them another bump.
    if username.lower() in _AFFINITY_ACCOUNTS_CACHE:
        max_posts = min(40, max(max_posts, int(base_cap * 1.5)))
    # Curated accounts get at least the base cap regardless of yield.
    if username.lower() in {a.lower() for a in IG_ACCOUNTS}:
        max_posts = max(max_posts, base_cap)

    # Yield-scaled fresh-refetch: top-volume accounts post events DAILY
    # (e.g. @nyc_forfree at ~daily cadence). The default 3-post refetch
    # might miss yesterday's events if a curator posted multiple times
    # since last cron. Scale refetch depth proportionally so we never
    # lose a day of high-yield content.
    fresh_refetch = _MIN_FRESH_REFETCH  # default 3
    if posts_seen_lifetime >= 10:
        yield_lifetime = events_emitted_lifetime / max(1, posts_seen_lifetime)
        if yield_lifetime >= 1.0:        # multi-event roundups; 7+ days fresh
            fresh_refetch = 8
        elif yield_lifetime >= 0.5:      # daily-cadence event accounts
            fresh_refetch = 5
        elif yield_lifetime < 0.1:       # low-yield: 1 fresh is enough
            fresh_refetch = 1

    # Capture the profile's external URL — many event accounts say "link in bio"
    # and the actual ticket page is at this URL.
    bio_url = getattr(profile, "external_url", "") or ""
    # Capture the bio TEXT itself — contains physical addresses, hours,
    # closure indicators, and inferred categories. We're already loading
    # the profile so this is free. Used to:
    #   - Auto-detect "permanently closed" accounts and mark them dead
    #   - Auto-extract venue addresses for accounts not in the
    #     _account_default_location map
    biography = (getattr(profile, "biography", "") or "").strip()
    bio_venue = _venue_from_biography(biography)
    # Closure detection: if the bio explicitly says the venue closed, mark
    # the account dead so we stop wasting budget. Manual unblock available
    # via dead_accounts.json.
    if _bio_indicates_closure(biography):
        print(f"[instagram] @{username} bio indicates closure — marking stale")
        _mark_dead_account(username, "stale_no_recent_posts")
        return []

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
        # returned newest-first by instaloader). EXCEPTION: always
        # re-process the most recent fresh-refetch posts regardless of
        # cursor, because:
        #   (1) curators frequently EDIT captions after posting (add the
        #       ticket link, fix the date, add @-mentions).
        #   (2) engagement grows over time → velocity boost in ranking.
        #   (3) attendance signals in comments accumulate.
        # Tradeoff: small risk of producing duplicate event dicts, but
        # the dedup chain handles that cleanly.
        if last_seen and post.shortcode == last_seen and count >= fresh_refetch:
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

        # IG geo-tag: in principle, location-tagged posts give us an
        # authoritative venue. In practice, IG has deprecated the
        # /explore/locations/<id>/?__a=1 endpoint and now returns HTTP 201
        # for every fetch — instaloader interprets that as transient and
        # falls into a retry loop that hangs scrape() for tens of minutes
        # per geo-tagged post. We get most of the same signal from
        # bio-venue extraction (`_venue_from_biography`) and caption-text
        # location parsing, so we disable the live geo lookup by default.
        # Opt back in with IG_FETCH_GEOTAGS=1 if/when IG restores the API.
        geo_name = ""
        geo_lat = None
        geo_lng = None
        if os.environ.get("IG_FETCH_GEOTAGS", "0") == "1":
            try:
                ig_loc = getattr(post, "location", None)
                if ig_loc is not None:
                    geo_name = (getattr(ig_loc, "name", "") or "").strip()
                    geo_lat = getattr(ig_loc, "lat", None)
                    geo_lng = getattr(ig_loc, "lng", None)
            except Exception:
                pass

        # Tagged users: the AUTHORITATIVE list of accounts in this post.
        # Distinct from caption @-mentions (which need regex parsing and can
        # false-match emails or hashtags). When a flyer post tags
        # @venue1 + @djset1 + @opener1, those are the actual collaborators.
        # Use these for high-confidence account auto-discovery.
        tagged_users: list[str] = []
        try:
            for u in (post.tagged_users or []):
                if isinstance(u, str) and u:
                    tagged_users.append(u.lower())
        except Exception:
            pass

        # Video / Reel signal — view count is a stronger popularity proxy
        # than likes for video. Reels going viral are usually trending
        # events worth surfacing.
        is_video = bool(getattr(post, "is_video", False))
        video_views = 0
        if is_video:
            try:
                video_views = int(getattr(post, "video_view_count", 0) or 0)
            except Exception:
                pass

        # Pinned posts are the account's own editorial pick — IG accounts
        # can pin up to 3 posts to the top of their feed. Pinned event
        # posts are nearly guaranteed to be high-priority content (a venue
        # pins "TONIGHT'S SHOW" or "WEEKEND LINEUP"). Strong quality signal.
        is_pinned = False
        try:
            is_pinned = bool(getattr(post, "is_pinned", False))
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
            "geo_name": geo_name or bio_venue,
            "geo_lat": geo_lat,
            "geo_lng": geo_lng,
            "tagged_users": tagged_users,
            "is_video": is_video,
            "video_views": video_views,
            "is_pinned": is_pinned,
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

    # Stale-account auto-prune: if newest post is >90 days old AND the
    # account isn't user-curated (saved/affinity/following) AND not in
    # the IG_ACCOUNTS curated seed list, mark it stale. Curated and saved
    # accounts are protected from auto-prune since the user chose them.
    if newest_post_date is not None \
            and username.lower() not in _AFFINITY_ACCOUNTS_CACHE \
            and username.lower() not in _FOLLOWING_ACCOUNTS_CACHE \
            and username.lower() not in {a.lower() for a in IG_ACCOUNTS}:
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

# Closure indicators in IG bios — when present we stop scraping the account
# and mark it stale. Conservative phrasing only — avoids false positives
# from generic words ("closing soon for the season" still scrapes).
_BIO_CLOSURE_RES = [
    re.compile(r"\bpermanently\s+closed\b", re.IGNORECASE),
    re.compile(r"\bnow\s+closed\b", re.IGNORECASE),
    re.compile(r"\bvenue\s+(?:is\s+)?closed\b", re.IGNORECASE),
    re.compile(r"\bno\s+longer\s+(?:open|operating|booking|in\s+business)\b", re.IGNORECASE),
    re.compile(r"\baccount\s+inactive\b", re.IGNORECASE),
    re.compile(r"\brest\s+in\s+peace\b", re.IGNORECASE),
    re.compile(r"\bfinal\s+show\s+(?:was\s+)?\d{4}\b", re.IGNORECASE),
]


def _bio_indicates_closure(biography: str) -> bool:
    """True if the account's bio text explicitly signals the venue is
    closed / no longer operating. Triggers an automatic stale-marker.
    """
    if not biography:
        return False
    return any(r.search(biography) for r in _BIO_CLOSURE_RES)


# Patterns that look like NYC venue addresses in IG bios:
#   "📍 200 Wythe Ave, Brooklyn"
#   "Brooklyn, NY 11211"
#   "228 Bedford Ave"
_BIO_ADDRESS_RES = [
    # Pin-emoji followed by street address with optional borough. Note
    # alternation order — longer alternatives first so 'Street' isn't
    # truncated to 'St' by Python's leftmost-match semantics.
    re.compile(
        r"📍\s*(\d{1,5}\s+[A-Z][A-Za-z]+(?:\s+[A-Za-z]+){0,3}"
        r"(?:\s+(?:Street|Avenue|Boulevard|Road|Place|Drive|Lane|Ave|Blvd|Rd|Pl|Dr|Way|Ln|St))"
        r"(?:[,.\s][^\n]{0,40})?)",
    ),
    # Address line without emoji marker
    re.compile(
        r"\b(\d{1,5}\s+[A-Z][A-Za-z]+(?:\s+[A-Za-z]+){0,3}"
        r"\s+(?:Street|Avenue|Boulevard|Road|Place|Drive|Lane|Ave|Blvd|Rd|Pl|Dr|Way|Ln|St))\b",
    ),
]


def _venue_from_biography(biography: str) -> str:
    """Extract a venue address from the IG profile bio if present.

    Returns a cleaned address string (e.g., "200 Wythe Ave, Brooklyn") or
    an empty string when no address is detectable. Used to seed
    `_account_default_location()` for accounts the curated map doesn't
    know about — so their events get a venue stamp without a per-account
    code change.
    """
    if not biography:
        return ""
    for r in _BIO_ADDRESS_RES:
        m = r.search(biography)
        if m:
            addr = m.group(1).strip().rstrip(",.")
            addr = re.sub(r"\s+", " ", addr)
            # Drop trailing emoji / unicode noise.
            addr = re.sub(r"[^\w\s,.&'\-]+$", "", addr).strip()
            if 5 <= len(addr) <= 120:
                return addr
    return ""


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
    # Curated-account posts get more leeway (we chose this account because
    # it produces events). When account is in IG_ACCOUNTS we trust them.
    is_curated_acct = account.lower() in {a.lower() for a in IG_ACCOUNTS}
    if not _looks_like_event_post(
        caption,
        has_image=bool(image_url),
        is_curated_account=is_curated_acct,
    ):
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

    # Spot accounts produce evergreen "cool place to check out" content
    # rather than dated events. Posts from them survive the date-required
    # path: if no date is parseable, we use today's date and mark
    # `evergreen=true` so the date-pill in UI says "Spot" / always-current.
    is_spot_account = account.lower() in IG_SPOTS_ACCOUNTS

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
        categories = infer_categories(title or section, section, ig_account=account)

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
        # Capture recurring status before building (the module-level sentinel
        # is overwritten by every _find_dates call).
        section_recurring = _LAST_FIND_DATES_RECURRING

        loc_name = location or default_location
        ev = build_event(
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
        )
        if section_recurring:
            ev["recurring"] = True
        events.append(ev)

    # If single-event post: treat the whole caption as one event with the post's
    # main date. This is more accurate than splitting captions that aren't roundups.
    if not multi_event:
        events = []  # discard the per-section attempts
        if post_date:
            full_caption = caption
            title = _extract_title(full_caption) or full_caption.split("\n")[0][:80]
            event_date = _find_dates(full_caption, post_date)
            full_recurring = _LAST_FIND_DATES_RECURRING
            event_date = event_date[0] if event_date else post_date.date()
            extracted_loc = _extract_location(full_caption)
            ev = build_event(
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
                categories=infer_categories(title, full_caption, ig_account=account),
            )
            if full_recurring:
                ev["recurring"] = True
            events.append(ev)

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
            categories=infer_categories(title, caption, ig_account=account),
        ))

    # Tag every event with the IG account it came from + engagement + profile signals.
    likes = post.get("likes", 0)
    comments = post.get("comments", 0)
    followers = post.get("profile_followers", 0)
    verified = post.get("profile_is_verified", False)
    is_video = post.get("is_video", False)
    video_views = post.get("video_views", 0) or 0
    is_pinned = post.get("is_pinned", False)
    # Defensive: account should always be a non-empty string. If it's None
    # or empty (rare edge — IG owner_username can be missing on archived
    # posts), drop these events entirely rather than emit @None garbage.
    if not account or not isinstance(account, str):
        return []
    is_affinity = account.lower() in _AFFINITY_ACCOUNTS_CACHE
    is_following = account.lower() in _FOLLOWING_ACCOUNTS_CACHE
    for ev in events:
        ev["instagramAccount"] = account
        # Spot-account events are evergreen: place recommendations rather
        # than dated events. Survive the future-only filter and render with
        # a "Spot" pill instead of a date pill.
        if is_spot_account:
            ev["evergreen"] = True
            ev["categories"] = sorted(set((ev.get("categories") or []) + ["exploration"]))
        if likes:
            ev["likes"] = likes
        if comments:
            ev["comments"] = comments
        if followers:
            ev["accountFollowers"] = followers
        if verified:
            ev["accountVerified"] = True
        if is_video:
            ev["isVideo"] = True
        if video_views:
            ev["video_views"] = video_views
        if is_pinned:
            ev["isPinned"] = True
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


def _looks_like_event_post(
    caption: str,
    has_image: bool = False,
    is_curated_account: bool = False,
) -> bool:
    """Decide if an Instagram post is actually about an event.

    Most IG posts are NOT events — they're announcements, art descriptions,
    hype, behind-the-scenes content. We only emit an event if the post has
    sufficient positive signals AND no strong negative signals.

    Curated accounts (in IG_ACCOUNTS) get extra leniency because we've
    explicitly chosen them as event sources — the curator's pick is itself
    quality signal. For curated, we accept posts with 1 signal regardless
    of image presence.
    """
    # Length floor: posts with images get a much lower bar since OCR can
    # extract event details directly from the flyer (calendars, posters).
    min_len = 5 if (has_image or is_curated_account) else 20
    if not caption or len(caption) < min_len:
        return False

    # Strong negative signals = not an event
    if any(r.search(caption) for r in _NON_EVENT_SIGNAL_RES):
        return False

    # Very short caption + has_image: accept by default; OCR will gate
    # whether an actual event gets emitted. We DON'T blanket-accept curated
    # short captions here because curated accounts also post promo/BTS
    # content with no event payload — requiring a positive signal below
    # filters those out.

    # Curated accounts → 1 signal is enough (we trust the curator).
    # Posts with images → 1 signal (OCR will extract details from flyer).
    # Default → 2 signals (rigorous).
    if is_curated_account or has_image:
        threshold = 1
    else:
        threshold = 2
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
    # "every Tuesday", "every other Friday" — recurring marker. Resolves
    # to the next occurrence; downstream uses event["recurring"]=True so
    # the dedup pass doesn't collapse week-spaced repeats.
    r"every\s+(?:other\s+)?(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)s?",
    # "Tuesdays at 7pm" — recurring weekday-plural marker
    r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)s\s+(?:at|@)\s",
    # Bare weekday: "Saturday at 8pm", "Sat 7pm", "Friday: doors at 9".
    # This is the BIG missing pattern — IG captions routinely drop "this"
    # prefix. Risky in isolation (could match "had a great Saturday last
    # week"), so we only resolve when context indicates an upcoming event
    # (see _has_future_event_context). Anchored with word-boundary +
    # following time/event-marker so we only match likely event refs.
    r"\b(?:Mon|Tue|Tues|Wed|Weds|Thu|Thur|Thurs|Fri|Sat|Sun|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b(?=\s*(?:[,:]|@|at|night|evening|morning|afternoon|\d|doors|set|show))",
]


# Phrases signaling the surrounding text describes an upcoming event.
# Used to guard bare-weekday matches from false positives like
# "we had an amazing Saturday last week".
_FUTURE_EVENT_CONTEXT_RE = re.compile(
    r"\b(?:"
    r"join us|come thru|come through|don'?t miss|save the date|see you|"
    r"rsvp|tickets|doors|set\s|show|gig|line[- ]?up|presale|on sale|"
    r"this (?:friday|saturday|sunday|week|weekend|month)|"
    r"upcoming|next week|next month|"
    r"@\d{1,2}\s*(?:am|pm)|\bat\s+\d{1,2}\s*(?:am|pm)|"
    r"happening|playing|performing|hosting|presents|"
    r"reservation|reserve your|secure your spot"
    r")\b",
    re.IGNORECASE,
)


_WEEKDAY_NAMES = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


_WEEKDAY_ABBREV = {
    "mon": 0, "tue": 1, "tues": 1, "wed": 2, "weds": 2,
    "thu": 3, "thur": 3, "thurs": 3, "fri": 4, "sat": 5, "sun": 6,
}


def _weekday_index(name: str) -> "int | None":
    n = name.lower().rstrip("s")  # "tuesdays" → "tuesday"
    if n in _WEEKDAY_NAMES:
        return _WEEKDAY_NAMES[n]
    if n in _WEEKDAY_ABBREV:
        return _WEEKDAY_ABBREV[n]
    return None


def _resolve_relative(phrase: str, base_date) -> "tuple | date | None":
    """Resolve relative phrases like 'tonight', 'this Saturday', 'next Fri',
    'every Tuesday', 'Saturday' (bare).

    Returns either:
      - date object (one-shot resolution)
      - (date, True) tuple when phrase indicates a recurring event so the
        caller can mark event["recurring"]=True
      - None when the phrase can't be resolved.

    base_date is the anchor (post date for IG posts).
    """
    from datetime import timedelta
    p = phrase.lower().strip()

    if p in ("tonight", "today"):
        return base_date
    if p == "tomorrow":
        return base_date + timedelta(days=1)

    # "every Tuesday" / "every other Friday" → next Tuesday + mark recurring
    m = re.match(r"every\s+(?:other\s+)?(\w+?)s?$", p)
    if m:
        wd = _weekday_index(m.group(1))
        if wd is not None:
            days_ahead = (wd - base_date.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7  # "every Tuesday" posted on Tuesday → next one
            return (base_date + timedelta(days=days_ahead), True)

    # "Tuesdays at 7pm" — plural weekday + at-time = recurring
    m = re.match(r"(\w+)s\s+(?:at|@)\s", p)
    if m:
        wd = _weekday_index(m.group(1))
        if wd is not None:
            days_ahead = (wd - base_date.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            return (base_date + timedelta(days=days_ahead), True)

    # "this Saturday" → next Saturday on or after base_date
    m = re.match(r"this\s+(\w+)", p)
    if m:
        wd = _weekday_index(m.group(1))
        if wd is not None:
            days_ahead = (wd - base_date.weekday()) % 7
            return base_date + timedelta(days=days_ahead)

    # "next Saturday" → Saturday strictly AFTER this week
    m = re.match(r"next\s+(\w+)", p)
    if m:
        wd = _weekday_index(m.group(1))
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

    # Bare weekday: "Saturday", "Sat", "Tuesday" → next occurrence on or after
    # base_date. ONLY resolved when the caller has already verified
    # _FUTURE_EVENT_CONTEXT_RE matches in the surrounding text — see
    # _find_dates which gates this path.
    wd = _weekday_index(p)
    if wd is not None:
        days_ahead = (wd - base_date.weekday()) % 7
        # If posted on the same weekday, assume next week (e.g., Tuesday
        # post saying "Tuesday at 7" almost always means next Tuesday).
        if days_ahead == 0:
            days_ahead = 7
        return base_date + timedelta(days=days_ahead)

    return None


def _is_bare_weekday(phrase: str) -> bool:
    """True if the phrase is JUST a weekday name (no 'this/next/every' prefix)."""
    p = phrase.lower().strip().rstrip(",: ")
    if p in _WEEKDAY_NAMES:
        return True
    if p in _WEEKDAY_ABBREV:
        return True
    return False


def _find_dates(text: str, post_date=None) -> list:
    """Extract date objects from text using regex patterns + dateparser.

    If post_date is given, relative phrases like "tonight" / "tomorrow" /
    "this Friday" are anchored to the post's date instead of the scraper's
    "now".  This is critical because we scrape posts from days/weeks ago
    that mention "tomorrow" — meaning the day AFTER the post, not the day
    after we ran the scraper.

    Bare weekday matches ("Saturday at 8pm") are only resolved when the
    surrounding text indicates an upcoming event (`_FUTURE_EVENT_CONTEXT_RE`)
    — guards against false positives like "we had an amazing Saturday".

    Returns a list of date objects. Recurring markers ("every Tuesday")
    set the module-level last-call recurring sentinel via _LAST_FIND_DATES_RECURRING
    so callers can opt into reading it.
    """
    dates = []
    base_date = None
    if post_date is not None:
        base_date = post_date.date() if hasattr(post_date, "date") else post_date

    has_future_context = bool(_FUTURE_EVENT_CONTEXT_RE.search(text))
    is_recurring = False

    for pat in _DATE_PATTERNS:
        for match in re.finditer(pat, text, re.IGNORECASE):
            phrase = match.group()
            # Bare-weekday gate: requires future-event context to suppress
            # false positives like "we had a great Saturday last week".
            if _is_bare_weekday(phrase) and not has_future_context:
                continue
            resolved = None
            if base_date is not None:
                resolved = _resolve_relative(phrase, base_date)
            if resolved is None:
                # Fall back to dateparser (handles "May 5", "5/5", etc.)
                resolved = parse_date(phrase)
            if resolved is None:
                continue
            # Resolver may return a (date, True) tuple for recurring patterns.
            if isinstance(resolved, tuple):
                d, rec = resolved
                if rec:
                    is_recurring = True
                dates.append(d)
            else:
                dates.append(resolved)

    # Stash recurring flag for the caller. Module-level (not threaded) since
    # all three call sites in this file are single-threaded.
    global _LAST_FIND_DATES_RECURRING
    _LAST_FIND_DATES_RECURRING = is_recurring
    return dates


_LAST_FIND_DATES_RECURRING: bool = False


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
    # Lowercase function-word starters that signal a mid-sentence fragment.
    # Removed "the" — false-matches legit titles like "The Cribs @ Warsaw",
    # "The Book of Mormon", "The Rocky Horror Show". The other words almost
    # never legitimately start an event title.
    r"we\s|to\s|from\s|in\s|on\s|of\s|and\s|but\s|or\s|that\s|this\s|"
    r"would\s|could\s|should\s|will\s|stills?\s|next\s|"
    # Caption-mid-sentence narrative openers picked up at IG extraction
    r"whether\s|find\s+(?:the\s*\(|your\s|a\s+)|use\s+code\s|enter\s+code\s|"
    r"join\s+us\s|swipe\s|tag\s+a\s|friday\s+outside|sree\s+lo|"
    r"guber\s+one|just\s+rsvp|"
    r"not\s+your\s+(?:typical|average|usual|ordinary)|"
    # Location-label fragments ('Saturday Location:', 'Location:')
    r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+location:|"
    r"location:\s|venue:\s|where:\s|when:\s|"
    # Promo / giveaway captions
    r"grads\s+get\s|giving\s+away\s|win\s+a\s+|gift\s+card|"
    r"date\s+change\s|rescheduled\s+to|postponed\s+to|"
    # Title starts with '=' character (OCR garbage)
    r"=|"
    # Address-like start: digits + street word
    r"\d{1,5}\s+\w+\s+(?:st|street|ave|avenue|blvd|boulevard|rd|road|pl|"
    r"place|way|dr|drive|ln|lane)[\.,\s]|"
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
        # Skip lines that END as fragments — "X presents", "X introduces",
        # "X presented by", "X feat.", "X featuring" without the rest.
        # These are partial captions where the actual event name comes after
        # a line break and we picked up only the prefix.
        lower_end = cleaned.lower().rstrip(":!.…")
        if any(lower_end.endswith(suffix) for suffix in (
            " presents", " presented by", " introducing",
            " feat.", " featuring", " presents:", " present",
            " in collaboration with", " in partnership with",
            " hosted by", " brought to you by",
        )):
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
        # Inherit IG-account context from the base event so fan-out events
        # don't render as @None. Without this, slides 2-N of a carousel get
        # emitted but lose the IG account attribution.
        for field in ("instagramAccount", "accountVerified", "accountFollowers", "evergreen"):
            if base.get(field):
                new_ev[field] = base[field]
        # Carry engagement signals too — they're per-post not per-slide.
        for field in ("likes", "comments"):
            if base.get(field):
                new_ev[field] = base[field]
        extras.append(new_ev)

    return extras
