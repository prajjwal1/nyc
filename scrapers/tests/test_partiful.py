"""Tests for the Partiful event parser (scrapers.sources.partiful).

Locks in the robustness-critical behavior of `_parse_event_obj`:
  - NYC gate via event timezone (cross-listed LA/SF events are dropped)
  - UTC→America/New_York conversion (Partiful startDate is UTC; naive slicing
    mis-dated evening events by a day)
  - image-shape handling (coverPhotoUrl / image.url / image.upload.url)
  - venue + guest-count extraction
  - graceful None on unusable input
"""
import pytest

from scrapers.sources.partiful import _parse_event_obj


def _event(**over):
    base = {
        "id": "abc123",
        "title": "Rooftop Social",
        "startDate": "2026-06-06T00:00:00.000Z",  # = June 5, 8pm ET
        "timezone": "America/New_York",
        "locationInfo": {"mapsInfo": {"name": "Magic Hour Rooftop",
                                       "addressLines": ["485 7th Ave", "New York, NY"]}},
        "image": {"url": "https://img.partiful.com/x.jpg"},
        "goingGuestCount": 42,
        "interestedGuestCount": 10,
        "description": "Come hang out on the roof.",
    }
    base.update(over)
    return base


class TestNYCGate:
    def test_nyc_event_is_built(self):
        ev = _parse_event_obj(_event())
        assert isinstance(ev, dict)
        assert ev["title"] == "Rooftop Social"
        assert ev["source"] == "partiful"

    def test_non_nyc_timezone_is_dropped(self):
        assert _parse_event_obj(_event(timezone="America/Los_Angeles")) == "non-nyc"
        assert _parse_event_obj(_event(timezone="America/Chicago")) == "non-nyc"

    def test_missing_timezone_is_allowed(self):
        # explore/nyc is NYC-scoped; a missing tz shouldn't drop the event.
        assert isinstance(_parse_event_obj(_event(timezone="")), dict)


class TestDateConversion:
    def test_utc_evening_converts_to_correct_et_date(self):
        # 2026-06-06T00:00Z is 8pm ET on June 5 — must NOT be June 6.
        ev = _parse_event_obj(_event())
        assert ev["date"] == "2026-06-05"
        assert ev["startTime"] == "20:00"

    def test_unusable_input_returns_none(self):
        assert _parse_event_obj(_event(title="")) is None
        assert _parse_event_obj(_event(startDate="")) is None


class TestFieldExtraction:
    def test_venue_and_address(self):
        ev = _parse_event_obj(_event())
        assert ev["location"]["name"] == "Magic Hour Rooftop"
        assert "485 7th Ave" in ev["location"]["address"]

    def test_source_url_from_id(self):
        ev = _parse_event_obj(_event(id="XYZ789"))
        assert ev["sourceUrl"] == "https://partiful.com/e/XYZ789"

    def test_guest_counts_in_description(self):
        ev = _parse_event_obj(_event())
        assert "42 going" in ev["description"]
        assert "10 interested" in ev["description"]

    @pytest.mark.parametrize("image_field,expected", [
        ({"coverPhotoUrl": "https://c.jpg"}, "https://c.jpg"),
        ({"image": {"url": "https://u.jpg"}}, "https://u.jpg"),
        ({"image": {"upload": {"url": "https://up.jpg"}}}, "https://up.jpg"),
    ])
    def test_image_shapes(self, image_field, expected):
        e = _event()
        e.pop("image", None)
        e.update(image_field)
        assert _parse_event_obj(e)["imageUrl"] == expected
