import json
import os
import re
import tempfile

import httpx

from .event_parser import parse_date, parse_time

_SKIP = os.environ.get("SKIP_IMAGE_ANALYSIS", "0") == "1"


def analyze_event_image(image_url: str) -> dict | None:
    if _SKIP or not image_url:
        return None

    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return None

    try:
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            resp = client.get(image_url)
            resp.raise_for_status()

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(resp.content)
            tmp_path = f.name

        try:
            img = Image.open(tmp_path)
            text = pytesseract.image_to_string(img)
        finally:
            os.unlink(tmp_path)

        if not text or len(text.strip()) < 10:
            return None

        return _parse_ocr_text(text)

    except Exception:
        return None


def _parse_ocr_text(text: str) -> dict:
    result = {}

    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if lines:
        for line in lines:
            cleaned = re.sub(r"[^a-zA-Z0-9\s&'\-]", "", line).strip()
            if 5 < len(cleaned) < 100:
                result["title"] = cleaned
                break

    date_patterns = [
        r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:\s*,?\s*\d{4})?",
        r"\d{1,2}/\d{1,2}(?:/\d{2,4})?",
        r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+\w+\s+\d{1,2}",
    ]
    for pat in date_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            d = parse_date(m.group())
            if d:
                result["date"] = d.isoformat()
                break

    t = parse_time(text)
    if t:
        result["time"] = t

    loc_patterns = [
        r"(?:at|@)\s+([A-Z][A-Za-z\s&']+?)(?:\n|$|,)",
        r"(\d{1,5}\s+[A-Z][A-Za-z]+(?:\s+[A-Za-z]+)?\s+(?:St|Ave|Blvd|Rd|Pl|Dr)\.?)",
    ]
    for pat in loc_patterns:
        m = re.search(pat, text)
        if m:
            result["location"] = m.group(1).strip()
            break

    return result if result else None
