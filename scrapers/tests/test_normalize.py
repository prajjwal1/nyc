"""Regression tests for scrapers.normalize.

Locks in:
  - Exact-title same-source dedup (pass 1).
  - Cross-source same-venue same-date merge with shared distinctive tokens
    (iter 65 — songkick + allevents Charlie Puth at MSG should collapse).
  - Same-venue same-date but DIFFERENT titles do NOT merge.
  - `_strip_outdoors_indoor_arena` removes the "outdoors" tag from MSG /
    Barclays events unless a strong outdoor signal is present.
  - `_backfill_neighborhood_from_venue` resolves Liz's Book Bar →
    carroll gardens and Book Club Bar → east village.
"""

import pytest

from scrapers.normalize import (
    _backfill_neighborhood_from_venue,
    _strip_outdoors_indoor_arena,
    deduplicate,
)


# ---------------------------------------------------------------------------
# deduplicate — exact-key merge plus the cross-source fuzzy merge.
# ---------------------------------------------------------------------------


class TestDeduplicate:
    def test_identical_source_title_date_collapses(self):
        # Two events with the same (source, title, date) merge in pass 1.
        events = [
            {
                "source": "songkick",
                "title": "Test Show",
                "date": "2026-05-30",
                "location": {"name": "Venue X"},
            },
            {
                "source": "songkick",
                "title": "Test Show",
                "date": "2026-05-30",
                "location": {"name": "Venue X"},
            },
        ]
        result = deduplicate(events)
        assert len(result) == 1

    def test_cross_source_same_venue_charlie_puth_merge(self):
        # iter 65: songkick's "Charlie Puth @ Madison Square Garden" and
        # allevents's "Charlie Puth, Daniel Seavey, Ally Salort in New York"
        # — same date, same venue, 2+ shared distinctive tokens (charlie,
        # puth) → cross-source merge.
        events = [
            {
                "source": "songkick",
                "title": "Charlie Puth @ Madison Square Garden",
                "date": "2026-05-29",
                "location": {"name": "Madison Square Garden"},
            },
            {
                "source": "allevents",
                "title": "Charlie Puth, Daniel Seavey, Ally Salort in New York",
                "date": "2026-05-29",
                "location": {"name": "Madison Square Garden"},
            },
        ]
        result = deduplicate(events)
        assert len(result) == 1
        # Both sources retained on the merged record for the "Recommended
        # by N sources" UI.
        sources = set(result[0].get("contributingSources", []))
        assert sources == {"songkick", "allevents"}

    def test_different_venues_same_date_do_not_merge(self):
        # Different titles, different venues, same date → 2 events.
        events = [
            {
                "source": "a",
                "title": "Jazz Night",
                "date": "2026-05-29",
                "location": {"name": "Blue Note"},
            },
            {
                "source": "b",
                "title": "Rock Show",
                "date": "2026-05-29",
                "location": {"name": "Bowery Ballroom"},
            },
        ]
        result = deduplicate(events)
        assert len(result) == 2

    def test_different_dates_same_venue_same_title_do_not_merge(self):
        # Same venue + same title but different dates = two real events
        events = [
            {
                "source": "songkick",
                "title": "Recurring Show",
                "date": "2026-05-29",
                "location": {"name": "Same Venue"},
            },
            {
                "source": "songkick",
                "title": "Recurring Show",
                "date": "2026-06-05",
                "location": {"name": "Same Venue"},
            },
        ]
        result = deduplicate(events)
        assert len(result) == 2

    def test_empty_list_returns_empty(self):
        assert deduplicate([]) == []

    def test_single_event_passes_through(self):
        ev = {
            "source": "songkick",
            "title": "Solo Event",
            "date": "2026-05-29",
            "location": {"name": "Venue"},
        }
        assert deduplicate([ev]) == [ev]


# ---------------------------------------------------------------------------
# _strip_outdoors_indoor_arena — defensive scrub of stale "outdoors" tags
# on MSG / Barclays / other indoor arenas.
# ---------------------------------------------------------------------------


class TestStripOutdoorsIndoorArena:
    def test_msg_loses_outdoors_tag(self):
        ev = {
            "title": "Concert",
            "description": "",
            "categories": ["music", "outdoors"],
            "location": {"name": "Madison Square Garden"},
        }
        _strip_outdoors_indoor_arena([ev])
        assert ev["categories"] == ["music"]

    def test_msg_with_rooftop_keeps_outdoors(self):
        # Strong outdoor signal ("rooftop") preserves the tag even at MSG
        ev = {
            "title": "Concert",
            "description": "rooftop session",
            "categories": ["music", "outdoors"],
            "location": {"name": "Madison Square Garden"},
        }
        _strip_outdoors_indoor_arena([ev])
        assert "outdoors" in ev["categories"]

    def test_barclays_loses_outdoors(self):
        ev = {
            "title": "NBA Game",
            "description": "",
            "categories": ["outdoors"],
            "location": {"name": "Barclays Center"},
        }
        _strip_outdoors_indoor_arena([ev])
        # When the only category was outdoors and it was stripped, the code
        # backfills with "other" so a card without a category isn't created.
        assert "outdoors" not in ev["categories"]
        assert ev["categories"] == ["other"]

    def test_non_arena_keeps_outdoors(self):
        ev = {
            "title": "Picnic",
            "description": "",
            "categories": ["outdoors"],
            "location": {"name": "Prospect Park"},
        }
        _strip_outdoors_indoor_arena([ev])
        assert "outdoors" in ev["categories"]

    def test_no_outdoors_tag_untouched(self):
        # If the event never had outdoors, the function leaves it alone
        ev = {
            "title": "Show",
            "description": "",
            "categories": ["music"],
            "location": {"name": "Madison Square Garden"},
        }
        _strip_outdoors_indoor_arena([ev])
        assert ev["categories"] == ["music"]


# ---------------------------------------------------------------------------
# _backfill_neighborhood_from_venue — venue-name table + address fallback.
# ---------------------------------------------------------------------------


class TestBackfillNeighborhood:
    def test_lizs_book_bar_to_carroll_gardens(self):
        # Bookmanager-powered scrapers (lizsbookbar) lack addresses, so
        # the venue-name → neighborhood table is the only signal.
        events = [
            {
                "title": "Reading",
                "location": {
                    "name": "Liz's Book Bar",
                    "neighborhood": None,
                    "address": "",
                },
            }
        ]
        _backfill_neighborhood_from_venue(events)
        assert events[0]["location"]["neighborhood"] == "carroll gardens"

    def test_book_club_bar_to_east_village(self):
        events = [
            {
                "title": "Lit Talk",
                "location": {
                    "name": "Book Club Bar",
                    "neighborhood": None,
                    "address": "",
                },
            }
        ]
        _backfill_neighborhood_from_venue(events)
        assert events[0]["location"]["neighborhood"] == "east village"

    def test_address_fallback_when_no_venue_match(self):
        # No venue-name match → re-runs infer_neighborhood on address
        events = [
            {
                "title": "Event",
                "location": {
                    "name": "Random Venue",
                    "neighborhood": None,
                    "address": "100 Spring St",
                },
            }
        ]
        _backfill_neighborhood_from_venue(events)
        assert events[0]["location"]["neighborhood"] == "soho"

    def test_stale_neighborhood_cleared_when_no_signal(self):
        # If existing tag isn't derivable from the current keyword list
        # and the venue/address don't yield a new one, the tag is cleared
        # to avoid lying to the user.
        events = [
            {
                "title": "Event",
                "location": {
                    "name": "",
                    "neighborhood": "soho",  # stale
                    "address": "",
                },
            }
        ]
        _backfill_neighborhood_from_venue(events)
        assert events[0]["location"]["neighborhood"] is None

    def test_venue_name_overrides_address(self):
        # Venue lookup is the strongest signal — even if the address
        # would point somewhere else, the venue table wins.
        events = [
            {
                "title": "Reading",
                "location": {
                    "name": "Liz's Book Bar",
                    "neighborhood": None,
                    "address": "100 Spring St",  # would say "soho"
                },
            }
        ]
        _backfill_neighborhood_from_venue(events)
        assert events[0]["location"]["neighborhood"] == "carroll gardens"

    def test_empty_list_no_error(self):
        # Just shouldn't raise
        _backfill_neighborhood_from_venue([])
