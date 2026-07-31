import json

from scrapers.utils import discovery_plan


def _event(i, score, categories):
    return {
        "id": str(i), "title": f"Event {i}", "description": "",
        "categories": categories, "score": score, "sourceUrl": "https://example.com/e",
    }


def test_select_mixed_reserves_exploration(monkeypatch):
    prefs = {
        "categories": {"books": 8}, "neg_categories": {}, "accounts": {},
        "hosts": {}, "topics": {}, "signal_accounts": set(),
        "curated_hosts": set(), "excluded_accounts": set(), "excluded_hosts": set(),
    }
    monkeypatch.setattr(discovery_plan, "preference_snapshot", lambda: prefs)
    events = [_event(i, 1 - i / 100, ["books"]) for i in range(10)]
    events += [_event(i + 10, .8 - i / 100, ["art"]) for i in range(10)]
    selected = discovery_plan.select_mixed(events, 10)
    assert sum(e["discoveryLane"] == "personal" for e in selected) == 7
    assert sum(e["discoveryLane"] == "explore" for e in selected) == 3


def test_organizer_match_produces_explanation():
    prefs = {
        "categories": {}, "neg_categories": {}, "accounts": {"reading rhythms": 5},
        "hosts": {}, "topics": {}, "signal_accounts": set(),
        "curated_hosts": set(), "excluded_accounts": set(), "excluded_hosts": set(),
    }
    event = _event(1, .8, ["books"])
    event["organizer"] = "Reading Rhythms"
    discovery_plan.annotate_event(event, prefs)
    assert event["discoveryLane"] == "personal"
    assert event["recommendationReasons"][0] == "From Reading Rhythms"
