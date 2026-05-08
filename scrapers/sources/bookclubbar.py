"""Book Club Bar event scraper.

bookclubbar.com is a Bookmanager-powered React SPA — the index /events
page has no server-side event list (JS-rendered).

HOWEVER: individual /events/<numeric-id> URLs have rich server-side
OpenGraph metadata (title, image, description), so the generic OG
strategy in scrapers/sources/generic.py parses them correctly. Example:

    https://www.bookclubbar.com/events/5159120260521
      og:title=Game Night: Adult Spelling Bee | Book Club Bar
      og:image=…GAME_NIGHT_ADULT_SPELLING_BEE…
      og:description=Independent general bookstore…

Discovery path: @bookclubbar (IG_ACCOUNTS) posts bookclubbar.com/events/
URLs in captions → IG caption-URL harvester adds them to
discovered_urls.json → generic scraper fetches each → OG metadata
extraction.

This module is a no-op stub. The pipeline reaches Book Club Bar events
via the IG-→-discovered-URLs-→-generic-OG path.
"""


async def scrape() -> list[dict]:
    return []
