from scrapers.sanity_check import (
    _active_follow_accounts,
    _feed_horizon_days,
    _source_yield_cliffs,
    _today_event_count,
)


def test_active_follow_accounts_excludes_past_events():
    events = [
        {
            "date": "2026-09-02",
            "userFollowing": True,
            "account": "past_club",
        },
        {
            "date": "2026-09-03",
            "userFollowing": True,
            "account": "today_club",
        },
        {
            "date": "2026-09-04",
            "userFollowing": True,
            "account": "future_club_nyc",
        },
    ]

    assert _active_follow_accounts(
        events,
        ["past_club", "today_club", "future_club"],
        today="2026-09-03",
    ) == {"today_club", "future_club"}


def test_today_coverage_and_future_horizon():
    events = [
        {"date": "2026-09-09"},
        {"date": "2026-09-10"},
        {"date": "2026-11-20"},
    ]

    assert _today_event_count(events, today="2026-09-10") == 1
    assert _feed_horizon_days(events, today="2026-09-10") == 71


def test_source_yield_cliff_warns_for_large_drop_and_includes_timestamp():
    records = [
        {"timestamp": f"2026-09-0{day}T12:00:00Z", "sources": {"nycforfree": count}}
        for day, count in enumerate([51, 53, 55, 52, 54], start=1)
    ]

    assert _source_yield_cliffs({}, records) == [{
        "source": "nycforfree",
        "median": 53,
        "lastNonzeroAt": "2026-09-05T12:00:00Z",
    }]


def test_source_yield_cliff_ignores_seasonal_one_to_zero():
    records = [
        {"timestamp": f"2026-09-0{day}T12:00:00Z", "sources": {"seasonal": count}}
        for day, count in enumerate([1, 0, 1, 0, 1], start=1)
    ]

    assert _source_yield_cliffs({}, records) == []
