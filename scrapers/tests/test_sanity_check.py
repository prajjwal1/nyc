from scrapers.sanity_check import _active_follow_accounts


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
