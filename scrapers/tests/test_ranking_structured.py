from scrapers.ranking import compute_score


def test_structured_bookmanager_title_survives_generic_caption_rule():
    event = {
        "title": "Celebrate Patricia Lockwood with a reading and conversation",
        "description": "Liz's Book Bar hosts a literary evening with the author.",
        "date": "2026-09-10",
        "startTime": "19:00",
        "source": "bookmanager",
        "sourceUrl": "https://www.lizsbookbar.com/event/patricia-lockwood",
        "location": {
            "name": "Liz's Book Bar",
            "address": "315 Smith St, Brooklyn, NY",
            "neighborhood": "carroll gardens",
        },
        "categories": ["books"],
        "structuredTitle": True,
    }

    assert compute_score(event) > 0
