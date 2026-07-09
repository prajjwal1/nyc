"""Tests for the semantic taste model (WS2)."""
import json

from scrapers.utils.taste import build_taste_model


def _corpus():
    return [
        {"title": "Underground techno DJ set with Marcellus Pittman", "categories": ["music"], "description": "warehouse-free listening room techno"},
        {"title": "Beginner watercolor painting class", "categories": ["art"], "description": "learn watercolor basics"},
        {"title": "Silent book club reading hour", "categories": ["books"], "description": "quiet reading"},
        {"title": "Dopplereffekt live electro", "categories": ["music"], "description": "experimental electro techno"},
        {"title": "Morning yoga in the park", "categories": ["fitness"], "description": "gentle flow"},
    ]


def test_inert_without_snapshot(tmp_path):
    model = build_taste_model(_corpus(), data_dir=str(tmp_path))
    assert model.active is False
    assert model.score(_corpus()[0]) == 0.0


def test_liked_techno_ranks_similar_over_unrelated(tmp_path):
    (tmp_path / "user_engagement.json").write_text(json.dumps({
        "positiveTexts": [
            "Warm Up: Carlos Souffront Dopplereffekt techno moma ps1",
            "Underground techno DJ night experimental electro",
        ],
    }))
    corpus = _corpus()
    model = build_taste_model(corpus, data_dir=str(tmp_path))
    assert model.active is True
    techno = model.score({"title": "Late electro techno DJ set", "categories": ["music"], "description": "experimental"})
    watercolor = model.score({"title": "Beginner watercolor painting class", "categories": ["art"], "description": "learn watercolor"})
    assert techno > watercolor
    assert techno > 0  # a clear taste match gets a positive boost


def test_score_is_bounded(tmp_path):
    (tmp_path / "user_engagement.json").write_text(json.dumps({
        "positiveTexts": ["techno techno techno electro dj"],
    }))
    model = build_taste_model(_corpus(), data_dir=str(tmp_path))
    s = model.score({"title": "techno electro dj techno", "categories": ["music"], "description": "techno"})
    assert -0.10 <= s <= 0.15
