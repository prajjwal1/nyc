import hashlib
import re
from datetime import datetime, date, time

import dateparser


def make_event_id(source: str, title: str, event_date: str) -> str:
    raw = f"{source}:{title}:{event_date}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def parse_date(text: str) -> date | None:
    if not text:
        return None
    parsed = dateparser.parse(
        text,
        settings={
            "PREFER_DATES_FROM": "future",
            "RELATIVE_BASE": datetime.now(),
        },
    )
    if parsed:
        return parsed.date()
    return None


def parse_time(text: str) -> str | None:
    if not text:
        return None
    patterns = [
        r"(\d{1,2}):(\d{2})\s*(am|pm|AM|PM)",
        r"(\d{1,2})\s*(am|pm|AM|PM)",
        r"(\d{1,2}):(\d{2})",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            groups = m.groups()
            if len(groups) == 3 and ":" in pat:
                h, mi, ampm = int(groups[0]), int(groups[1]), groups[2].lower()
                if ampm == "pm" and h != 12:
                    h += 12
                if ampm == "am" and h == 12:
                    h = 0
                return f"{h:02d}:{mi:02d}"
            elif len(groups) == 2 and ":" not in pat:
                h, ampm = int(groups[0]), groups[1].lower()
                if ampm == "pm" and h != 12:
                    h += 12
                if ampm == "am" and h == 12:
                    h = 0
                return f"{h:02d}:00"
            elif len(groups) == 2:
                return f"{int(groups[0]):02d}:{int(groups[1]):02d}"
    return None


def extract_price(text: str) -> str:
    if not text:
        return "unknown"
    lower = text.lower()
    if any(w in lower for w in ["free", "$0", "no cover", "no charge", "complimentary"]):
        return "free"
    m = re.search(r"\$(\d+(?:\.\d{2})?)", text)
    if m:
        return f"${m.group(1)}"
    return "unknown"


CATEGORY_KEYWORDS = {
    "books": ["book", "reading", "author", "literary", "poetry", "library", "novel", "zine"],
    "art": ["art", "gallery", "exhibition", "museum", "painting", "sculpture", "installation", "moma", "whitney", "guggenheim"],
    "music": ["music", "concert", "live band", "dj", "jazz", "rock", "hip hop", "electronic", "acoustic", "show", "gig", "sofar"],
    "parties": ["party", "social", "mixer", "networking", "happy hour", "housewarming", "brunch"],
    "outdoors": ["park", "outdoor", "garden", "hike", "walk", "picnic", "rooftop"],
    "food": ["food", "dinner", "tasting", "culinary", "chef", "restaurant", "supper", "brunch", "cocktail"],
    "games": ["game", "board game", "trivia", "backgammon", "chess", "puzzle", "arcade"],
    "theater": ["theater", "theatre", "film", "screening", "comedy", "improv", "stand-up", "standup"],
    "free": ["free", "no cover", "$0", "complimentary", "donation"],
    "special": ["gala", "benefit", "fundraiser", "opening night", "premiere", "met gala"],
}


def infer_categories(title: str, description: str = "") -> list[str]:
    text = f"{title} {description}".lower()
    cats = []
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            cats.append(cat)
    return cats if cats else ["other"]


NYC_NEIGHBORHOODS = {
    "williamsburg": ["williamsburg", "n 6th", "n 7th", "bedford ave", "berry st", "wythe ave", "kent ave"],
    "east village": ["east village", "e 3rd", "e 4th", "e 5th", "e 6th", "e 7th", "e 9th", "st marks"],
    "lower east side": ["lower east side", "les", "ludlow", "rivington", "orchard st", "delancey"],
    "bushwick": ["bushwick"],
    "greenpoint": ["greenpoint"],
    "dumbo": ["dumbo"],
    "park slope": ["park slope"],
    "soho": ["soho", "spring st", "prince st", "broadway", "greene st"],
    "chelsea": ["chelsea", "w 20th", "w 21st", "w 22nd", "w 23rd", "w 24th", "w 25th"],
    "midtown": ["midtown", "times square", "5th ave", "42nd"],
    "upper east side": ["upper east side", "ues", "5th avenue", "museum mile"],
    "upper west side": ["upper west side", "uws", "columbus ave", "amsterdam"],
    "brooklyn heights": ["brooklyn heights"],
    "fort greene": ["fort greene"],
    "prospect heights": ["prospect heights"],
}


def infer_neighborhood(address: str) -> str | None:
    if not address:
        return None
    lower = address.lower()
    for hood, keywords in NYC_NEIGHBORHOODS.items():
        if any(kw in lower for kw in keywords):
            return hood
    if "brooklyn" in lower:
        return "brooklyn"
    if "manhattan" in lower or "new york" in lower or "ny " in lower:
        return "manhattan"
    return None


def build_event(
    title: str,
    description: str,
    event_date: str | date,
    start_time: str | None = None,
    end_time: str | None = None,
    location_name: str | None = None,
    address: str | None = None,
    source: str = "",
    source_url: str = "",
    image_url: str | None = None,
    price: str | None = None,
    categories: list[str] | None = None,
) -> dict:
    if isinstance(event_date, date):
        date_str = event_date.isoformat()
    else:
        date_str = event_date

    if categories is None:
        categories = infer_categories(title, description)

    return {
        "id": make_event_id(source, title, date_str),
        "title": title.strip(),
        "description": description.strip() if description else "",
        "date": date_str,
        "startTime": start_time,
        "endTime": end_time,
        "location": {
            "name": location_name or "",
            "address": address or "",
            "neighborhood": infer_neighborhood(address or location_name or ""),
        },
        "categories": categories,
        "source": source,
        "sourceUrl": source_url,
        "imageUrl": image_url,
        "price": price or extract_price(f"{title} {description}"),
        "scrapedAt": datetime.now().isoformat(),
    }
