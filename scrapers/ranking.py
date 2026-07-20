"""Sophisticated multi-signal event ranking optimized for engagement.

Designed to surface events the user would actually want to attend, like
Instagram's algorithm — using source curation, proximity, category match,
title/description quality, and time-of-day signals.
"""

import re
from .config import USER_INTERESTS, SOURCE_QUALITY
from .quality import quality_signals

NEIGHBORHOOD_PROXIMITY = {
    "williamsburg": 1.0,
    "greenpoint": 0.92,
    "bushwick": 0.88,
    "east village": 0.82,
    "lower east side": 0.82,
    "dumbo": 0.78,
    "brooklyn heights": 0.76,
    "fort greene": 0.78,
    "prospect heights": 0.74,
    "park slope": 0.72,
    "soho": 0.68,
    "chelsea": 0.62,
    "midtown": 0.45,
    "upper east side": 0.4,
    "upper west side": 0.4,
    "brooklyn": 0.7,
    "manhattan": 0.55,
}


def compute_score(event: dict) -> float:
    """Compute a 0-1 relevance score. Each event 'fights' for its position.

    Multi-signal scoring:
      - Source curation (40% weight via source + IG-author signal)
      - Category match against user interests (with category-specific multipliers)
      - Proximity to Williamsburg
      - Title/description quality (zero out caption fragments)
      - Time-of-day fit (post-work weekday, all-day weekend)
      - Hard penalty for soft-block keywords and audience mismatches
      - Boost for high-value vibes (rooftop, opening, premiere) and social keywords
    """
    signals = quality_signals(event)

    # Caption fragments get nuked entirely
    if signals["is_caption_fragment"]:
        return 0.0

    # Title quality below 0.3 = clearly bad title, nuke
    if signals["title_quality"] < 0.3:
        return 0.0

    # Story-scoped title floor (fb-175): IG-story OCR/caption fragments that pass
    # the global fragment detector but aren't real events ("2 mini lobster rolls",
    # "45 minutes of feel Sood", "Purchase a @nike kit..."). Scoped to isStory so
    # legit non-story digit-led/imperative titles (e.g. "718 Sessions PRIDE BOAT
    # PARTY", "Get the Beauty Scoop") are untouched.
    if event.get("isStory") or event.get("discoveredVia") == "ig_story":
        _t = (event.get("title") or "").strip().lower()
        _imperative = (
            "purchase ",
            "buy ",
            "get ",
            "try ",
            "grab ",
            "order ",
            "shop ",
            "tap ",
            "swipe ",
            "click ",
            "use code",
            "dm us",
            "head to",
        )
        if re.match(r"^\d", _t) or _t.startswith(_imperative):
            return 0.0

    # Multi-signal ranking
    proximity = _proximity_score(event)
    category = _category_score(event)
    price = _price_score(event)
    popularity = _popularity_score(event)
    source = _source_score(event)
    completeness = _completeness_score(event)

    # Quality signals
    title_q = signals["title_quality"]
    desc_q = signals["desc_quality"]
    time_q = signals["time_score"]

    # Engagement boosts/penalties
    high_value_boost = min(0.30, signals["high_value_hits"] * 0.15)
    # Alcohol-free boost — user wants to see more sober-friendly events.
    # Drinking-centric events still surface (soft_penalty already pushes
    # them down a bit), this just floats alcohol-free options up.
    alcohol_free_boost = min(0.10, signals.get("alcohol_free_hits", 0) * 0.05)
    # Social events are the user's primary goal (meet people, not just attend).
    # Bumped cap from 0.20 → 0.28 to push singles/mixers/social events to top.
    social_boost = min(0.28, signals["social_hits"] * 0.12)
    # "Meet-people tier": 2+ social signals AND event is in the next 21 days.
    # Immediacy matters for social events — a singles mixer next month is much
    # less useful than one this week.
    meet_people_boost = _meet_people_tier_boost(event, signals)
    soft_penalty = min(0.4, signals["soft_penalty_hits"] * 0.15)
    audience_penalty = 0.5 if signals["audience_mismatch"] else 0.0

    # Strict baseline weighted average — every signal must pull its weight.
    # Weights sum to 0.55 (not 1.0) so a "perfect" base leaves headroom for
    # boosts to differentiate top-tier events instead of saturating at 1.0.
    base_score = (
        proximity * 0.09
        + category * 0.12  # interests are critical
        + price * 0.02
        + popularity * 0.04
        + source * 0.11  # IG is curated
        + completeness * 0.03
        + title_q * 0.07  # punish caption fragments
        + desc_q * 0.03
        + time_q * 0.04
    )

    # User-saved posts get a major boost — explicit bookmark is highest signal
    saved_boost = 0.25 if event.get("userSaved") else 0.0

    # User-tagged: someone tagged the user — implicit invitation
    tagged_boost = (
        0.20 if event.get("userTagged") and not event.get("userSaved") else 0.0
    )

    # User-affinity: events from accounts user has saved from in the past
    affinity_boost = (
        0.10
        if event.get("userAffinity")
        and not (event.get("userSaved") or event.get("userTagged"))
        else 0.0
    )

    # User-following: account user directly follows on IG (manual choice).
    # Even if they haven't saved, the user actively chose to follow.
    following_boost = (
        0.08
        if event.get("userFollowing")
        and not (
            event.get("userSaved")
            or event.get("userTagged")
            or event.get("userAffinity")
        )
        else 0.0
    )

    # User-curated source/series boost — reads scrapers/data/user_curated_sources.json
    # at runtime. Designed to be appended-to over time by an
    # engagement-tracking loop (or by the user directly editing the JSON),
    # NOT by changing code. Hosts user has saved events from get added
    # automatically; cold-start seed entries also live here.
    curated_boost = _user_curated_boost(event)

    # Auto-derived interest profile — reads scrapers/data/user_interest_profile.json
    # which is built from the user's IG follow graph + affinity engagement
    # (utils/interest_profile.py). No hardcoded keywords; the profile evolves
    # as the user's follow graph evolves.
    try:
        from .utils.interest_profile import interest_profile_boost

        interest_boost = interest_profile_boost(event)
    except Exception:
        interest_boost = 0.0

    # Cross-source confirmation: same event appearing on 2+ sources is
    # very strong validation (e.g., Eventbrite + Instagram both list it).
    n_sources = len(event.get("contributingSources", []))
    cross_source_boost = 0.0
    if n_sources >= 4:
        cross_source_boost = 0.16  # 4+ sources → trending
    elif n_sources >= 3:
        cross_source_boost = 0.12
    elif n_sources == 2:
        cross_source_boost = 0.07
    # Cross-IG-account confirmation: when 2+ DIFFERENT IG accounts promote
    # the same event, it's a strong "definitely happening + worth seeing"
    # signal — distinct from cross-source (which is platform diversity).
    # Stacks with cross_source but capped so a single channel can't
    # dominate the boost stack.
    n_accts = len(event.get("contributingAccounts", []))
    cross_acct_boost = 0.0
    if n_accts >= 4:
        cross_acct_boost = 0.10
    elif n_accts >= 3:
        cross_acct_boost = 0.07
    elif n_accts == 2:
        cross_acct_boost = 0.04
    cross_source_boost += cross_acct_boost
    # Hot boost: cross-source AND firstSeenAt within last 7 days = trending
    hot_boost = _hot_event_boost(event)
    # Account-yield boost: IG accounts that consistently produce events
    yield_boost = _account_yield_boost(event)
    # Affinity co-mention boost: accounts repeatedly @-tagged in event
    # posts by accounts the user saves-from are high-confidence picks.
    comention_boost = _affinity_comention_boost(event)
    # Engagement velocity: events whose likes/comments have grown since
    # the last scrape are trending — distinct from raw popularity score.
    velocity_boost = _engagement_velocity_boost(event)
    # Content-quality boost: real flyer image + substantive description
    quality_boost = _content_quality_boost(event)

    # Account-level credibility: verified or large follower count = trustworthy
    cred_boost = _account_credibility_boost(event)

    # Time relevance: events in the next 14 days get a small boost
    # (people care more about "what to do this weekend" than 2 months out)
    time_relevance = _time_relevance_boost(event)
    # Story urgency: IG stories are 24h-ephemeral by nature — if it's still
    # in our pool it's by definition very recent. Small extra boost so
    # story-sourced events surface above feed-sourced equivalents.
    if event.get("isStory") or event.get("discoveredVia") == "ig_story":
        time_relevance += 0.04
    # Highlight curation: the venue explicitly pinned this event in a
    # highlight collection ("Upcoming Shows" etc.) — strongest editorial
    # signal we can get from the venue itself. Slightly bigger than the
    # story boost since highlights are intentionally curated.
    if event.get("isHighlight") or event.get("discoveredVia") == "ig_highlight":
        time_relevance += 0.05
    # Pinned post: the account pinned this post to the top of their feed.
    # IG limits pinning to 3 slots — when an account pins an event post
    # that's their own "must-see" call. Strong quality signal independent
    # of engagement counts (a freshly-pinned post may not yet have likes).
    if event.get("isPinned"):
        time_relevance += 0.04
    # Composite trending boost — events firing 2+ trend signals get an
    # additional bump on top of the individual signal boosts. This is
    # bounded (+0.05) since the underlying signals already contributed.
    if _is_trending(event):
        time_relevance += 0.05
    # Day-of-week fit: parties on Fri/Sat, fitness on weekdays, etc.
    dow_fit = _day_of_week_fit_boost(event)
    # Time-of-day fit: evening events boosted (working-professional bias).
    tod_fit = _time_of_day_fit_boost(event)
    # Geographic proximity boost when event has lat/lng coordinates.
    geo_proximity = _distance_proximity_boost(event)

    # User-explicit signals (saved/tagged/affinity/following) are uncapped —
    # an explicit bookmark should always pull an event to the top regardless
    # of how many other signals fire. Everything else stacks under a sum-cap
    # so events with broad keyword overlap don't saturate at 1.0 and tie.
    explicit_boost = (
        saved_boost
        + tagged_boost
        + affinity_boost
        + following_boost
        + curated_boost
        + interest_boost
    )
    stacked_boosts = (
        high_value_boost
        + alcohol_free_boost
        + social_boost
        + meet_people_boost
        + cred_boost
        + cross_source_boost
        + hot_boost
        + yield_boost
        + comention_boost
        + velocity_boost
        + quality_boost
        + time_relevance
        + dow_fit
        + tod_fit
        + geo_proximity
        # WS2: semantic taste — similarity to events the user saves/attends.
        # Bounded in taste.py (+0.15/−0.10); 0.0 until the user syncs taste.
        + (event.get("tasteScore", 0.0) or 0.0)
    )
    # dow_fit/tod_fit/geo_proximity can be negative; preserve their downward
    # signal but cap the positive sum so ranking still differentiates.
    # Cap lowered 0.55→0.32 (critic P1): at 0.55 almost any broadly-social
    # event maxed the stack → base(~0.45)+0.55≈1.0, saturating 30+ events at
    # 1.0 and making the top of the feed unordered. A tighter cap leaves
    # headroom so explicit conviction (saved/following) + the semantic taste
    # signal actually differentiate the top — e.g. a Warm Up the user's taste
    # matches now beats a generic wine tasting instead of tying it.
    capped_stack = min(0.32, max(-0.20, stacked_boosts))

    final = base_score + explicit_boost + capped_stack - soft_penalty - audience_penalty
    return max(0.0, min(1.0, final))


def _content_quality_boost(event: dict) -> float:
    """Small boost for events that have substantive content — proper
    description AND a real flyer image. These signal "this is a real event
    someone took the time to post about" vs a bare placeholder.

    Capped at +0.05 so it nudges, doesn't dominate.
    """
    boost = 0.0
    img = (event.get("imageUrl") or "").strip()
    desc = (event.get("description") or "").strip()
    # Image presence — a real flyer is a strong quality signal
    if img and len(img) > 30:
        boost += 0.02
    # Description in the sweet-spot range (not too short, not pasted novel)
    desc_len = len(desc)
    if 60 <= desc_len <= 600:
        boost += 0.03
    elif 30 <= desc_len < 60:
        boost += 0.01
    return min(0.05, boost)


def _account_yield_boost(event: dict) -> float:
    """Boost events from IG accounts that historically emit lots of events.

    accountEventYield is events_emitted / posts_scraped (lifetime).
      - >= 0.5 (every other post is an event): +0.06 — a true event venue
      - >= 0.25:                                 +0.04
      - >= 0.10:                                 +0.02
    Below 0.10: no boost (account posts mostly non-event content).
    """
    yield_ = event.get("accountEventYield", 0.0)
    if not yield_:
        return 0.0
    posts_seen = event.get("accountPostsSeen", 0)
    if posts_seen < 5:
        return 0.0
    if yield_ >= 0.5:
        return 0.06
    if yield_ >= 0.25:
        return 0.04
    if yield_ >= 0.10:
        return 0.02
    return 0.0


def _engagement_velocity_boost(event: dict) -> float:
    """Boost when this event's likes/comments have grown since last scrape.
    Trending signal — distinct from raw popularity (which scores absolute
    counts). An event going from 50 likes to 200 likes between scrapes is
    going viral; we should surface it.

    delta = (likes_delta) + 5 * (comments_delta), only positive deltas
    are stored (prefer trending up). Tiers:
      >= 500 delta: +0.10  (going viral)
      >= 150 delta: +0.07  (rapidly accumulating attention)
      >= 50 delta:  +0.04  (steady growth)
      >= 10 delta:  +0.02  (some growth)
    """
    delta = event.get("engagementDelta", 0) or 0
    if delta >= 500:
        return 0.10
    if delta >= 150:
        return 0.07
    if delta >= 50:
        return 0.04
    if delta >= 10:
        return 0.02
    return 0.0


def _affinity_comention_boost(event: dict) -> float:
    """Boost when this event's IG account has been @-mentioned in event posts
    by accounts the user already saves from. Strong recommendation signal:
    'people you trust point to this account.'

    Tier:
      >= 5 comentions: +0.10
      >= 3 comentions: +0.07
      >= 2 comentions: +0.05
      >= 1 comention:  +0.03
    """
    n = event.get("affinityComentions", 0)
    if n >= 5:
        return 0.10
    if n >= 3:
        return 0.07
    if n >= 2:
        return 0.05
    if n >= 1:
        return 0.03
    return 0.0


def _hot_event_boost(event: dict) -> float:
    """Trending boost: event has 2+ sources AND was first seen recently.

    A multi-source event that just landed in our pool is one currently
    being talked about. Cap small (+0.08) since cross_source_boost already
    captures the multi-source signal.
    """
    n_sources = len(event.get("contributingSources", []))
    if n_sources < 2:
        return 0.0
    fs = event.get("firstSeenAt", "")
    if not fs:
        return 0.0
    from datetime import datetime, timezone, timedelta

    try:
        ts = datetime.fromisoformat(fs)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
    except Exception:
        return 0.0
    age_days = (datetime.now(timezone.utc) - ts).days
    if age_days > 7:
        return 0.0
    if age_days <= 1:
        return 0.08
    if age_days <= 3:
        return 0.05
    return 0.03


def _meet_people_tier_boost(event: dict, signals: dict) -> float:
    """Extra boost for events that are *primarily* about meeting people:
    2+ social signals AND happening within the next 21 days.

    User's stated goal: replace IG scrolling with a curated feed of events to
    meet people. This boost makes those events float to the top.
    """
    if signals.get("social_hits", 0) < 2:
        return 0.0
    from datetime import date, datetime

    date_str = event.get("date", "")
    if not date_str:
        return 0.0
    try:
        ev_date = datetime.fromisoformat(date_str).date()
    except Exception:
        return 0.0
    days_out = (ev_date - date.today()).days
    if days_out < 0 or days_out > 21:
        return 0.0
    # 0.10 base + extra for events sooner
    if days_out <= 3:
        return 0.14
    if days_out <= 7:
        return 0.12
    return 0.10


def _account_credibility_boost(event: dict) -> float:
    """Small boost for events from verified or large IG accounts.

    Verified = +0.04
    >100k followers = +0.04
    >25k followers = +0.025
    >5k followers = +0.015
    """
    boost = 0.0
    if event.get("accountVerified"):
        boost += 0.04
    followers = event.get("accountFollowers", 0) or 0
    if followers >= 100_000:
        boost += 0.04
    elif followers >= 25_000:
        boost += 0.025
    elif followers >= 5_000:
        boost += 0.015
    return min(0.06, boost)  # cap so it doesn't dominate


def _time_of_day_fit_boost(event: dict) -> float:
    """Match event start time to typical preference for after-work attendance.

    Working professional in their 20s/30s mostly attends events after 5pm.
    - 18:00-22:00 (prime evening): +0.04
    - 17:00-23:00 (extended evening): +0.02
    - 06:30-09:00 (morning fitness/run): +0.02 (only for fitness/wellness)
    - 09:00-16:00 weekdays: -0.02 (mid-day events less accessible)
    - 09:00-16:00 weekends: 0 (no penalty — weekends are open)
    """
    from datetime import date as _date, datetime

    start = event.get("startTime") or ""
    if not start or ":" not in start:
        return 0.0
    try:
        h = int(start.split(":")[0])
    except Exception:
        return 0.0
    date_str = event.get("date", "")
    try:
        ev_date = datetime.fromisoformat(date_str).date()
        is_weekend = ev_date.weekday() >= 5
    except Exception:
        is_weekend = False

    cats = set(event.get("categories", []))
    is_fitness_morning = 6 <= h <= 9 and bool(
        cats & {"fitness", "wellness", "outdoors"}
    )

    if is_fitness_morning:
        return 0.02
    if 18 <= h < 22:
        return 0.04
    if 17 <= h < 23:
        return 0.02
    if 9 <= h < 16 and not is_weekend:
        return -0.02
    return 0.0


def _day_of_week_fit_boost(event: dict) -> float:
    """Match event type to typical attendance patterns.

    - Parties / nightlife / social: Friday + Saturday boost; weekday penalty
    - Run clubs / fitness / classes: weekday boost; weekend slight penalty
    - Brunch / food: Sat/Sun late-morning boost
    - Live music: Thu-Sat boost
    Cap small (+0.05/-0.03) so it nudges, doesn't dominate.
    """
    from datetime import date as _date, datetime

    date_str = event.get("date", "")
    if not date_str:
        return 0.0
    try:
        ev_date = datetime.fromisoformat(date_str).date()
    except Exception:
        return 0.0

    weekday = ev_date.weekday()  # 0=Mon..6=Sun
    is_weekend = weekday >= 5  # Sat/Sun
    is_fri_sat = weekday in (4, 5)
    cats = set(event.get("categories", []))
    text = (event.get("title", "") + " " + event.get("description", ""))[:300].lower()

    boost = 0.0
    # Parties / nightlife / singles benefit on Fri/Sat
    if cats & {"parties", "singles"} or any(
        k in text for k in ("dj", "dance party", "nightlife", "rooftop")
    ):
        if is_fri_sat:
            boost += 0.05
        elif weekday in (0, 1, 2):  # Mon/Tue/Wed
            boost -= 0.03
    # Live music: Thu/Fri/Sat
    if "music" in cats or any(
        k in text for k in ("concert", "live music", "live band")
    ):
        if weekday in (3, 4, 5):
            boost += 0.04
    # Fitness / run clubs: weekdays preferred (people work-out before/after work)
    if cats & {"fitness", "wellness"} or any(
        k in text for k in ("run club", "yoga", "workout")
    ):
        if not is_weekend:
            boost += 0.03
    # fb-184: profile-aligned fitness/run/dance Eventbrite-category events
    # score ~0.36-0.51 on completeness/title/time and miss the 0.55 floor
    # despite being user-requested (fb-179). Recover ONLY well-formed ones:
    # require BOTH a parsed startTime AND a venue name, so a low-info
    # caption-only event still floors out (preserves the 0.55 quality gate —
    # this is NOT a category-wide exemption). The +0.05 lifts the verified
    # 0.49-0.54 cluster over 0.55; the final clamp below caps total stacking
    # at +0.06 so it can't run away.
    if cats & {"fitness", "wellness", "outdoors"} or any(
        k in text for k in ("run club", "yoga", "pilates", "contra", "swing dance")
    ):
        if event.get("startTime") and (event.get("location", {}) or {}).get("name"):
            boost += 0.05
    # Brunch / food on weekends
    if "food" in cats and any(k in text for k in ("brunch", "morning", "breakfast")):
        if is_weekend:
            boost += 0.03
    return max(-0.05, min(0.06, boost))


def _time_relevance_boost(event: dict) -> float:
    """Boost events happening soon. Weighted heavily for "tonight" (today,
    after current time) since that's the user's primary use case — replacing
    IG scrolling for "what's happening tonight"."""
    from datetime import date, datetime

    date_str = event.get("date", "")
    if not date_str:
        return 0.0
    try:
        ev_date = datetime.fromisoformat(date_str).date()
    except Exception:
        return 0.0
    today = date.today()
    days_out = (ev_date - today).days
    if days_out < 0:
        return 0.0
    if days_out == 0:
        # "Tonight" — strongest urgency. If startTime is known and in the
        # next 6 hours, treat it as prime-time. Otherwise still boost as
        # today's event.
        start = (event.get("startTime") or "").strip()
        if start and ":" in start:
            try:
                hh, mm = start.split(":")[:2]
                ev_hm = int(hh) * 60 + int(mm)
                now = datetime.now()
                cur_hm = now.hour * 60 + now.minute
                # Future-of-today: stronger boost the closer to now
                if ev_hm >= cur_hm:
                    diff_min = ev_hm - cur_hm
                    if diff_min <= 180:  # within 3 hours
                        return 0.12
                    if diff_min <= 360:  # within 6 hours
                        return 0.10
                    return 0.07  # later today
                else:
                    # Already started today — moderate boost so it doesn't
                    # disappear (some events are multi-hour).
                    return 0.03
            except Exception:
                pass
        return 0.07  # today, no time known
    if days_out == 1:
        return 0.06  # tomorrow
    if days_out <= 4:
        return 0.04  # this week-ish
    if days_out <= 7:
        return 0.03  # next 7 days
    if days_out <= 14:
        return 0.015  # next 2 weeks
    return 0.0


def _is_trending(event: dict) -> bool:
    """Composite 'going viral right now' check.

    Returns True when 2+ of these signals fire AND the event is upcoming:
      - Multi-account: >= 2 distinct IG accounts promoted it
      - Engagement velocity: engagementDelta >= 50 (likes/comments growing)
      - Fresh: firstSeenAt within last 3 days

    The 2-of-3 floor avoids false positives (a recently-discovered event
    isn't 'trending' on its own — it just got scraped) while catching the
    "this is taking off" pattern users notice when scrolling IG.
    """
    from datetime import date, datetime, timezone, timedelta

    # Event must be upcoming
    date_str = event.get("date", "")
    if not date_str:
        return False
    try:
        ev_date = datetime.fromisoformat(date_str).date()
    except Exception:
        return False
    days_out = (ev_date - date.today()).days
    if days_out < 0 or days_out > 14:
        return False

    signals = 0
    if len(event.get("contributingAccounts", [])) >= 2:
        signals += 1
    delta = event.get("engagementDelta", 0) or 0
    if delta >= 50:
        signals += 1
    fs = event.get("firstSeenAt", "")
    if fs:
        try:
            ts = datetime.fromisoformat(fs)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - ts) <= timedelta(days=3):
                signals += 1
        except Exception:
            pass
    return signals >= 2


_USER_EXCLUDED_CACHE: dict | None = None


def _load_user_excluded_sources() -> dict:
    """Read scrapers/data/user_excluded_sources.json (cached). Returns
    {accounts, hosts, title_hints}. Symmetric to user_curated_sources.json
    — sources/series the user has explicitly said NO to. Auto-grows from
    repeated hide signals.
    """
    global _USER_EXCLUDED_CACHE
    if _USER_EXCLUDED_CACHE is not None:
        return _USER_EXCLUDED_CACHE
    import os as _os, json as _json

    path = _os.path.join(
        _os.path.dirname(_os.path.abspath(__file__)),
        "data",
        "user_excluded_sources.json",
    )
    if not _os.path.isfile(path):
        _USER_EXCLUDED_CACHE = {
            "accounts": set(),
            "hosts": [],
            "title_hints": [],
            "title_hint_matchers": [],
        }
        return _USER_EXCLUDED_CACHE
    try:
        with open(path) as f:
            raw = _json.load(f)
        title_hints = [k.lower() for k in (raw.get("title_hints") or {}).keys()]
        # fb-181: short single-word hints (e.g. "rave") substring-matched into
        # legitimate words ("Raven & Goose", "travel", "gravel", "brave"),
        # dropping events the user actually wants. Precompile a word-boundary
        # matcher for any hint that is a single short alpha word; keep plain
        # substring matching for multi-word / longer / non-alpha hints (e.g.
        # "warehouse rave", "@ 99 scott", "abacus.ai") where substring is
        # intended. Cached on the cfg so is_user_excluded doesn't recompile.
        title_hint_matchers = []
        for h in title_hints:
            if len(h) <= 6 and " " not in h and h.isalpha():
                title_hint_matchers.append(re.compile(rf"\b{re.escape(h)}\b"))
            else:
                title_hint_matchers.append(h)
        _USER_EXCLUDED_CACHE = {
            "accounts": {k.lower() for k in (raw.get("accounts") or {}).keys()},
            "hosts": [k.lower() for k in (raw.get("hosts") or {}).keys()],
            "title_hints": title_hints,
            "title_hint_matchers": title_hint_matchers,
        }
        return _USER_EXCLUDED_CACHE
    except Exception:
        _USER_EXCLUDED_CACHE = {
            "accounts": set(),
            "hosts": [],
            "title_hints": [],
            "title_hint_matchers": [],
        }
        return _USER_EXCLUDED_CACHE


def is_user_excluded(event: dict) -> bool:
    """True if event matches any user-excluded source. Used by
    normalize.process() to drop events BEFORE ranking — these are
    "I don't want to see this" signals so they shouldn't be scored.
    """
    cfg = _load_user_excluded_sources()
    if not cfg["accounts"] and not cfg["hosts"] and not cfg["title_hints"]:
        return False
    acct = (event.get("instagramAccount") or "").lower()
    if acct and acct in cfg["accounts"]:
        return True
    # Iter 111: also check event.location.name against the accounts set
    # via the same alphanumeric-fold + suffix-strip/add used in
    # normalize._enrich_provenance_from_url. Cross-source events from
    # excluded venues (e.g. Eventbrite event at "House of Yes") need to
    # be dropped even though their instagramAccount field is empty.
    if cfg["accounts"]:
        loc = event.get("location") or {}
        loc_name = (
            (loc.get("name") or "").strip().lower() if isinstance(loc, dict) else ""
        )
        if loc_name and len(loc_name) >= 3:
            import re as _re

            loc_norm = _re.sub(r"[^a-z0-9]", "", loc_name)
            if len(loc_norm) >= 5:
                variants = {loc_norm}
                for suffix in ("nyc", "ny", "brooklyn", "manhattan", "bk"):
                    if loc_norm.endswith(suffix) and len(loc_norm) - len(suffix) >= 5:
                        variants.add(loc_norm[: -len(suffix)])
                for suffix in ("nyc", "ny", "bk"):
                    if not loc_norm.endswith(suffix):
                        variants.add(loc_norm + suffix)
                if any(v in cfg["accounts"] for v in variants):
                    return True
                # Iter 211: also check if any excluded account is a SUBSTRING
                # of loc_norm. Caught QA leak "Ruins, Knockdown Center" — the
                # venue is presented as a multi-room space "Ruins, KDC", and
                # the alphanumeric fold "ruinsknockdowncenter" didn't match
                # any variant of "knockdowncenter". Restrict to accounts >= 8
                # chars to avoid spurious matches (all current excluded
                # accounts are well above this threshold).
                for excl_acct in cfg["accounts"]:
                    if len(excl_acct) >= 8 and excl_acct in loc_norm:
                        return True
    url = (event.get("sourceUrl") or "").lower()
    for host in cfg["hosts"]:
        if host in url:
            return True
    matchers = cfg.get("title_hint_matchers") or cfg["title_hints"]
    if matchers:
        text = (
            (event.get("title") or "") + " " + (event.get("description") or "")[:300]
        ).lower()
        for m in matchers:
            # m is a compiled \bword\b pattern (short single-word hint) or a
            # plain substring (multi-word / longer / non-alpha hint).
            if m.search(text) if hasattr(m, "search") else m in text:
                return True
    return False


def _load_user_curated_sources() -> dict:
    """Read scrapers/data/user_curated_sources.json (cached). Returns a dict
    of {host_fragment: weight} and {title_hint: weight}.

    This file is intended to grow over time from user engagement (saved
    events, opened events) — not be hand-edited by the developer. Each
    entry has a `score` (0-1) that maps to the rank boost magnitude and
    a `source` field tagging where the entry came from ('user_mentioned',
    'engagement_saved', 'engagement_opens_count', etc.).
    """
    global _USER_CURATED_CACHE
    if _USER_CURATED_CACHE is not None:
        return _USER_CURATED_CACHE
    import os as _os

    path = _os.path.join(
        _os.path.dirname(_os.path.abspath(__file__)),
        "data",
        "user_curated_sources.json",
    )
    if not _os.path.isfile(path):
        _USER_CURATED_CACHE = {"hosts": {}, "title_hints": {}}
        return _USER_CURATED_CACHE
    try:
        import json as _json

        with open(path) as f:
            raw = _json.load(f)
        _USER_CURATED_CACHE = {
            "hosts": {
                k.lower(): float(v.get("score", 1.0))
                for k, v in (raw.get("hosts") or {}).items()
            },
            "title_hints": {
                k.lower(): float(v.get("score", 1.0))
                for k, v in (raw.get("title_hints") or {}).items()
            },
            # Hosts tagged "floor_bypass": false are "boost-only" — they get
            # the ranking boost but must still clear the 0.55 MIN_SCORE floor
            # (Critic S4: e.g. Elsewhere books on-taste AND off-taste late shows).
            "no_floor_hosts": {
                k.lower()
                for k, v in (raw.get("hosts") or {}).items()
                if isinstance(v, dict) and v.get("floor_bypass") is False
            },
        }
        return _USER_CURATED_CACHE
    except Exception:
        _USER_CURATED_CACHE = {"hosts": {}, "title_hints": {}, "no_floor_hosts": set()}
        return _USER_CURATED_CACHE


_USER_CURATED_CACHE: dict | None = None
_USER_CURATED_MAX_BOOST = 0.15


def _user_curated_boost(event: dict) -> float:
    """Boost for events from user-curated hosts or title-matching series.
    Magnitude scales with the score in user_curated_sources.json, capped at
    _USER_CURATED_MAX_BOOST. Generalizes across any source the user (or
    future auto-engagement-tracking) marks as high-signal — no hardcoded
    URLs in code.

    SUPPRESSED when the title is a caption fragment: we don't want a
    curated host (reading_rhythms, bookclubbar, etc.) to push 'Not your
    typical outdoor' or 'Preorder today on our website' to the top of
    the feed just because the publisher is one the user follows.
    Mirrors the iter-8 fix for interest_profile_boost.
    """
    # Skip if title is a caption fragment — the host signal shouldn't
    # rescue an unintelligible title.
    try:
        from .quality import _is_caption_fragment

        if _is_caption_fragment(
            event.get("title", ""), event.get("description", "") or ""
        ):
            return 0.0
    except Exception:
        pass
    cfg = _load_user_curated_sources()
    if not cfg["hosts"] and not cfg["title_hints"]:
        return 0.0
    boost = 0.0
    # Check sourceUrl AND organizerUrl. Events scraped from eventbrite
    # organizer pages keep the per-event slug URL in sourceUrl and the
    # /o/<id> URL in organizerUrl — both need to be checked against the
    # curated hosts so Lululemon's individual events still match the
    # organizer-host fragment.
    urls = (
        (event.get("sourceUrl") or "").lower(),
        (event.get("organizerUrl") or "").lower(),
    )
    for url in urls:
        if not url:
            continue
        for host, weight in cfg["hosts"].items():
            if host in url:
                boost = max(boost, weight)
    if boost < 1.0:
        text = (
            (event.get("title") or "") + " " + (event.get("description") or "")[:300]
        ).lower()
        for hint, weight in cfg["title_hints"].items():
            if hint in text:
                boost = max(boost, weight)
    return min(_USER_CURATED_MAX_BOOST, boost * _USER_CURATED_MAX_BOOST)


# --- fb-202: top-of-feed diversity (per-source + per-topic) ---------------
# A single prolific followed venue (Book Club Bar) was saturating the top of
# the feed (top-12 = 8 bookclubbar + 4 readingrhythms; 20/25 books), burying
# the user's other named tastes. compute_score is per-event; rank_events sees
# the whole batch, so the diversity pass lives here.

# Graduated demotion: first 2 events from a source (and a topic) are free —
# protects a followed venue's best 1-2 events (conviction preserved); the 3rd+
# is progressively demoted so no one venue/topic owns the top.
_SRC_STEPS = [0.0, 0.0, 0.16, 0.24, 0.32, 0.40]
_TOP_STEPS = [0.0, 0.0, 0.10, 0.16, 0.22, 0.27, 0.31, 0.34]


def _conviction(e: dict) -> bool:
    return bool(
        e.get("userSaved") or e.get("userTagged")
        or e.get("userAffinity") or e.get("userFollowing")
    )


def _diversity_floor(e: dict) -> float:
    # Conservative inline mirror of normalize._min_score_floor (avoids a
    # circular import). Always <= the real floor, so the clamp can only be
    # MORE lenient — it never drops an event the real gate would keep.
    return 0.40 if _conviction(e) else 0.55


def _diversity_source_key(e: dict) -> str:
    acct = (e.get("account") or e.get("instagramAccount") or "").strip().lower()
    if acct:
        return f"acct:{acct}"
    org = (e.get("organizerUrl") or e.get("organizer") or "").strip().lower()
    if org:
        return f"org:{org}"
    loc = ((e.get("location") or {}).get("name") or "").strip().lower()
    if loc:
        return f"srcloc:{e.get('source','')}|{loc}"
    return f"src:{e.get('source','')}"


_MUSIC_DJ_RE = re.compile(r"\b(dj|techno|house music|warm up|b2b)\b", re.IGNORECASE)


def _diversity_primary_topic(e: dict) -> str:
    """One topic per event for the diversity cap. Reuse the categorizer's
    categories first; only fall back to title heuristics for the KNOWN co-tag
    case (run clubs / social dances are tagged `music` because their titles say
    'Live Music'). DJ/electronic titles miscategorized as `other` count as music."""
    cats = e.get("categories") or []
    title = (e.get("title") or "").lower()
    # Co-tag correction: run/dance hidden under a music tag.
    if "run" in title and ("run club" in title or "run " in title or title.endswith("run")):
        return "run"
    if any(k in title for k in ("contra", "salsa", "swing danc", "lindy", "bachata")):
        return "dance"
    # DJ/electronic often lands in `other` — pull it into music (user's taste).
    if _MUSIC_DJ_RE.search(title):
        return "music"
    for t in ("run", "dance", "comedy", "books", "music", "fitness", "wellness",
              "outdoors", "singles", "parties", "food", "art", "games", "film"):
        if t in cats:
            return t
    return cats[0] if cats else "other"


def _apply_diversity_penalty(events: list[dict]) -> None:
    """Demote 3rd+ events from the same source/topic (floor-clamped), then
    guarantee ≥1 music/electronic event in the top-12 (fb-202)."""
    by_src: dict[str, list[dict]] = {}
    by_top: dict[str, list[dict]] = {}
    for e in events:
        by_src.setdefault(_diversity_source_key(e), []).append(e)
        by_top.setdefault(_diversity_primary_topic(e), []).append(e)
    srank = {}
    for group in by_src.values():
        for i, e in enumerate(sorted(group, key=lambda x: -(x.get("score") or 0))):
            srank[id(e)] = i
    trank = {}
    for group in by_top.values():
        for i, e in enumerate(sorted(group, key=lambda x: -(x.get("score") or 0))):
            trank[id(e)] = i
    for e in events:
        raw = e.get("score") or 0.0
        pen = (_SRC_STEPS[min(srank[id(e)], len(_SRC_STEPS) - 1)]
               + _TOP_STEPS[min(trank[id(e)], len(_TOP_STEPS) - 1)])
        if pen <= 0:
            continue
        new = raw - pen
        floor = _diversity_floor(e)
        if raw >= floor:  # floor-safe clamp: only re-order survivors
            new = max(floor, new)
        e["score"] = round(new, 3)

    # Deterministic music-slot: graduated subtraction alone can't guarantee a
    # music event in top-12 (highest music base often sits below the literary
    # cluster). If none is present, bump the best floor-clearing music event
    # just above the lowest non-conviction, non-music event in the top-12.
    top_n = 12
    ordered = sorted(events, key=lambda x: -(x.get("score") or 0))
    top = ordered[:top_n]
    if any(_diversity_primary_topic(e) == "music" for e in top):
        return
    music = [e for e in events
             if _diversity_primary_topic(e) == "music" and (e.get("score") or 0) >= _diversity_floor(e)]
    if not music:
        return
    best = max(music, key=lambda x: x.get("score") or 0)
    if best in top:
        return
    displaceable = [e for e in top if not _conviction(e) and _diversity_primary_topic(e) != "music"]
    if not displaceable:
        return  # don't displace conviction; rare all-conviction top
    victim = min(displaceable, key=lambda x: x.get("score") or 0)
    best["score"] = round(min(1.0, (victim.get("score") or 0) + 0.005), 3)


def rank_events(events: list[dict]) -> list[dict]:
    # WS2: build the semantic taste model once over the batch and stash a
    # per-event taste score (similarity to what the user saves/attends).
    # Inert (0.0) until the user has synced liked-event text — safe cold start.
    try:
        from .utils.taste import build_taste_model

        taste = build_taste_model(events)
        if taste.active:
            for event in events:
                event["tasteScore"] = round(taste.score(event), 4)
    except Exception as exc:
        print(f"[ranking] taste model skipped: {exc}")
    for event in events:
        event["score"] = round(compute_score(event), 3)
        event["highlights"] = _compute_highlights(event)
    # fb-202: diversity pass over the whole batch (after base scores).
    _apply_diversity_penalty(events)
    return events


def _compute_highlights(event: dict) -> list[str]:
    """Extract 'must-go' indicator labels (free, opening, premiere, etc.)."""
    text = (event.get("title", "") + " " + event.get("description", "")).lower()
    highlights: list[str] = []

    # Saved-by-user is the strongest signal
    if event.get("userSaved"):
        highlights.append("saved")
    elif event.get("userTagged"):
        highlights.append("tagged")
    elif event.get("userAffinity"):
        highlights.append("affinity")
    elif event.get("userFollowing"):
        highlights.append("following")

    # Cross-source confirmation
    if len(event.get("contributingSources", [])) >= 2:
        highlights.append("verified")
    # Cross-IG-account confirmation — surfaces when 2+ different IG accounts
    # promoted the same event. Distinct from cross-source (platform diversity).
    if len(event.get("contributingAccounts", [])) >= 2:
        highlights.append("multi-promoted")
    # IG Story — 24h ephemeral. Important to flag because the source URL
    # may stop working after the story expires; user should know.
    if event.get("isStory") or event.get("discoveredVia") == "ig_story":
        highlights.append("story")
    # IG Highlight — pinned by the venue/account on their profile. This
    # is the venue's own editorial pick of "events worth knowing about"
    # so it's a strong curation signal. Persists indefinitely unlike
    # stories, so we use the highlight title (e.g. "Upcoming Shows")
    # as additional context in the UI when rendering.
    if event.get("isHighlight") or event.get("discoveredVia") == "ig_highlight":
        highlights.append("highlight")
    # Pinned post: account pinned this to top of feed (max 3 pinned slots
    # on IG). Account-level editorial signal — they thought this was worth
    # promoting above everything else they've posted recently.
    if event.get("isPinned"):
        highlights.append("pinned")

    # Composite "trending now" — when MULTIPLE trend signals fire on the
    # same event, that's the "everyone's talking about this RIGHT NOW"
    # situation users currently scroll IG to catch. Requires:
    #   - At least 2 of: multi-account (≥2 IG accts), engagement growth
    #     (delta ≥ 50), or recent first-seen (≤ 3 days)
    #   - AND event is upcoming (today through next 14 days)
    if _is_trending(event):
        highlights.append("trending")

    # "Just Added" — first seen within last 30 hours
    first_seen = event.get("firstSeenAt", "")
    if first_seen:
        try:
            from datetime import datetime, timedelta

            fs = datetime.fromisoformat(first_seen)
            if (datetime.now() - fs) < timedelta(hours=30):
                highlights.append("new")
        except Exception:
            pass

    if event.get("price") == "free":
        highlights.append("free")

    # Special / time-limited
    if any(
        kw in text
        for kw in ["opening night", "premiere", "launch party", "first look", "preview"]
    ):
        highlights.append("special")
    if any(kw in text for kw in ["festival", "block party", "street fair"]):
        highlights.append("festival")
    if any(
        kw in text
        for kw in [
            "meet new people",
            "make new friends",
            "singles",
            "speed dating",
            "social mixer",
            "icebreaker",
        ]
    ):
        highlights.append("meet-people")
    if any(kw in text for kw in ["rooftop", "harbor cruise", "boat party", "sunset"]):
        highlights.append("vibes")
    if any(kw in text for kw in ["live jazz", "jazz set", "jazz club", "jazz night"]):
        highlights.append("jazz")
    if any(
        kw in text
        for kw in ["dj set", "dj night", "warehouse", "house music", "techno"]
    ):
        highlights.append("nightlife")

    # Williamsburg-local
    neighborhood = (event.get("location", {}).get("neighborhood") or "").lower()
    if neighborhood in ("williamsburg", "greenpoint", "bushwick"):
        highlights.append("nearby")

    return highlights


def _haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Distance in miles between two lat/lng points (haversine)."""
    import math

    R = 3958.8  # Earth radius in miles
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


# User's home neighborhood (Williamsburg). Future: make this configurable
# in scrapers/config.py.
_USER_HOME_LAT = 40.7081
_USER_HOME_LNG = -73.9571


def _distance_proximity_boost(event: dict) -> float:
    """Bonus for events with lat/lng physically close to user's home.
    Stacks with the existing neighborhood-text proximity score and only
    applies when the event has actual coordinates (currently from IG
    geo-tags; future geocoding will expand coverage)."""
    loc = event.get("location") or {}
    lat = loc.get("lat")
    lng = loc.get("lng")
    if lat is None or lng is None:
        return 0.0
    try:
        miles = _haversine_miles(float(lat), float(lng), _USER_HOME_LAT, _USER_HOME_LNG)
    except Exception:
        return 0.0
    if miles <= 1:
        return 0.06  # walking distance
    if miles <= 3:
        return 0.04  # short bike / quick L train
    if miles <= 6:
        return 0.02  # within Brooklyn / lower Manhattan
    if miles >= 15:
        return -0.03  # NJ / outer queens — actually deboost
    return 0.0


def _proximity_score(event: dict) -> float:
    neighborhood = (event.get("location", {}).get("neighborhood") or "").lower()
    if neighborhood in NEIGHBORHOOD_PROXIMITY:
        return NEIGHBORHOOD_PROXIMITY[neighborhood]

    address = (event.get("location", {}).get("address") or "").lower()
    name = (event.get("location", {}).get("name") or "").lower()
    combined = f"{address} {name}"

    for hood, score in NEIGHBORHOOD_PROXIMITY.items():
        if hood in combined:
            return score

    if "brooklyn" in combined or "bk" in combined:
        return 0.7
    if "new york" in combined or "nyc" in combined or "manhattan" in combined:
        return 0.55

    return 0.5


def _category_score(event: dict) -> float:
    preferred = set(USER_INTERESTS["preferred_categories"])
    boost_cats = USER_INTERESTS.get("boost_categories", {})
    event_cats = set(event.get("categories", []))
    if not event_cats:
        return 0.3
    overlap = preferred & event_cats
    if not overlap:
        return 0.15

    # Apply boost multipliers for 20s-30s NYC lifestyle categories
    max_boost = max((boost_cats.get(c, 1.0) for c in overlap), default=1.0)

    n = len(overlap)
    if n == 1:
        base = 0.6
    elif n == 2:
        base = 0.85
    else:
        base = 1.0
    return min(1.0, base * max_boost)


def _price_score(event: dict) -> float:
    price = event.get("price", "unknown")
    if price == "free":
        return 1.0
    if price == "unknown":
        return 0.6
    m = re.search(r"\$(\d+(?:\.\d+)?)", price)
    if m:
        amount = float(m.group(1))
        if amount == 0:
            return 1.0
        if amount <= 20:
            return 0.85
        if amount <= 50:
            return 0.6
        if amount <= 100:
            return 0.4
        return 0.25
    return 0.5


def _popularity_score(event: dict) -> float:
    # IG likes/comments are the strongest popularity signal we have.
    # For Reels, video_views is the dominant signal — a viral Reel can hit
    # 100k+ views with only 1-2k likes, so we fold views into engagement
    # at a discount (1 view ≈ 0.1 like) capped to avoid drowning likes.
    # Attendance signals from comments ("going!", "+5 friends") are highest-
    # quality — they indicate real-people-actually-attending, not passive
    # scrolling. Each attendance hit is worth 50 likes.
    likes = event.get("likes", 0) or 0
    comments = event.get("comments", 0) or 0
    video_views = event.get("video_views", 0) or 0
    attendance = event.get("attendanceSignal", 0) or 0
    view_contribution = min(2000, video_views * 0.1) if video_views else 0
    attendance_contribution = attendance * 50  # one "going!" ≈ 50 likes
    if likes or comments or view_contribution or attendance_contribution:
        engagement = likes + comments * 5 + view_contribution + attendance_contribution
        if engagement >= 5000:
            return 1.0
        if engagement >= 1500:
            return 0.9
        if engagement >= 500:
            return 0.75
        if engagement >= 150:
            return 0.6
        if engagement >= 30:
            return 0.5
        return 0.35

    # Fallback: scrape RSVP / attendance counts from description
    desc = event.get("description", "")
    m = re.search(r"(\d+)\s*(?:going|attending|RSVP|interested)", desc, re.IGNORECASE)
    if m:
        count = int(m.group(1))
        if count >= 1000:
            return 1.0
        if count >= 500:
            return 0.9
        if count >= 100:
            return 0.7
        if count >= 30:
            return 0.5
        return 0.4
    return 0.4


def _source_score(event: dict) -> float:
    source = event.get("source", "")
    return SOURCE_QUALITY.get(source, 0.5)


def _completeness_score(event: dict) -> float:
    score = 0.0
    if event.get("imageUrl"):
        score += 0.35
    if event.get("description") and len(event["description"]) > 30:
        score += 0.3
    if event.get("startTime"):
        score += 0.2
    if event.get("location", {}).get("name"):
        score += 0.15
    return min(1.0, score)
