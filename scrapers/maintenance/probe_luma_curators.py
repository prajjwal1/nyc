"""Probe lu.ma/<handle> for every signal_account + curated IG_ACCOUNTS handle.

The Critic's run 2026-05-28-1552 D1 dream proposal (fb-105). Probes one
lu.ma curator-calendar URL per account; if it yields ≥ 3 distinct events
not already in the bare /nyc list, the URL becomes a candidate add to
`LUMA_PAGES` in `scrapers/sources/luma.py`.

Run as a one-off:
    python -m scrapers.maintenance.probe_luma_curators

Output: prints a report and writes proposed additions to
`scrapers/data/luma_curator_candidates.json` so the next /self-improve
run can pick them up.

Hard-rule compliance:
- Read-only against existing `LUMA_PAGES` (no edits in this script).
- No removals proposed.
- All candidates yield ≥ 3 net-new events (event-key not in bare-/nyc set).
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from scrapers.config import IG_ACCOUNTS
from scrapers.sources.luma import LUMA_PAGES, _try_luma_url


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CANDIDATES_OUT = DATA_DIR / "luma_curator_candidates.json"


def _event_key(ev: dict) -> str:
    title = (ev.get("title") or "").strip().lower()[:60]
    date = (ev.get("date") or "").strip()
    return f"{title}|{date}"


def _existing_handles() -> set[str]:
    """Curator handles already covered by LUMA_PAGES."""
    handles: set[str] = set()
    for url in LUMA_PAGES:
        # path-tail after the last "/"
        tail = url.rstrip("/").rsplit("/", 1)[-1]
        if tail and not tail.startswith("nyc"):
            handles.add(tail.lower())
    return handles


def _candidate_handles() -> list[str]:
    """Build the candidate handle list: signal_accounts ∪ IG_ACCOUNTS."""
    profile_path = DATA_DIR / "user_interest_profile.json"
    signal: list[str] = []
    if profile_path.exists():
        try:
            prof = json.loads(profile_path.read_text())
            signal = list(prof.get("signal_accounts", []) or [])
        except Exception:
            signal = []
    pool = sorted(set(h.lower() for h in (list(IG_ACCOUNTS) + signal)))
    covered = _existing_handles()
    return [h for h in pool if h not in covered]


async def _fetch_baseline() -> set[str]:
    """Bare /nyc discover-page event-keys — anything we already get without
    a curator probe."""
    events = await _try_luma_url("https://lu.ma/nyc")
    return {_event_key(e) for e in events}


async def _probe_one(handle: str) -> tuple[int, list[dict]]:
    url = f"https://lu.ma/{handle}"
    try:
        events = await _try_luma_url(url)
    except Exception as exc:
        return -1, [{"error": str(exc)}]
    return len(events), events


async def main(min_yield: int = 3, delay: float = 1.5) -> None:
    candidates = _candidate_handles()
    print(f"[probe] checking {len(candidates)} lu.ma curator handles (sequential, delay={delay}s)")
    baseline = await _fetch_baseline()
    print(f"[probe] baseline /nyc set: {len(baseline)} event-keys")

    additions: list[dict] = []
    skipped_rate_limited = 0

    for i, handle in enumerate(candidates):
        count, events = await _probe_one(handle)
        if count == -1:
            err = events[0].get("error", "") if events else ""
            if "429" in err or "Too Many Requests" in err:
                skipped_rate_limited += 1
            if (i + 1) % 20 == 0:
                print(f"[probe] progress {i+1}/{len(candidates)} (rate-limited so far: {skipped_rate_limited})")
            await asyncio.sleep(delay * 2)  # back off on errors
            continue
        if count <= 0:
            await asyncio.sleep(delay)
            continue
        keys = {_event_key(e) for e in events if isinstance(e, dict)}
        net_new = keys - baseline
        if len(net_new) >= min_yield:
            additions.append({
                "handle": handle,
                "url": f"https://lu.ma/{handle}",
                "yield": count,
                "net_new": len(net_new),
                "sample_titles": [
                    (e.get("title") or "")[:80]
                    for e in events[:3]
                    if isinstance(e, dict)
                ],
            })
            print(f"[probe] ✓ @{handle}: {count} events, {len(net_new)} net-new")
        await asyncio.sleep(delay)

    additions.sort(key=lambda x: -x["net_new"])
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CANDIDATES_OUT.write_text(json.dumps({"candidates": additions}, indent=2))
    print(f"\n[probe] wrote {len(additions)} candidates → {CANDIDATES_OUT}")
    for a in additions[:20]:
        print(f"  - {a['url']} (yield={a['yield']}, net_new={a['net_new']})")


if __name__ == "__main__":
    asyncio.run(main(
        min_yield=int(os.environ.get("LUMA_PROBE_MIN_YIELD", "3")),
        delay=float(os.environ.get("LUMA_PROBE_DELAY", "1.5")),
    ))
