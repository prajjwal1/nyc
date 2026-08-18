import json

from scrapers.sources import eventbrite, generic, instagram, luma
from scrapers.normalize import _is_distinct_schedule_source
from scrapers.instagram_browser_worker import (
    _account_plan, _caption_from_og, _merge_snapshot_posts, _sanitize_posts,
)


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
    assert event["organizerRefs"][0]["platform"] == "luma"


def test_luma_no_longer_fans_out_fake_category_routes():
    assert luma.LUMA_PAGES == [luma.LUMA_DISCOVER_URL]
    assert not hasattr(luma, "LUMA_CURATOR_PAGES")


def test_luma_fast_refresh_is_catalog_first_and_bounded(monkeypatch):
    monkeypatch.setenv("PLATFORM_FAST_REFRESH", "1")
    plan = luma._calendar_plan()
    assert plan[0].kind == "discover"
    assert len(plan) <= 5
    assert all(item.kind != "event" for item in plan)


def test_luma_city_api_row_keeps_graphic_canonical_url_and_host():
    row = {
        "api_id": "evt-1",
        "event": {
            "name": "Open Studio",
            "url": "open-studio-nyc",
            "start_at": "2026-08-22T23:00:00.000Z",
            "end_at": "2026-08-23T01:00:00.000Z",
            "cover_url": "https://images.lumacdn.com/open-studio.jpg",
            "geo_address_info": {
                "city": "Brooklyn",
                "address": "Pioneer Works",
                "full_address": "159 Pioneer St, Brooklyn, NY 11231",
            },
        },
        "calendar": {"api_id": "cal-1", "name": "Arts NYC", "slug": "artsnyc"},
        "hosts": [{"api_id": "usr-1", "name": "Arts NYC", "instagram_handle": "artsnyc"}],
        "ticket_info": {"is_free": True},
        "guest_count": 42,
    }

    event = luma._parse_luma_discover_entry(row)

    assert event["sourceUrl"] == "https://luma.com/open-studio-nyc"
    assert event["imageUrl"] == "https://images.lumacdn.com/open-studio.jpg"
    assert event["organizerUrl"] == "https://luma.com/artsnyc"
    assert event["organizerRefs"][0]["handle"] == "artsnyc"
    assert event["attendingCount"] == 42
    assert event["catalogSource"] == "luma_nyc"


def test_luma_city_bootstrap_reads_advertised_inventory():
    html = """
    <script id="__NEXT_DATA__" type="application/json">
      {"props":{"pageProps":{"initialData":{"data":{"place":{"api_id":"disc-nyc","event_count":84}}}}}}
    </script>
    """
    assert luma._luma_discover_bootstrap(html) == ("disc-nyc", 84)


def test_generic_crawler_never_fetches_meetup(tmp_path, monkeypatch):
    path = tmp_path / "discovered_urls.json"
    path.write_text(json.dumps([
        {"url": "https://www.meetup.com/group/events/1"},
        {"url": "https://example.com/events"},
    ]))
    monkeypatch.setattr(generic, "DISCOVERED_URLS_PATH", str(path))

    assert all("meetup.com" not in url for url in generic.GENERIC_URLS)
    assert generic._load_discovered_urls() == ["https://example.com/events"]


def test_eventbrite_search_plan_is_bounded(monkeypatch):
    topics = list(eventbrite._TOPIC_SEARCH_SLUG)
    monkeypatch.setattr(eventbrite, "ranked_topics", lambda: [
        (topic, 2.0 if index < 6 else 0.25, "personal" if index < 6 else "explore")
        for index, topic in enumerate(topics)
    ])
    plan = eventbrite._search_plan()
    assert len(plan) == 24
    assert sum(lane == "personal" for _, lane in plan) == 18
    assert sum(lane == "explore" for _, lane in plan) == 6
    # Breadth first: all twelve canonical categories appear before any
    # Brooklyn deepening, including the previously missed health + film lanes.
    first_pass = [url for url, _lane in plan[:12]]
    assert any("sports-and-fitness" in url for url in first_pass)
    assert any("health-and-wellness" in url for url in first_pass)
    assert any("film-and-media" in url for url in first_pass)
    assert any("books" in url for url in first_pass)
    assert all("?page=2" in url for url, _lane in plan[12:18])
    assert all("ny--brooklyn" in url for url, _lane in plan[18:])


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
    assert event["organizerRefs"][0]["externalId"] == "123"


def test_eventbrite_extracts_slugged_organizer_id():
    assert eventbrite._eventbrite_organizer_id(
        "https://www.eventbrite.com/o/st-mazie-5803675324"
    ) == "5803675324"


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


def test_browser_roundup_events_get_distinct_clickable_urls(tmp_path, monkeypatch):
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps({
        "generatedAt": "2026-07-30T12:00:00+00:00",
        "posts": [{
            "owner": "bookstore", "lane": "feed",
            "url": "https://www.instagram.com/p/roundup/",
            "caption": "August events", "capturedAt": "2026-07-30T12:00:00+00:00",
        }],
    }))
    monkeypatch.setattr(instagram, "_BROWSER_SNAPSHOT_PATH", str(path))
    monkeypatch.setattr(instagram, "_try_ocr_first_then_caption", lambda post, owner: [
        {"date": "2026-08-04", "sourceUrl": post["url"], "title": "First"},
        {"date": "2026-08-05", "sourceUrl": post["url"], "title": "Second"},
    ])
    events = instagram._scrape_browser_snapshot()
    assert len({event["sourceUrl"] for event in events}) == 2
    assert all(event["sourceUrl"].startswith("https://www.instagram.com/p/roundup/#event-") for event in events)


def test_browser_roundup_items_are_distinct_scheduled_events():
    assert _is_distinct_schedule_source({
        "source": "instagram", "browserCaptured": True,
        "sourceUrl": "https://instagram.com/p/x/#event-2026-08-04-2",
    })


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


def test_browser_account_rotation_advances_past_daily_four_chunks(monkeypatch):
    accounts = [
        {"username": f"account{i}", "discovered_via": "user_following"}
        for i in range(200)
    ]
    monkeypatch.setattr(
        "scrapers.instagram_browser_worker._json",
        lambda name, default: (
            {"accounts": accounts} if name == "discovered_accounts.json"
            else {"accounts": []} if name == "user_affinity_accounts.json"
            else {}
        ),
    )
    protected, rotating, next_cursor = _account_plan(rotation_cursor=5)
    assert len(protected) == 6
    assert rotating[0] == "account50"
    assert next_cursor == 6


def test_browser_snapshot_retains_other_rotation_candidates():
    current = [{"url": "https://instagram.com/p/new/", "owner": "new", "capturedAt": "2026-07-31"}]
    previous = [{"url": "https://instagram.com/p/old/", "owner": "old", "capturedAt": "2026-07-30"}]
    merged = _merge_snapshot_posts(current, previous)
    assert [post["owner"] for post in merged] == ["new", "old"]


def test_browser_og_caption_strips_post_metadata_and_trailing_period():
    raw = '626 likes - venue on July 31, 2026: "Concert August 5 at 7pm".'
    assert _caption_from_og(raw) == "Concert August 5 at 7pm"


def test_browser_snapshot_rejects_retail_giveaways():
    posts = [{
        "url": "https://instagram.com/p/promo/", "owner": "freebies",
        "lane": "feed", "caption": "Free item August 5, no purchase required",
        "image": "https://cdn/x.jpg",
    }]
    assert _sanitize_posts(posts) == []
