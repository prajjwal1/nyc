"""Squarespace platform event scraper.

Squarespace event collections expose a public iCal feed at `?format=ical`
(when the site owner hasn't explicitly disabled feeds). This is the
single most reliable cross-Squarespace pattern: rather than parse the
React shell HTML (which never has event data) we hit the iCal feed and
get a fully-structured calendar back.

Same playbook as `bookmanager.py`:
  is_squarespace(html)        — detect Squarespace from HTML fingerprints
  scrape_url_as_squarespace() — try ?format=ical on common paths and parse

Many small NYC venues run on Squarespace: comedy clubs, indie galleries,
artist studios, specialty bookstores, etc. A single platform helper
unlocks all of them at once.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse, urlencode, parse_qsl


# Squarespace embeds these in nearly every site's HTML — distinctive
# enough to fingerprint without false positives.
_SQUARESPACE_FINGERPRINTS = (
    "static.squarespace.com",
    "squarespace.com/universal/",
    "Squarespace.Constants",
    "Static.SQUARESPACE_CONTEXT",
    "X-ServedBy: squarespace.com",
)


def is_squarespace(html: str | None) -> bool:
    """True if HTML looks like a Squarespace-rendered page."""
    if not html or len(html) < 200:
        return False
    return any(fp in html for fp in _SQUARESPACE_FINGERPRINTS)


def ical_candidates(url: str) -> list[str]:
    """Return URL candidates to probe for a Squarespace iCal feed.

    Squarespace exposes iCal at the same path the event collection lives,
    with `format=ical` appended. The collection path varies — common
    patterns: /events, /calendar, /shows, /upcoming. We probe the input
    URL itself first (most common) plus a few canonical fallbacks.
    """
    parsed = urlparse(url)
    if not parsed.netloc:
        return []
    base = f"{parsed.scheme}://{parsed.netloc}"

    def _with_ical(u: str) -> str:
        p = urlparse(u)
        q = dict(parse_qsl(p.query))
        q["format"] = "ical"
        return urlunparse((p.scheme, p.netloc, p.path, p.params, urlencode(q), ""))

    paths = [
        parsed.path or "/events",
        "/events",
        "/calendar",
        "/shows",
        "/upcoming",
        "/upcoming-events",
        "/events/upcoming",
    ]
    seen: set[str] = set()
    out: list[str] = []
    for p in paths:
        full = base + p
        if not p.startswith("/"):
            full = base + "/" + p
        ical_url = _with_ical(full)
        if ical_url not in seen:
            seen.add(ical_url)
            out.append(ical_url)
    return out


async def try_scrape_ical_for_squarespace(
    url: str,
    html: str,
    source_label: str,
) -> list[dict]:
    """If `html` is Squarespace, probe iCal paths and return parsed events.

    Returns [] when:
      - the page isn't Squarespace, OR
      - no iCal feed is accessible, OR
      - the iCal feed parses to zero events.
    """
    if not is_squarespace(html):
        return []
    # Lazy-import to avoid cross-module cycles on module load.
    from ..utils.http import fetch_text
    from ..sources.generic import _parse_ical  # reuse the existing parser

    for cand in ical_candidates(url):
        try:
            text = await fetch_text(cand)
        except Exception:
            continue
        if not text or "BEGIN:VCALENDAR" not in text:
            continue
        try:
            events = _parse_ical(text, source_label, cand)
        except Exception:
            continue
        if events:
            print(f"[squarespace] {url}: iCal at {cand} → {len(events)} events")
            return events
    return []
