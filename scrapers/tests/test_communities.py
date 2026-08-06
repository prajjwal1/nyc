from datetime import date
import json

from scrapers.communities import _cadence, build_communities, platform_identities, platform_identity


def event(event_id, day, **extra):
    value = {
        "id": event_id, "title": f"Event {event_id}", "date": day,
        "source": "meetup", "sourceUrl": f"https://www.meetup.com/chess-nyc/events/{event_id}/",
        "categories": ["games"],
        "location": {"name": "Cafe", "neighborhood": "williamsburg"},
    }
    value.update(extra)
    return value


def test_exact_meetup_identity_links_events_without_replacing_schema(tmp_path, monkeypatch):
    import scrapers.communities as module
    monkeypatch.setattr(module, "HISTORY_PATH", tmp_path / "history.json")
    monkeypatch.setattr(module, "CANDIDATES_PATH", tmp_path / "candidates.json")
    monkeypatch.setattr(module, "PUBLIC_PATHS", (tmp_path / "communities.json",))
    events = [event("a", "2026-08-11"), event("b", "2026-08-18")]
    result = build_communities(events, today=date(2026, 8, 6))
    assert len(result) == 1
    assert result[0]["schedule"]["cadence"] == "weekly"
    assert result[0]["kind"] == "club"
    assert result[0]["activity"]["upcomingEventCount"] == 2
    assert events[0]["primaryCommunityId"] == result[0]["id"]
    assert events[0]["communityIds"] == [result[0]["id"]]


def test_same_name_different_platform_ids_do_not_merge(tmp_path, monkeypatch):
    import scrapers.communities as module
    monkeypatch.setattr(module, "HISTORY_PATH", tmp_path / "history.json")
    monkeypatch.setattr(module, "CANDIDATES_PATH", tmp_path / "candidates.json")
    monkeypatch.setattr(module, "PUBLIC_PATHS", (tmp_path / "communities.json",))
    a = event("a", "2026-08-11", organizer="Chess NYC", organizerUrl="https://eventbrite.com/o/111", source="eventbrite", sourceUrl="https://eventbrite.com/e/a")
    b = event("b", "2026-08-12", organizer="Chess NYC", organizerUrl="https://eventbrite.com/o/222", source="eventbrite", sourceUrl="https://eventbrite.com/e/b")
    result = build_communities([a, b], today=date(2026, 8, 6))
    assert result == []
    candidates = json.loads((tmp_path / "candidates.json").read_text())["candidates"]
    assert len(candidates) == 2
    assert candidates[0]["identity"] != candidates[1]["identity"]


def test_instagram_publishers_are_candidates_not_automatic_communities(tmp_path, monkeypatch):
    import scrapers.communities as module
    monkeypatch.setattr(module, "HISTORY_PATH", tmp_path / "history.json")
    monkeypatch.setattr(module, "CANDIDATES_PATH", tmp_path / "candidates.json")
    monkeypatch.setattr(module, "PUBLIC_PATHS", (tmp_path / "communities.json",))
    ig = event("ig", "2026-08-11", source="instagram", sourceUrl="https://instagram.com/p/x", instagramAccount="nyc-media")
    assert build_communities([ig], today=date(2026, 8, 6)) == []
    assert "communityIds" not in ig


def test_cadence_requires_two_distinct_observations():
    assert _cadence([{"date": "2026-08-11"}]) is None
    cadence = _cadence([{"date": "2026-08-11"}, {"date": "2026-09-08"}])
    assert cadence["label"] == "monthly"
    assert cadence["sampleSize"] == 2


def test_luma_calendar_identity_is_canonical():
    identity = platform_identity({"source": "luma", "account": "reading-rhythms"})
    assert identity[0] == "luma:reading-rhythms"


def test_organizer_refs_link_cohosts_and_ignore_venues(tmp_path, monkeypatch):
    import scrapers.communities as module
    monkeypatch.setattr(module, "HISTORY_PATH", tmp_path / "history.json")
    monkeypatch.setattr(module, "CANDIDATES_PATH", tmp_path / "candidates.json")
    monkeypatch.setattr(module, "PUBLIC_PATHS", (tmp_path / "communities.json",))
    item = event("a", "2026-08-11", organizerRefs=[
        {"platform": "partiful", "externalId": "host-1", "name": "Chess Club", "role": "organizer", "url": "https://partiful.com/u/host-1"},
        {"platform": "instagram", "handle": "cohost", "name": "Co Host", "role": "cohost", "url": "https://instagram.com/cohost"},
        {"platform": "maps", "externalId": "cafe", "name": "Cafe", "role": "venue"},
    ])
    assert len(platform_identities(item)) == 3  # two hosts + cohost's IG alias
    result = build_communities([item], today=date(2026, 8, 6))
    assert result == []
    assert "communityIds" not in item


def test_partiful_host_and_instagram_alias_resolve_to_one_community(tmp_path, monkeypatch):
    import scrapers.communities as module
    monkeypatch.setattr(module, "HISTORY_PATH", tmp_path / "history.json")
    monkeypatch.setattr(module, "CANDIDATES_PATH", tmp_path / "candidates.json")
    monkeypatch.setattr(module, "PUBLIC_PATHS", (tmp_path / "communities.json",))
    hosted = event("p", "2026-08-11", source="partiful", sourceUrl="https://partiful.com/e/p", organizerRefs=[
        {"platform": "partiful", "externalId": "owner-1", "name": "Chess Friends", "handle": "chessfriends", "role": "host"},
        {"platform": "partiful", "externalId": "owner-2", "name": "Game Night", "handle": "gamenight", "role": "cohost"},
    ])
    instagram = event("i", "2026-08-18", source="instagram", sourceUrl="https://instagram.com/p/i", instagramAccount="chessfriends")
    result = build_communities([hosted, instagram], today=date(2026, 8, 6))
    assert len(result) == 1
    primary = next(c for c in result if c["name"] == "Chess Friends")
    assert instagram["primaryCommunityId"] == primary["id"]
    assert primary["id"] in hosted["communityIds"]
    assert not any(c["name"] == "Game Night" for c in result)


def test_exact_analog_match_adds_attributed_reference_only(tmp_path, monkeypatch):
    import scrapers.communities as module
    community_id = module._community_id("meetup:chess-nyc")
    analog_path = tmp_path / "analog.json"
    analog_path.write_text(json.dumps({"communities": [{
        "matchedCommunityId": community_id,
        "sourceUrl": "https://analog.directory/communities/chess-nyc",
    }]}))
    monkeypatch.setattr(module, "ANALOG_INDEX_PATH", analog_path)
    monkeypatch.setattr(module, "HISTORY_PATH", tmp_path / "history.json")
    monkeypatch.setattr(module, "CANDIDATES_PATH", tmp_path / "candidates.json")
    monkeypatch.setattr(module, "PUBLIC_PATHS", (tmp_path / "communities.json",))
    result = build_communities([event("a", "2026-08-11"), event("b", "2026-08-18")], today=date(2026, 8, 6))
    assert result[0]["links"][-1] == {
        "type": "directory_reference",
        "label": "Analog Directory reference",
        "url": "https://analog.directory/communities/chess-nyc",
    }
    assert "Analog Directory (reference)" in result[0]["sourceAttributions"]


def test_recurring_community_has_factual_description_and_newcomer_evidence(tmp_path, monkeypatch):
    import scrapers.communities as module
    monkeypatch.setattr(module, "HISTORY_PATH", tmp_path / "history.json")
    monkeypatch.setattr(module, "CANDIDATES_PATH", tmp_path / "candidates.json")
    monkeypatch.setattr(module, "PUBLIC_PATHS", (tmp_path / "communities.json",))
    events = [
        event("a", "2026-08-11", title="Beginner chess night", description="No experience needed; beginners welcome."),
        event("b", "2026-08-18", title="Chess night"),
    ]
    result = build_communities(events, today=date(2026, 8, 6))
    assert result[0]["verificationStatus"] == "observed_recurring"
    assert result[0]["verified"] is False
    assert result[0]["newcomerFriendly"] is True
    assert "Based on 2 observed event dates" in result[0]["description"]


def test_community_display_name_collapses_source_whitespace(tmp_path, monkeypatch):
    import scrapers.communities as module
    monkeypatch.setattr(module, "HISTORY_PATH", tmp_path / "history.json")
    monkeypatch.setattr(module, "CANDIDATES_PATH", tmp_path / "candidates.json")
    monkeypatch.setattr(module, "PUBLIC_PATHS", (tmp_path / "communities.json",))
    events = [
        event("a", "2026-08-11", organizer="A  Club", organizerUrl="https://example.com/a-club"),
        event("b", "2026-08-18", organizer="A  Club", organizerUrl="https://example.com/a-club"),
    ]

    result = build_communities(events, today=date(2026, 8, 6))

    assert result[0]["name"] == "A Club"


def test_recurring_media_publisher_and_personal_partiful_host_stay_candidates(tmp_path, monkeypatch):
    import scrapers.communities as module
    monkeypatch.setattr(module, "HISTORY_PATH", tmp_path / "history.json")
    monkeypatch.setattr(module, "CANDIDATES_PATH", tmp_path / "candidates.json")
    monkeypatch.setattr(module, "PUBLIC_PATHS", (tmp_path / "communities.json",))
    media = [
        event("i1", "2026-08-11", source="instagram", sourceUrl="https://instagram.com/p/1", instagramAccount="explorenyc"),
        event("i2", "2026-08-18", source="instagram", sourceUrl="https://instagram.com/p/2", instagramAccount="explorenyc"),
    ]
    people = [
        event("p1", "2026-08-12", source="partiful", sourceUrl="https://partiful.com/e/1", organizerRefs=[{"platform": "partiful", "externalId": "julia", "name": "Julia", "role": "host"}]),
        event("p2", "2026-08-19", source="partiful", sourceUrl="https://partiful.com/e/2", organizerRefs=[{"platform": "partiful", "externalId": "julia", "name": "Julia", "role": "host"}]),
    ]
    assert build_communities(media + people, today=date(2026, 8, 6)) == []
    candidates = json.loads((tmp_path / "candidates.json").read_text())["candidates"]
    assert {candidate["reason"] for candidate in candidates} == {
        "publisher_not_confirmed_as_community",
        "personal_host_not_confirmed_as_community",
    }
