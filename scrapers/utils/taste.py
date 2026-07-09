"""Semantic taste model (WS2) — rank by similarity to what the user actually
saves/attends, so recommendations generalize WITHOUT hand-keyword lists.

"Semantic" here is a dependency-free TF-IDF-over-the-corpus model (no torch, no
model download — the pipeline runs in rate-limited CI every ~30 min). It learns
from the TEXT of events the user engaged with (synced via tasteExport.ts into
`user_engagement.json` → `positiveTexts` / `negativeTexts`) and scores each new
event by cosine similarity to the positive taste centroid, minus similarity to
the negative one. So "more like the MoMA Warm Up" surfaces other underground-
electronic events automatically — the terms that co-occur in liked events win,
learned rather than hardcoded.

Inert (returns 0.0) until the user has synced some liked-event text, so it never
harms cold-start ranking. The backend is intentionally swappable: `_vectorize`
could later be replaced with transformer embeddings behind a flag.
"""
from __future__ import annotations

import json
import math
import os
import re

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

# Bounds for the taste signal's contribution to ranking.
MAX_BOOST = 0.15
MAX_PENALTY = 0.10
_SCALE = 0.35  # cosine (0..1) → boost; tuned so a close match lands near MAX_BOOST
_NEG_WEIGHT = 0.5

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOP = frozenset(
    "the a an and or of for to in on at by with from your you this that is are "
    "we our nyc new york city event events night day pm am".split()
)


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall((text or "").lower()) if len(t) > 2 and t not in _STOP]


def _event_text(e: dict) -> str:
    loc = e.get("location") or {}
    return " ".join(
        [
            e.get("title", ""),
            e.get("description", "") or "",
            " ".join(e.get("categories") or []),
            loc.get("name", "") if isinstance(loc, dict) else "",
        ]
    )


class TasteModel:
    """Built once per ranking batch; `score(event)` is cheap per-event."""

    def __init__(self, idf: dict[str, float], pos: dict[str, float], neg: dict[str, float], default_idf: float = 1.0):
        self._idf = idf
        self._pos = pos  # normalized tf-idf centroid of liked events
        self._neg = neg
        self._idf_default = default_idf
        self.active = bool(pos)

    def _vectorize(self, text: str) -> dict[str, float]:
        toks = _tokens(text)
        if not toks:
            return {}
        tf: dict[str, float] = {}
        for t in toks:
            tf[t] = tf.get(t, 0.0) + 1.0
        vec = {t: (c / len(toks)) * self._idf.get(t, self._default_idf) for t, c in tf.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {t: v / norm for t, v in vec.items()}

    @property
    def _default_idf(self) -> float:
        # Unknown terms treated as moderately rare.
        return self._idf_default

    def score(self, event: dict) -> float:
        if not self.active:
            return 0.0
        vec = self._vectorize(_event_text(event))
        if not vec:
            return 0.0
        pos_sim = sum(vec.get(t, 0.0) * w for t, w in self._pos.items())
        neg_sim = sum(vec.get(t, 0.0) * w for t, w in self._neg.items()) if self._neg else 0.0
        raw = (pos_sim - _NEG_WEIGHT * neg_sim) * _SCALE
        return max(-MAX_PENALTY, min(MAX_BOOST, raw))


def _centroid(texts: list[str], idf: dict[str, float], default_idf: float) -> dict[str, float]:
    """Sum L2-normalized tf-idf vectors of the example texts, then normalize."""
    acc: dict[str, float] = {}
    for text in texts:
        toks = _tokens(text)
        if not toks:
            continue
        tf: dict[str, float] = {}
        for t in toks:
            tf[t] = tf.get(t, 0.0) + 1.0
        vec = {t: (c / len(toks)) * idf.get(t, default_idf) for t, c in tf.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        for t, v in vec.items():
            acc[t] = acc.get(t, 0.0) + v / norm
    norm = math.sqrt(sum(v * v for v in acc.values())) or 1.0
    return {t: v / norm for t, v in acc.items()}


def build_taste_model(events: list[dict], data_dir: str = _DATA_DIR) -> TasteModel:
    """Compute corpus IDF over `events` and pos/neg taste centroids from the
    synced engagement snapshot. Inert model if there's no liked-event text."""
    # Corpus document frequencies for IDF.
    n = max(1, len(events))
    df: dict[str, int] = {}
    for e in events:
        for t in set(_tokens(_event_text(e))):
            df[t] = df.get(t, 0) + 1
    idf = {t: math.log(n / (1 + c)) + 1.0 for t, c in df.items()}
    default_idf = math.log(n / 1.0) + 1.0

    pos_texts: list[str] = []
    neg_texts: list[str] = []
    try:
        with open(os.path.join(data_dir, "user_engagement.json")) as f:
            snap = json.load(f)
        pos_texts = [t for t in (snap.get("positiveTexts") or []) if t and t.strip()]
        neg_texts = [t for t in (snap.get("negativeTexts") or []) if t and t.strip()]
    except Exception:
        pass

    pos = _centroid(pos_texts, idf, default_idf) if pos_texts else {}
    neg = _centroid(neg_texts, idf, default_idf) if neg_texts else {}
    return TasteModel(idf, pos, neg, default_idf)
