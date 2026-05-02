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
    signals = quality_signals(event)

    # Caption fragments get nuked entirely
    if signals["is_caption_fragment"]:
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
    high_value_boost = min(0.25, signals["high_value_hits"] * 0.12)
    soft_penalty = min(0.3, signals["soft_penalty_hits"] * 0.12)
    audience_penalty = 0.4 if signals["audience_mismatch"] else 0.0

    base_score = (
        proximity * 0.18
        + category * 0.20
        + price * 0.06
        + popularity * 0.08
        + source * 0.20         # source quality matters a lot — IG is curated
        + completeness * 0.05
        + title_q * 0.10        # punish caption fragments
        + desc_q * 0.05
        + time_q * 0.08         # weekend evening bias
    )

    final = base_score + high_value_boost - soft_penalty - audience_penalty
    return max(0.0, min(1.0, final))


def rank_events(events: list[dict]) -> list[dict]:
    for event in events:
        event["score"] = round(compute_score(event), 3)
    return events


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
