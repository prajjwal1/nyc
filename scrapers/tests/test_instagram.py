"""Tests for the spot-account / multi-event-roundup evergreen logic in
scrapers.sources.instagram._extract_events_from_caption.

@onefinedaynyc is in IG_SPOTS_ACCOUNTS, so its everyday single posts are
"cool spot" recommendations rendered evergreen (a "Spot" pill, no date). But
its MONTHLY curated event carousel is a genuine dated-events roundup — those
events must keep their real dates and NOT be flattened to evergreen. The
discriminator is the multi-event roundup detection (3+ dated sections).

This matters because the monthly Substack guide that used to carry those
dated events is now paywalled, so the IG roundup is the only path to them.
"""

from datetime import datetime

import pytest

from scrapers.config import IG_SPOTS_ACCOUNTS
from scrapers.sources.instagram import _extract_events_from_caption


def _post(caption, when=datetime(2026, 6, 1, 12, 0), slides=1):
    return {
        "caption": caption,
        "date": when,
        "shortcode": "TEST123",
        "url": "https://instagram.com/p/TEST123",
        "all_images": [f"img{i}" for i in range(slides)],
        "image": "img0",
        "likes": 250,
        "comments": 8,
    }


# A monthly-roundup caption: 4 clearly-dated sections → multi_event.
ROUNDUP_CAPTION = """Your June Guide to NYC is here! Swipe through for the month.

June 6 | Philosophy at the Museum: Rococo at The Met. A guided salon exploring art.
June 10 | The New York Philosophy Club at McCarren Parkhouse in Williamsburg.
June 14 | Smorgasburg Opening Day at Prospect Park. Eat your way through the market.
June 20 | Bryant Park Jazz concert. Free outdoor live music in Midtown.
"""

# A single evergreen "cool spot" post: venue rec, no real event date.
SPOT_CAPTION = ("Golden Swan (West Village) has the best pancakes in the city. "
                "A charming all-day cafe to check out this weekend with friends.")


class TestSpotAccountEvergreen:
    def test_precondition_account_is_a_spot_account(self):
        assert "onefinedaynyc" in IG_SPOTS_ACCOUNTS

    def test_multi_event_roundup_keeps_real_dates_not_evergreen(self):
        # Build the caption from dates that are always in the future relative
        # to "now" so the test isn't brittle as the calendar advances (a bare
        # "June 6" flips to next year once June 6 is past — dateparser future
        # preference). Use today + 20/25/30/35 days.
        from datetime import datetime, timedelta
        now = datetime(2026, 6, 1, 12, 0)
        offs = [20, 25, 30, 35]
        ds = [now + timedelta(days=o) for o in offs]
        lines = [f"{d.strftime('%B %-d')} | Event {i} at a NYC venue, a great time."
                 for i, d in enumerate(ds)]
        caption = "Your NYC Guide is here!\n\n" + "\n".join(lines)
        post = _post(caption, when=now, slides=5)
        events = _extract_events_from_caption(post, "onefinedaynyc")
        assert len(events) >= 3, "roundup should yield its dated sections"
        # None of the roundup events are flattened to evergreen Spot pills.
        assert all(not e.get("evergreen") for e in events)
        # They carry the real parsed dates, not the post date as a fallback.
        got = {e["date"] for e in events}
        expected = {d.date().isoformat() for d in ds}
        assert len(got & expected) >= 3

    def test_single_spot_post_stays_evergreen(self):
        events = _extract_events_from_caption(_post(SPOT_CAPTION, when=datetime(2026, 6, 4, 12, 0)),
                                              "onefinedaynyc")
        assert len(events) == 1
        assert events[0].get("evergreen") is True
        assert "exploration" in events[0]["categories"]


class TestNonSpotControl:
    def test_non_spot_account_never_marked_evergreen(self):
        # A normal account's roundup is dated and never evergreen (control:
        # the evergreen flag is exclusively a spot-account behavior).
        events = _extract_events_from_caption(_post(ROUNDUP_CAPTION, slides=5), "somerandomvenue")
        assert len(events) >= 3
        assert all(not e.get("evergreen") for e in events)
