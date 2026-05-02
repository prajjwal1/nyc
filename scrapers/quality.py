"""Event quality filtering and signals.

Filters out low-quality events (kids programs, recurring services, ESL classes,
captions mistaken for events) and boosts high-quality social/cultural events.
"""

import re

# Hard blocks: events with these keywords are removed entirely.
# These are events you would never want to attend as a 20-30 something in NYC.
HARD_BLOCK_KEYWORDS = [
    # Kids / family
    "storytime", "story time", "kids", "children", "child ", "toddler", "baby",
    "babies", "preschool", "preteen", "tween", "teen ", "teens ", "after-school",
    "afterschool", "family saturday", "family sunday", "playtime", "popup play",
    "pop in play", "pop-in play", "youth ", "ages 0", "ages 3", "ages 5", "ages 6",
    "ages 7", "ages 8", "ages 9", "ages 10",

    # Education / utility
    "esl", "english class", "english language class", "spanish class",
    "high beginner english", "computer basics", "computer class", "computer lab",
    "homework help", "tutoring", "study group", "citizenship study",
    "tax help", "tax preparation", "legal clinic", "resume help", "resume workshop",
    "job search", "job club", "career help", "ged ", "tefl ", "language exchange",
    "language meetup", "english practice", "spanish practice", "french practice",
    "italian practice", "deutsch", "korean–english", "korean-english",
    "internationals coffee", "lexgo language", "langroops", "conversation française",

    # Senior services / accessibility
    "seniors", "senior citizens", "55+", "aarp", "braille", "accessible reading",

    # Recurring services / boring
    "knitting circle", "crochet circle", "knitting and crochet", "library card",
    "library tour", "library orientation", "open lab", "drop-in", "drop in tech",
    "tech help", "device help", "ebook help",
    "book sale", "book donation", "book drop",
    "bingo for", "puzzle group",

    # Wellness / support
    "support group", "aa meeting", "al-anon", "narcotics anonymous",
    "grief group", "therapy group", "12-step", "12 step",
    "narcan training", "naloxone training",

    # Religious services
    "bible study", "torah study", "quran study",

    # Random noise
    "registration for", "sign up for", "info session for", "orientation session",
]

# Soft penalties: not blocked but pushed down in ranking.
SOFT_PENALTY_KEYWORDS = [
    "free house dance", "salsa class", "swing dance class",
    "speed dating", "gay men's speed", "lesbian speed",
    "code & coffee", "code and coffee", "tech mixer",
    "discussion group", "book club meeting", "writing workshop",
    "open mic", "comedy show",  # too generic
    "yoga class", "pilates class", "meditation class",
    "running club", "walking tour",
    "trivia night",
]

# Strong boosts: signals of a genuinely cool, engaging event.
HIGH_VALUE_KEYWORDS = [
    # Live music — major boost (NYC 20s-30s love this)
    "live music", "live jazz", "jazz night", "jazz club", "jazz set",
    "concert", "dj set", "dj night", "live band", "live set", "live show",
    "vinyl night", "record listening", "listening party", "listening session",
    "lo-fi", "house music", "techno", "indie band", "indie show",
    "acoustic set", "open mic night", "songwriter showcase",
    "music festival", "summer concert", "music venue",
    "performance", "live performance",

    # Nightlife venues / vibes
    "rooftop", "speakeasy", "warehouse party", "loft party",
    "warehouse", "underground", "secret", "after hours", "late night",
    "natural wine bar", "wine bar", "cocktail bar", "nightclub",

    # Special / time-limited
    "opening night", "premiere", "launch party", "release party",
    "exclusive", "vip", "invite only", "first look", "preview",
    "exhibition opening", "gallery opening", "art opening", "show opening",

    # Curated cultural
    "literary salon", "salon ", "supper club", "tasting menu",
    "natural wine", "cocktail party", "wine tasting",
    "film screening", "movie screening", "private screening",
    "outdoor movie", "rooftop screening",

    # Festival / pop-up
    "pop-up", "pop up", "popup", "festival", "block party",
    "street fair", "open studios", "smorgasburg",

    # Curated NYC moments
    "first friday", "first saturday", "free friday",
    "sunset", "rooftop sunset", "harbor cruise", "boat party",

    # Signature events (you'd brag about going)
    "gala", "benefit", "fundraiser dinner",

    # 20s-30s NYC lifestyle
    "brooklyn brewery", "brooklyn bowl", "house of yes",
    "elsewhere", "the broadway", "knockdown center",
]

# Audience targeting markers - if event explicitly targets demographics
# that don't match, penalize.
NON_TARGET_AUDIENCE = [
    "for kids", "for children", "for families", "for seniors",
    "for moms", "for dads", "for parents", "for teens",
    "for ages", "ages 0-", "ages 3-", "ages 5-", "ages 6-",
]


def is_blocked(event: dict) -> bool:
    """True if event should be entirely filtered out (kids/utility/services)."""
    text = _searchable_text(event).lower()
    return any(kw in text for kw in HARD_BLOCK_KEYWORDS)


def quality_signals(event: dict) -> dict:
    """Compute fine-grained quality signals for ranking."""
    text = _searchable_text(event).lower()
    title_lower = event.get("title", "").lower()

    # Count keyword hits
    soft_penalty_hits = sum(1 for kw in SOFT_PENALTY_KEYWORDS if kw in text)
    high_value_hits = sum(1 for kw in HIGH_VALUE_KEYWORDS if kw in text)
    audience_mismatch = any(kw in text for kw in NON_TARGET_AUDIENCE)

    # Title quality: is the title an actual event title or a fragment?
    title = event.get("title", "")
    title_quality = _title_quality(title)

    # Description quality
    desc = event.get("description", "")
    desc_quality = _description_quality(desc)

    # Time of day signal — evenings/weekends rank higher than weekday mornings
    time_score = _time_of_day_score(event.get("startTime"), event.get("date", ""))

    return {
        "soft_penalty_hits": soft_penalty_hits,
        "high_value_hits": high_value_hits,
        "audience_mismatch": audience_mismatch,
        "title_quality": title_quality,
        "desc_quality": desc_quality,
        "time_score": time_score,
        "is_caption_fragment": _is_caption_fragment(title, desc),
    }


def _searchable_text(event: dict) -> str:
    parts = [
        event.get("title", ""),
        event.get("description", ""),
        event.get("location", {}).get("name", ""),
    ]
    return " ".join(parts)


def _title_quality(title: str) -> float:
    """0-1 score for how 'event-like' the title is."""
    if not title:
        return 0.0

    # Penalize titles that are clearly caption fragments
    if len(title) > 100:
        return 0.2
    if len(title) < 8:
        return 0.3

    # Penalize titles ending with mid-sentence punctuation
    if title.endswith((",", ":", ";", " and", " or", " the", " a", " of", " in", " on", " at", " to")):
        return 0.2

    # Penalize titles starting with lowercase (often caption fragments)
    if title[0].islower() and not title.startswith(("a ", "an ", "the ")):
        return 0.4

    # Penalize titles that are mostly hashtags
    hashtag_ratio = len(re.findall(r"#\w+", title)) / max(len(title.split()), 1)
    if hashtag_ratio > 0.3:
        return 0.2

    # Penalize titles that contain "Throughout his career" or other narrative phrases
    narrative_starters = [
        "throughout", "since ", "in his", "in her", "the artist", "the work",
        "this work", "this piece", "the painting", "the sculpture",
        "as part of", "see this", "join us at", "view of", "📷",
    ]
    if any(title.lower().startswith(p) for p in narrative_starters):
        return 0.2

    return 1.0


def _description_quality(desc: str) -> float:
    if not desc:
        return 0.4
    if len(desc) < 30:
        return 0.5
    if len(desc) > 100:
        return 1.0
    return 0.7


def _time_of_day_score(start_time: str | None, date_str: str) -> float:
    """Score events by how 'going-out worthy' the time slot is."""
    if not start_time:
        return 0.5

    try:
        hour = int(start_time.split(":")[0])
    except (ValueError, IndexError):
        return 0.5

    # Determine if weekend
    is_weekend = False
    try:
        from datetime import datetime
        d = datetime.fromisoformat(date_str)
        is_weekend = d.weekday() >= 5
    except Exception:
        pass

    if is_weekend:
        # Weekends - prefer afternoon/evening
        if 11 <= hour < 14:
            return 0.85  # brunch
        if 14 <= hour < 17:
            return 0.85  # afternoon
        if 17 <= hour < 21:
            return 1.0   # prime evening
        if 21 <= hour <= 23:
            return 0.95  # late night
        if 0 <= hour < 4:
            return 0.7   # very late
        return 0.4       # morning weekend
    else:
        # Weekdays - prefer evening
        if 18 <= hour < 22:
            return 1.0   # post-work prime
        if 17 <= hour < 18:
            return 0.85  # early evening
        if 22 <= hour <= 23:
            return 0.8   # late
        if 12 <= hour < 17:
            return 0.5   # midday
        return 0.3       # weekday morning


def _is_caption_fragment(title: str, desc: str) -> bool:
    """Detect Instagram captions that got split into bogus 'events'."""
    if not title:
        return False

    # Caption fragments often start with lowercase or narrative phrases
    fragment_starts = [
        "throughout", "since ", "in his", "in her", "the artist", "the work",
        "this work", "this piece", "as part of", "see this", "📷",
        "📸", "see ", "view ", "watch ", "currently on view",
    ]
    if any(title.lower().startswith(p) for p in fragment_starts):
        return True

    # Hashtag-only titles
    if title.startswith("#") or re.match(r"^#\w+(\s+#\w+)+$", title.strip()):
        return True

    # Narrative phrases inside the title
    narrative_phrases = [
        "consist of", "throughout his", "throughout her",
        "experimented with", "still want a", "the largest",
    ]
    if any(p in title.lower() for p in narrative_phrases):
        return True

    return False
