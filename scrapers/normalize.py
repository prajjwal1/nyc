import hashlib
from datetime import date, datetime


def deduplicate(events: list[dict]) -> list[dict]:
    seen = {}
    for ev in events:
        key = _dedup_key(ev)
        if key not in seen:
            seen[key] = ev
        else:
            existing = seen[key]
            seen[key] = _merge(existing, ev)
    return list(seen.values())


_STOPWORDS = {
    "a", "an", "the", "at", "in", "on", "of", "for", "with", "to", "and",
    "or", "is", "are", "by", "from", "this", "that", "your", "our", "my",
    "presents", "presented", "live", "show", "event", "ticket", "tickets",
    "free", "nyc", "ny", "new", "york", "brooklyn", "manhattan",
}


def _dedup_key(ev: dict) -> str:
    """Build a normalized key for dedup.

    - Lowercase, alphanumeric only
    - Drop stopwords (so 'a night at the moma' = 'night moma')
    - Take first 6 distinctive words, sorted
    - Combine with date
    """
    title = ev.get("title", "").lower().strip()
    title_clean = "".join(c if c.isalnum() or c == " " else " " for c in title)
    words = title_clean.split()
    distinctive = [w for w in words if w not in _STOPWORDS and len(w) > 1][:6]
    title_norm = " ".join(sorted(distinctive))
    d = ev.get("date", "")
    return hashlib.md5(f"{title_norm}:{d}".encode()).hexdigest()


def _merge(a: dict, b: dict) -> dict:
    """Merge duplicate events, taking the best fields from both."""
    merged = dict(a)

    # Prefer the longer description
    if (b.get("description") or "") > (merged.get("description") or ""):
        merged["description"] = b["description"]

    # Prefer specific time over none
    if not merged.get("startTime") and b.get("startTime"):
        merged["startTime"] = b["startTime"]
    if not merged.get("endTime") and b.get("endTime"):
        merged["endTime"] = b["endTime"]

    # Prefer non-empty image
    if not merged.get("imageUrl") and b.get("imageUrl"):
        merged["imageUrl"] = b["imageUrl"]

    # Merge location fields
    loc_a = merged.get("location", {})
    loc_b = b.get("location", {})
    if not loc_a.get("name") and loc_b.get("name"):
        merged["location"]["name"] = loc_b["name"]
    if not loc_a.get("address") and loc_b.get("address"):
        merged["location"]["address"] = loc_b["address"]
    if not loc_a.get("neighborhood") and loc_b.get("neighborhood"):
        merged["location"]["neighborhood"] = loc_b["neighborhood"]

    # Union of categories
    cats = set(merged.get("categories", []) + b.get("categories", []))
    if "other" in cats and len(cats) > 1:
        cats.discard("other")
    merged["categories"] = sorted(cats)

    # Preserve user signals from either side
    merged["userSaved"] = bool(a.get("userSaved") or b.get("userSaved"))
    merged["recurring"] = bool(a.get("recurring") or b.get("recurring"))
    merged["ocrEnriched"] = bool(a.get("ocrEnriched") or b.get("ocrEnriched"))

    # Prefer real ticket URL over IG post URL
    a_url = merged.get("sourceUrl", "")
    b_url = b.get("sourceUrl", "")
    if "instagram.com/p/" in a_url and "instagram.com/p/" not in b_url and b_url:
        merged["sourceUrl"] = b_url

    # Engagement: take the higher count
    merged["likes"] = max(a.get("likes", 0) or 0, b.get("likes", 0) or 0)
    merged["comments"] = max(a.get("comments", 0) or 0, b.get("comments", 0) or 0)

    return merged


def filter_future(events: list[dict]) -> list[dict]:
    today = date.today().isoformat()
    return [ev for ev in events if ev.get("date", "") >= today]


def sort_by_date(events: list[dict]) -> list[dict]:
    return sorted(events, key=lambda e: (e.get("date", ""), e.get("startTime", "") or ""))


def _load_previous_events_index(path: str) -> dict:
    """Load previous events.json keyed by event id, for firstSeenAt preservation."""
    import json, os
    if not os.path.isfile(path):
        return {}
    try:
        with open(path) as f:
            d = json.load(f)
        return {e["id"]: e for e in d.get("events", []) if "id" in e}
    except Exception:
        return {}


def process(events: list[dict], previous_index: dict | None = None) -> list[dict]:
    from .ranking import rank_events
    from .quality import is_blocked
    from .utils.event_parser import detect_recurring_weekday, expand_recurring_event

    events = [ev for ev in events if ev.get("title") and ev.get("date")]
    events = filter_future(events)

    # Hard-filter blocked events (kids/utility/services/non-NYC/captions)
    before = len(events)
    events = [ev for ev in events if not is_blocked(ev)]
    blocked = before - len(events)
    if blocked:
        print(f"[normalize] Blocked {blocked} low-quality events")

    # Expand recurring events ("every Saturday at Smorgasburg" → 6 weeks of dates)
    expanded: list[dict] = []
    recurring_count = 0
    for ev in events:
        text = (ev.get("title", "") + " " + ev.get("description", "")).lower()
        weekday = detect_recurring_weekday(text)
        if weekday is not None:
            occurrences = expand_recurring_event(ev, weekday, weeks_ahead=6)
            expanded.extend(occurrences)
            recurring_count += 1
        else:
            expanded.append(ev)
    if recurring_count:
        print(f"[normalize] Expanded {recurring_count} recurring events into {len(expanded) - len(events) + recurring_count} total occurrences")
    events = expanded

    events = deduplicate(events)

    # Preserve firstSeenAt across runs — if an event existed in the previous
    # events.json, carry its original firstSeenAt forward; otherwise stamp now.
    if previous_index is None:
        previous_index = {}
    now_iso = datetime.now().isoformat()
    for ev in events:
        prev = previous_index.get(ev.get("id"))
        if prev and prev.get("firstSeenAt"):
            ev["firstSeenAt"] = prev["firstSeenAt"]
        else:
            ev["firstSeenAt"] = now_iso

    events = rank_events(events)

    # Drop low-score events — every event must justify its position
    MIN_SCORE = 0.5
    before = len(events)
    events = [ev for ev in events if ev.get("score", 0) >= MIN_SCORE]
    dropped = before - len(events)
    if dropped:
        print(f"[normalize] Dropped {dropped} low-score events (below {MIN_SCORE})")

    events = sort_by_date(events)
    return events
