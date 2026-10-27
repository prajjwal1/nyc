"""Bounded public-page trial; use curl's system TLS trust in this environment.

Usage: python description-trial.py SNAPSHOT_JSON OUTPUT_DIR
Production continues to use its existing httpx transport. Raw pages stay in
OUTPUT_DIR; only the summarized results belong in the run report.
"""
import asyncio
import copy
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from scrapers.sources import eventbrite, luma
from scrapers.utils import descriptions


async def main():
    payload = json.loads(Path(sys.argv[1]).read_text())
    output = Path(sys.argv[2])
    output.mkdir(exist_ok=True, parents=True)
    rows = copy.deepcopy(payload["events"])
    captured = {}

    async def fetch(url, timeout=8):
        process = await asyncio.create_subprocess_exec(
            "/usr/bin/curl", "-sS", "--max-time", str(timeout),
            "--write-out", "%{http_code}", url,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await process.communicate()
        except BaseException:
            if process.returncode is None:
                process.kill()
            await process.wait()
            raise
        if process.returncode:
            raise httpx.ConnectError(stderr.decode()[:200])
        status = int(stdout[-3:])
        if not 200 <= status < 300:
            request = httpx.Request("GET", url)
            raise httpx.HTTPStatusError(
                f"HTTP {status}", request=request, response=httpx.Response(status),
            )
        html = stdout[:-3].decode()
        captured[url] = html
        (output / f"detail-{len(captured)}.html").write_text(html)
        return html

    descriptions.fetch_text = fetch
    stats = await descriptions.enrich_descriptions(
        rows, candidates=rows, today=datetime.now(ZoneInfo("America/New_York")).date(),
    )
    changed = []
    for before, after in zip(payload["events"], rows):
        if before.get("description") == after.get("description"):
            continue
        assert {**before, "description": after["description"]} == after
        key = descriptions._event_key(after)
        matched_html = next(
            html for url, html in captured.items()
            if descriptions._event_key({**after, "sourceUrl": url}) == key
        )
        parser = luma._parse_luma_page if after["source"] == "luma" else eventbrite._parse_search_page
        strict_before = any(
            descriptions._event_key(detail) == key
            and len(descriptions._description(detail)) >= descriptions.MIN_DESCRIPTION_LENGTH
            for detail in parser(matched_html, after["sourceUrl"])
        )
        changed.append({
            "id": after["id"], "title": after["title"], "date": after["date"],
            "sourceUrl": after["sourceUrl"], "description": after["description"],
            "newSeriesRecovery": not strict_before,
        })
    result = {
        "stats": stats, "changed": changed,
        "strictMatchesOnSamePages": sum(not row["newSeriesRecovery"] for row in changed),
        "additionalSeriesMatches": sum(row["newSeriesRecovery"] for row in changed),
    }
    (output / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    payload["events"] = rows
    (output / "enriched-feed.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(result, indent=2))


asyncio.run(main())
