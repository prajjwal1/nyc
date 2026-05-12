"""Lightweight perceptual image hashing for event-flyer dedup.

Uses average-hash (aHash) — resize to 8x8 grayscale, threshold each pixel
against the mean, output 64 bits as hex. Captures "same flyer" semantics
across CDN URL variants and minor compression differences.

Cached by image URL in scrapers/data/image_hashes.json so repeat runs
don't re-download the same flyers. Network/PIL failures degrade gracefully
to None — no event ever gets dropped because hashing failed.
"""

from __future__ import annotations

import json
import os
from typing import Optional

import httpx

_HASH_CACHE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "image_hashes.json",
)


def _load_cache() -> dict:
    if not os.path.isfile(_HASH_CACHE_PATH):
        return {}
    try:
        with open(_HASH_CACHE_PATH) as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save_cache(cache: dict) -> None:
    try:
        os.makedirs(os.path.dirname(_HASH_CACHE_PATH), exist_ok=True)
        tmp = _HASH_CACHE_PATH + ".tmp"
        with open(tmp, "w") as f:
            json.dump(cache, f)
        os.replace(tmp, _HASH_CACHE_PATH)
    except Exception:
        pass


_CACHE: Optional[dict] = None
_DIRTY = False


def _ahash_from_bytes(image_bytes: bytes) -> Optional[str]:
    """Compute 64-bit aHash from image bytes. Returns 16-char hex or None."""
    try:
        from PIL import Image  # type: ignore
    except ImportError:
        return None
    try:
        from io import BytesIO
        img = Image.open(BytesIO(image_bytes)).convert("L").resize((8, 8))
    except Exception:
        return None
    pixels = list(img.getdata())
    if len(pixels) != 64:
        return None
    avg = sum(pixels) / 64
    bits = 0
    for i, p in enumerate(pixels):
        if p >= avg:
            bits |= (1 << (63 - i))
    return f"{bits:016x}"


def _normalize_url(url: str) -> str:
    """Drop CDN auth tokens / cache-busting params so the same image
    re-fetched on a different request maps to the same cache key."""
    return (url or "").split("?")[0].split("#")[0]


def compute_phash(image_url: str, *, timeout: float = 8.0) -> Optional[str]:
    """Return a perceptual hash for the image at `image_url`, or None.

    Downloads + hashes once per normalized URL; cached on disk so repeat
    runs don't re-fetch. Returns None if PIL is unavailable, the URL is
    empty/too short, the network fails, or the image can't be decoded.
    """
    global _CACHE, _DIRTY
    if _CACHE is None:
        _CACHE = _load_cache()

    if not image_url or len(image_url) < 30:
        return None
    key = _normalize_url(image_url)
    cached = _CACHE.get(key)
    if cached:
        # Cache stores either the hex hash or the sentinel "" (failed).
        return cached or None

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(image_url)
            if resp.status_code != 200:
                _CACHE[key] = ""
                _DIRTY = True
                return None
            data = resp.content
    except Exception:
        # Don't cache transient network failures — they may succeed next run.
        return None

    if not data or len(data) < 1024:
        _CACHE[key] = ""
        _DIRTY = True
        return None

    h = _ahash_from_bytes(data)
    _CACHE[key] = h or ""
    _DIRTY = True
    return h


def hamming_distance(a: str, b: str) -> int:
    """Hamming distance between two 16-char hex hashes (max 64)."""
    if not a or not b or len(a) != len(b):
        return 64
    try:
        return bin(int(a, 16) ^ int(b, 16)).count("1")
    except ValueError:
        return 64


def flush_cache() -> None:
    """Persist the in-memory hash cache to disk. Call once per scrape run."""
    global _DIRTY
    if _DIRTY and _CACHE is not None:
        _save_cache(_CACHE)
        _DIRTY = False
