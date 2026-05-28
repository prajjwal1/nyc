"""Auto-derive the user's interests from their IG follow graph + engagement.

The goal: stop hardcoding keyword block/boost lists. Instead, observe who
the user follows and what they've engaged with, then derive a profile that
the ranker uses to push the most-relevant events to the top.

What feeds the profile (in priority order):
  1. user_curated_sources.json — explicit + engagement-saved hosts/hints
  2. user_affinity_accounts.json — accounts the user has saved-from
  3. discovered_accounts.json — accounts the user follows on IG
     (discovered_via == 'user_following')
  4. account_quality.json — historical events-per-post yield, used to weight

Output: scrapers/data/user_interest_profile.json with:
  - venue_hosts: hosts that user-followed accounts link to in bios
  - keywords: ngrams from followed-account usernames + bios
  - signal_accounts: set of IG accounts treated as 'voice of the user'
  - last_built: ISO timestamp

The ranker reads this file via `interest_profile_boost(event)` and applies
a small (≤0.15) boost when an event matches the profile. Combined with a
tighter score floor, this surfaces fewer-but-more-relevant events without
manual keyword maintenance.
"""

import json
import os
import re
from collections import Counter
from datetime import datetime
from typing import Iterable

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
PROFILE_PATH = os.path.join(DATA_DIR, "user_interest_profile.json")
DISCOVERED_PATH = os.path.join(DATA_DIR, "discovered_accounts.json")
AFFINITY_PATH = os.path.join(DATA_DIR, "user_affinity_accounts.json")
QUALITY_PATH = os.path.join(DATA_DIR, "account_quality.json")
CURATED_PATH = os.path.join(DATA_DIR, "user_curated_sources.json")


def _load(path: str, default):
    if not os.path.isfile(path):
        return default
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


# Common substrings inside IG usernames that signal what an account is
# about — we use them as soft topic tokens. Not blocklists, not hardcoded
# matches against event titles; just hints derived from who the user
# follows. The set evolves automatically as the follow graph evolves.
_USERNAME_TOPIC_HINTS = (
    "book", "lit", "poet", "read", "literary",     # books
    "jazz", "music", "live", "dj", "vinyl", "sound", "band",  # music
    "art", "gallery", "museum",                    # art
    "comedy", "improv", "standup",                 # comedy
    "food", "kitchen", "chef", "wine", "bar",      # food
    "running", "run", "fit", "yoga", "wellness",   # fitness
    "ny", "nyc", "brooklyn", "bk", "manhattan",    # NYC location
    "single", "date", "love",                      # singles
    "park", "outdoor", "garden", "nature",         # outdoors
    "rave", "club", "party", "social",             # nightlife/social
    "queer", "lgbtq", "pride",                     # (descriptive, not exclusive)
    "vintage", "thrift", "flea",                   # shopping/exploration
    "dance",                                       # dance
    "tech", "ai", "startup", "founder",            # (de-boost zone)
)


def _username_topics(username: str) -> set[str]:
    """Extract topic hints embedded in an IG username (a.k.a. handle)."""
    u = username.lower()
    return {t for t in _USERNAME_TOPIC_HINTS if t in u}


def build_profile() -> dict:
    """Read the user's follow + engagement signals and write a fresh profile."""

    disc = _load(DISCOVERED_PATH, {"accounts": []})
    aff = _load(AFFINITY_PATH, {"accounts": []})
    quality = _load(QUALITY_PATH, {})
    curated = _load(CURATED_PATH, {"hosts": {}, "title_hints": {}})

    follows = [
        a for a in disc.get("accounts", [])
        if a.get("discovered_via") == "user_following"
    ]
    follow_usernames = {(a.get("username") or "").lower() for a in follows}
    follow_usernames.discard("")

    # Saved-from (affinity) accounts come either from a dict {accounts:[]}
    # or from a flat list of usernames. Tolerate both formats.
    if isinstance(aff, dict):
        affinity_usernames = {
            (a if isinstance(a, str) else a.get("username", "")).lower()
            for a in aff.get("accounts", [])
        }
    else:
        affinity_usernames = {str(a).lower() for a in aff}
    affinity_usernames.discard("")

    # Topic-hint frequency across the follow graph — pure observation, no
    # hardcoded preferences. If the user follows 30 accounts with 'book'
    # in the handle and 2 with 'tech', the profile reflects that.
    topic_counts: Counter[str] = Counter()
    for u in follow_usernames | affinity_usernames:
        for t in _username_topics(u):
            topic_counts[t] += 1

    # Build per-account yield map for weighting how much each follow
    # contributes to the profile. Accounts that consistently produce events
    # the pipeline accepts get more weight; dormant or noisy accounts less.
    yield_map = {}
    for u in follow_usernames | affinity_usernames:
        info = (quality.get(u) or {}) if isinstance(quality, dict) else {}
        posts = info.get("posts_scraped", 0) or 0
        ev = info.get("events_emitted", 0) or 0
        y = ev / posts if posts else 0.0
        yield_map[u] = round(y, 3)

    # Read excluded accounts so user-rejected handles don't keep getting
    # the follow-graph boost (e.g. user follows houseofyesnyc for the
    # aesthetic but doesn't want their events surfaced).
    excluded_path = os.path.join(DATA_DIR, "user_excluded_sources.json")
    excluded_usernames: set[str] = set()
    if os.path.isfile(excluded_path):
        try:
            with open(excluded_path) as f:
                exc = json.load(f)
            excluded_usernames = {k.lower() for k in (exc.get("accounts") or {}).keys()}
        except Exception:
            pass

    # Signal accounts = follows + affinity (minus exclusions), ordered by
    # yield desc. Excluded accounts get NO boost even if user follows them.
    signal = sorted(
        (follow_usernames | affinity_usernames) - excluded_usernames,
        key=lambda u: -yield_map.get(u, 0),
    )

    profile = {
        "last_built": datetime.utcnow().isoformat() + "Z",
        "follow_count": len(follow_usernames),
        "affinity_count": len(affinity_usernames),
        "topic_counts": dict(topic_counts.most_common()),
        "signal_accounts": signal[:200],
        "yield_map": yield_map,
        # Curated hosts/hints carried forward; the ranker reads
        # user_curated_sources.json directly but we surface them here
        # so a single file describes the user's revealed preferences.
        "curated_hosts": list(curated.get("hosts", {}).keys()),
        "curated_title_hints": list(curated.get("title_hints", {}).keys()),
    }

    os.makedirs(os.path.dirname(PROFILE_PATH), exist_ok=True)
    with open(PROFILE_PATH, "w") as f:
        json.dump(profile, f, indent=2)
    return profile


# In-process cache so the ranker doesn't re-read the file for every event.
_CACHE: dict | None = None


def get_profile() -> dict:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    if not os.path.isfile(PROFILE_PATH):
        build_profile()
    _CACHE = _load(PROFILE_PATH, {})
    return _CACHE


_WORD_RE = re.compile(r"[a-z0-9]+")


def interest_profile_boost(event: dict) -> float:
    """Return a 0..0.25 boost for events that align with the user's profile.

    Boost magnitudes tuned so events from accounts the user actually
    follows reliably outrank generic aggregator content.

    Signals checked (cumulative, capped):
      - Event IG account is in signal_accounts → +0.15
      - Event title/desc contains topic hints with positive follow-graph
        frequency → +0.03 each (capped at 0.10)
      - Event's host (from sourceUrl) matches a curated host → +0.05

    Caption-fragment titles get NO account-level boost — we don't want
    'Preorder today on our website!' from a curated bookstore to rank
    above its actual book-launch event just because the user follows
    that bookstore. The fragment detector already lowers title_quality
    but the +0.15 explicit boost was overriding it.
    """
    profile = get_profile()
    if not profile:
        return 0.0
    boost = 0.0

    # Suppress account-level boost when title looks like a CTA / caption
    # fragment. Topic + host signals still apply because they reflect
    # the event's actual content / source, not just who posted it.
    try:
        from ..quality import _is_caption_fragment
        title_is_fragment = _is_caption_fragment(
            event.get("title", ""), event.get("description", "") or "",
        )
    except Exception:
        title_is_fragment = False

    # 1) Account-level signal — the strongest tell, but only when the
    # title is actually a real event (not a fragment).
    acct = (event.get("instagramAccount") or "").lower()
    if acct and acct in set(profile.get("signal_accounts", [])) and not title_is_fragment:
        boost += 0.15

    # 2) Topic overlap
    topic_counts = profile.get("topic_counts", {}) or {}
    if topic_counts:
        text = " ".join([
            (event.get("title") or "").lower(),
            (event.get("description") or "")[:200].lower(),
        ])
        tokens = set(_WORD_RE.findall(text))
        # User-shorthand fold: a follow with "bk" in its handle (franklinparkbk,
        # anaiswinebk, …) signals Brooklyn interest. Mirror tokens so the
        # `bk` topic also matches "brooklyn" text and vice versa.
        if "brooklyn" in tokens:
            tokens.add("bk")
        if "bk" in tokens:
            tokens.add("brooklyn")
        # Only count topics with at least 2 followed accounts referencing
        # them — singletons are noise.
        matched = sum(1 for t, c in topic_counts.items()
                      if c >= 2 and t in tokens)
        boost += min(0.10, matched * 0.03)

    # 3) Host match
    url = (event.get("sourceUrl") or "").lower()
    if any(h in url for h in profile.get("curated_hosts", [])):
        boost += 0.05

    return min(0.25, boost)
