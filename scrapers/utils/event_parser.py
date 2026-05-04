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
    "books": [
        "book club", "reading series", "reading by", "author talk", "in conversation with",
        "literary", "poetry", "novel", "zine", "book launch", "book signing", "book swap",
        "book release", "memoir", "bookstore", "lit ", "literature",
        "reading rhythms", "rest and read", "book hub", "essay collection",
        "novelist", "writers ", "writing workshop",
    ],
    "art": [
        "art opening", "gallery", "exhibition", "museum", "painting", "sculpture",
        "installation", "moma", "whitney", "guggenheim", "art show", "open studios",
        "first saturday", "first friday", "art fair", "biennial", "vernissage",
        "artist talk", "panel discussion", "exhibition opens",
    ],
    "music": [
        "live music", "live jazz", "jazz", "concert", "dj set", "dj night",
        "live band", "rock show", "hip hop", "electronic", "acoustic",
        "music venue", "live show", "vinyl night", "listening party",
        "house music", "techno", "indie band", "songwriter", "open mic",
        "music festival", "live performance", " performance", " set ",
        "sofar", "bowery", "elsewhere", "knockdown center",
        "lo-fi", "chillout", "ambient", "experimental music",
        "showcase", "lineup", "headlining", "supporting act",
        "national sawdust", "rough trade", "le poisson rouge",
        "summerstage", "celebrate brooklyn", "lincoln center out of doors",
        "free concert", "outdoor concert", "tribute show",
    ],
    "parties": [
        "party", "social mixer", "mixer", "networking", "happy hour",
        "housewarming", "brunch party", "rooftop party", "loft party",
        "warehouse party", "speakeasy", "cocktail party", "after-hours",
        "underground", "boat party", "block party", "kickback",
        "anniversary party", "release party",
    ],
    "outdoors": [
        "park", "outdoor", "garden", "hike", "walk", "picnic", "rooftop",
        "boat", "harbor", "waterfront", "pier ", "beach", "ferry",
        "high line", "domino park", "central park",
    ],
    "food": [
        "food festival", "dinner party", "tasting menu", "tasting", "culinary",
        "chef ", "supper club", "natural wine", "wine tasting", "wine bar",
        "cocktail", "smorgasburg", "popup dinner", "pop-up dinner",
        "restaurant week", "food crawl", "speakeasy",
    ],
    "games": [
        "board game", "trivia", "backgammon", "chess", "arcade", "game night",
        "mahjong", "poker night", "puzzle night", "gammon", "scrabble",
        "settlers of catan", "game social",
    ],
    "theater": [
        "theater", "theatre", "play opening", "broadway", "off-broadway",
        "drama", "musical",
    ],
    "comedy": [
        "comedy show", "improv", "stand-up", "standup", "open mic comedy",
        "comedy night", "sketch show",
    ],
    "dance": [
        "dance class", "dance party", "dance night", "salsa night",
        "swing dance", "ballroom", "tango social",
    ],
    "design": [
        "design week", "design fair", "design show", "icff",
        "open studios", "interior design",
    ],
    "photography": [
        "photo exhibition", "photography exhibition", "photo show",
        "photo book", "photography",
    ],
    "wellness": [
        "yoga ", "outdoor yoga", "yoga class", "meditation", "mindfulness",
        "sound bath", "breathwork", "qigong", "tai chi",
        "ice bath", "cold plunge", "sauna",
    ],
    "fitness": [
        "run club", "running club", "weekend run", "morning run",
        "social run", "saturday run", "sunday run",
        "group run", "casual run", "track club",
        "5k ", "10k ", "marathon training",
        "bike ride", "group ride", "cycling club",
        "pickleball", "tennis meetup",
    ],
    "movies": [
        "movie", "film screening", "movie screening", "outdoor movie",
        "rooftop movie", "rooftop screening", "indie film", "premiere",
        "movie night", "drive-in", "movies under the stars",
    ],
    "celebrities": [
        "celebrity", "in conversation with", "live appearance",
        "meet & greet", "fireside chat", "with special guest",
        "in person ", "live taping",
    ],
    "exploration": [
        "walking tour", "neighborhood tour", "self-guided tour",
        "hidden gems", "secret nyc", "lesser-known", "off-the-beaten",
        "explore brooklyn", "explore manhattan", "explore queens",
        "open house", "first look", "pop-up shop", "popup shop",
        "urban exploration", "street art tour", "architecture tour",
        "rooftop tour", "scavenger hunt", "treasure hunt",
        "hidden bar", "speakeasy",
    ],
    "viewings": [
        "viewing party", "watch party", "live screening",
        "stream watch", "screening party", "premiere watch",
    ],
    "singles": [
        "singles event", "singles night", "singles party",
        "singles mixer", "speed dating", "singles social",
        "matchmaking", "dating event", "date night ", "date my friend",
        "let's date", "date my", "first date",
        "new in town", "meet new people", "make new friends",
        "20s & 30s mixer", "20s and 30s", "in your 20s", "in your 30s",
    ],
    "film": [
        "film screening", "movie screening", "premiere screening",
        "film festival", "outdoor movie", "rooftop screening", "indie film",
    ],
    "free": ["free admission", "no cover", "$0", "complimentary", "free event"],
    "special": [
        "gala", "benefit", "fundraiser", "opening night", "premiere",
        "launch party", "met gala", "anniversary",
    ],
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
