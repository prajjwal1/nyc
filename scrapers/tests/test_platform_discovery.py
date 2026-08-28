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


def test_curated_eventbrite_frontier_prefers_explicit_user_signal(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write(data_dir / "discovered_urls.json", [])
    _write(data_dir / "user_curated_sources.json", {"hosts": {
        "eventbrite.com/o/inferred-host-111": {
            "source": "inferred_from_taste",
            "weight": 0.8,
        },
        "eventbrite.com/o/lizs-book-bar-83466825333": {
            "source": "user_mentioned",
            "weight": 1.0,
        },
    }})
    events_path = tmp_path / "events.json"
    _write(events_path, [])
    monkeypatch.setattr(discovery, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(discovery, "DISCOVERED_URLS_PATH", str(data_dir / "discovered_urls.json"))
    monkeypatch.setattr(discovery, "EVENTS_PATH", str(events_path))

    rows = discovery.platform_frontier("eventbrite", kinds={"organizer"})

    assert [row.url for row in rows] == [
        "https://eventbrite.com/o/83466825333",
        "https://eventbrite.com/o/111",
    ]
    assert rows[0].via == "curated:user_mentioned"
    assert rows[1].via == "curated:inferred_from_taste"


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


def test_eventbrite_search_promotion_requires_recurring_organizer():
    rows = eventbrite._promoted_organizers([
        {
            "organizerUrl": "https://eventbrite.com/o/111",
            "sourceUrl": "https://eventbrite.com/e/one",
            "discoveryLane": "personal",
            "discoveryVia": "eventbrite_search",
        },
        {
            "organizerUrl": "https://eventbrite.com/o/111",
            "sourceUrl": "https://eventbrite.com/e/one?aff=duplicate",
            "discoveryLane": "personal",
            "discoveryVia": "eventbrite_search",
        },
        {
            "organizerUrl": "https://eventbrite.com/o/222",
            "sourceUrl": "https://eventbrite.com/e/two",
            "discoveryLane": "personal",
            "discoveryVia": "eventbrite_search",
        },
        {
            "organizerUrl": "https://eventbrite.com/o/222",
            "sourceUrl": "https://eventbrite.com/e/three",
            "discoveryLane": "personal",
            "discoveryVia": "eventbrite_search",
        },
    ])

    assert [row.url for row in rows] == ["https://eventbrite.com/o/222"]


def test_eventbrite_explicit_organizer_outranks_raw_search_volume():
    events = [{
        "organizerUrl": "https://eventbrite.com/o/lizs-book-bar-83466825333",
        "sourceUrl": "https://eventbrite.com/e/liz-event",
        "discoveryLane": "personal",
        "discoveryVia": "user_mentioned",
    }]
    events.extend({
        "organizerUrl": "https://eventbrite.com/o/generic-network-222",
        "sourceUrl": f"https://eventbrite.com/e/generic-{index}",
        "discoveryLane": "explore",
        "discoveryVia": "eventbrite_search",
    } for index in range(10))

    rows = eventbrite._promoted_organizers(events)

    assert rows[0].url == "https://eventbrite.com/o/83466825333"
    assert rows[0].lane == "personal"


def test_eventbrite_automatic_organizer_requires_yield_and_clean_mix(monkeypatch):
    clean = [{"title": f"Clean event {index}"} for index in range(5)]
    monkeypatch.setattr(eventbrite, "is_blocked", lambda event: event.get("blocked", False))
    monkeypatch.setattr(eventbrite, "is_user_excluded", lambda event: event.get("excluded", False))

    assert eventbrite._organizer_calendar_is_useful(clean)
    assert not eventbrite._organizer_calendar_is_useful(clean[:4])
    assert not eventbrite._organizer_calendar_is_useful(
        clean + [{"title": "Nightlife spam", "blocked": True}, {"blocked": True}]
    )
    assert not eventbrite._organizer_calendar_is_useful(
        clean + [{"title": "AI Apocalypse", "excluded": True}, {"excluded": True}]
    )


def test_eventbrite_search_parser_merges_server_organizer_id():
    server_data = {
        "search_data": {
            "events": {
                "results": [{
                    "id": "evt-1",
                    "name": "Smart Comedy Night",
                    "summary": "Comedy and science in the Lower East Side.",
                    "start_date": "2026-09-10",
                    "start_time": "19:30",
                    "end_time": "21:00",
                    "url": "https://www.eventbrite.com/e/smart-comedy-night-tickets-1",
                    "primary_organizer_id": "13580085802",
                    "primary_venue": {
                        "name": "Caveat",
                        "address": {
                            "localized_address_display": "21 A Clinton St, New York, NY",
                            "latitude": "40.7202",
                            "longitude": "-73.9840"
                        }
                    }
                }]
            }
        }
    }
    json_ld = {
        "@type": "Event",
        "name": "Smart Comedy Night",
        "startDate": "2026-09-10T19:30:00-04:00",
        "url": "https://www.eventbrite.com/e/smart-comedy-night-tickets-1?aff=search",
        "offers": {"price": "15", "priceCurrency": "USD"}
    }
    html = (
        f'<script type="application/ld+json">{json.dumps(json_ld)}</script>'
        f'<script>window.__SERVER_DATA__ = {json.dumps(server_data)};</script>'
    )

    events = eventbrite._parse_search_page(
        html, "https://eventbrite.com/d/ny--new-york/comedy--events/"
    )

    assert len(events) == 1
    assert events[0]["organizerUrl"] == "https://eventbrite.com/o/13580085802"
    assert events[0]["organizerRefs"][0]["externalId"] == "13580085802"
    assert events[0]["location"]["name"] == "Caveat"
    assert events[0]["price"] == "$15"


def test_eventbrite_server_parser_drops_equal_end_time():
    server_data = {"search_data": {"events": {"results": [{
        "id": "evt-1",
        "name": "Reading Night",
        "start_date": "2026-09-10",
        "start_time": "19:30",
        "end_time": "19:30",
        "url": "https://eventbrite.com/e/reading-night-1",
    }]}}}
    html = f'<script>window.__SERVER_DATA__ = {json.dumps(server_data)};</script>'

    events = eventbrite._parse_server_search_events(html)

    assert events[0]["startTime"] == "19:30"
    assert events[0]["endTime"] is None


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
