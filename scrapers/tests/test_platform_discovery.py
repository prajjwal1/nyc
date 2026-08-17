import json

from scrapers.sources import eventbrite, generic, partiful
from scrapers.utils import platform_discovery as discovery


def _write(path, payload):
    path.write_text(json.dumps(payload))
    return str(path)


def test_topic_scores_keep_coverage_and_fold_user_signals(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write(data_dir / "user_interest_profile.json", {
        "topic_counts": {"run": 5, "read": 3, "cinema": 2},
    })
    _write(data_dir / "user_engagement.json", {
        "categories": {"wellness": 4},
        "negCategories": {},
    })
    events_path = tmp_path / "events.json"
    _write(events_path, [])
    monkeypatch.setattr(discovery, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(discovery, "EVENTS_PATH", str(events_path))

    scores = discovery.topic_scores()

    assert scores["fitness"] > scores["art"]
    assert scores["books"] > scores["art"]
    assert scores["movies"] > scores["art"]
    assert scores["wellness"] > scores["art"]
    assert set(scores) == set(discovery.CORE_TOPICS)


def test_frontier_normalizes_slugged_eventbrite_organizers(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    discovered = [{
        "url": "https://www.eventbrite.com/o/st-mazie-5803675324?aff=ig",
        "discovered_at": "2026-08-17T12:00:00Z",
        "discovered_via": "instagram_bio",
    }]
    _write(data_dir / "discovered_urls.json", discovered)
    _write(data_dir / "user_curated_sources.json", {"hosts": {}})
    events_path = tmp_path / "events.json"
    _write(events_path, [])
    monkeypatch.setattr(discovery, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(discovery, "DISCOVERED_URLS_PATH", str(data_dir / "discovered_urls.json"))
    monkeypatch.setattr(discovery, "EVENTS_PATH", str(events_path))

    rows = discovery.platform_frontier("eventbrite", kinds={"organizer"})

    assert [(row.url, row.kind) for row in rows] == [
        ("https://eventbrite.com/o/5803675324", "organizer")
    ]


def test_repeated_luma_source_graduates_to_calendar(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write(data_dir / "discovered_urls.json", [])
    _write(data_dir / "user_curated_sources.json", {"hosts": {}})
    events_path = tmp_path / "events.json"
    _write(events_path, [
        {"source": "luma", "sourceUrl": "https://lu.ma/bookclub", "title": "One"},
        {"source": "luma", "sourceUrl": "https://lu.ma/bookclub", "title": "Two"},
        {"source": "luma", "sourceUrl": "https://lu.ma/abc12345", "title": "Direct"},
    ])
    monkeypatch.setattr(discovery, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(discovery, "DISCOVERED_URLS_PATH", str(data_dir / "discovered_urls.json"))
    monkeypatch.setattr(discovery, "EVENTS_PATH", str(events_path))

    calendars = discovery.platform_frontier("luma", kinds={"calendar"})
    direct = discovery.platform_frontier("luma", kinds={"event"})

    assert [item.url for item in calendars] == ["https://lu.ma/bookclub"]
    assert direct == []  # previous direct events are carried over, not refetched


def test_partiful_tags_are_learned_from_metadata():
    data = {
        "filters": [{"tagId": "FITNESS"}, {"tag_id": "BOOKS"}],
        "navigation": [{"type": "discover-tag", "id": "FILM_AND_MEDIA"}],
        "event": {"id": "must-not-be-treated-as-a-tag"},
    }
    assert partiful._extract_discover_tags(data) == {
        "FITNESS", "BOOKS", "FILM_AND_MEDIA"
    }


def test_generic_pool_has_no_dedicated_platform_urls():
    assert not any(discovery.is_dedicated_platform_url(url) for url in generic.GENERIC_URLS)


def test_eventbrite_promotes_slugged_organizer_without_hardcoding():
    rows = eventbrite._promoted_organizers([{
        "organizerUrl": "https://www.eventbrite.com/o/st-mazie-5803675324",
        "discoveryLane": "personal",
    }])
    assert rows[0].url == "https://eventbrite.com/o/5803675324"
    assert rows[0].lane == "personal"


def test_eventbrite_organizer_parser_walks_nested_hydration():
    payload = {
        "props": {"pageProps": {"organizer": {"name": "St. Mazie"}}},
        "dehydratedState": {
            "queries": [{
                "state": {
                    "data": {
                        "events": [{
                            "id": "evt-1",
                            "name": {"text": "Live Jazz Supper Club"},
                            "start_date": "2026-09-10",
                            "start_time": "19:30:00",
                            "url": "https://eventbrite.com/e/live-jazz-1",
                            "primary_venue": {
                                "name": "St. Mazie",
                                "address": {
                                    "localized_address_display": "345 Grand St, Brooklyn"
                                },
                            },
                        }],
                    },
                },
            }],
        },
    }
    html = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(payload)}</script>'

    events = eventbrite._parse_organizer_page(
        html, "https://www.eventbrite.com/o/st-mazie-5803675324"
    )

    assert [event["title"] for event in events] == ["Live Jazz Supper Club"]
    assert events[0]["organizer"] == "St. Mazie"
    assert events[0]["organizerRefs"][0]["externalId"] == "5803675324"
