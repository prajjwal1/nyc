import json

from scrapers.sources import eventbrite, instagram, luma
from scrapers.instagram_browser_worker import _sanitize_posts


def test_luma_listing_uses_canonical_url_and_organizer():
    raw = {
        "@type": "Event", "name": "Reading Party",
        "startDate": "2026-08-01T19:00:00-04:00",
        "url": "https://luma.com/abc12345",
        "location": {"name": "The Nook", "address": {"streetAddress": "Williamsburg"}},
        "organizer": {"name": "Reading Rhythms", "url": "https://luma.com/readingrhythms"},
    }
    event = luma._parse_ld_json(raw, "https://lu.ma/nyc")
    assert event["sourceUrl"] == "https://luma.com/abc12345"
    assert event["organizer"] == "Reading Rhythms"
    assert event["organizerUrl"] == "https://luma.com/readingrhythms"


def test_luma_no_longer_fans_out_fake_category_routes():
    assert luma.LUMA_PAGES[0] == "https://lu.ma/nyc"
    assert not any("/nyc/" in url for url in luma.LUMA_PAGES)


def test_eventbrite_search_plan_is_bounded(monkeypatch):
    monkeypatch.setattr(eventbrite, "_build_interest_topic_urls", lambda: [f"https://x/{i}" for i in range(30)])
    plan = eventbrite._search_plan()
    assert len(plan) == 18
    assert sum(lane == "personal" for _, lane in plan) == 12
    assert sum(lane == "explore" for _, lane in plan) == 6


def test_eventbrite_extracts_organizer():
    raw = {
        "@type": "Event", "name": "Social Chess",
        "description": "Meet people over chess.",
        "startDate": "2026-08-02T19:00:00-04:00", "url": "https://eventbrite.com/e/1",
        "organizer": {"name": "Chess Place", "url": "https://eventbrite.com/o/123"},
    }
    event = eventbrite._parse_ld_event(raw)
    assert event["organizer"] == "Chess Place"
    assert event["organizerUrl"].endswith("/o/123")


def test_browser_snapshot_is_parsed_without_instaloader(tmp_path, monkeypatch):
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps({
        "generatedAt": "2026-07-30T12:00:00+00:00",
        "posts": [{
            "owner": "reading_rhythms", "lane": "saved",
            "url": "https://www.instagram.com/p/abc/", "caption": "Reading party Aug 2 at 7pm",
            "capturedAt": "2026-07-30T12:00:00+00:00", "images": [],
        }],
    }))
    monkeypatch.setattr(instagram, "_BROWSER_SNAPSHOT_PATH", str(path))
    monkeypatch.setattr(instagram, "_try_ocr_first_then_caption", lambda post, owner: [{
        "id": "1", "instagramAccount": owner, "sourceUrl": post["url"],
    }])
    events = instagram._scrape_browser_snapshot()
    assert events[0]["userSaved"] is True
    assert events[0]["account"] == "reading_rhythms"
    assert events[0]["browserCaptured"] is True


def test_browser_snapshot_does_not_commit_arbitrary_saved_content():
    posts = [
        {"url": "https://www.instagram.com/p/dog/", "owner": "friend", "lane": "saved",
         "caption": "cute dog at home", "image": "https://cdn/x.jpg", "cookie": "secret"},
        {"url": "https://www.instagram.com/p/event/", "owner": "venue", "lane": "saved",
         "caption": "Book club August 12 at 7pm in Brooklyn", "image": "https://cdn/y.jpg",
         "cookie": "secret"},
    ]
    clean = _sanitize_posts(posts)
    assert [p["owner"] for p in clean] == ["venue"]
    assert "cookie" not in clean[0]
