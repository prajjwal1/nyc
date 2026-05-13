"""Book Club Bar event scraper — multi-SAN wrapper over the shared
Bookmanager API helper. The actual extraction logic lives in
`scrapers/utils/bookmanager.py` so any Bookmanager-powered NYC bookstore
can reuse it without duplication.

Book Club Bar has two locations (East Village + Bushwick). The East
Village SAN currently hosts events for both (Bushwick events are listed
under the EV SAN, the description text notes the actual venue). When
the Bushwick site publishes events under its own SAN, add it to _SANS.
"""

import asyncio

from ..utils.bookmanager import scrape_san


# Book Club Bar SANs (visible inline as `var san="..."` on the venue site).
# 9911545 = East Village (197 E 3rd St). Currently closed for renovations
# but still the publishing SAN for all BCB events including Bushwick ones.
_SANS = ("9911545",)
_PUBLIC_EVENT_URL_TMPL = "https://www.bookclubbar.com/events/{event_id}"


def _dedup_key(ev: dict) -> tuple:
    return (
        (ev.get("title") or "").strip().lower(),
        ev.get("date") or "",
        ev.get("startTime") or "",
    )


async def scrape() -> list[dict]:
    results = await asyncio.gather(
        *[
            scrape_san(
                san=san,
                source_label="bookclubbar",
                default_venue="Book Club Bar",
                public_url_template=_PUBLIC_EVENT_URL_TMPL,
            )
            for san in _SANS
        ],
        return_exceptions=True,
    )

    merged: dict[tuple, dict] = {}
    total_per_san: list[int] = []
    for san, res in zip(_SANS, results):
        if isinstance(res, Exception):
            print(f"[bookclubbar] SAN={san} failed: {res}")
            total_per_san.append(0)
            continue
        total_per_san.append(len(res))
        for ev in res:
            merged.setdefault(_dedup_key(ev), ev)

    if not merged:
        print(
            f"[bookclubbar] WARNING: zero events from any SAN "
            f"({list(zip(_SANS, total_per_san))})"
        )

    return list(merged.values())
