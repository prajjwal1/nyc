import json
import asyncio
from datetime import date, timedelta

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


def test_persisted_platform_links_keep_provenance_and_canonical_identity(
    tmp_path, monkeypatch
):
    path = tmp_path / "discovered_urls.json"
    _write(path, [])
    monkeypatch.setattr(discovery, "DISCOVERED_URLS_PATH", str(path))

    added = discovery.persist_discovered_urls(
        ["https://www.eventbrite.com/o/st-mazie-5803675324?aff=instagram"],
        discovered_via="instagram_bio_browser",
        source_account="reading_rhythms",
        lane="personal",
    )
    duplicate = discovery.persist_discovered_urls(
        ["https://eventbrite.com/o/5803675324"],
        discovered_via="eventbrite_organizer_graph",
    )

    rows = json.loads(path.read_text())
    assert added == 1
    assert duplicate == 0
    assert len(rows) == 1
    assert rows[0]["url"] == "https://eventbrite.com/o/5803675324"
    assert rows[0]["platform"] == "eventbrite"
    assert rows[0]["kind"] == "organizer"
    assert rows[0]["lane"] == "personal"
    assert rows[0]["source_accounts"] == ["reading_rhythms"]
    assert rows[0]["discovery_vias"] == [
        "instagram_bio_browser", "eventbrite_organizer_graph"
    ]

    discovery.record_platform_results([{
        "url": "https://eventbrite.com/o/5803675324", "yield": 7,
    }])
    discovery.record_platform_survival([{
        "source": "eventbrite",
        "sourceUrl": "https://eventbrite.com/e/a-night-123",
        "organizerUrl": "https://eventbrite.com/o/5803675324",
    }])
    row = json.loads(path.read_text())[0]
    assert row["status"] == "active"
    assert row["last_parsed_yield"] == 7
    assert row["last_surviving_yield"] == 1


def test_empty_direct_event_expires_after_three_attempts(tmp_path, monkeypatch):
    path = tmp_path / "discovered_urls.json"
    _write(path, [])
    events_path = tmp_path / "events.json"
    _write(events_path, [])
    _write(tmp_path / "user_curated_sources.json", {"hosts": {}})
    monkeypatch.setattr(discovery, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(discovery, "DISCOVERED_URLS_PATH", str(path))
    monkeypatch.setattr(discovery, "EVENTS_PATH", str(events_path))
    url = "https://partiful.com/e/past-event"
    discovery.persist_discovered_urls([url], discovered_via="instagram_bio")

    discovery.record_platform_results([
        {"url": url, "yield": 0},
        {"url": url, "yield": 0},
        {"url": url, "yield": 0},
    ])

    row = json.loads(path.read_text())[0]
    assert row["status"] == "stale"
    assert row["consecutive_empty_runs"] == 3
    assert row["next_retry_at"] > row["last_attempt_at"]
    assert discovery.platform_frontier("partiful", kinds={"event"}) == []


def test_link_aggregator_html_extracts_only_dedicated_platforms():
    document = r'''
      <a href="https:\/\/partiful.com\/e\/party123?c=ig">Party</a>
      <a href="https://www.eventbrite.com/o/club-name-12345?aff=ig">Club</a>
      <script>{"url":"https:\/\/lu.ma\/readingrhythms"}</script>
      <a href="https://example.com/events/ignore-me">Other</a>
    '''

    assert discovery.extract_platform_links(document) == {
        "https://partiful.com/e/party123",
        "https://eventbrite.com/o/12345",
        "https://lu.ma/readingrhythms",
    }


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


def test_discovered_user_mentioned_organizer_outranks_inferred_curated_host(
    tmp_path, monkeypatch
):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write(data_dir / "discovered_urls.json", [{
        "url": "https://www.eventbrite.com/o/st-mazie-5803675324",
        "discovered_at": "2026-09-03T12:00:00Z",
        "discovered_via": "user_mentioned",
    }])
    _write(data_dir / "user_curated_sources.json", {"hosts": {
        "eventbrite.com/o/inferred-host-111": {
            "source": "inferred_from_taste",
            "score": 1.0,
        },
    }})
    events_path = tmp_path / "events.json"
    _write(events_path, [{
        "source": "eventbrite",
        "organizerUrl": "https://eventbrite.com/o/111",
        "sourceUrl": f"https://eventbrite.com/e/inferred-{index}",
    } for index in range(10)])
    monkeypatch.setattr(discovery, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(
        discovery, "DISCOVERED_URLS_PATH", str(data_dir / "discovered_urls.json")
    )
    monkeypatch.setattr(discovery, "EVENTS_PATH", str(events_path))

    rows = discovery.platform_frontier("eventbrite", kinds={"organizer"})

    assert rows[0].url == "https://eventbrite.com/o/5803675324"
    assert rows[0].via == "user_mentioned"
    assert rows[1].url == "https://eventbrite.com/o/111"


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


def test_partiful_organizer_page_exposes_published_events():
    payload = {
        "props": {"pageProps": {
            "user": {"id": "host-a", "name": "Chess Friends"},
            "initialPublishedEvents": [{
                "id": "event-a",
                "title": "Social Chess Night",
                "startDate": "2026-09-20T23:00:00.000Z",
                "timezone": "America/New_York",
                "ownerIds": ["host-a"],
                "locationInfo": {"mapsInfo": {
                    "name": "The Nook",
                    "addressLines": ["45 Irving Ave", "Brooklyn, NY 11237"],
                }},
            }],
        }},
    }
    html = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(payload)}</script>'

    events = partiful._parse_organizer_page(
        html, "https://partiful.com/u/host-a"
    )

    assert [event["title"] for event in events] == ["Social Chess Night"]
    assert events[0]["organizer"] == "Chess Friends"
    assert events[0]["organizerUrl"] == "https://partiful.com/u/host-a"
    assert events[0]["catalogSource"] == "partiful_organizer"


def test_partiful_promotes_recurring_and_personal_hosts_only():
    recurring = [{
        "sourceUrl": f"https://partiful.com/e/{index}",
        "organizerRefs": [{"platform": "partiful", "externalId": "host-recurring"}],
        "discoveryLane": "explore",
    } for index in range(2)]
    personal = [{
        "sourceUrl": "https://partiful.com/e/personal",
        "organizerRefs": [{"platform": "partiful", "externalId": "host-personal"}],
        "discoveryLane": "personal",
    }]
    singleton = [{
        "sourceUrl": "https://partiful.com/e/one-off",
        "organizerRefs": [{"platform": "partiful", "externalId": "host-one-off"}],
        "discoveryLane": "explore",
    }]

    rows = partiful._promoted_organizers(recurring + personal + singleton)

    assert [row.url for row in rows] == [
        "https://partiful.com/u/host-personal",
        "https://partiful.com/u/host-recurring",
    ]


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


def test_eventbrite_organizer_frontier_protects_top_and_rotates_tail():
    items = [
        discovery.FrontierItem(
            url=f"https://eventbrite.com/o/{index}", kind="organizer"
        )
        for index in range(10)
    ]

    first = eventbrite._rotating_targets(
        items, limit=6, protected=2, slot=0
    )
    second = eventbrite._rotating_targets(
        items, limit=6, protected=2, slot=1
    )

    assert [item.url for item in first[:2]] == [item.url for item in items[:2]]
    assert [item.url for item in second[:2]] == [item.url for item in items[:2]]
    assert {item.url for item in first[2:]} != {item.url for item in second[2:]}


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


def _collection_event(index, *, category="books", event_date=None, blocked=False):
    return {
        "title": f"Collection event {index}",
        "date": event_date or (date.today() + timedelta(days=7)).isoformat(),
        "sourceUrl": f"https://eventbrite.com/e/collection-{index}",
        "categories": [category],
        "blocked": blocked,
    }


def test_eventbrite_collection_gate_rejects_past_only(monkeypatch):
    monkeypatch.setattr(eventbrite, "is_blocked", lambda event: event.get("blocked", False))
    monkeypatch.setattr(eventbrite, "is_user_excluded", lambda event: False)
    rows = [_collection_event(i, event_date="2026-01-01") for i in range(6)]

    assert eventbrite._accepted_collection_events(
        rows, personal_topics={"books"}, today="2026-09-08"
    ) == []


def test_eventbrite_collection_gate_rejects_sub_eighty_percent_fit(monkeypatch):
    monkeypatch.setattr(eventbrite, "is_blocked", lambda event: event.get("blocked", False))
    monkeypatch.setattr(eventbrite, "is_user_excluded", lambda event: False)
    rows = [_collection_event(i, category="books" if i < 3 else "music") for i in range(5)]

    assert eventbrite._accepted_collection_events(
        rows, personal_topics={"books"}, today="2026-09-08"
    ) == []


def test_eventbrite_collection_gate_canonicalizes_duplicate_urls(monkeypatch):
    monkeypatch.setattr(eventbrite, "is_blocked", lambda event: False)
    monkeypatch.setattr(eventbrite, "is_user_excluded", lambda event: False)
    rows = [_collection_event(i) for i in range(5)]
    duplicate = dict(rows[0], sourceUrl=rows[0]["sourceUrl"] + "?aff=duplicate")

    accepted = eventbrite._accepted_collection_events(
        rows + [duplicate], personal_topics={"books"}, today="2026-09-08"
    )

    assert len(accepted) == 5


def test_eventbrite_scrape_schedules_collection_frontier(monkeypatch):
    item = discovery.FrontierItem(
        url="https://eventbrite.com/cc/existing-collection-123",
        kind="collection",
        lane="personal",
        via="historical_probe",
    )
    monkeypatch.setenv("IG_SAVED_ONLY", "1")
    monkeypatch.setattr(
        eventbrite,
        "platform_frontier",
        lambda _platform, *, kinds, limit: [item] if kinds == {"collection"} else [],
    )

    async def fake_fetch(_url, attempts=3):
        return "collection html"

    monkeypatch.setattr(eventbrite, "_fetch_with_backoff", fake_fetch)
    monkeypatch.setattr(eventbrite, "record_platform_results", lambda _results: None)
    monkeypatch.setattr(eventbrite, "_search_plan", lambda: [])
    monkeypatch.setattr(eventbrite, "_parse_search_page", lambda _html, _url: [
        _collection_event(index) for index in range(5)
    ])
    monkeypatch.setattr(eventbrite, "ranked_topics", lambda: [("books", 4.0, "personal")])

    events = asyncio.run(eventbrite.scrape())

    assert len(events) == 5
    assert all(event["discoveryVia"] == "historical_probe" for event in events)
    health = eventbrite.catalog_health()
    assert health["collectionTargets"] == 1
    assert health["collectionTargetsFetched"] == 1
    assert health["collectionsAdmitted"] == 1


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
