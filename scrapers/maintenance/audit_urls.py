"""Audit every URL in GENERIC_URLS + substack.FEEDS for current health.

Probes each URL, classifies by yield, and prints a report. URLs returning
0 events, all-past-dated events, or 404/5xx errors are flagged as
review candidates. Throughout this session (iter 87, 102, 113, 114),
manual audits found multiple silently-dead feeds + broken pagination.
This script makes that audit reproducible.

Run from the repo root:

    python -m scrapers.maintenance.audit_urls

Output is human-readable. JSON output via `--json` flag for piping into
a follow-up tool. Slow (60+ URLs × ~3s each). The `--limit N` flag
samples the first N URLs for quick iteration.
"""
from __future__ import annotations

import argparse
import asyncio
import json as _json
import sys
import time
from datetime import date as _date
from urllib.parse import urlparse

from scrapers.sources.generic import GENERIC_URLS, scrape_url
from scrapers.sources.substack import FEEDS as SUBSTACK_FEEDS, _parse_feed
from scrapers.utils.http import fetch_text


HEALTHY_FUTURE_FLOOR = 3
WARN_FUTURE_FLOOR = 1


def _classify(yield_count: int, future_count: int, err: str | None) -> str:
    if err:
        return "ERROR"
    if yield_count == 0:
        return "EMPTY"
    if future_count >= HEALTHY_FUTURE_FLOOR:
        return "HEALTHY"
    if future_count >= WARN_FUTURE_FLOOR:
        return "WARN"
    return "STALE"  # has events but all past


async def _audit_generic_url(url: str) -> dict:
    today = str(_date.today())
    try:
        events = await scrape_url(url)
    except Exception as exc:
        return {
            "url": url,
            "kind": "generic",
            "yield": 0,
            "future": 0,
            "err": str(exc)[:120],
            "classification": "ERROR",
        }
    future = [e for e in events if (e.get("date", "") or "") >= today]
    cls = _classify(len(events), len(future), None)
    return {
        "url": url,
        "kind": "generic",
        "yield": len(events),
        "future": len(future),
        "err": None,
        "classification": cls,
    }


async def _audit_substack_feed(url: str) -> dict:
    today = str(_date.today())
    try:
        xml = await fetch_text(url, timeout=30)
    except Exception as exc:
        return {
            "url": url,
            "kind": "substack",
            "yield": 0,
            "future": 0,
            "err": str(exc)[:120],
            "classification": "ERROR",
        }
    try:
        events, _ = _parse_feed(xml)
    except Exception as exc:
        return {
            "url": url,
            "kind": "substack",
            "yield": 0,
            "future": 0,
            "err": str(exc)[:120],
            "classification": "ERROR",
        }
    future = [e for e in events if (e.get("date", "") or "") >= today]
    cls = _classify(len(events), len(future), None)
    return {
        "url": url,
        "kind": "substack",
        "yield": len(events),
        "future": len(future),
        "err": None,
        "classification": cls,
    }


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").replace("www.", "")[:30]
    except Exception:
        return "?"


async def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0, help="audit first N URLs from each list")
    parser.add_argument("--json", action="store_true", help="JSON output (otherwise human-readable)")
    parser.add_argument("--concurrency", type=int, default=4, help="parallel HTTP fetches")
    args = parser.parse_args(argv)

    generic = list(GENERIC_URLS)
    substack = list(SUBSTACK_FEEDS)
    if args.limit:
        generic = generic[: args.limit]
        substack = substack[: args.limit]

    sem = asyncio.Semaphore(args.concurrency)

    async def gated(coro):
        async with sem:
            return await coro

    started = time.monotonic()
    results = await asyncio.gather(
        *(gated(_audit_generic_url(u)) for u in generic),
        *(gated(_audit_substack_feed(u)) for u in substack),
    )
    elapsed = time.monotonic() - started

    if args.json:
        print(_json.dumps({"results": results, "elapsed_seconds": round(elapsed, 1)}, indent=2))
        return 0

    by_class: dict[str, list[dict]] = {}
    for r in results:
        by_class.setdefault(r["classification"], []).append(r)

    print(f"Audited {len(results)} URLs in {elapsed:.1f}s "
          f"(concurrency={args.concurrency})\n")
    for cls in ("HEALTHY", "WARN", "STALE", "EMPTY", "ERROR"):
        rows = by_class.get(cls, [])
        if not rows:
            continue
        print(f"=== {cls} ({len(rows)}) ===")
        rows.sort(key=lambda r: -r["future"])
        for r in rows:
            host = _host(r["url"])
            path = (urlparse(r["url"]).path or "/")[:50]
            tail = f" — {r['err']}" if r.get("err") else ""
            print(f"  yield={r['yield']:3d} future={r['future']:3d}  "
                  f"{host:30s} {path:50s}{tail}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1:])))
