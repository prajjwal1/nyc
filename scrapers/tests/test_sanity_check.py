import json

import pytest

from scrapers import sanity_check
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


def successful_history():
    return [
        {
            "timestamp": f"2026-10-{day:02}T12:01:00Z",
            "snapshot_updated": f"2026-10-{day:02}T12:00:00Z",
            "sources": {"nycforfree": 53},
            "critical_failures": [],
            "run_completed": True,
        }
        for day in range(18, 23)
    ]


@pytest.mark.parametrize("failure", [
    {"critical_failures": ["Free events"]},
    {"run_completed": False},
    {"partial_run": True},
    {"timed_out_sources": ["nycforfree"]},
])
def test_failed_or_incomplete_runs_cannot_hide_source_cliffs(failure):
    records = successful_history()
    records.extend({
        "timestamp": f"2026-10-{day:02}T12:00:00Z",
        "sources": {"eventbrite": 100},
        **failure,
    } for day in range(23, 26))
    assert _source_yield_cliffs({}, records) == [{
        "source": "nycforfree", "median": 53,
        "lastNonzeroAt": "2026-10-22T12:00:00Z",
    }]


def test_repeated_checks_of_one_snapshot_do_not_replace_five_run_history():
    records = successful_history()
    for minute in range(4):
        records.append({
            "timestamp": f"2026-10-23T12:0{minute}:00Z",
            "snapshot_updated": "2026-10-23T12:00:00Z",
            "sources": {"eventbrite": 100},
            "run_completed": True,
        })
    assert _source_yield_cliffs({}, records)[0]["source"] == "nycforfree"


def test_current_snapshot_does_not_count_as_its_own_baseline():
    records = successful_history()
    records[-2]["sources"] = {}
    records[-1]["sources"] = {}
    stamp = "2026-10-23T12:00:00Z"
    records.append({"timestamp": stamp, "snapshot_updated": stamp, "sources": {}})
    assert _source_yield_cliffs({}, records, snapshot_updated=stamp)[0]["median"] == 53
    assert _source_yield_cliffs({}, records) == []


def test_source_cliffs_require_five_valid_distinct_snapshots():
    records = successful_history()[:4]
    records.extend([None, [], {"sources": []}, {"sources": {"nycforfree": "bad"}},
                    {"sources": {"nycforfree": -5}}, {"sources": {"nycforfree": True}}])
    records.extend([records[0]] * 6)
    assert _source_yield_cliffs({}, records) == []


def test_stats_preserve_snapshot_identity_and_run_health(tmp_path, monkeypatch):
    monkeypatch.setattr(sanity_check, "__file__", str(tmp_path / "sanity_check.py"))
    sanity_check._append_stats(
        total=100, sources={"eventbrite": 100}, cats={}, failures=[], warnings=[],
        age_hours=0, snapshot_updated="2026-10-26T12:00:00Z",
        run={"runCompleted": True, "partialRun": True, "timedOutSources": ["luma"]},
    )
    record = json.loads((tmp_path / "data" / "stats_history.jsonl").read_text())
    assert record["snapshot_updated"] == "2026-10-26T12:00:00Z"
    assert record["run_completed"] is True
    assert record["partial_run"] is True
    assert record["timed_out_sources"] == ["luma"]


def test_source_cliff_is_a_nonfatal_warning_with_timestamp(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sanity_check, "__file__", str(tmp_path / "sanity_check.py"))
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "stats_history.jsonl").write_text(
        "\n".join(json.dumps(record) for record in successful_history()) + "\ninvalid-json\n"
    )
    assert sanity_check._print_source_regressions({}) is None
    output = capsys.readouterr().out
    assert "nycforfree: rolling median 53 → 0" in output
    assert "last non-zero 2026-10-22T12:00:00Z" in output
