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


def _dedup_key(ev: dict) -> str:
    title = ev.get("title", "").lower().strip()
    title_words = "".join(c for c in title if c.isalnum() or c == " ").split()
    title_norm = " ".join(sorted(title_words[:5]))
    d = ev.get("date", "")
    return hashlib.md5(f"{title_norm}:{d}".encode()).hexdigest()


def _merge(a: dict, b: dict) -> dict:
    merged = dict(a)
    if not merged.get("description") and b.get("description"):
        merged["description"] = b["description"]
    if not merged.get("startTime") and b.get("startTime"):
        merged["startTime"] = b["startTime"]
    if not merged.get("imageUrl") and b.get("imageUrl"):
        merged["imageUrl"] = b["imageUrl"]
    loc_a = merged.get("location", {})
    loc_b = b.get("location", {})
    if not loc_a.get("address") and loc_b.get("address"):
        merged["location"]["address"] = loc_b["address"]
    if not loc_a.get("neighborhood") and loc_b.get("neighborhood"):
        merged["location"]["neighborhood"] = loc_b["neighborhood"]
    cats = set(merged.get("categories", []) + b.get("categories", []))
    merged["categories"] = sorted(cats)
    return merged


def filter_future(events: list[dict]) -> list[dict]:
    today = date.today().isoformat()
    return [ev for ev in events if ev.get("date", "") >= today]


def sort_by_date(events: list[dict]) -> list[dict]:
    return sorted(events, key=lambda e: (e.get("date", ""), e.get("startTime", "") or ""))


def process(events: list[dict]) -> list[dict]:
    from .ranking import rank_events
    from .quality import is_blocked

    events = [ev for ev in events if ev.get("title") and ev.get("date")]
    events = filter_future(events)

    # Hard-filter blocked events (kids/utility/services/non-NYC/captions)
    before = len(events)
    events = [ev for ev in events if not is_blocked(ev)]
    blocked = before - len(events)
    if blocked:
        print(f"[normalize] Blocked {blocked} low-quality events")

    events = deduplicate(events)
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
