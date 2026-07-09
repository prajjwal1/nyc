"""Tests for the client-engagement -> preference-layer ingest (WS1)."""
import json

from scrapers.utils.engagement import apply_engagement


def _seed(data_dir):
    (data_dir / "user_curated_sources.json").write_text(json.dumps({
        "hosts": {"litclub.nyc": {"score": 1.0, "added_at": "2026-05-14", "source": "user_mentioned"}},
        "title_hints": {},
    }))
    (data_dir / "user_excluded_sources.json").write_text(json.dumps({
        "accounts": {"houseofyesnyc": {"reason": "user_mentioned_clubs", "added_at": "2026-05-18"}},
        "hosts": {}, "title_hints": {},
    }))


def _write_snapshot(data_dir, **maps):
    payload = {"updatedAt": "2026-07-09T00:00:00Z"}
    payload.update(maps)
    (data_dir / "user_engagement.json").write_text(json.dumps(payload))


def test_noop_when_absent(tmp_path):
    _seed(tmp_path)
    out = apply_engagement(str(tmp_path))
    assert out["present"] is False
    assert out["curated_added"] == 0 and out["excluded_added"] == 0


def test_positive_host_grows_curated(tmp_path):
    _seed(tmp_path)
    _write_snapshot(tmp_path, hosts={"nowadays.nyc": 8}, accounts={"harlemrun": 6})
    out = apply_engagement(str(tmp_path))
    assert out["curated_added"] == 2
    curated = json.loads((tmp_path / "user_curated_sources.json").read_text())
    assert "nowadays.nyc" in curated["hosts"]
    assert curated["hosts"]["nowadays.nyc"]["source"] == "engagement_saved"
    assert "harlemrun" in curated["hosts"]  # engaged IG handle also curated
    assert "litclub.nyc" in curated["hosts"]  # human entry preserved


def test_weak_signal_below_threshold_ignored(tmp_path):
    _seed(tmp_path)
    _write_snapshot(tmp_path, hosts={"weaksite.com": 3})  # < POS_THRESHOLD(5)
    out = apply_engagement(str(tmp_path))
    assert out["curated_added"] == 0


def test_too_broad_host_skipped(tmp_path):
    _seed(tmp_path)
    _write_snapshot(tmp_path, hosts={"eventbrite.com": 50})
    out = apply_engagement(str(tmp_path))
    assert out["curated_added"] == 0
    curated = json.loads((tmp_path / "user_curated_sources.json").read_text())
    assert "eventbrite.com" not in curated["hosts"]


def test_repeated_hides_grow_excluded(tmp_path):
    _seed(tmp_path)
    _write_snapshot(tmp_path, negAccounts={"spamclub": 4}, negHosts={"spamsite.com": 3})
    out = apply_engagement(str(tmp_path))
    assert out["excluded_added"] == 2
    excl = json.loads((tmp_path / "user_excluded_sources.json").read_text())
    assert "spamclub" in excl["accounts"] and "spamsite.com" in excl["hosts"]


def test_hide_beats_save_conflict(tmp_path):
    # Same host both engaged AND hidden repeatedly -> exclusion wins, not curated.
    _seed(tmp_path)
    _write_snapshot(tmp_path, hosts={"mixed.com": 9}, negHosts={"mixed.com": 4})
    out = apply_engagement(str(tmp_path))
    curated = json.loads((tmp_path / "user_curated_sources.json").read_text())
    excl = json.loads((tmp_path / "user_excluded_sources.json").read_text())
    assert "mixed.com" in excl["hosts"]
    assert "mixed.com" not in curated["hosts"]
    assert out["skipped_conflict"] >= 1


def test_idempotent(tmp_path):
    _seed(tmp_path)
    _write_snapshot(tmp_path, hosts={"nowadays.nyc": 8}, negAccounts={"spamclub": 4})
    first = apply_engagement(str(tmp_path))
    second = apply_engagement(str(tmp_path))
    assert first["curated_added"] == 1 and first["excluded_added"] == 1
    assert second["curated_added"] == 0 and second["excluded_added"] == 0
