from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from scrapers import discover
from scrapers.discover import SCORE_THRESHOLD, score_event_account
from scrapers.sources import instagram_bios
from scrapers.utils.recurring_profiles import (
    NY_TZ,
    assess_profile,
    events_from_state,
    extract_schedules,
    parse_profile_html,
    update_profile_state,
)


NBD_HTML = '''
<meta content="8,466 Followers, 511 Following, 127 Posts - No Bad Days Run Club
(@nbd_rc) on Instagram: &quot;Social with a sweat 🩵&#10;Running with @on ☁️&#10;
Thursday 6:45pm @ ON store, WillyB&#10;Lead: @nathan_putrich&quot;" name="description" />
'''

VITAL_HTML = '''
<meta content="2,162 Followers, 92 Following, 100 Posts - VRC (@vitalrunclub) on Instagram:
&quot;HOME OF THE SEXY PACE&#10;📍vital bk climbing gym&#10;🏃🏻‍♀️mondays @ 7pm&#10;
💌 hi@vitalrunclub.com&quot;" name="description" />
'''


def test_no_bad_days_profile_is_admitted_from_live_bio_shape():
    profile = parse_profile_html(NBD_HTML, "nbd_rc")
    assessed = assess_profile(profile, discovered_via="user_mentioned")

    assert assessed["followers"] == 8466
    assert assessed["qualified"] is True
    assert assessed["schedules"] == [{
        "weekday": 3,
        "startTime": "18:45",
        "locationName": "ON store, WillyB",
        "evidence": "Thursday 6:45pm @ ON store, WillyB",
    }]


def test_vital_combines_location_and_schedule_lines():
    profile = parse_profile_html(VITAL_HTML, "vitalrunclub")
    assessed = assess_profile(profile, discovered_via="user_following")

    assert assessed["qualified"] is True
    assert assessed["schedules"][0]["weekday"] == 0
    assert assessed["schedules"][0]["startTime"] == "19:00"
    assert assessed["schedules"][0]["locationName"] == "vital bk climbing gym"


def test_follower_threshold_triggers_investigation_not_publication():
    assessed = assess_profile({
        "username": "popular_person",
        "displayName": "Popular Person",
        "biography": "NYC · join me Mondays at 7pm · 📍Central Park",
        "followers": 25_000,
    }, discovered_via="suggested_for:seed")

    assert assessed["investigatedByFollowerThreshold"] is True
    assert assessed["qualified"] is False
    assert assessed["reason"] == "not_an_organization"


def test_small_club_with_strong_first_party_schedule_can_qualify():
    assessed = assess_profile({
        "username": "tinychessclubnyc",
        "displayName": "Tiny Chess Club NYC",
        "biography": "Thursdays 7pm @ Bryant Park, NYC",
        "followers": 650,
    }, discovered_via="suggested_for:nycbackgammonclub")

    assert assessed["investigatedByFollowerThreshold"] is False
    assert assessed["qualified"] is True


def test_profile_requires_actionable_location():
    assert extract_schedules("NYC Run Club\nEvery Thursday at 6:45pm") == [{
        "weekday": 3,
        "startTime": "18:45",
        "locationName": "",
        "evidence": "Every Thursday at 6:45pm",
    }]
    assessed = assess_profile({
        "username": "runclubnyc",
        "displayName": "NYC Run Club",
        "biography": "Every Thursday at 6:45pm",
        "followers": 5_000,
    })
    assert assessed["qualified"] is False
    assert assessed["reason"] == "missing_location"


def test_business_hours_are_not_treated_as_recurring_events():
    assessed = assess_profile({
        "username": "coffeestudio.nyc",
        "displayName": "Coffee Studio",
        "biography": "Japanese craft drinks\nThu-Fri 10:30am-4pm\nSat-Sun 10:30am-5pm",
        "followers": 12_000,
    }, discovered_via="suggested_for:food")

    assert assessed["schedules"] == []
    assert assessed["qualified"] is False


def test_two_successful_missing_schedule_checks_deactivate_profile():
    state = {"version": 1, "profiles": {}}
    profile = parse_profile_html(NBD_HTML, "nbd_rc")
    update_profile_state(state, profile, discovered_via="user_mentioned")
    missing = {**profile, "biography": "NYC run club — details soon"}

    first = update_profile_state(state, missing, discovered_via="user_mentioned")
    second = update_profile_state(state, missing, discovered_via="user_mentioned")

    assert first["active"] is True
    assert second["active"] is False


def test_older_browser_observation_cannot_replace_newer_profile_state():
    state = {"version": 1, "profiles": {}}
    profile = parse_profile_html(NBD_HTML, "nbd_rc")
    newer = datetime(2026, 9, 9, 16, tzinfo=timezone.utc)
    update_profile_state(state, profile, discovered_via="user_mentioned", checked_at=newer)

    result = update_profile_state(
        state,
        {**profile, "biography": "old stale biography"},
        discovered_via="browser_snapshot",
        checked_at=newer - timedelta(days=2),
    )

    assert result["biography"] == profile["biography"]
    assert result["active"] is True


def test_low_signal_profile_is_not_persisted_in_registry():
    state = {"version": 1, "profiles": {}}
    result = update_profile_state(state, {
        "username": "random_person",
        "displayName": "Random Person",
        "biography": "some photos",
        "followers": 80,
    })

    assert result["qualified"] is False
    assert state["profiles"] == {}


def test_events_generate_four_future_occurrences_and_expire():
    state = {"version": 1, "profiles": {}}
    profile = parse_profile_html(NBD_HTML, "nbd_rc")
    verified = datetime(2026, 9, 9, 16, tzinfo=timezone.utc)
    update_profile_state(state, profile, discovered_via="user_mentioned", checked_at=verified)

    events = events_from_state(state, now=datetime(2026, 9, 9, 12, tzinfo=NY_TZ))

    assert len(events) == 4
    assert events[0]["date"] == "2026-09-10"
    assert events[0]["scheduleSource"] == "instagram_bio"
    assert events[0]["organizerUrl"] == "https://www.instagram.com/nbd_rc/"
    assert all(event["date"] >= "2026-09-09" for event in events)

    expired = events_from_state(
        state,
        now=datetime(2026, 9, 25, 12, tzinfo=NY_TZ),
    )
    assert expired == []


def test_matching_cancellation_suppresses_only_one_occurrence():
    state = {"version": 1, "profiles": {}}
    update_profile_state(
        state,
        parse_profile_html(NBD_HTML, "nbd_rc"),
        discovered_via="user_mentioned",
        checked_at=datetime(2026, 9, 9, 16, tzinfo=timezone.utc),
    )
    events = events_from_state(
        state,
        now=datetime(2026, 9, 9, 12, tzinfo=NY_TZ),
        cancellations={("nbd_rc", "2026-09-10")},
    )
    assert len(events) == 3
    assert events[0]["date"] == "2026-09-17"


def test_candidate_plan_includes_suggested_accounts_beyond_follow_graph(monkeypatch):
    monkeypatch.setattr(instagram_bios, "IG_ACCOUNTS", [])
    monkeypatch.setattr(instagram_bios, "load_excluded_account_set", lambda: set())
    monkeypatch.setattr(instagram_bios, "_discovered_accounts", lambda: [
        {"username": "beyondfollowclub", "score": 0.8, "discovered_via": "suggested_for:seed"},
        {"username": "followedclub", "score": 0.4, "discovered_via": "user_following"},
    ])

    plan, _cursor = instagram_bios._candidate_plan(
        {"version": 1, "cursor": 0, "profiles": {}}, limit=2
    )

    assert {username for username, _via in plan} == {"beyondfollowclub", "followedclub"}


def test_one_thousand_follower_club_schedule_enters_discovery_pool():
    profile = SimpleNamespace(
        biography="Thursdays at 7pm · meet at the track",
        external_url="",
        full_name="Neighborhood Run Club",
        mediacount=80,
        followers=1_500,
    )

    assert score_event_account(profile) >= SCORE_THRESHOLD


def test_authenticated_discovery_persists_profile_bio(monkeypatch):
    state = {"version": 1, "profiles": {}}
    saved = []
    monkeypatch.setattr(discover, "load_recurring_state", lambda: state)
    monkeypatch.setattr(discover, "save_recurring_state", lambda value: saved.append(value))
    profile = SimpleNamespace(
        username="beyondfollowclub",
        full_name="Beyond Follow Run Club NYC",
        biography="Thursdays 7pm @ McCarren Park, Brooklyn",
        followers=1_500,
    )

    discover._persist_recurring_profile_observations([
        (profile, "suggested_for:anotherclub"),
    ])

    assert saved == [state]
    assert state["profiles"]["beyondfollowclub"]["active"] is True
