import re
from .config import USER_INTERESTS, SOURCE_QUALITY

NEIGHBORHOOD_PROXIMITY = {
    "williamsburg": 1.0,
    "greenpoint": 0.9,
    "bushwick": 0.85,
    "east village": 0.8,
    "lower east side": 0.8,
    "dumbo": 0.75,
    "brooklyn heights": 0.75,
    "fort greene": 0.75,
    "prospect heights": 0.7,
    "park slope": 0.7,
    "soho": 0.65,
    "chelsea": 0.6,
    "midtown": 0.5,
    "upper east side": 0.45,
    "upper west side": 0.45,
    "brooklyn": 0.7,
    "manhattan": 0.55,
}


def compute_score(event: dict) -> float:
    return (
        _proximity_score(event) * 0.25
        + _category_score(event) * 0.25
        + _price_score(event) * 0.15
        + _popularity_score(event) * 0.15
        + _source_score(event) * 0.10
        + _completeness_score(event) * 0.10
    )


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

    return 0.4


def _category_score(event: dict) -> float:
    preferred = set(USER_INTERESTS["preferred_categories"])
    event_cats = set(event.get("categories", []))
    if not event_cats:
        return 0.3
    overlap = preferred & event_cats
    if not overlap:
        return 0.2
    return min(1.0, len(overlap) / 2)


def _price_score(event: dict) -> float:
    price = event.get("price", "unknown")
    if price == "free":
        return 1.0
    if price == "unknown":
        return 0.5
    m = re.search(r"\$(\d+(?:\.\d+)?)", price)
    if m:
        amount = float(m.group(1))
        if amount == 0:
            return 1.0
        if amount <= 20:
            return 0.7
        if amount <= 50:
            return 0.4
        return 0.2
    return 0.5


def _popularity_score(event: dict) -> float:
    desc = event.get("description", "")
    m = re.search(r"(\d+)\s*(?:going|attending|RSVP|interested)", desc, re.IGNORECASE)
    if m:
        count = int(m.group(1))
        if count >= 500:
            return 1.0
        if count >= 100:
            return 0.8
        if count >= 30:
            return 0.6
        return 0.4
    return 0.3


def _source_score(event: dict) -> float:
    source = event.get("source", "")
    return SOURCE_QUALITY.get(source, 0.5)


def _completeness_score(event: dict) -> float:
    score = 0.0
    if event.get("imageUrl"):
        score += 0.3
    if event.get("description") and len(event["description"]) > 20:
        score += 0.3
    if event.get("startTime"):
        score += 0.2
    if event.get("location", {}).get("name"):
        score += 0.2
    return score
