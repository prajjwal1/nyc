from scrapers.ranking_audit import evaluate_ranked_feed


def _event(i, *, source="luma", organizer=None, categories=None, lane="explore", title=None):
    return {
        "id": str(i),
        "title": title or f"Event {i}",
        "date": "2026-09-01",
        "score": 1 - i / 100,
        "source": source,
        "organizer": organizer or f"Organizer {i}",
        "categories": categories or ["art"],
        "discoveryLane": lane,
    }


def test_ranked_feed_evaluation_measures_relevance_and_diversity():
    events = [
        _event(i, source="luma" if i < 3 else "eventbrite", categories=["art" if i % 2 else "music"], lane="personal" if i < 4 else "explore")
        for i in range(6)
    ]
    result = evaluate_ranked_feed(events, top_n=6, today="2026-08-01")

    assert result["personalRatio"] == 0.667
    assert result["distinctOrganizers"] == 6
    assert result["distinctCategories"] == 2
    assert result["topSourceShare"] == 0.5


def test_ranked_feed_evaluation_normalizes_recurring_series_dates():
    events = [
        _event(0, organizer="Reading Club", title="Reading Night August 20"),
        _event(1, organizer="Reading Club", title="Reading Night August 27"),
    ]
    result = evaluate_ranked_feed(events, top_n=2, today="2026-08-01")
    assert result["maxRepeatedSeries"] == 2
