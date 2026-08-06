from datetime import datetime, timezone

from scrapers.site_audit import audit_payloads


def event(i, **updates):
    value = {
        "id": str(i), "title": f"Useful event {i}", "date": "2026-08-07",
        "startTime": "18:00", "description": "A specific and useful description for people considering this event.",
        "imageUrl": "https://example.com/image.jpg", "sourceUrl": "https://example.com/event",
        "source": f"source-{i % 4}", "organizer": f"Organizer {i}", "score": .8,
        "location": {"name": "A real venue", "neighborhood": "Williamsburg"},
        "communityIds": [f"community-{i % 10}"],
    }
    value.update(updates)
    return value


def test_audit_flags_caption_leak_and_thin_communities():
    events = [event(i) for i in range(110)]
    events[0]["title"] = "If you're looking for a new cocktail bar, this is it"
    result = audit_payloads(
        {"lastUpdated": "2026-08-06T11:30:00+00:00", "events": events},
        {"communities": [{}] * 20},
        now=datetime(2026, 8, 6, 12, tzinfo=timezone.utc),
        route_status={"home": 200},
    )
    assert result["status"] == "fail"
    assert result["showcase"]["captionLike"][0]["id"] == "0"
    assert any("150-community" in warning for warning in result["warnings"])


def test_audit_flags_stale_or_unavailable_deployment():
    result = audit_payloads(
        {"lastUpdated": "2026-08-01T00:00:00+00:00", "events": []},
        {"communities": []},
        now=datetime(2026, 8, 6, 12, tzinfo=timezone.utc),
        route_status={"home": 200, "communities": 404},
    )
    assert result["status"] == "fail"
    assert any("two hours" in failure for failure in result["failures"])
    assert any("routes" in failure for failure in result["failures"])
