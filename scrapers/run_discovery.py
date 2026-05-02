"""Standalone orchestration script: run Instagram BFS discovery once.

This is intended to be invoked on a less-frequent schedule (e.g. a daily
GitHub Actions job) than the main ``run_all.py`` scrape, since profile
fetches are expensive and rate-limited by Instagram.

Usage:
    python -m scrapers.run_discovery
or:
    python scrapers/run_discovery.py
"""

import asyncio
import os
import sys

# Allow running as a top-level script as well as a module.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.discover import run_discovery


async def main() -> None:
    accounts = await run_discovery()
    print(f"[run_discovery] Done. {len(accounts)} accounts available for scraping.")


if __name__ == "__main__":
    asyncio.run(main())
