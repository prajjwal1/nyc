"""Book Club Bar event scraper.

Note: bookclubbar.com is a Bookmanager-powered React SPA where the HTML is
empty until JavaScript runs. The Bookmanager API requires browser-only auth.

Events are now scraped via Instagram (@bookclubbar) instead, which has all
the same event posts. This scraper is kept as a no-op for source diversity
in case the underlying API becomes accessible.
"""


async def scrape() -> list[dict]:
    return []
