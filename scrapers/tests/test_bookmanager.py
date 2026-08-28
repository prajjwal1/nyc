from scrapers.utils.bookmanager import _row_to_event


def _row(location_text: str) -> dict:
    return {
        "id": "1",
        "title": "Offsite Literary Event",
        "description": "A thoughtful evening with writers and readers.",
        "date": "20260912",
        "start_time": "19:00:00",
        "location_text": location_text,
        "category": {"name": "Books"},
    }


def test_event_specific_street_address_overrides_store_default():
    for location in (
        "Book Club Bar Bushwick, 380 Troutman Street",
        "Caveat, 21A Clinton Street",
        "Tompkins Square Library, 331 East 10th Street",
        "Queens Arts Center, 37-14 31st Ave",
    ):
        event = _row_to_event(_row(location), "bookclubbar", "Book Club Bar", default_address="197 E 3rd St")
        assert event["location"]["address"] == location
        assert event["structuredTitle"] is True


def test_prose_location_keeps_store_default_address():
    event = _row_to_event(_row("Meet by the front window"), "bookclubbar", "Book Club Bar", default_address="197 E 3rd St")
    assert event["location"]["address"] == "197 E 3rd St"
