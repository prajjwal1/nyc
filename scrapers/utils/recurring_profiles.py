"""Discover and materialize recurring events from public Instagram profiles.

The useful schedule often lives only in an organizer's bio (for example,
"Mondays @ 7pm" plus a venue line).  This module owns the deterministic,
source-agnostic parts of that pipeline: profile-meta parsing, admission gates,
state persistence, and generation of short-horizon calendar occurrences.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
from html.parser import HTMLParser
import html
import json
import re
from pathlib import Path
from zoneinfo import ZoneInfo

from .event_parser import build_event, infer_categories
from .user_excluded import load_excluded_account_set


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "scrapers" / "data"
STATE_PATH = DATA_DIR / "recurring_instagram_schedules.json"
SNAPSHOT_PATH = DATA_DIR / "instagram_browser_snapshot.json"
NY_TZ = ZoneInfo("America/New_York")
FOLLOWER_INVESTIGATION_THRESHOLD = 1_000
VERIFICATION_TTL_DAYS = 14
OCCURRENCES_AHEAD = 4

_DAY_NAMES = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2, "weds": 2,
    "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}
_DAY = r"monday|mon|tuesday|tue|tues|wednesday|wed|weds|thursday|thu|thur|thurs|friday|fri|saturday|sat|sunday|sun"
_TIME = r"\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)"
_DAY_THEN_TIME_RE = re.compile(
    rf"\b(?P<day>{_DAY})(?:day)?s?\b(?:\s+(?:mornings?|afternoons?|evenings?|nights?))?"
    rf"\s*(?:[-|,:•]\s*)?(?:(?:at|@)\s*)?(?P<clock>{_TIME})",
    re.I,
)
_TIME_THEN_DAY_RE = re.compile(
    rf"\b(?P<clock>{_TIME})\s*(?:[-|,:•]\s*)?(?:on\s+)?(?P<day>{_DAY})(?:day)?s?\b",
    re.I,
)
_LOCATION_LINE_RE = re.compile(
    r"^(?:\s*[📍🗺🏠]\s*|\s*(?:meet(?:ing)?|start|location|at)\s*(?:at|@|:)\s*)(.+)$",
    re.I,
)
_NYC_RE = re.compile(
    r"\b(?:nyc|new york(?: city)?|brooklyn|bk|manhattan|queens|bronx|"
    r"williamsburg|willyb|greenpoint|bushwick|harlem|astoria|ridgewood|"
    r"long island city|lower east side|east village|west village|soho|"
    r"tribeca|park slope|crown heights|bed(?:ford)?[ -]stuy(?:vesant)?)\b",
    re.I,
)
_ORG_RE = re.compile(
    r"\b(?:club|collective|community|society|association|coalition|group|"
    r"meetup|runners?|running|run\s*club|walkers?|walking|book\s*club|"
    r"reading|readers?|writers?|series|chess|backgammon|games?|dance|dancing|"
    r"craft\s+(?:club|collective|circle)|cycling|hiking|volunteer|choir)\b",
    re.I,
)
_USEFUL_RE = re.compile(
    rf"\b(?:{_DAY})s?\b|\b(?:join|meet|rsvp|calendar|schedule|weekly|events?)\b|"
    r"(?:lu\.ma|luma\.com|partiful\.com|eventbrite\.com|linktr\.ee)",
    re.I,
)
_PAUSE_RE = re.compile(
    r"\b(?:on hiatus|season (?:is )?over|paused|no longer meeting|"
    r"runs? (?:are )?cancelled|runs? (?:are )?canceled|closed permanently)\b",
    re.I,
)
_CANCEL_RE = re.compile(
    r"\b(?:no run|run (?:is )?cancelled|run (?:is )?canceled|"
    r"cancelled tonight|canceled tonight|taking this week off|not meeting)\b",
    re.I,
)


class _MetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.description = ""
        self.og_description = ""
        self.og_title = ""

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() != "meta":
            return
        values = {str(key).lower(): value or "" for key, value in attrs}
        if values.get("name", "").lower() == "description":
            self.description = values.get("content", "")
        if values.get("property", "").lower() == "og:description":
            self.og_description = values.get("content", "")
        if values.get("property", "").lower() == "og:title":
            self.og_title = values.get("content", "")


def _parse_count(value: str) -> int:
    value = (value or "").strip().replace(",", "")
    match = re.fullmatch(r"([\d.]+)\s*([kmb])?", value, re.I)
    if not match:
        return 0
    number = float(match.group(1))
    scale = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}.get(
        (match.group(2) or "").lower(), 1
    )
    return int(number * scale)


def parse_profile_html(document: str, expected_username: str = "") -> dict | None:
    """Extract the public profile fields embedded in Instagram meta tags."""
    parser = _MetaParser()
    try:
        parser.feed(document or "")
    except Exception:
        return None
    content = html.unescape(parser.description or "")
    match = re.match(
        r"^\s*([\d.,]+\s*[KMB]?)\s+Followers?.*?\s-\s(.+?)\s+"
        r"\(@([A-Za-z0-9._]+)\)\s+on Instagram:\s*[\"“](.*)[\"”]\s*$",
        content,
        re.I | re.S,
    )
    if match:
        username = match.group(3).lower()
        if expected_username and username != expected_username.lower():
            return None
        return {
            "username": username,
            "displayName": re.sub(r"\s+", " ", match.group(2)).strip(),
            "biography": match.group(4).strip(),
            "followers": _parse_count(match.group(1)),
            "profileUrl": f"https://www.instagram.com/{username}/",
        }

    # Logged-in/rendered variants occasionally omit the rich description.
    title = html.unescape(parser.og_title or "")
    username_match = re.search(r"@([A-Za-z0-9._]+)", title)
    username = (username_match.group(1) if username_match else expected_username).lower()
    if not username:
        return None
    followers_match = re.search(r"([\d.,]+\s*[KMB]?)\s+Followers?", parser.og_description, re.I)
    return {
        "username": username,
        "displayName": re.sub(r"\s*\(@[^)]+\).*", "", title).strip() or username,
        "biography": "",
        "followers": _parse_count(followers_match.group(1)) if followers_match else 0,
        "profileUrl": f"https://www.instagram.com/{username}/",
    }


def _day_index(value: str) -> int | None:
    folded = value.lower().rstrip("s")
    if folded.endswith("day") and folded not in _DAY_NAMES:
        folded = folded[:-3]
    return _DAY_NAMES.get(folded)


def _clock(value: str) -> str | None:
    # Keep the expression local to avoid accepting bare numbers as schedules.
    match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?", value, re.I)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    if not 1 <= hour <= 12 or minute > 59:
        return None
    if match.group(3).lower() == "p" and hour != 12:
        hour += 12
    if match.group(3).lower() == "a" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"


def _clean_location(value: str) -> str:
    value = re.sub(r"^[\s@|,:;\-–—•]+", "", value or "")
    value = re.sub(r"^(?:(?:meet(?:ing)?|start|location)\s*)?(?:at|@|:)\s+", "", value, flags=re.I)
    value = re.sub(r"\s+", " ", value).strip(" .,-–—|")
    if (
        not value
        or re.fullmatch(rf"{_TIME}(?:\s*[-–—]\s*{_TIME})?", value, re.I)
        or ("@" in value and " " not in value)
        or re.search(r"https?://|\S+@\S+\.\S+", value)
    ):
        return ""
    return value[:140]


def extract_schedules(biography: str) -> list[dict]:
    """Parse strict weekday+time schedules and attach a nearby venue line."""
    lines = [re.sub(r"\s+", " ", line).strip() for line in (biography or "").splitlines()]
    lines = [line for line in lines if line]
    location_lines: list[str] = []
    for line in lines:
        match = _LOCATION_LINE_RE.match(line)
        if match:
            location = _clean_location(match.group(1))
            if location:
                location_lines.append(location)

    schedules: list[dict] = []
    seen: set[tuple[int, str, str]] = set()
    for line in lines:
        if re.search(rf"\b(?:{_DAY})(?:day)?s?\s*[-–—]\s*(?:{_DAY})(?:day)?s?\b", line, re.I):
            # Opening-hour ranges ("Thu-Fri 10am-4pm") are not events.
            continue
        for pattern in (_DAY_THEN_TIME_RE, _TIME_THEN_DAY_RE):
            for match in pattern.finditer(line):
                weekday = _day_index(match.group("day"))
                start_time = _clock(match.group("clock"))
                if weekday is None or not start_time:
                    continue
                remainder = _clean_location(line[match.end():])
                location = remainder or (location_lines[0] if location_lines else "")
                key = (weekday, start_time, location.lower())
                if key in seen:
                    continue
                seen.add(key)
                schedules.append({
                    "weekday": weekday,
                    "startTime": start_time,
                    "locationName": location,
                    "evidence": line[:240],
                })
    return schedules


def assess_profile(profile: dict, *, discovered_via: str = "") -> dict:
    """Apply autonomous investigation and publication gates to a profile."""
    username = str(profile.get("username") or "").lower().strip()
    display = str(profile.get("displayName") or username).strip()
    biography = str(profile.get("biography") or "").strip()
    followers = int(profile.get("followers") or 0)
    schedules = extract_schedules(biography)
    combined = f"{display} {username} {biography}"
    collapsed_identity = re.sub(r"[^a-z0-9]", "", f"{display} {username}".lower())
    organization = bool(_ORG_RE.search(combined)) or any(
        token in collapsed_identity
        for token in ("club", "collective", "community", "society", "runners", "running")
    )
    nyc = bool(_NYC_RE.search(combined))
    useful = bool(_USEFUL_RE.search(biography))
    investigated = followers >= FOLLOWER_INVESTIGATION_THRESHOLD and useful
    trusted_origin = any(token in discovered_via.lower() for token in (
        "user_mentioned", "user_following", "user_saved", "curated",
    ))
    strong_smaller_club = organization and nyc and bool(schedules) and trusted_origin
    complete_schedules = [schedule for schedule in schedules if schedule.get("locationName")]
    excluded = username in load_excluded_account_set()
    qualified = bool(
        username and organization and nyc and complete_schedules and not excluded
        and (investigated or strong_smaller_club or followers >= 500)
    )
    confidence = 0.0
    if qualified:
        confidence = 0.94 if followers >= FOLLOWER_INVESTIGATION_THRESHOLD else 0.84
        if trusted_origin:
            confidence = min(0.99, confidence + 0.03)
    reason = "qualified" if qualified else (
        "excluded" if excluded else
        "not_an_organization" if not organization else
        "missing_nyc_evidence" if not nyc else
        "missing_weekday_time" if not schedules else
        "missing_location" if not complete_schedules else
        "below_investigation_threshold"
    )
    return {
        **profile,
        "username": username,
        "displayName": display,
        "biography": biography[:1200],
        "followers": followers,
        "schedules": complete_schedules,
        "investigatedByFollowerThreshold": investigated,
        "qualified": qualified,
        "confidence": round(confidence, 2),
        "reason": reason,
        "discoveredVia": discovered_via or str(profile.get("discoveredVia") or "profile_scan"),
    }


def load_state(path: Path = STATE_PATH) -> dict:
    try:
        state = json.loads(path.read_text())
        if isinstance(state, dict):
            state.setdefault("version", 1)
            state.setdefault("cursor", 0)
            state.setdefault("profiles", {})
            return state
    except Exception:
        pass
    return {"version": 1, "cursor": 0, "profiles": {}}


def save_state(state: dict, path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updatedAt"] = datetime.now(timezone.utc).isoformat()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)


def update_profile_state(
    state: dict,
    profile: dict,
    *,
    discovered_via: str = "",
    checked_at: datetime | None = None,
) -> dict:
    checked_at = checked_at or datetime.now(timezone.utc)
    assessed = assess_profile(profile, discovered_via=discovered_via)
    username = assessed["username"]
    if not username:
        return assessed
    profiles = state.setdefault("profiles", {})
    previous = profiles.get(username, {}) if isinstance(profiles.get(username), dict) else {}
    if (
        not previous
        and not assessed.get("investigatedByFollowerThreshold")
        and not assessed.get("schedules")
    ):
        # The rotation may inspect hundreds of low-signal profiles. Keep the
        # durable registry focused on follower-triggered investigations and
        # schedule-bearing accounts rather than mirroring all of Instagram.
        return assessed
    try:
        previous_checked = datetime.fromisoformat(
            str(previous.get("lastCheckedAt") or "").replace("Z", "+00:00")
        )
        if previous_checked.tzinfo is None:
            previous_checked = previous_checked.replace(tzinfo=timezone.utc)
        observed = checked_at if checked_at.tzinfo else checked_at.replace(tzinfo=timezone.utc)
        if observed.astimezone(timezone.utc) < previous_checked.astimezone(timezone.utc):
            return previous
    except Exception:
        pass
    entry = {
        **previous,
        **assessed,
        "profileUrl": assessed.get("profileUrl") or f"https://www.instagram.com/{username}/",
        "lastCheckedAt": checked_at.isoformat(),
        "bioHash": sha256(assessed.get("biography", "").encode()).hexdigest()[:16],
    }
    if assessed["qualified"]:
        entry["active"] = True
        entry["missingConfirmations"] = 0
        entry["lastVerifiedAt"] = checked_at.isoformat()
    elif previous.get("active"):
        missing = int(previous.get("missingConfirmations") or 0) + 1
        entry["missingConfirmations"] = missing
        entry["active"] = not bool(_PAUSE_RE.search(assessed.get("biography", ""))) and missing < 2
        if entry["active"]:
            entry["schedules"] = previous.get("schedules") or []
            entry["lastVerifiedAt"] = previous.get("lastVerifiedAt")
    else:
        entry["active"] = False
        entry["missingConfirmations"] = int(previous.get("missingConfirmations") or 0)
    profiles[username] = entry
    return entry


def cancellation_dates_from_snapshot(
    snapshot_path: Path = SNAPSHOT_PATH,
) -> set[tuple[str, str]]:
    """Extract explicit near-term cancellations from sanitized browser posts."""
    try:
        posts = json.loads(snapshot_path.read_text()).get("posts", [])
    except Exception:
        return set()
    cancelled: set[tuple[str, str]] = set()
    for post in posts:
        caption = str(post.get("caption") or "")
        if not _CANCEL_RE.search(caption):
            continue
        username = str(post.get("owner") or "").lower()
        try:
            anchor = datetime.fromisoformat(
                str(post.get("takenAt") or post.get("capturedAt") or "").replace("Z", "+00:00")
            ).astimezone(NY_TZ).date()
        except Exception:
            continue
        if re.search(r"\b(?:today|tonight)\b", caption, re.I):
            cancelled.add((username, anchor.isoformat()))
        for day_match in re.finditer(rf"\b(?:this\s+|next\s+)?(?P<day>{_DAY})(?:day)?\b", caption, re.I):
            weekday = _day_index(day_match.group("day"))
            if weekday is None:
                continue
            days = (weekday - anchor.weekday()) % 7
            if day_match.group(0).lower().startswith("next "):
                days = days + 7 if days else 7
            cancelled.add((username, (anchor + timedelta(days=days)).isoformat()))
    return cancelled


def _verified_recently(entry: dict, now: datetime) -> bool:
    try:
        verified = datetime.fromisoformat(str(entry.get("lastVerifiedAt") or "").replace("Z", "+00:00"))
        if verified.tzinfo is None:
            verified = verified.replace(tzinfo=timezone.utc)
        return now.astimezone(timezone.utc) - verified.astimezone(timezone.utc) <= timedelta(days=VERIFICATION_TTL_DAYS)
    except Exception:
        return False


def events_from_state(
    state: dict,
    *,
    now: datetime | None = None,
    cancellations: set[tuple[str, str]] | None = None,
) -> list[dict]:
    now = now.astimezone(NY_TZ) if now else datetime.now(NY_TZ)
    cancellations = cancellations or set()
    events: list[dict] = []
    for username, entry in (state.get("profiles") or {}).items():
        if not isinstance(entry, dict) or not entry.get("active") or not _verified_recently(entry, now):
            continue
        display = str(entry.get("displayName") or username).strip()
        biography = str(entry.get("biography") or "")
        categories = infer_categories(display, biography, ig_account=username)
        if "run" in f"{display} {username} {biography}".lower() and "fitness" not in categories:
            categories.append("fitness")
        title = display
        if "fitness" in categories and "run" not in display.lower():
            title = f"{display} Weekly Run"
        verified_date = str(entry.get("lastVerifiedAt") or "")[:10]
        for schedule in entry.get("schedules") or []:
            weekday = int(schedule.get("weekday"))
            start_time = str(schedule.get("startTime") or "")
            location = str(schedule.get("locationName") or "").strip()
            if not start_time or not location:
                continue
            delta = (weekday - now.weekday()) % 7
            first = now.date() + timedelta(days=delta)
            if delta == 0:
                try:
                    hour, minute = map(int, start_time.split(":"))
                    if now.time() >= time(hour, minute):
                        first += timedelta(days=7)
                except Exception:
                    first += timedelta(days=7)
            recurrence_key = f"instagram:{username}:{weekday}:{start_time}:{location.lower()}"
            for offset in range(OCCURRENCES_AHEAD):
                event_date = first + timedelta(weeks=offset)
                if (username, event_date.isoformat()) in cancellations:
                    continue
                description = (
                    f"{display} meets weekly on {event_date.strftime('%A')} at "
                    f"{datetime.strptime(start_time, '%H:%M').strftime('%-I:%M %p')} at {location}. "
                    f"Schedule verified from the organizer's Instagram bio on {verified_date}; "
                    "check Instagram for changes."
                )
                profile_url = entry.get("profileUrl") or f"https://www.instagram.com/{username}/"
                event = build_event(
                    title=title,
                    description=description,
                    event_date=event_date,
                    start_time=start_time,
                    location_name=location,
                    source="instagram",
                    source_url=profile_url,
                    categories=categories,
                    organizer=display,
                    organizer_url=profile_url,
                    organizer_refs=[{
                        "platform": "instagram", "handle": username,
                        "name": display, "url": profile_url, "role": "host",
                    }],
                )
                event.update({
                    "instagramAccount": username,
                    "account": username,
                    "accountFollowers": int(entry.get("followers") or 0),
                    "recurring": True,
                    "recurrenceKey": recurrence_key,
                    "scheduleSource": "instagram_bio",
                    "scheduleVerifiedAt": entry.get("lastVerifiedAt"),
                    "scheduleConfidence": float(entry.get("confidence") or 0),
                    "discoveryLane": "personal" if any(
                        token in str(entry.get("discoveredVia") or "").lower()
                        for token in ("user_following", "user_mentioned", "user_saved")
                    ) else "explore",
                    "discoveryVia": f"instagram_bio:{entry.get('discoveredVia') or 'profile_scan'}",
                })
                events.append(event)
    return events


def health(state: dict) -> dict:
    profiles = [entry for entry in (state.get("profiles") or {}).values() if isinstance(entry, dict)]
    return {
        "scannedProfiles": len(profiles),
        "followerTriggered": sum(bool(entry.get("investigatedByFollowerThreshold")) for entry in profiles),
        "activeSchedules": sum(bool(entry.get("active")) for entry in profiles),
        "qualifiedProfiles": sum(bool(entry.get("qualified")) for entry in profiles),
    }
