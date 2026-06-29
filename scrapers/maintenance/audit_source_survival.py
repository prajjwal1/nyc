"""Audit: does each configured source actually SURVIVE into the feed?

Catches the lu.ma/philosophy class of bug — a source that is configured and
yields events live, but whose events all get filtered out downstream (shell
filter, score floor, dedup) so it contributes 0 to the feed. A live metrics
snapshot can't distinguish "source is dead" from "source is silently
filtered"; this does, by running each source's scraper live and then through
normalize.process(), reporting raw vs survived.

Usage:
    python -m scrapers.maintenance.audit_source_survival            # default set
    python -m scrapers.maintenance.audit_source_survival --all      # incl. slow
    python -m scrapers.maintenance.audit_source_survival luma meetup # named only

Flags:
  ZERO-RAW   : scraper returned nothing live (dead handle / empty / parse break)
  ZERO-SURV  : raw >= 3 but 0 survived normalize (the philosophy class — a
               silent downstream filter is eating the whole source)
  LOW-SURV   : < 25% survived (worth a look)
"""

from __future__ import annotations

import asyncio
import sys

from scrapers import normalize


# Fast, single-or-few-page sources — the ones most prone to the silent-filter
# bug and cheap to probe. The slow/bulk sources (generic, substack,
# eventbrite, instagram) are gated behind --all.
DEFAULT_SOURCES = [
    "luma",
    "meetup",
    "dice",
    "partiful",
    "bookclubbar",
    "lizsbookbar",
    "mcnallyjackson",
    "powerhousearena",
    "centerforfiction",
    "brooklyncomedy",
    "bondandgrace",
    "smorgasburg",
    "brooklyncontra",
    "nycforfree",
    "museums",
    "music_venues",
    "parks",
    "theskint",
]
SLOW_SOURCES = ["generic", "substack", "eventbrite"]


async def _scrape(name: str):
    mod = __import__(f"scrapers.sources.{name}", fromlist=["scrape"])
    res = mod.scrape()
    return await res if asyncio.iscoroutine(res) else res


def _classify(raw: int, surv: int) -> str:
    if raw == 0:
        return "ZERO-RAW"
    if surv == 0 and raw >= 3:
        return "ZERO-SURV"
    if raw >= 4 and surv / raw < 0.25:
        return "LOW-SURV"
    return "ok"


async def main(names: list[str]) -> None:
    print(f"{'source':18s} {'raw':>5s} {'survived':>9s}  flag")
    print("-" * 48)
    flagged = []
    for name in names:
        try:
            raw = await _scrape(name)
        except Exception as e:  # noqa: BLE001
            print(f"{name:18s} {'ERR':>5s} {'-':>9s}  SCRAPE-ERROR: {e}")
            flagged.append((name, "SCRAPE-ERROR"))
            continue
        # process() mutates/needs a list copy; run this source in isolation.
        surv = normalize.process(list(raw)) if raw else []
        flag = _classify(len(raw), len(surv))
        print(
            f"{name:18s} {len(raw):5d} {len(surv):9d}  {flag if flag != 'ok' else ''}"
        )
        if flag != "ok":
            flagged.append((name, flag))
    print("-" * 48)
    if flagged:
        print("FLAGGED:")
        for name, why in flagged:
            print(f"  {name}: {why}")
    else:
        print("All sources survive into the feed.")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opts = {a for a in sys.argv[1:] if a.startswith("--")}
    if args:
        sources = args
    elif "--all" in opts:
        sources = DEFAULT_SOURCES + SLOW_SOURCES
    else:
        sources = DEFAULT_SOURCES
    asyncio.run(main(sources))
