"""Sanity-check the scraped events.

Verifies that we're getting events from key sources we expect to see.
Returns non-zero exit code if critical sources are missing.
"""
import json
import os
import sys


# Sources we MUST have events from. If any of these return 0 events, fail.
# Each entry is (name, predicate function, min_count).
CRITICAL_CHECKS = [
    (
        "NYC Backgammon Club",
        lambda e: "backgammon" in e["title"].lower()
        or "backgammon" in e.get("sourceUrl", "").lower(),
        1,
    ),
    (
        "Reading Rhythms",
        lambda e: "reading rhythms" in e.get("title", "").lower()
        or "reading rhythms" in e.get("sourceUrl", "").lower(),
        1,
    ),
    (
        "Live music events",
        lambda e: "music" in e.get("categories", []),
        15,
    ),
    (
        "Williamsburg / Greenpoint / Bushwick events",
        lambda e: e.get("location", {}).get("neighborhood")
        in ("williamsburg", "greenpoint", "bushwick"),
        3,
    ),
    (
        "Free events",
        lambda e: e.get("price") == "free",
        20,
    ),
    (
        "Instagram is dominant source",
        lambda e: e.get("source") == "instagram",
        50,
    ),
]

# Sources we'd LIKE to have, but won't fail without.
WARNING_CHECKS = [
    (
        "Book Club Bar (via @bookclubbar)",
        lambda e: "book club bar" in (
            e.get("title", "").lower()
            + e.get("description", "").lower()
            + e.get("location", {}).get("name", "").lower()
        ),
        1,
    ),
    (
        "Brooklyn Museum events",
        lambda e: "brooklyn museum" in e.get("location", {}).get("name", "").lower()
        or "@brooklynmuseum" in e.get("description", "").lower()
        or "brooklynmuseum" in e.get("sourceUrl", "").lower(),
        1,
    ),
    (
        "Smorgasburg",
        lambda e: "smorgasburg" in e["title"].lower()
        + e.get("description", "").lower(),
        1,
    ),
    (
        "Singles / dating events",
        lambda e: "singles" in e.get("categories", []) or any(
            kw in e["title"].lower() for kw in ["singles", "speed dating", "matchmaking", "date my friend"]
        ),
        1,
    ),
    (
        "Comedy events",
        lambda e: "comedy" in e.get("categories", []),
        3,
    ),
    (
        "Run clubs / fitness",
        lambda e: "fitness" in e.get("categories", []),
        1,
    ),
    (
        "Art openings / first saturday",
        lambda e: "first saturday" in e["title"].lower()
        or "art opening" in e["title"].lower()
        or "exhibition opening" in e["title"].lower(),
        1,
    ),
    (
        "Elsewhere / Brooklyn Bowl / Music Hall venues",
        lambda e: any(
            kw in e["title"].lower() + e.get("location", {}).get("name", "").lower()
            for kw in ["elsewhere", "brooklyn bowl", "music hall", "rough trade", "sawdust"]
        ),
        1,
    ),
]


def main(events_path: str = "data/events.json", *, write_stats: bool = False, hard_fail: bool = False) -> int:
    if not os.path.isfile(events_path):
        print(f"ERROR: {events_path} not found")
        return 1

    with open(events_path) as f:
        data = json.load(f)
    events = data["events"]

    print(f"\n=== SANITY CHECK on {events_path} ===")
    print(f"Total events: {len(events)}\n")

    # Source breakdown
    sources = {}
    for e in events:
        sources[e["source"]] = sources.get(e["source"], 0) + 1
    print("By source:")
    for s, c in sorted(sources.items(), key=lambda x: -x[1]):
        print(f"  {s}: {c}")

    # Category breakdown
    cats = {}
    for e in events:
        for c in e.get("categories", []):
            cats[c] = cats.get(c, 0) + 1
    print("\nBy category:")
    for c, n in sorted(cats.items(), key=lambda x: -x[1])[:15]:
        print(f"  {c}: {n}")

    # Run checks
    print("\n--- CRITICAL CHECKS ---")
    failures = []
    critical_results = []
    for name, check, min_count in CRITICAL_CHECKS:
        matching = [e for e in events if check(e)]
        ok = len(matching) >= min_count
        symbol = "✓" if ok else "✗"
        print(f"  {symbol} {name}: {len(matching)} events (need {min_count}+)")
        critical_results.append({"name": name, "count": len(matching), "min": min_count, "ok": ok})
        if not ok:
            failures.append(name)

    print("\n--- WARNING CHECKS ---")
    warnings = []
    for name, check, min_count in WARNING_CHECKS:
        matching = [e for e in events if check(e)]
        ok = len(matching) >= min_count
        symbol = "✓" if ok else "⚠"
        print(f"  {symbol} {name}: {len(matching)} events")
        if not ok:
            warnings.append(name)
        elif matching and len(matching) <= 3:
            for e in matching[:2]:
                print(f"      - {e['title'][:60]} ({e['source']})")

    # Top events spot-check
    print("\n--- TOP 10 EVENTS BY SCORE ---")
    top = sorted(events, key=lambda e: e.get("score", 0), reverse=True)[:10]
    for e in top:
        cats_s = ",".join(e.get("categories", [])[:3])
        print(f"  [{e['score']}] {e['title'][:60]} | {e['source']} | {cats_s}")

    _print_ig_diagnostics(events)

    # Freshness
    last_updated = data.get("lastUpdated", "")
    age_hours = None
    if last_updated:
        try:
            from datetime import datetime as _dt
            ts = _dt.fromisoformat(last_updated.replace("Z", "+00:00"))
            now = _dt.now(ts.tzinfo) if ts.tzinfo else _dt.now()
            age_hours = (now - ts).total_seconds() / 3600
            print(f"\nFreshness: lastUpdated {age_hours:.1f}h ago")
        except Exception:
            pass

    # Summary
    print(f"\n=== SUMMARY ===")
    print(f"Critical failures: {len(failures)}")
    print(f"Warnings: {len(warnings)}")
    if failures:
        print(f"\nMUST FIX: {', '.join(failures)}")
    if warnings:
        print(f"Could improve: {', '.join(warnings)}")

    # Write stats history (append-only) — useful for regression tracking
    if write_stats:
        _append_stats(
            total=len(events),
            sources=sources,
            cats=dict(cats),
            failures=failures,
            warnings=warnings,
            age_hours=age_hours,
        )

    return 1 if (hard_fail and failures) else 0


def _print_ig_diagnostics(events: list) -> None:
    """Print per-account IG yield, silenced top-yield accounts, dead-account
    growth, discovered_via distribution, and session age.

    Print-only — no failure thresholds. Surfaces low-yield/broken-scrape
    states immediately in the run log.
    """
    from collections import Counter
    from datetime import datetime, timedelta, timezone

    print("\n--- INSTAGRAM YIELD DIAGNOSTICS ---")

    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

    ig_events = [e for e in events if e.get("source") == "instagram"]
    print(f"Total IG events in feed: {len(ig_events)}")

    per_acct: Counter = Counter()
    for e in ig_events:
        acct = (e.get("instagramAccount") or "").lower()
        if acct:
            per_acct[acct] += 1
    if per_acct:
        print("Top accounts in current feed:")
        for acct, n in per_acct.most_common(15):
            print(f"  @{acct}: {n}")
    else:
        print("(no IG events in current feed)")

    # Silenced high-yield accounts — lifetime yield >= 0.5 but 0 in this feed
    quality_path = os.path.join(data_dir, "account_quality.json")
    silenced: list[tuple[str, float, int]] = []
    if os.path.isfile(quality_path):
        try:
            with open(quality_path) as f:
                quality = json.load(f)
            for acct, info in quality.items():
                if not isinstance(info, dict):
                    continue
                posts = info.get("posts_scraped", 0) or 0
                ev = info.get("events_emitted", 0) or 0
                if posts < 10:
                    continue
                y = ev / posts
                if y >= 0.5 and per_acct.get(acct.lower(), 0) == 0:
                    silenced.append((acct, y, ev))
            silenced.sort(key=lambda t: -t[1])
        except Exception as exc:
            print(f"(account_quality.json read failed: {exc})")
    if silenced:
        print(f"\nSilenced high-yield accounts (lifetime yield ≥0.5, 0 in this feed): {len(silenced)}")
        for acct, y, ev in silenced[:10]:
            print(f"  @{acct} yield={y:.2f} lifetime_events={ev}")

    # Newly-dead accounts in last 7 days
    dead_path = os.path.join(data_dir, "dead_accounts.json")
    if os.path.isfile(dead_path):
        try:
            with open(dead_path) as f:
                dead = json.load(f)
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            recent_dead = []
            for acct, info in (dead.get("accounts", {}) or {}).items():
                since = info.get("since") or info.get("dead_at")
                if not since:
                    continue
                try:
                    ts = datetime.fromisoformat(since.replace("Z", "+00:00"))
                    if ts >= cutoff:
                        recent_dead.append((acct, info.get("reason", "unknown")))
                except Exception:
                    continue
            print(f"\nNewly-dead accounts in last 7 days: {len(recent_dead)}")
            if len(recent_dead) > 30:
                print("  WARNING: sudden dead-account growth — possible session expiry or IG API change")
            for acct, reason in recent_dead[:8]:
                print(f"  @{acct} ({reason})")
        except Exception as exc:
            print(f"(dead_accounts.json read failed: {exc})")

    # discovered_via distribution — proves suggested-for-you sweep ran
    disc_path = os.path.join(data_dir, "discovered_accounts.json")
    if os.path.isfile(disc_path):
        try:
            with open(disc_path) as f:
                disc = json.load(f)
            via: Counter = Counter()
            sugg_seeds: Counter = Counter()
            for entry in disc.get("accounts", []):
                v = entry.get("discovered_via", "")
                if v.startswith("suggested_for:"):
                    via["suggested_for"] += 1
                    sugg_seeds[v.split(":", 1)[1]] += 1
                elif v == "user_following":
                    via["user_following"] += 1
                else:
                    via["other"] += 1
            print(f"\nDiscovered accounts ({sum(via.values())} total):")
            for k, n in via.most_common():
                print(f"  {k}: {n}")
            if via.get("suggested_for", 0) == 0:
                print("  WARNING: 0 suggested_for entries — run scrapers.run_discovery to populate")
        except Exception as exc:
            print(f"(discovered_accounts.json read failed: {exc})")

    # Session age — instaloader sessions practically die at ~25-30 days.
    # The mass-kill on 2026-05-24 (54 accounts) traced to feedback_required
    # errors that started while the session was 23+ days old, so the 30-day
    # bar was too lenient. Flag at 25 (warn), 28 (critical).
    try:
        from .config import IG_SESSION_FILE
        if os.path.isfile(IG_SESSION_FILE):
            age_days = (datetime.now().timestamp() - os.stat(IG_SESSION_FILE).st_mtime) / 86400
            if age_days >= 28:
                flag = " ⛔ CRITICAL — refresh now (run: instaloader --login <username>)"
            elif age_days >= 25:
                flag = " ⚠ STALE — refresh soon"
            else:
                flag = ""
            print(f"\nIG session age: {age_days:.1f} days{flag}")
        else:
            print(f"\nIG session file MISSING at {IG_SESSION_FILE}")
    except Exception:
        pass


def _append_stats(*, total, sources, cats, failures, warnings, age_hours):
    """Append a one-line snapshot to scrapers/data/stats_history.jsonl.

    Useful for debugging regressions over time.
    """
    from datetime import datetime, timezone
    path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "data",
        "stats_history.jsonl",
    )
    os.makedirs(os.path.dirname(path), exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": total,
        "sources": sources,
        "category_counts": cats,
        "critical_failures": failures,
        "warnings": warnings,
        "age_hours": age_hours,
    }
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default="data/events.json")
    parser.add_argument("--write-stats", action="store_true", help="Append to stats_history.jsonl")
    parser.add_argument("--hard-fail", action="store_true", help="Exit non-zero on critical failures")
    args = parser.parse_args()
    sys.exit(main(args.path, write_stats=args.write_stats, hard_fail=args.hard_fail))
