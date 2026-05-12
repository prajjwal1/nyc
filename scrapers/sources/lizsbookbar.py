"""Liz's Book Bar event scraper — thin wrapper over the shared Bookmanager
API helper. Same pattern as bookclubbar.py — only the SAN differs.
"""

from ..utils.bookmanager import scrape_san


_SAN = "9936106"  # Liz's Book Bar SAN — visible as `var san="9936106"` inline
_PUBLIC_EVENT_URL_TMPL = "https://lizsbookbar.com/events/{event_id}"


async def scrape() -> list[dict]:
    return await scrape_san(
        san=_SAN,
        source_label="lizsbookbar",
        default_venue="Liz's Book Bar",
        public_url_template=_PUBLIC_EVENT_URL_TMPL,
    )
