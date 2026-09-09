"""Bounded discovery of recurring NYC events published in Instagram bios."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path

from ..config import IG_ACCOUNTS
from ..utils.http import fetch_text
from ..utils.recurring_profiles import (
    SNAPSHOT_PATH,
    cancellation_dates_from_snapshot,
    events_from_state,
    health,
    load_state,
    parse_profile_html,
    save_state,
    update_profile_state,
)
from ..utils.user_excluded import load_excluded_account_set


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "scrapers" / "data"
DISCOVERED_PATH = DATA_DIR / "discovered_accounts.json"
_LAST_HEALTH: dict = {}


def _discovered_accounts() -> list[dict]:
    try:
        rows = json.loads(DISCOVERED_PATH.read_text()).get("accounts", [])
    except Exception:
        return []
    return [row for row in rows if isinstance(row, dict) and row.get("username")]


def _candidate_plan(
    state: dict, *, limit: int, include_new: bool = True
) -> tuple[list[tuple[str, str]], int]:
    """Prioritize due active profiles, then rotate across the discovery pool."""
    excluded = load_excluded_account_set()
    now = datetime.now(timezone.utc)
    due: list[tuple[str, str]] = []
    for username, entry in (state.get("profiles") or {}).items():
        if username in excluded or not isinstance(entry, dict) or not entry.get("active"):
            continue
        try:
            checked = datetime.fromisoformat(str(entry.get("lastCheckedAt") or "").replace("Z", "+00:00"))
            is_due = now - checked.astimezone(timezone.utc) >= timedelta(hours=24)
        except Exception:
            is_due = True
        if is_due:
            due.append((username, str(entry.get("discoveredVia") or "active_schedule")))

    discovered = _discovered_accounts()
    origin_by_account = {
        str(row["username"]).lower(): str(row.get("discovered_via") or "discovered")
        for row in discovered
        if str(row["username"]).lower() not in excluded
    }
    score_by_account = {
        str(row["username"]).lower(): float(row.get("score") or 0)
        for row in discovered
        if str(row["username"]).lower() not in excluded
    }
    follower_by_account = {
        str(row["username"]).lower(): int(row.get("followers") or 0)
        for row in discovered
        if str(row["username"]).lower() not in excluded
    }
    schedule_hint_accounts = {
        str(row["username"]).lower()
        for row in discovered
        if row.get("bio_schedule") and str(row["username"]).lower() not in excluded
    }
    for account in IG_ACCOUNTS:
        origin_by_account.setdefault(account.lower(), "curated")
        score_by_account.setdefault(account.lower(), 0.5)
        follower_by_account.setdefault(account.lower(), 0)

    def priority(account: str) -> tuple:
        via = origin_by_account[account].lower()
        tier = (
            0 if "user_mentioned" in via else
            1 if any(token in via for token in ("user_following", "user_saved", "user_tagged")) else
            2 if any(token in via for token in ("suggested_for", "mentioned", "tagged")) else
            3
        )
        club_hint = 0 if any(token in account for token in (
            "club", "run", "runners", "reading", "chess", "dance", "walk", "yoga", "collective",
        )) else 1
        bio_schedule = 0 if account in schedule_hint_accounts else 1
        follower_trigger = 0 if follower_by_account.get(account, 0) >= 1_000 else 1
        return (
            bio_schedule, follower_trigger, tier, club_hint,
            -score_by_account.get(account, 0), account,
        )

    pool = sorted(origin_by_account, key=priority) if include_new else []
    due_names = {username for username, _via in due}
    pool = [account for account in pool if account not in due_names]
    cursor = int(state.get("cursor") or 0)
    if pool:
        cursor %= len(pool)
        pool = pool[cursor:] + pool[:cursor]
    remaining = max(0, limit - len(due))
    selected = due[:limit] + [
        (account, origin_by_account[account]) for account in pool[:remaining]
    ]
    next_cursor = (cursor + remaining) % max(1, len(pool))
    return selected, next_cursor


def _snapshot_profiles() -> list[dict]:
    try:
        snapshot = json.loads(SNAPSHOT_PATH.read_text())
    except Exception:
        return []
    out = []
    for profile in snapshot.get("profiles") or []:
        if not isinstance(profile, dict) or not profile.get("username"):
            continue
        out.append({
            "username": str(profile["username"]).lower(),
            "displayName": profile.get("displayName") or profile["username"],
            "biography": profile.get("biography") or "",
            "followers": profile.get("followers") or 0,
            "profileUrl": profile.get("profileUrl") or f"https://www.instagram.com/{profile['username']}/",
            "capturedAt": profile.get("capturedAt") or snapshot.get("generatedAt"),
            "discoveredVia": profile.get("discoveredVia") or "browser_snapshot",
        })
    return out


async def _fetch_profile(username: str) -> dict | None:
    url = f"https://www.instagram.com/{username}/"
    last_error = "profile shell omitted biography"
    for attempt in range(2):
        try:
            document = await fetch_text(
                url,
                timeout=20,
                headers={"Cache-Control": "no-cache"} if attempt else None,
            )
        except Exception as exc:
            last_error = str(exc)
            continue
        profile = parse_profile_html(document, username)
        # Instagram sometimes returns the generic logged-out shell with
        # follower counts but no biography. That is a fetch miss, not evidence
        # that an organizer removed its schedule.
        if profile and str(profile.get("biography") or "").strip():
            return profile
        await asyncio.sleep(0.25)
    print(f"[instagram-bios] @{username} fetch failed: {last_error}")
    return None


async def scrape() -> list[dict]:
    state = load_state()
    discovered_via = {
        str(row["username"]).lower(): str(row.get("discovered_via") or "discovered")
        for row in _discovered_accounts()
    }

    # Browser metadata is first-party evidence captured while the worker is
    # already visiting a profile. Apply it before public-HTML refreshes.
    snapshot_updates = 0
    for profile in _snapshot_profiles():
        username = profile["username"]
        try:
            captured = datetime.fromisoformat(str(profile.get("capturedAt") or "").replace("Z", "+00:00"))
            if captured.tzinfo is None:
                captured = captured.replace(tzinfo=timezone.utc)
        except Exception:
            captured = datetime.now(timezone.utc)
        update_profile_state(
            state,
            profile,
            discovered_via=discovered_via.get(username, profile.get("discoveredVia") or "browser_snapshot"),
            checked_at=captured,
        )
        snapshot_updates += 1

    quick = os.environ.get("IG_SAVED_ONLY", "0") == "1"
    default_limit = 8 if quick else 12
    limit = max(0, int(os.environ.get("IG_BIO_SCAN_LIMIT", default_limit)))
    discover_new = not quick or os.environ.get("IG_BIO_DISCOVERY", "0") == "1"
    plan, next_cursor = _candidate_plan(state, limit=limit, include_new=discover_new)
    sem = asyncio.Semaphore(4)

    async def fetch_one(username: str, via: str):
        async with sem:
            return username, via, await _fetch_profile(username)

    results = await asyncio.gather(*(fetch_one(username, via) for username, via in plan))
    fetched = 0
    qualified = 0
    for username, via, profile in results:
        if not profile:
            continue
        fetched += 1
        entry = update_profile_state(state, profile, discovered_via=via)
        qualified += bool(entry.get("qualified"))
        if entry.get("investigatedByFollowerThreshold"):
            print(
                f"[instagram-bios] investigated @{username} "
                f"({entry.get('followers', 0):,} followers): {entry.get('reason')}"
            )

    state["cursor"] = next_cursor
    save_state(state)
    cancellations = cancellation_dates_from_snapshot()
    events = events_from_state(state, cancellations=cancellations)
    global _LAST_HEALTH
    _LAST_HEALTH = {
        **health(state),
        "plannedProfiles": len(plan),
        "fetchedProfiles": fetched,
        "qualifiedThisRun": qualified,
        "snapshotProfiles": snapshot_updates,
        "generatedEvents": len(events),
    }
    print(
        f"[instagram-bios] {fetched}/{len(plan)} profiles fetched, "
        f"{_LAST_HEALTH['activeSchedules']} active schedules, {len(events)} events"
    )
    return events


def catalog_health() -> dict:
    if _LAST_HEALTH:
        return dict(_LAST_HEALTH)
    return health(load_state())
