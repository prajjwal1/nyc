"""Tests for the fb-202 top-of-feed diversity penalty + music-slot guarantee."""
from scrapers.ranking import _apply_diversity_penalty, _diversity_primary_topic


def _ev(score, account, cats, title="Event", **kw):
    e = {"score": score, "account": account, "categories": cats, "title": title,
         "source": "eventbrite"}
    e.update(kw)
    return e


def test_single_source_pileup_capped():
    # One venue with 10 near-max books events + a few other-topic events.
    events = [_ev(0.99 - i * 0.01, "megavenue", ["books"], f"Book {i}") for i in range(10)]
    # A realistic pool of diverse single-source alternatives (as the real feed
    # has hundreds), each its own source+topic so they take no penalty.
    alt = [("runco", "fitness", "Run Club"), ("comco", "comedy", "Comedy Night"),
           ("danceco", "dance", "Swing Social"), ("artco", "art", "Gallery Hop"),
           ("foodco", "food", "Supper Club"), ("outco", "outdoors", "Park Walk"),
           ("gameco", "games", "Chess Night"), ("filmco", "film", "Screening")]
    events += [_ev(0.86 - i * 0.005, a, [c], t) for i, (a, c, t) in enumerate(alt)]
    _apply_diversity_penalty(events)
    top8 = sorted(events, key=lambda x: -x["score"])[:8]
    mega_in_top8 = sum(1 for e in top8 if e["account"] == "megavenue")
    assert mega_in_top8 <= 3, f"pile-up not capped: {mega_in_top8} megavenue in top-8"
    assert any(e["account"] != "megavenue" for e in top8)


def test_top1_and_floor_clamp_invariant():
    events = [_ev(0.99 - i * 0.01, "megavenue", ["books"], f"Book {i}") for i in range(10)]
    starts = {id(e): e["score"] for e in events}
    top1_before = max(events, key=lambda x: x["score"])
    _apply_diversity_penalty(events)
    # top-1 (best base) is never demoted
    assert max(events, key=lambda x: x["score"]) is top1_before
    # floor-clamp: nothing that started >=0.55 ends <0.55 (non-conviction floor)
    for e in events:
        if starts[id(e)] >= 0.55:
            assert e["score"] >= 0.55, f"floor clamp broken: {e['title']} → {e['score']}"


def test_music_slot_guarantee():
    # 12 non-music events across 6 sources (2 each → no penalty) all ~0.90,
    # one music event well below. Without the slot, music is rank 13.
    events = []
    for s in range(6):
        for j in range(2):
            events.append(_ev(0.90, f"src{s}", ["books"], f"Book s{s} j{j}"))
    events.append(_ev(0.60, "djco", ["other"], "Pearly Drops, RIP Swirl (DJ)"))
    _apply_diversity_penalty(events)
    top12 = sorted(events, key=lambda x: -x["score"])[:12]
    assert any(_diversity_primary_topic(e) == "music" for e in top12), \
        "music-slot guarantee failed — no music/electronic event in top-12"


def test_dj_title_detected_as_music_topic():
    assert _diversity_primary_topic({"title": "Pearly Drops, RIP Swirl (DJ)", "categories": ["other"]}) == "music"
    assert _diversity_primary_topic({"title": "Warm Up: Carlos Souffront", "categories": ["other"]}) == "music"
    # a bare 'dj' inside a word must NOT trigger
    assert _diversity_primary_topic({"title": "Adjacent Possible talk", "categories": ["books"]}) != "music"


def test_conviction_event_not_displaced_by_music_slot():
    # All 12 top slots are conviction → music slot must NOT displace conviction.
    events = [_ev(0.95, f"src{i}", ["books"], f"Book {i}", userFollowing=True) for i in range(12)]
    events.append(_ev(0.60, "djco", ["music"], "Techno Night"))
    _apply_diversity_penalty(events)
    top12 = sorted(events, key=lambda x: -x["score"])[:12]
    assert all(e.get("userFollowing") for e in top12), "conviction event wrongly displaced"
