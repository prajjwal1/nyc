"""Tests for the One Fine Day NYC pin-marker event parser in
scrapers.sources.substack.

These lock in the structured extraction of the weekly "NYC This Week" posts,
which encode each curated event as:

    📍<Title> (@ <Venue>)☁️ <Date> | <Time>🎟️ <Price><Description…>

plus a per-event link. The old heading-fragment heuristic mangled these into
duplicate / mis-dated (2027!) / mis-linked fragments and leaked the shop and
product sections as fake events. The pin (📍) + cloud (☁️) pair is the event
discriminator; shops use 🛍️/🍀/☕ and products 👖/📱.

Critically, the pin arrives HTML-encoded as &#128205; in the raw RSS XML, so
the dispatch must test the DECODED soup text — there's an explicit case below.
"""

from datetime import date, datetime

import pytest
from bs4 import BeautifulSoup

from scrapers.sources import substack
from scrapers.sources.substack import (
    _extract_pin_marker_events,
    _parse_marker_date,
    _parse_item,
)


# ---------------------------------------------------------------------------
# _parse_marker_date — year anchoring fixes the dateparser 2027 bug
# ---------------------------------------------------------------------------

class TestParseMarkerDate:
    def test_anchors_to_post_year_not_future(self):
        # Post published 2026-05-27 references "May 29" — must be 2026-05-29,
        # NOT 2027 (dateparser's PREFER_DATES_FROM=future was the old bug).
        ref = date(2026, 5, 27)
        assert _parse_marker_date("May 29", ref) == date(2026, 5, 29)

    def test_past_within_year_stays_in_post_year(self):
        # "May 20" referenced by a June 1 post is ~12 days before — within the
        # 90-day window, so it stays in the post's year (not bumped forward).
        assert _parse_marker_date("May 20", date(2026, 6, 1)) == date(2026, 5, 20)

    def test_range_takes_start(self):
        assert _parse_marker_date("May 28-31", date(2026, 5, 27)) == date(2026, 5, 28)

    def test_opens_prefix(self):
        assert _parse_marker_date("Opens May 14 (on view through Fall)", date(2026, 5, 13)) == date(2026, 5, 14)

    def test_december_to_january_rollover(self):
        # A late-December post linking a January event should roll to next year.
        assert _parse_marker_date("January 5", date(2026, 12, 28)) == date(2027, 1, 5)

    def test_dateless_returns_none(self):
        assert _parse_marker_date("Open daily", date(2026, 6, 1)) is None
        assert _parse_marker_date("", date(2026, 6, 1)) is None


# ---------------------------------------------------------------------------
# _extract_pin_marker_events — the structured per-event parse
# ---------------------------------------------------------------------------

# A realistic weekly-post body fragment. Two real events (📍), one shop (🛍️)
# and one product pick (👖) that must NOT become events.
WEEKLY_HTML = """
<h2>NYC Local Events I'm Excited About This Week</h2>
<p>📍<strong>Pet Adoption Day (@ Elizabeth Street Garden)</strong>☁️ May 29 | 2:30PM-4:30PM🎟️ Free to attendHang out with rescue dogs from Animal Haven.<a href="https://www.instagram.com/p/DYr3fFLkXSk/">link</a></p>
<p>📍<strong>High Line Plant Sale (@ High Line - 14th Street)</strong>☁️ May 30 | 11AM-1PM🎟️ Free to attendPurchase plants propagated from the High Line gardens.<a href="https://www.thehighline.org/events/high-line-plant-sale/">link</a></p>
<h2>NYC Small Businesses / Local Finds</h2>
<p>🛍️<strong>Ma Vie (West Village)</strong>The sweetest new gift shop.<a href="https://www.instagram.com/mavie_newyork/">link</a></p>
<h2>Taylor's Top Picks This Week</h2>
<p>👖<strong>J.Crew Cosmo pant (link)</strong>Silk pants are such a vibe.<a href="https://go.shopmy.us/p-60876215">link</a></p>
"""


class TestExtractPinMarkerEvents:
    @pytest.fixture
    def events(self):
        soup = BeautifulSoup(WEEKLY_HTML, "html.parser")
        ref = date(2026, 5, 27)
        return _extract_pin_marker_events(soup, ref, "https://onefinedaynyc.substack.com/p/x", ref)

    def test_only_pin_lines_become_events(self, events):
        # 2 pinned events; the shop (🛍️) and product (👖) are excluded.
        titles = {e["title"] for e in events}
        assert titles == {"Pet Adoption Day", "High Line Plant Sale"}
        assert not any("Ma Vie" in t for t in titles)
        assert not any("J.Crew" in t for t in titles)

    def test_title_venue_split(self, events):
        pet = next(e for e in events if e["title"] == "Pet Adoption Day")
        assert pet["location"]["name"] == "Elizabeth Street Garden"

    def test_date_anchored_to_post_year(self, events):
        # Both events parse to 2026, never 2027.
        assert {e["date"] for e in events} == {"2026-05-29", "2026-05-30"}

    def test_per_event_external_url(self, events):
        plant = next(e for e in events if e["title"] == "High Line Plant Sale")
        assert plant["sourceUrl"] == "https://www.thehighline.org/events/high-line-plant-sale/"

    def test_time_and_price_parsed(self, events):
        pet = next(e for e in events if e["title"] == "Pet Adoption Day")
        assert pet["startTime"] == "14:30"
        assert pet["price"] == "free"

    def test_description_strips_ticket_prefix(self, events):
        # "Free to attend" must not bleed into the description text.
        pet = next(e for e in events if e["title"] == "Pet Adoption Day")
        assert not pet["description"].lower().startswith("free to attend")
        assert "rescue dogs" in pet["description"].lower()


# ---------------------------------------------------------------------------
# _parse_item dispatch — entity-encoded pins + roundup-container suppression
# ---------------------------------------------------------------------------

def _make_item(title, html, pub="Wed, 27 May 2026 14:21:50 GMT"):
    """Build a minimal RSS <item> ElementTree node."""
    import xml.etree.ElementTree as ET
    ns_uri = "http://purl.org/rss/1.0/modules/content/"
    item = ET.Element("item")
    ET.SubElement(item, "title").text = title
    ET.SubElement(item, "link").text = "https://onefinedaynyc.substack.com/p/test"
    ET.SubElement(item, "pubDate").text = pub
    ce = ET.SubElement(item, "{%s}encoded" % ns_uri)
    ce.text = html
    return item


NS = {"content": "http://purl.org/rss/1.0/modules/content/"}


class TestParseItemDispatch:
    def test_entity_encoded_pin_is_detected(self):
        # The raw feed ships the pin as &#128205; — the dispatch must decode
        # the soup text, not scan the raw XML. (This was an actual bug.)
        html = ('<p>&#128205;<strong>Brooklyn Ceramic Arts Tour (@ Brooklyn)</strong>'
                '☁️ May 28 | 6PM🎟️ Free to attendA celebration of clay.'
                '<a href="https://brooklynceramicartstour.com/map-2026">link</a></p>')
        item = _make_item("NYC This Week | May 27 - 31", html)
        events = _parse_item(item, NS)
        assert len(events) == 1
        assert events[0]["title"] == "Brooklyn Ceramic Arts Tour"
        assert events[0]["date"] == "2026-05-28"
        assert events[0]["sourceUrl"] == "https://brooklynceramicartstour.com/map-2026"

    def test_guide_container_post_emits_no_junk_event(self):
        # A now-paywalled monthly guide ships only an intro + "Read more" with
        # no pins and no event headings. It must NOT emit a whole-post event
        # titled "Your June Guide to NYC".
        html = ('<p>Happy June, New Yorkers!</p>'
                '<p>This monthly guide is now exclusively for subscribers.</p>'
                '<p><a href="https://onefinedaynyc.substack.com/p/your-june">Read more</a></p>')
        item = _make_item("Your June Guide to NYC ✨", html,
                          pub="Mon, 01 Jun 2026 13:58:13 GMT")
        events = _parse_item(item, NS)
        assert events == []

    def test_pin_path_preempts_heading_fragmentation(self):
        # When pins are present, the clean pin parse runs — not the heading
        # heuristic that would fragment <strong> tags.
        html = ('<h2>NYC Local Events</h2>'
                '<p>&#128205;<strong>Well-Read/Best Dressed: A Literary Salon</strong>'
                '☁️ May 19 | 6:30PM-9PM🎟️ TicketedJoin Lit Society.'
                '<a href="https://www.bondandgrace.com/products/literary-salon">link</a></p>')
        item = _make_item("NYC This Week | May 13 - 19", html,
                          pub="Wed, 13 May 2026 14:21:21 GMT")
        events = _parse_item(item, NS)
        assert len(events) == 1
        assert events[0]["title"] == "Well-Read/Best Dressed: A Literary Salon"
        assert "books" in events[0]["categories"]
