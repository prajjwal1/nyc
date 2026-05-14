"""Event quality filtering and signals.

Filters out low-quality events (kids programs, recurring services, ESL classes,
captions mistaken for events) and boosts high-quality social/cultural events.
"""

import re

# Hard blocks: events with these keywords are removed entirely.
# These are events you would never want to attend as a 20-30 something in NYC.
# IMPORTANT: This is the most aggressive layer. Use whole-word boundaries when
# the keyword could falsely match (e.g., "play" matches "playing").
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
    "language meetup", "english practice", "english conversation",
    "spanish practice", "french practice",
    "italian practice", "deutsch", "korean–english", "korean-english",
    "internationals coffee", "lexgo language", "langroops", "conversation française",
    # Language-mixer / international-mixer events (excluded per user request)
    "internationals and language mixer", "international and language mixer",
    "internationals language", "language mixer", "languages mixer",
    "internationals mixer", "language exchange mixer",
    # Music genres user excluded (reggaeton)
    "reggaeton",

    # Professional / finance / corporate networking (excluded — site is
    # for events worth attending to meet people for connection, not
    # for-business connections). "tech mixer" is explicitly OK.
    "professional networking", "professionals networking",
    "professional mixer", "professionals mixer",
    "business networking", "business mixer",
    "finance networking", "finance mixer", "finance professionals",
    "wall street networking", "wall street mixer",
    "executive networking", "executive mixer", "executives mixer",
    "career networking", "career mixer",
    # User explicitly: NO career-related events. Specific phrases only
    # so we don't false-positive on artist bios ("throughout her career")
    # or comedy showcases ("new faces" of comedy).
    "career fair", "career fairs",
    "career expo", "career expos",
    "career talk", "career talks",
    "career panel", "career panels",
    "career workshop", "career workshops",
    "career conference", "career conferences",
    "career summit",
    "career advice", "career coaching", "career coach",
    "career mentorship", "career mentor",
    "career development", "career growth",
    "career transition", "career transitions",
    "career change", "career switch", "career switching",
    "career blueprint", "career-ready", "career ready",
    "career-changing", "career changing",
    "job fair", "job fairs", "job expo", "job expos",
    "job training", "job seekers", "job hunters", "job hunting",
    "hiring event", "hiring fair", "hiring expo",
    "professional development",
    "leadership development", "leadership summit", "leadership conference",
    "leadership workshop", "leadership forum",
    "executive coaching", "executive summit",
    "speed networking",
    "networking breakfast", "networking lunch", "networking happy hour",
    "founder summit", "founders summit", "founders conference",
    "investor summit", "investors summit", "investor conference",
    "biz dev mixer", "bizdev mixer",
    "interview prep", "interview workshop", "interview practice",
    "resume review", "resume writing",
    "industry networking", "industry mixer",
    "corporate networking", "corporate mixer",
    "investor networking", "investor mixer", "investors mixer",
    "founders networking", "founders mixer",  # focus on founder events; tech mixer stays
    "real estate networking", "real estate mixer",
    "lawyer networking", "lawyer mixer", "attorneys mixer",
    "consulting networking", "consultant mixer",
    "banking networking", "banking mixer",
    "linkedin networking", "linkedin mixer",
    "b2b networking", "b2b mixer",
    "sales networking", "sales mixer",

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

    # Nightclubs / late-night-only — user explicitly excluded these. The
    # site is for events worth attending to meet people; nightclub
    # "bottle service" / "vip section" culture isn't the target.
    "nightclub", "night club ", "bottle service", "vip table", "vip booth",
    "vip section", "bottle package", "table reservation", "table service",
    "bottle minimum", "guest list",  # the bottle-service-y kind
    # Late-night-only events (going past midnight)
    "after hours", "afterhours", "after-hours",
    "till sunrise", "until sunrise", "til sunrise",
    "all night long", "till morning", "till dawn", "until dawn",
    "till 4am", "until 4am", "til 4am", "till 5am", "until 5am",
    "till 3am", "until 3am", "til 3am", "till 6am", "until 6am",
    "rave 'til", "warehouse till", "club till",
    "no last call",

    # Mega-arena stadium acts the user doesn't want surfacing here. The
    # site is for going-out-with-friends events, not "buy 200 USD seats
    # at MSG four months out" listings — those have their own apps.
    "wwe ", "wwe:", "wwe at", "wwe presents",
    # Virtual / remote-only events — user wants IRL events to meet people
    "virtual race", "virtual run", "virtual 5k", "virtual 10k",
    "virtual half marathon", "virtual marathon", "virtual fun run",
    "virtual workout", "virtual yoga", "online event",
    "zoom event", "via zoom",
    # Tribute / cover-band schlock at venue mass-market shows
    "tribute concert", "tribute band", "ultimate tribute",
    # Generic "X 5K Walk/Run" charity races aren't the social-event vibe
    # the user wants. Specific races (NYC Marathon, etc.) won't hit this.
    "5k walk/run", "5k run/walk", "5k charity",
]

# Soft penalties: not blocked but pushed down in ranking.
SOFT_PENALTY_KEYWORDS = [
    "free house dance", "salsa class", "swing dance class",
    "speed dating", "gay men's speed", "lesbian speed",
    "code & coffee", "code and coffee", "tech meetup",
    "discussion group", "writing workshop",
    "yoga class", "pilates class", "meditation class",
    "running club",
    "trivia night",
    # Heavy-drinking emphasis — user's stated preference is to avoid
    # excessive-drinking culture. Soft-penalty (not block) so events
    # that mention drinks in passing aren't excluded, but events that
    # CENTER drinking get pushed down.
    "open bar", "all you can drink", "all-you-can-drink",
    "free drinks all night", "unlimited drinks", "bottomless mimosas",
    "pre-game", "kegger", "shotgun beer",
    # Generic recurring stuff
    "weekly meeting", "monthly meeting", "regular meetup",
    "every monday", "every tuesday", "every wednesday",
    # Vague titles
    "various artists", "tba", "more info", "stay tuned",
]

# Social signals: events specifically conducive to meeting people.
# These get a meaningful score boost since the user is single & wants to meet folks.
SOCIAL_KEYWORDS = [
    # Explicit
    "singles night", "singles event", "singles mixer", "singles party",
    "speed dating", "matchmaking", "date my friend", "blind date",
    "first dates", "dating in nyc",
    # Meet new people
    "meet new people", "make new friends", "new in town",
    "newcomers", "expats meetup", "newbies in nyc",
    # Social mixers / connection-focused
    "social mixer", "meet & greet", "meet and greet", "icebreaker",
    "20s & 30s", "20s and 30s", "young professionals",
    # Vibe-based connection events
    "kickback", "house party", "social", "salon",
    "after party", "afterparty", "cocktail hour",
    "happy hour", "rooftop hour",
    # Group activities for meeting
    "run club", "social run", "social club",
    "supper club", "dinner club",
    "gallery hop", "art hop",
]


# Strong boosts: signals of a genuinely cool, engaging event.
# Alcohol-free signals — user explicitly wants more sober-friendly events
# in the feed AND wants drinking-centered events down-weighted (not blocked).
# Each match contributes a small positive boost via _alcohol_free_boost.
ALCOHOL_FREE_KEYWORDS = [
    "alcohol free", "alcohol-free", "alcohol  free",
    "sober", "sober curious", "sober social",
    "non-alcoholic", "non alcoholic", "non-alc", "non alc",
    "zero proof", "zero-proof",
    "dry january", "dry month",
    "mocktail", "mocktails",
    "no booze", "booze-free", "booze free",
    "tea ceremony", "matcha", "specialty coffee",
    "kombucha tasting", "tea tasting",
]


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


# Keywords that need WORD-BOUNDARY matching to avoid false positives.
# Substring matching catches "baby" inside "Baby's All Right" (NYC music
# venue) and "teen " inside "Springsteen ". For single-word age/family
# tokens, require word boundaries. For multi-word phrases (e.g.
# "professional networking", "job fair"), substring is fine because
# those phrases don't appear inside unrelated words.
_WORD_BOUNDARY_KEYWORDS = {
    "kids", "children", "toddler", "toddlers", "baby", "babies",
    "teen", "teens", "tween", "tweens", "preteen", "preteens",
    "youth", "infant", "infants",
}

import re as _re
# Word-boundary match BUT exclude possessive form ("Baby's All Right",
# "Kid's Choice"). Negative lookahead `(?!')` ensures we don't match
# inside venue/band names that use the apostrophe-s form.
_WORD_BOUNDARY_RES = [
    _re.compile(rf"\b{_re.escape(kw)}\b(?!')", _re.IGNORECASE)
    for kw in _WORD_BOUNDARY_KEYWORDS
]


def is_blocked(event: dict) -> bool:
    """True if event should be entirely filtered out (kids/utility/services/non-NYC).

    Single-word age/family keywords use word-boundary matching to avoid
    false-positive blocks on venue names ("Baby's All Right") and band
    names ("Bruce Springsteen"). Multi-word phrases stay on cheap
    substring matching since they're unambiguous.
    """
    text = _searchable_text(event).lower()
    # Multi-word phrases: substring match (cheap, unambiguous).
    for kw in HARD_BLOCK_KEYWORDS:
        # Skip single tokens we've moved to word-boundary matching.
        if kw.strip() in _WORD_BOUNDARY_KEYWORDS:
            continue
        if kw in text:
            return True
    # Word-boundary single-word matches.
    for r in _WORD_BOUNDARY_RES:
        if r.search(text):
            return True
    if _is_non_nyc(event):
        return True
    return False


# Cities that strongly suggest the event is NOT in NYC.
_NON_NYC_CITIES = [
    "los angeles", " la,", " la ", "los feliz", "echo park", "silverlake",
    "san francisco", " sf,", " sf ", "oakland", "berkeley",
    "chicago", "miami", "austin", "atlanta", "boston", "philadelphia", "philly",
    "portland", "seattle", "denver", "nashville", "new orleans",
    "washington dc", "d.c.", "dc,",
    "london", "paris", "tokyo", "berlin", "amsterdam", "barcelona",
    "mexico city", "toronto", "vancouver", "montreal",
    "honolulu", "hawaii", "miami beach",
    "las vegas", "vegas",
    "dallas", "houston", "phoenix", "minneapolis",
    "long beach", "santa monica", "venice beach",
    # NJ cities (close to NYC but separate)
    "jersey city", "hoboken", "newark",
]

# NYC-positive markers (presence of these suggests it IS in NYC)
_NYC_MARKERS = [
    "nyc", "new york", "brooklyn", "manhattan", "queens", "bronx",
    "staten island", "harlem", "williamsburg", "bushwick", "greenpoint",
    "soho", "tribeca", "chelsea", "lower east side", "east village",
    "west village", "midtown", "upper east", "upper west",
    "park slope", "fort greene", "dumbo", "prospect heights",
    "long island city", "lic", "astoria",
]


def _is_non_nyc(event: dict) -> bool:
    """Detect events that are clearly not in NYC."""
    location = event.get("location", {})
    address = (location.get("address", "") or "").lower()
    loc_name = (location.get("name", "") or "").lower()
    title = event.get("title", "").lower()
    desc = event.get("description", "").lower()

    combined = f"{address} {loc_name} {title} {desc}"

    # Strong non-NYC marker
    has_other_city = any(c in combined for c in _NON_NYC_CITIES)
    has_nyc_marker = any(m in combined for m in _NYC_MARKERS)

    # If it mentions another city AND no NYC markers, block
    if has_other_city and not has_nyc_marker:
        return True

    return False


def quality_signals(event: dict) -> dict:
    """Compute fine-grained quality signals for ranking."""
    text = _searchable_text(event).lower()
    title_lower = event.get("title", "").lower()

    # Count keyword hits
    soft_penalty_hits = sum(1 for kw in SOFT_PENALTY_KEYWORDS if kw in text)
    high_value_hits = sum(1 for kw in HIGH_VALUE_KEYWORDS if kw in text)
    social_hits = sum(1 for kw in SOCIAL_KEYWORDS if kw in text)
    alcohol_free_hits = sum(1 for kw in ALCOHOL_FREE_KEYWORDS if kw in text)
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
        "social_hits": social_hits,
        "alcohol_free_hits": alcohol_free_hits,
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

    title_lower = title.lower()

    # Penalize titles ending with mid-sentence punctuation
    if title.endswith((",", ":", ";", " and", " or", " the", " a", " of", " in", " on", " at", " to", " is", " are", " was", " were")):
        return 0.2

    # Penalize titles starting with lowercase (often caption fragments)
    if title[0].islower() and not title.startswith(("a ", "an ", "the ")):
        return 0.4

    # Penalize titles that are mostly hashtags
    hashtag_ratio = len(re.findall(r"#\w+", title)) / max(len(title.split()), 1)
    if hashtag_ratio > 0.3:
        return 0.2

    # Penalize narrative caption fragments
    narrative_starters = [
        "throughout", "since ", "in his", "in her", "the artist", "the work",
        "this work", "this piece", "the painting", "the sculpture",
        "as part of", "see this", "join us at", "view of", "📷",
        "did you know", "fun fact", "happy ", "today is", "let me",
        "we love", "we're loving", "we’re loving", "we’re thrilled",
        "we are thrilled", "we are excited", "what a ", "behind the scenes",
        "swipe to", "swipe ⬅", "swipe ➡", "tap link", "link in bio",
        "back by", "tickets on sale", "now showing", "now open",
        "last chance", "don't miss", "don’t miss", "save the date",
        "calling all", "coming up", "coming soon", "celebrating ",
        "thank you", "thanks to", "shoutout", "photo by", "video by",
    ]
    if any(title_lower.startswith(p) for p in narrative_starters):
        return 0.1

    # Numbered list items
    if re.match(r"^\d+[\.\)]\s+", title):
        return 0.1

    # Title is just a date or relative time
    if re.match(r"^(?:today|tomorrow|tonight|this weekend)$", title_lower):
        return 0.1

    # Penalize titles with strong "ad copy" feel
    if any(p in title_lower for p in [" featuring ", " ft. ", " presents "]):
        return 0.7  # actually this can be a real event lineup, mild penalty only

    # Reward titles with strong action verbs at the start (real events)
    action_starters = [
        "join ", "come ", "explore ", "discover ", "celebrate ", "experience ",
        "see ", "visit ", "attend ", "go to ", "watch ", "listen to ",
        "enjoy ", "shop ", "taste ", "dance to ", "party at ",
    ]
    if any(title_lower.startswith(p) for p in action_starters):
        return 1.0

    return 0.9


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

    title_lower = title.lower().strip()
    title_stripped = title.strip()

    # Caption fragments often start with lowercase or narrative phrases
    fragment_starts = [
        # Narrative / descriptive
        "throughout", "since ", "in his", "in her", "the artist", "the work",
        "this work", "this piece", "as part of", "see this", "📷",
        "📸", "see ", "view ", "watch ", "currently on view",
        # First-person / hype language
        "we are loving", "we're loving", "we’re loving",
        "we are thrilled", "we're thrilled", "we’re thrilled",
        "we are excited", "we're excited", "we’re excited",
        "we are so", "we’re so", "we are super", "we’re super",
        "we’ve got", "we've got", "we got", "we have ", "we’re back",
        # IG content patterns
        "🚨", "‼", "⚠", "📣",  # alert emoji starts
        "tomorrow,", "tomorrow we", "tomorrow night", "tomorrow morning",
        "tonight 7", "tonight 8", "tonight 9", "tonight, ",
        "spring starts", "summer starts", "fall starts", "winter starts",
        "20 years in", "10 years in", "5 years in",
        "raise a glass", "kick off ",
        "more @", "back @", "back at @",
        "tired of ", "are you tired",
        "new food alert", "new event alert",
        "i got the feeling", "this is your reminder",
        "it may not feel", "even before",
        "beautiful pictures", "amazing pictures", "great pictures",
        "shoutout to", "big shoutout",
        "i can't believe", "i can’t believe",
        "your weekly", "your monthly",
        "let's do", "let’s do",
        "what…", "what...",
        "*",  # asterisk-led fragments like "*Artist will not be present"
        "hosted by",
        "mid-week", "midweek",
        "bravo fans", "swifties", "beyhive",
        "this one's for you", "this one’s for you",
        "this is big", "this is huge",
        "we present", "we’re excited to present",
        "presenting:", "introducing ",
        "if you’ve been", "if you've been",
        "if you’re looking", "if you've been looking",
        "the wait is over", "the moment we",
        "you don’t want to", "you don't want to",
        "this is", "this was",
        "got some", "we’ve got some",
        "y’all", "yall",
        "good morning", "good afternoon", "good evening",
        "🎬", "🎉", "🎊", "🥳",  # celebration emoji starts (often hype)
        # Announcements / call-to-action
        "back by popular", "tickets on sale", "now showing", "now open",
        "last chance", "don't miss", "don’t miss", "save the date",
        "calling all", "for those of",
        "coming up", "coming soon",
        "happy ", "today is", "celebrating ", "celebrate ",
        "thank you", "thanks to", "shoutout", "shout out",
        "photo by", "📷", "video by", "captured by",
        # Hype / casual greetings
        "hey ", "hi ", "yo ", "psa", "p.s.a", "‼", "‼️",
        "big news", "huge news", "exciting news", "great news",
        "just announced", "newly announced", "announcing",
        "presale", "general on sale", "general sale",
        "got some", "we’ve got some", "we got some",
        "real dancers", "all dancers",
        "catch his", "catch her", "catch their",
        "[", "(",
        "@", "#",
    ]
    if any(title_lower.startswith(p) for p in fragment_starts):
        return True

    # Numbered list items (e.g., "3. Harley Spiller premieres ...")
    if re.match(r"^\d+[\.\)]\s+", title):
        return True

    # Titles starting with relative time like "Today" or "Tomorrow" alone
    if re.match(r"^(?:today|tomorrow|tonight|this weekend|this week)[^\w]?$", title_lower):
        return True

    # Hashtag-only titles
    if title.startswith("#") or re.match(r"^#\w+(\s+#\w+)+$", title.strip()):
        return True

    # Bracketed location tags like "[London]" or "[NYC]"
    if re.match(r"^\[[^\]]+\]\s*$", title_stripped):
        return True

    # Pure date / month titles
    months = "(?:january|february|march|april|may|june|july|august|september|october|november|december)"
    if re.match(rf"^{months}\s+\d{{1,2}}(?:st|nd|rd|th)?\.?$", title_lower):
        return True
    if re.match(r"^\d{1,2}(?:st|nd|rd|th)?\.?$", title_lower.strip(":!. ")):
        return True

    # Title that's just "Location:" or starts with a label
    if title_lower.startswith(("location:", "venue:", "where:", "when:", "what:", "info:", "details:")):
        return True

    # Stylized unicode fonts (mathematical alphanumeric symbols U+1D400-1D7FF)
    if re.search(r"[\U0001D400-\U0001D7FF]", title):
        return True

    # Title is just hype with emoji like "TO THE FRONT  ‼"
    if "‼" in title and len(title_stripped.replace("‼", "").strip()) < 30:
        return True

    # All-caps titles that are mostly hype
    if title_stripped.isupper() and len(title_stripped) > 6:
        words = title_stripped.split()
        # OK if it's a proper noun / festival name (1-3 short words)
        if len(words) > 3 or sum(len(w) for w in words) > 25:
            return True

    # Caption-y openers (relative time + verb)
    caption_openers = [
        "tomorrow night ", "tomorrow we ", "tomorrow we’",
        "tonight we ", "tonight we’", "tonight, ",
        "this week ", "this weekend ", "this weekend, ",
        "next week ", "next weekend ",
        "today we ", "today we’", "today, ",
        "yesterday ", "last night ",
        "happening now",
    ]
    if any(title_lower.startswith(p) for p in caption_openers):
        return True

    # "X takes over Y" / "X headline Y" announcement patterns
    announcement_patterns = [
        r"\b(?:takes over|takeover)\b",
        r"\bheadlines?\b",
        r"\bsold out\b",
        r"\bjust dropped\b",
    ]
    for pat in announcement_patterns:
        if re.search(pat, title_lower):
            return True

    # Title is just a name/title without context (3 words or less, no verbs)
    # like "Of Golden Sun" — these are usually song/album titles, not events.
    # CARVE-OUT: explicitly include single-token activity words that the user
    # specifically asked for. "Vital Run Club", "Books Are Magic",
    # "Sky Ting Yoga", "Greenpoint Comedy" should NOT be filtered out.
    words = title_stripped.split()
    if len(words) <= 3:
        # Common verbs/event words that would make it a real event
        event_words = {
            "party", "show", "concert", "night", "club", "festival",
            "open", "opens", "opening", "premiere", "launch",
            "screening", "reading", "tour", "fair", "market",
            "mixer", "meetup", "meet", "happy", "hour", "brunch",
            "dinner", "tasting", "class", "workshop", "talk",
            "series", "live", "vs", "v.", "vs.", "presents",
            # Single-token activity / venue / format words for the curated
            # account titles the user specifically wants — run clubs, yoga,
            # comedy, bookstores, supper clubs, brunches, etc.
            "run", "runs", "running", "yoga", "comedy", "books", "book",
            "supper", "fitness", "stretching", "stretch", "hike", "hiking",
            "walk", "walking", "biking", "ride", "race", "marathon",
            "ceramics", "pottery", "craft", "crafts", "sketching", "drawing",
            "magic", "ting", "stories", "trivia", "social", "salon",
        }
        # Strip trailing punctuation when comparing — "Run!" should match
        # "run" in event_words.
        normalized = [w.lower().strip("!?.,:;\"'") for w in words]
        if not any(w in event_words for w in normalized):
            return True

    # Narrative phrases inside the title
    narrative_phrases = [
        "consist of", "throughout his", "throughout her",
        "experimented with", "still want a", "the largest",
        "is #", " is now ", " is back", "are bringing",
        "loving the energy", "across nyc",
        "link in our bio", "link in bio", "swipe up",
        "presale begins", "tickets are live", "schedule and tickets",
    ]
    if any(p in title_lower for p in narrative_phrases):
        return True

    # Sentence-like titles (multiple commas, ends with period in mid-sentence)
    if title.count(",") >= 2 and len(title) > 80:
        return True

    # Title is mostly emoji/punctuation
    alpha_chars = sum(1 for c in title_stripped if c.isalpha())
    if alpha_chars < 5:
        return True

    # Title is all caps and looks like hype (e.g., "REAL DANCERS TO THE FRONT")
    if (title_stripped.isupper() and len(title_stripped) > 8
            and "‼" not in title_stripped[-3:]):
        # OK to allow festival/abbreviation names
        if not re.match(r"^[A-Z]{2,}\s*[A-Z0-9 ]*$", title_stripped):
            # Has hype words?
            hype = ["clear", "drop", "alert", "emergency", "urgent",
                    "warning", "incoming", "psa", "must"]
            if any(h in title_lower for h in hype):
                return True

    return False
