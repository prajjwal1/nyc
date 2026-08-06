from datetime import datetime, timezone

import json

from scrapers.site_audit import audit_payloads, merge_browser_evidence


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


def test_audit_excludes_caption_leak_from_showcase_and_flags_raw_data():
    events = [event(i) for i in range(110)]
    events[0]["title"] = "If you're looking for a new cocktail bar, this is it"
    result = audit_payloads(
        {"lastUpdated": "2026-08-06T11:30:00+00:00", "events": events},
        {"communities": [{}] * 20},
        now=datetime(2026, 8, 6, 12, tzinfo=timezone.utc),
        route_status={"home": 200},
    )
    assert result["status"] == "attention"
    assert result["showcase"]["captionLike"] == []
    assert "0" not in result["showcase"]["eventIds"]
    assert result["feed"]["captionLikeNext7Days"] == 1
    assert any("independently enriched" in warning for warning in result["warnings"])


def test_audit_separates_directory_references_from_enriched_communities():
    communities = ([{"profileStatus": "directory_reference"}] * 1000) + ([{}] * 20)
    result = audit_payloads(
        {"lastUpdated": "2026-08-06T11:30:00+00:00", "events": [event(i) for i in range(110)]},
        {"communities": communities},
        now=datetime(2026, 8, 6, 12, tzinfo=timezone.utc),
    )

    assert result["communities"]["count"] == 1020
    assert result["communities"]["directoryReferenceCount"] == 1000
    assert result["communities"]["eventBackedCount"] == 20
    assert not any("fewer than 1,000 profiles" in warning for warning in result["warnings"])
    assert any("independently enriched" in warning for warning in result["warnings"])


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


def test_merge_browser_evidence_uses_exact_rendered_ids(tmp_path):
    audit = audit_payloads(
        {"lastUpdated": "2026-08-06T11:30:00+00:00", "events": [event(i) for i in range(110)]},
        {"communities": [{}] * 150},
        now=datetime(2026, 8, 6, 12, tzinfo=timezone.utc),
        route_status={"home": 200},
    )
    (tmp_path / "audit.json").write_text(json.dumps(audit))
    (tmp_path / "browser-audit.json").write_text(json.dumps({"results": [
        {"route": "home", "status": 200, "viewport": "mobile", "showcased": [{"id": "7", "section": "tonight", "rank": 1}]},
        {"route": "home", "status": 200, "viewport": "desktop", "showcased": [{"id": "7", "section": "tonight", "rank": 1}, {"id": "8", "section": "date", "rank": 1}]},
    ]}))
    merged = merge_browser_evidence(tmp_path)
    assert merged["showcase"]["rendered"]["eventIds"] == ["7", "8"]
    assert merged["showcase"]["rendered"]["mobileCount"] == 1
