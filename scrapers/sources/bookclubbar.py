"""Book Club Bar event scraper — thin wrapper over the shared Bookmanager
API helper. The actual extraction logic lives in `scrapers/utils/bookmanager.py`
so any Bookmanager-powered NYC bookstore can reuse it without duplication.
"""

from ..utils.bookmanager import scrape_san


# Book Club Bar's public Bookmanager SAN (visible inline as
# `var san="9911545"` on bookclubbar.com).
_SAN = "9911545"
_PUBLIC_EVENT_URL_TMPL = "https://www.bookclubbar.com/events/{event_id}"


async def scrape() -> list[dict]:
    return await scrape_san(
        san=_SAN,
        source_label="bookclubbar",
        default_venue="Book Club Bar",
        public_url_template=_PUBLIC_EVENT_URL_TMPL,
    )
