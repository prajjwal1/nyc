"""Bond & Grace — "Lit Society" literary salons (bondandgrace.com).

The Lit Society page (/lit-society-by-bond-and-grace) lists in-person literary
events as links to Squarespace-style /products/<slug> ticket pages, with link
text shaped `Title - City, ST $price`. That format cleanly separates real
events from merch (hoodies/totes/membership, which have no "City, ST") and from
out-of-town events (e.g. "...- Chicago, IL"). The listing has no dates, but each
product page carries the date/time in text ("Tuesday, June 16", "7:00 PM").

So: harvest NYC event slugs from the listing, then fetch each product page for
the date/time/venue. Literary salons are the user's calibrated top interest.

Robust: defensive per-product parsing, 404s skipped, NYC-gated, year inferred.
"""
import re
from datetime import date, datetime

from bs4 import BeautifulSoup

from ..utils.http import fetch_text
from ..utils.event_parser import build_event, parse_date, parse_time, infer_categories

LISTING_URL = "https://www.bondandgrace.com/lit-society-by-bond-and-grace"
_BASE = "https://www.bondandgrace.com"

# Link text on the listing: "Title - City, ST $price". Capture title + locale.
_EVENT_LINK_RE = re.compile(r"^(?P<title>.+?)\s*-\s*(?P<city>[A-Za-z .']+),\s*(?P<st>[A-Z]{2})\b")
# NYC-area localities (state NY plus the boroughs spelled out).
_NYC_STATES = {"NY"}
_NYC_CITIES = {"new york", "brooklyn", "manhattan", "queens", "bronx",
               "staten island", "long island city", "brooklyn ny", "nyc"}
# Slugs that are merch / membership / gift cards, never events.
_NON_EVENT_SLUG = re.compile(
    r"hoodie|tee|tote|hat|crewneck|sweat|mug|membership|gift-card|"
    r"poster|print|book|edition|hardcover|tshirt|apparel|merch",
    re.IGNORECASE,
)
_WEEKDAY_DATE_RE = re.compile(
    r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+"
    r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}",
    re.IGNORECASE,
)


async def scrape() -> list[dict]:
    try:
        html = await fetch_text(LISTING_URL)
    except Exception as e:  # noqa: BLE001
        print(f"[bondandgrace] listing fetch failed: {e}")
        return []

    candidates = _harvest_event_slugs(html)
    print(f"[bondandgrace] {len(candidates)} NYC event candidates from listing")

    events = []
    for slug, hint in candidates.items():
        try:
            ev = await _scrape_product(slug, hint)
        except Exception as e:  # noqa: BLE001
            print(f"[bondandgrace] skip {slug}: {e}")
            continue
        if ev:
            events.append(ev)
    print(f"[bondandgrace] Found {len(events)} events")
    return events


def _harvest_event_slugs(html: str) -> dict[str, dict]:
    """Return {slug: {title, city}} for NYC event products on the listing."""
    soup = BeautifulSoup(html, "html.parser")
    out: dict[str, dict] = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/products/" not in href:
            continue
        slug = href.split("/products/", 1)[1].split("?")[0].strip("/")
        if not slug or slug in out or _NON_EVENT_SLUG.search(slug):
            continue
        text = " ".join(a.get_text(" ", strip=True).split())
        m = _EVENT_LINK_RE.match(text)
        if not m:
            continue  # not the "Title - City, ST $price" event shape
        city = m.group("city").strip().lower()
        st = m.group("st")
        if st not in _NYC_STATES and city not in _NYC_CITIES:
            continue  # out-of-town (e.g. Chicago, IL)
        out[slug] = {"title": m.group("title").strip(), "city": m.group("city").strip()}
    return out


def _infer_year(month: int, day: int) -> int:
    """Pick the year that makes the date upcoming (events have no year)."""
    today = date.today()
    try:
        d = date(today.year, month, day)
    except ValueError:
        return today.year
    # If it's more than ~30 days in the past, it's next year's edition.
    if (d - today).days < -30:
        return today.year + 1
    return today.year


async def _scrape_product(slug: str, hint: dict) -> dict | None:
    url = f"{_BASE}/products/{slug}"
    try:
        html = await fetch_text(url)
    except Exception as e:  # noqa: BLE001
        if "404" in str(e):
            return None  # stale slug on the listing — skip quietly
        raise
    soup = BeautifulSoup(html, "html.parser")

    def _meta(prop):
        tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
        return (tag.get("content") or "").strip() if tag else ""

    # Title: prefer og:title, strip the " - City, ST" suffix; fall back to hint.
    raw_title = _meta("og:title") or hint.get("title", "")
    title = re.split(r"\s*-\s*[A-Za-z .']+,\s*[A-Z]{2}\b", raw_title)[0].strip() or hint["title"]
    if len(title) < 4:
        return None

    text = soup.get_text(" ", strip=True)

    # Date: "Tuesday, June 16" (no year) → infer the upcoming year.
    event_date = None
    mdate = _WEEKDAY_DATE_RE.search(text)
    if mdate:
        parsed = parse_date(mdate.group(0))
        if parsed:
            event_date = date(_infer_year(parsed.month, parsed.day), parsed.month, parsed.day)
    if not event_date:
        return None  # no reliable date — don't emit a dateless literary event

    start_time = parse_time(text)

    image = _meta("og:image") or None
    description = _meta("og:description") or _meta("description") or ""
    if not description:
        # First substantive sentence of the body as a fallback blurb.
        description = text[:300]

    return build_event(
        title=title,
        description=description[:500],
        event_date=event_date,
        start_time=start_time,
        location_name=f"Bond & Grace ({hint['city']})",
        source="bondandgrace",
        source_url=url,
        image_url=image,
        categories=infer_categories(title, description) or ["books"],
    )
