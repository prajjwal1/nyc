"""Bookmanager bookstore event scraper — works for ANY site on Bookmanager.

bookclubbar.com was the first NYC venue we hit that's React-rendered with
no server-side event data — but the React app fetches events from a
hidden Bookmanager API. This module generalizes that pattern so any
bookstore on Bookmanager can be scraped the same way without per-venue
code.

How it works:

  1. The site's public SAN ("site account number") is inlined in the
     events page as `var san="<digits>"`. Extract via regex.
  2. Resolve SAN → internal store_id via:
       GET https://api.bookmanager.com/customer/store/getSettings?webstore_name=<SAN>
  3. Fetch events via:
       POST https://api.bookmanager.com/customer/event/v2/list
       multipart fields:
         session_id  — any 28-char alphanumeric (server doesn't validate)
         store_id    — from step 2
         uuid        — any string
         log_url     — any path
  4. Each row contains:
       title, description (HTML), date (YYYYMMDD), start_time (HH:MM:SS),
       image_url (full CDN URL), location_text (off-site override),
       category (Bookmanager taxonomy), books (linked book metadata)

Public callers:
  is_bookmanager(html)   — detect Bookmanager-powered sites from HTML
  detect_san(html)       — extract the SAN from a Bookmanager site's HTML
  scrape_san(san, source_label, default_venue) — return events for a SAN
"""

from __future__ import annotations

import re
import secrets
import string
from datetime import date as _date
from typing import Optional

import httpx

from .event_parser import build_event, infer_categories


_API_BASE = "https://api.bookmanager.com/customer"
_SETTINGS_URL = f"{_API_BASE}/store/getSettings"
_EVENT_LIST_URL = f"{_API_BASE}/event/v2/list"

_SAN_RE = re.compile(r'\bvar\s+san\s*=\s*["\'](\d{4,9})["\']')
_BM_FINGERPRINTS = (
    "bookmanager.com",
    "cdn1.bookmanager.com",
    "/shop/static/js/",
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_ANON_ALPHA = string.ascii_letters + string.digits

# Memo of resolved store_ids per SAN — bypass the lookup on repeat scrapes.
_STORE_ID_CACHE: dict[str, str] = {}


def is_bookmanager(html: str) -> bool:
    """True if the HTML looks like a Bookmanager-powered React shell."""
    if not html or len(html) < 200:
        return False
    if not _SAN_RE.search(html):
        return False
    return any(fp in html for fp in _BM_FINGERPRINTS)


def detect_san(html: str) -> Optional[str]:
    """Extract the public SAN from a Bookmanager site's HTML, or None."""
    if not html:
        return None
    m = _SAN_RE.search(html)
    return m.group(1) if m else None


def _anon_session_id() -> str:
    return "".join(secrets.choice(_ANON_ALPHA) for _ in range(28))


def _strip_html(html: str) -> str:
    if not html:
        return ""
    text = _HTML_TAG_RE.sub(" ", html)
    text = (
        text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"')
            .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">")
    )
    return _WS_RE.sub(" ", text).strip()


async def _resolve_store_id(client: httpx.AsyncClient, san: str) -> Optional[str]:
    """Look up the internal store_id from a public SAN."""
    cached = _STORE_ID_CACHE.get(san)
    if cached:
        return cached
    try:
        r = await client.get(_SETTINGS_URL, params={"webstore_name": san})
        if r.status_code != 200:
            return None
        data = r.json()
        sid = str(data.get("store_info", {}).get("id") or "")
        if not sid:
            return None
        _STORE_ID_CACHE[san] = sid
        return sid
    except Exception:
        return None


async def _resolve_store_info(client: httpx.AsyncClient, san: str) -> dict:
    """Get full store_info for a SAN (name, address, etc.) — used to
    auto-populate venue names without per-venue config."""
    try:
        r = await client.get(_SETTINGS_URL, params={"webstore_name": san})
        if r.status_code != 200:
            return {}
        data = r.json()
        info = data.get("store_info", {})
        sid = str(info.get("id") or "")
        if sid:
            _STORE_ID_CACHE[san] = sid
        return info
    except Exception:
        return {}


def _row_to_event(row: dict, source_label: str, default_venue: str,
                  default_url_template: Optional[str] = None) -> Optional[dict]:
    """Bookmanager row → normalized event dict."""
    title = (row.get("title") or "").strip()
    if not title:
        return None

    date_str = (row.get("date") or "").strip()
    if not date_str or not date_str.isdigit() or len(date_str) != 8:
        return None
    try:
        event_date = _date(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
    except ValueError:
        return None

    start_time = None
    start_raw = (row.get("start_time") or "").strip()
    if start_raw and ":" in start_raw:
        try:
            hh, mm = start_raw.split(":")[:2]
            start_time = f"{int(hh):02d}:{int(mm):02d}"
        except ValueError:
            pass

    description = _strip_html(row.get("description", ""))
    image_url = (row.get("image_url") or "").strip() or None
    loc_text = (row.get("location_text") or "").strip()
    location_name = loc_text or default_venue

    event_id = row.get("id")
    if default_url_template and event_id:
        source_url = default_url_template.format(event_id=event_id)
    elif event_id:
        # Generic fallback: just use the API URL as the source
        source_url = f"{_EVENT_LIST_URL}#event_id={event_id}"
    else:
        source_url = _EVENT_LIST_URL

    cats = infer_categories(title, description, source=source_label)
    bm_cat = ((row.get("category") or {}).get("name") or "").lower()
    if "book" in bm_cat:
        cats = sorted(set(list(cats) + ["books"]))
    if "music" in bm_cat:
        cats = sorted(set(list(cats) + ["music"]))

    return build_event(
        title=title,
        description=description[:600],
        event_date=event_date,
        start_time=start_time,
        location_name=location_name,
        source=source_label,
        source_url=source_url,
        image_url=image_url,
        categories=cats,
    )


async def scrape_san(
    san: str,
    source_label: str = "bookmanager",
    default_venue: Optional[str] = None,
    public_url_template: Optional[str] = None,
) -> list[dict]:
    """Fetch upcoming events for the bookstore identified by `san`.

    `source_label` distinguishes per-venue events (e.g., "bookclubbar")
    so ranking can apply venue-specific SOURCE_QUALITY weights.

    `public_url_template` overrides the source URL — pass something like
    "https://www.bookclubbar.com/events/{event_id}" to point at the
    venue's own event page instead of the raw API URL.

    `default_venue` defaults to the store name from Bookmanager settings
    when not provided.
    """
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        info = await _resolve_store_info(client, san)
        store_id = _STORE_ID_CACHE.get(san) or str(info.get("id") or "")
        if not store_id:
            print(f"[bookmanager] No store_id for SAN={san}")
            return []
        venue = default_venue or info.get("name", "").strip() or "Bookmanager venue"

        files = {
            "session_id": (None, _anon_session_id()),
            "store_id": (None, store_id),
            "uuid": (None, "nyc-events-bot"),
            "log_url": (None, "/events"),
        }
        try:
            r = await client.post(_EVENT_LIST_URL, files=files)
            data = r.json()
        except Exception as exc:
            print(f"[bookmanager:{source_label}] API call failed: {exc}")
            return []

        rows = data.get("rows") or []
        if not rows:
            err = data.get("error") if isinstance(data, dict) else None
            if err:
                print(f"[bookmanager:{source_label}] API error: {err}")
            return []

        events: list[dict] = []
        for row in rows:
            ev = _row_to_event(row, source_label, venue, public_url_template)
            if ev:
                events.append(ev)
        print(f"[bookmanager:{source_label}] Got {len(events)} events (SAN={san}, store_id={store_id})")
        return events
