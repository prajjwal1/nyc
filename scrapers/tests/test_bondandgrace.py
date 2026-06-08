"""Tests for the Bond & Grace (Lit Society) scraper.

Locks in the listing-parse logic: only NYC event products are harvested, while
out-of-town events (Chicago) and merch (hoodies/totes/membership) are excluded,
and the no-year date inference picks an upcoming year.
"""
from datetime import date

from scrapers.sources.bondandgrace import _harvest_event_slugs, _infer_year


LISTING_HTML = """
<section id="events">
  <a href="/products/the-art-of-wanting-a-writer-s-salon">The Art of Wanting: A Writer’s Salon - Brooklyn, NY $75.00</a>
  <a href="/products/just-a-taste-a-literary-wine-experience">Just a Taste: A Literary Wine Experience - Brooklyn, NY $75.00</a>
  <a href="/products/step-into-books-greedy-edition">Step into Books: Greedy Edition - Chicago, IL $15.00</a>
  <a href="/products/the-stacks-embroidered-hoodie"></a>
  <a href="/products/lit-society-organic-canvas-tote"></a>
  <a href="/products/lit-society-membership">Join NOW</a>
  <a href="/products/lit-society-signature-hat"></a>
</section>
"""


class TestHarvestEventSlugs:
    def test_keeps_only_nyc_events(self):
        out = _harvest_event_slugs(LISTING_HTML)
        assert set(out) == {
            "the-art-of-wanting-a-writer-s-salon",
            "just-a-taste-a-literary-wine-experience",
        }

    def test_excludes_out_of_town(self):
        out = _harvest_event_slugs(LISTING_HTML)
        assert "step-into-books-greedy-edition" not in out  # Chicago, IL

    def test_excludes_merch_and_membership(self):
        out = _harvest_event_slugs(LISTING_HTML)
        for merch in ("the-stacks-embroidered-hoodie", "lit-society-organic-canvas-tote",
                      "lit-society-membership", "lit-society-signature-hat"):
            assert merch not in out

    def test_extracts_title_and_city(self):
        out = _harvest_event_slugs(LISTING_HTML)
        e = out["the-art-of-wanting-a-writer-s-salon"]
        assert e["title"] == "The Art of Wanting: A Writer’s Salon"
        assert e["city"] == "Brooklyn"


class TestInferYear:
    def test_upcoming_month_uses_current_year(self):
        today = date.today()
        # A month ~2 months ahead should resolve to this year.
        m = (today.month % 12) + 1
        assert _infer_year(m, 15) in (today.year, today.year + 1)

    def test_far_past_rolls_to_next_year(self):
        today = date.today()
        # The month ~3 months *before* now should roll forward.
        past_month = ((today.month - 4) % 12) + 1
        y = _infer_year(past_month, 15)
        d = date(y, past_month, 15)
        assert (d - today).days > -40  # never deep in the past
