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
    # Social events are the user's primary goal (meet people, not just attend).
    # Bumped cap from 0.20 → 0.28 to push singles/mixers/social events to top.
    social_boost = min(0.28, signals["social_hits"] * 0.12)
    # "Meet-people tier": 2+ social signals AND event is in the next 21 days.
    # Immediacy matters for social events — a singles mixer next month is much
    # less useful than one this week.
    meet_people_boost = _meet_people_tier_boost(event, signals)
    soft_penalty = min(0.4, signals["soft_penalty_hits"] * 0.15)
    audience_penalty = 0.5 if signals["audience_mismatch"] else 0.0

    # Strict baseline weighted average — every signal must pull its weight
    base_score = (
        proximity * 0.16
        + category * 0.22       # interests are critical
        + price * 0.04
        + popularity * 0.07
        + source * 0.20         # IG is curated
        + completeness * 0.06
        + title_q * 0.12        # punish caption fragments
        + desc_q * 0.05
        + time_q * 0.08
    )

    # User-saved posts get a major boost — explicit bookmark is highest signal
    saved_boost = 0.25 if event.get("userSaved") else 0.0

    # User-tagged: someone tagged the user — implicit invitation
    tagged_boost = 0.20 if event.get("userTagged") and not event.get("userSaved") else 0.0

    # User-affinity: events from accounts user has saved from in the past
    affinity_boost = 0.10 if event.get("userAffinity") and not (event.get("userSaved") or event.get("userTagged")) else 0.0

    # User-following: account user directly follows on IG (manual choice).
    # Even if they haven't saved, the user actively chose to follow.
    following_boost = 0.08 if event.get("userFollowing") and not (
        event.get("userSaved") or event.get("userTagged") or event.get("userAffinity")
    ) else 0.0

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
    # Hot boost: cross-source AND firstSeenAt within last 7 days = trending
    hot_boost = _hot_event_boost(event)
    # Account-yield boost: IG accounts that consistently produce events
    yield_boost = _account_yield_boost(event)

    # Account-level credibility: verified or large follower count = trustworthy
    cred_boost = _account_credibility_boost(event)

    # Time relevance: events in the next 14 days get a small boost
    # (people care more about "what to do this weekend" than 2 months out)
    time_relevance = _time_relevance_boost(event)
    # Day-of-week fit: parties on Fri/Sat, fitness on weekdays, etc.
    dow_fit = _day_of_week_fit_boost(event)
    # Time-of-day fit: evening events boosted (working-professional bias).
    tod_fit = _time_of_day_fit_boost(event)

    final = (
        base_score + high_value_boost + social_boost + meet_people_boost
        + saved_boost + tagged_boost + affinity_boost + following_boost
        + cred_boost + cross_source_boost + hot_boost + yield_boost
        + time_relevance + dow_fit + tod_fit
        - soft_penalty - audience_penalty
    )
    return max(0.0, min(1.0, final))


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
    is_fitness_morning = (
        6 <= h <= 9 and bool(cats & {"fitness", "wellness", "outdoors"})
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
    if cats & {"parties", "singles"} or any(k in text for k in ("dj", "dance party", "nightlife", "rooftop")):
        if is_fri_sat:
            boost += 0.05
        elif weekday in (0, 1, 2):  # Mon/Tue/Wed
            boost -= 0.03
    # Live music: Thu/Fri/Sat
    if "music" in cats or any(k in text for k in ("concert", "live music", "live band")):
        if weekday in (3, 4, 5):
            boost += 0.04
    # Fitness / run clubs: weekdays preferred (people work-out before/after work)
    if cats & {"fitness", "wellness"} or any(k in text for k in ("run club", "yoga", "workout")):
        if not is_weekend:
            boost += 0.03
    # Brunch / food on weekends
    if "food" in cats and any(k in text for k in ("brunch", "morning", "breakfast")):
        if is_weekend:
            boost += 0.03
    return max(-0.05, min(0.06, boost))


def _time_relevance_boost(event: dict) -> float:
    """Small boost for events happening soon (within next 14 days)."""
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
    if days_out <= 1:
        return 0.06   # today / tomorrow
    if days_out <= 4:
        return 0.04   # this week-ish
    if days_out <= 7:
        return 0.03   # next 7 days
    if days_out <= 14:
        return 0.015  # next 2 weeks
    return 0.0


def rank_events(events: list[dict]) -> list[dict]:
    for event in events:
        event["score"] = round(compute_score(event), 3)
        event["highlights"] = _compute_highlights(event)
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
    if any(kw in text for kw in ["opening night", "premiere", "launch party", "first look", "preview"]):
        highlights.append("special")
    if any(kw in text for kw in ["festival", "block party", "street fair"]):
        highlights.append("festival")
    if any(kw in text for kw in ["meet new people", "make new friends", "singles", "speed dating", "social mixer", "icebreaker"]):
        highlights.append("meet-people")
    if any(kw in text for kw in ["rooftop", "harbor cruise", "boat party", "sunset"]):
        highlights.append("vibes")
    if any(kw in text for kw in ["live jazz", "jazz set", "jazz club", "jazz night"]):
        highlights.append("jazz")
    if any(kw in text for kw in ["dj set", "dj night", "warehouse", "house music", "techno"]):
        highlights.append("nightlife")

    # Williamsburg-local
    neighborhood = (event.get("location", {}).get("neighborhood") or "").lower()
    if neighborhood in ("williamsburg", "greenpoint", "bushwick"):
        highlights.append("nearby")

    return highlights


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
    # IG likes/comments are the strongest popularity signal we have
    likes = event.get("likes", 0) or 0
    comments = event.get("comments", 0) or 0
    if likes or comments:
        # Combine engagement: likes + 5*comments (comments require more effort)
        engagement = likes + comments * 5
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
