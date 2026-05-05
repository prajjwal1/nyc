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
    social_boost = min(0.20, signals["social_hits"] * 0.10)
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

    # Time relevance: events in the next 14 days get a small boost
    # (people care more about "what to do this weekend" than 2 months out)
    time_relevance = _time_relevance_boost(event)

    final = (
        base_score + high_value_boost + social_boost + saved_boost
        + time_relevance - soft_penalty - audience_penalty
    )
    return max(0.0, min(1.0, final))


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
