import hashlib
import re
from datetime import datetime, date, time
from zoneinfo import ZoneInfo

import dateparser


_NYC_TZ = ZoneInfo("America/New_York")


def make_event_id(source: str, title: str, event_date: str) -> str:
    raw = f"{source}:{title}:{event_date}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def parse_offers_price(offers) -> str:
    """Extract a display price from a JSON-LD `offers` field.

    JSON-LD `offers` can be a dict (single Offer) or a list of Offer
    objects. Returns:
      - "free" when any offer has price 0
      - "$N" for the first non-zero price
      - "unknown" if nothing is parseable

    Centralizing this so eventbrite/meetup/museums/dice all expose the
    same FREE pill behavior on the cards without each scraper
    re-implementing the same offers walk.
    """
    if isinstance(offers, dict):
        offers = [offers]
    if not isinstance(offers, list):
        return "unknown"
    free_seen = False
    paid_price = None
    for o in offers:
        if not isinstance(o, dict):
            continue
        # Accept either price (standard) or lowPrice (AggregateOffer)
        p = o.get("price", o.get("lowPrice", ""))
        if p == "" or p is None:
            continue
        # Normalize: "0", 0, "0.00", 0.0 all mean free
        try:
            pf = float(p)
            if pf == 0:
                free_seen = True
                continue
            if paid_price is None:
                paid_price = f"${pf:g}"  # strip trailing zeros ($25.00 -> $25)
            continue
        except (ValueError, TypeError):
            pass
        # Non-numeric price (e.g. "Free" string) — fall back to string form
        if isinstance(p, str) and p.lower() == "free":
            free_seen = True
        elif paid_price is None:
            paid_price = f"${p}"
    if free_seen and paid_price is None:
        return "free"
    if paid_price is not None:
        return paid_price
    return "unknown"


def parse_iso_to_local(iso_str: str) -> tuple[str | None, str | None]:
    """Parse a JSON-LD style ISO datetime into (date, HH:MM) in
    America/New_York. Handles "Z" suffix and explicit offsets.

    JSON-LD startDate values are typically UTC (e.g.
    "2026-05-26T22:00:00Z"). Naive slicing of chars 11-16 displays
    UTC verbatim, so an 18:00 ET event shows as 22:00 to the user.
    This helper does the timezone conversion centrally so every
    scraper doing JSON-LD ingestion stays consistent.

    Falls back to (date_str, naive HH:MM slice) when parsing fails,
    matching the legacy behavior so malformed values don't drop the
    event entirely.
    """
    if not iso_str:
        return None, None
    s = iso_str.replace("Z", "+00:00")
    # If there's no "T" separator, this is a date-only input. Return the
    # date and a None time — otherwise fromisoformat parses it as naive
    # midnight and every date-only event ends up displayed at 00:00, which
    # is worse than no time at all.
    if "T" not in s:
        return (s[:10] if len(s) >= 10 else None), None
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            local = dt  # already local
        else:
            local = dt.astimezone(_NYC_TZ)
        return local.date().isoformat(), local.strftime("%H:%M")
    except Exception:
        date_str = iso_str[:10] if len(iso_str) >= 10 else None
        time_str = iso_str[11:16] if len(iso_str) > 16 else None
        return date_str, time_str


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
                # No AM/PM specified — context-aware disambiguation.
                # Run clubs and yoga classes commonly say "7:30" meaning 7:30 AM
                # ("meet at 7:30 at McCarren track"). The old evening-bias rule
                # silently promoted these to PM, killing run-club events.
                h, mi = int(groups[0]), int(groups[1])
                text_lower = text.lower()
                # Strong AM signals — early-morning fitness / yoga / coffee /
                # brunch / breakfast contexts. If any present, leave hour as-is.
                AM_SIGNALS = (
                    "morning", " am", " a.m", "am ", "a.m.",
                    "run club", "running", "yoga", "stretch",
                    "sunrise", "early bird", "early-bird",
                    "breakfast", "brunch", "coffee meetup",
                    "track club", "marathon training",
                )
                PM_SIGNALS = (
                    "evening", " pm", " p.m", "pm ", "p.m.",
                    "night", "happy hour", "after work",
                    "doors", "concert", "show", "set ",
                    "dj", "party", "dinner",
                )
                has_am = any(s in text_lower for s in AM_SIGNALS)
                has_pm = any(s in text_lower for s in PM_SIGNALS)
                if has_am and not has_pm:
                    pass  # leave hour as-is (AM)
                elif has_pm and not has_am:
                    if h != 12:
                        h += 12  # explicit PM context
                elif 1 <= h <= 5:
                    # Strongly implausible AM event time. Default to PM.
                    h += 12
                else:
                    # Ambiguous (6-11) with no signals → return None rather than
                    # guess. Better to have no time than a wrong time.
                    return None
                return f"{h:02d}:{mi:02d}"
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
        # Eventbrite/B&N pattern: "Author Name discusses BOOK at venue"
        "discusses", "discuss her book", "discuss his book", "discuss their book",
        "audiobooks", "audiobook", "lectures on", "library reading",
        # Writing-event variants — kept as 2-word phrases so "Writing Code
        # in Python" / "Writing the Will" don't get tagged books.
        "writing practice", "writing salon", "writing series",
        "writing class", "writing group", "creative writing",
        "notes on writing", "writing rhythms", "writing community",
        "writers meet", "writer's group",
        # Generic literary patterns
        "readers meetup", "readers' meetup", "reading brooklyn",
        "rest & read", "rest and read", "rest n read",
        "book bar", "book nook", "book pop", "book pop up",
        "quiet reading", "silent reading",
        # Pattern "by <author>" + literary verb in same title
        " by hannah arendt", " by james mcb", " by tom perrotta",
        " by joe west", " by elsie silver",
        # iter 173: common book-event phrasings missing from the list above.
        # Audit found 'Book Fair', 'Author Signing Event', 'Reading Group:
        # Toni Morrison', 'Indie Press Showcase' all falling to ['other'].
        "book fair", "author signing", "reading group", "indie press",
        "books signing",  # variant
    ],
    "art": [
        "art opening", "gallery", "exhibition", "museum", "painting", "sculpture",
        "installation", "moma", "whitney", "guggenheim", "art show", "open studios",
        "first saturday", "first friday", "art fair", "biennial", "vernissage",
        "artist talk", "panel discussion", "exhibition opens",
        "sip and paint", "sip & paint", "paint and sip", "paint & sip",
        "mural", "ceramics", "pottery class", "drawing class",
        "art class", "art workshop", "creative workshop",
        "calligraphy", "sip & script", "drink 'n draft", "drink n draft",
        "animation nights", "anny", "screening:",
        "thesis projects", "mfa thesis", "bfa thesis",
        # iter 176: common art-event patterns missing from original list.
        # 'drawing' / 'printmaking' / 'collage' all standard NYC creative
        # workshops; 'art crawl' / 'studio visit' are gallery-circuit
        # formats; 'crafternoon' is a recurring craft-meetup brand.
        "drawing workshop", "drawing night", "drawing session",
        "printmaking", "print making", "linocut", "screen printing",
        "collage night", "collage workshop", "collage session",
        "art crawl", "art tour", "studio visit", "studio tour",
        "open studio", "crafternoon", "craft night", "craft workshop",
    ],
    "music": [
        # Bare "music" — word-bounded (5 chars, so re.search with \\b)
        # so "music album", "Rum and Music" tag music. Doesn't fire on
        # "musical" (would match "music" inside it without \\b).
        "music",
        "live music", "live jazz", "jazz", "concert", "dj set", "dj night",
        "live band", "rock show", "hip hop", "electronic", "acoustic",
        "disco",  # iter 170: genre word; word-boundary check applies (5 chars)
                  # so 'Discord', 'discomfort' won't match. Catches 'Horse Meat
                  # Disco', 'Disco Inferno', 'Disco Night' from DICE/Songkick.
        # iter 171: more genres found missing in an audit of Songkick/DICE
        # titles. All length-5+ so word-boundary applies — no 'metalcraft'
        # / 'reggae'-in-other-string false positives.
        "blues", "reggae", "metal ", "punk ", "karaoke",
        "music venue", "live show", "vinyl night", "listening party",
        "house music", "techno", "indie band", "songwriter", "open mic",
        "music festival", "live performance", " performance", " set ",
        "sofar", "bowery", "elsewhere", "knockdown center",
        "lo-fi", "chillout", "ambient", "experimental music",
        "showcase", "lineup", "headlining", "supporting act",
        "national sawdust", "rough trade", "le poisson rouge",
        "summerstage", "celebrate brooklyn", "lincoln center out of doors",
        "free concert", "outdoor concert", "tribute show",
        # Concert venues — Songkick uses "Artist @ Venue" format heavily
        "@ webster hall", "@ brooklyn paramount", "@ brooklyn bowl",
        "@ music hall of williamsburg", "@ bowery ballroom", "@ irving plaza",
        "@ knockdown center", "@ elsewhere", "@ public records",
        "@ nowadays", "@ avant gardner", "@ brooklyn steel",
        "@ terminal 5", "@ kings theatre", "@ beacon theatre",
        "carnegie hall", "lincoln center", "radio city",
        "msg ", "madison square garden",
        "blue note", "smoke jazz", "village vanguard", "small's jazz",
        # Generic Songkick-style "@ Venue" pattern
        " @ the hall", " @ the rooftop",
        # Orchestra/symphony/choir patterns
        "orchestra", "symphony", "philharmonic", "chamber music", "choir",
        "string quartet", "ensemble", "recital",
        # Touring-act fallbacks — "Artist Tour", "Springsteen", "Bruce
        # Springsteen and E Street Band", "American Tour", etc. Catches
        # the long tail of allevents arena-show listings that don't hit
        # any specific venue keyword.
        " tour", "world tour", "us tour", "north american tour",
        "american tour", "live in concert", "in concert",
        " at madison square garden", "at barclays center",
        "at radio city", "at carnegie hall", "at beacon theatre",
        "at lincoln center", "at the apollo", "at brooklyn steel",
        "at terminal 5", "at webster hall", "at kings theatre",
    ],
    "parties": [
        "party", "social mixer", "mixer", "networking", "happy hour",
        "social club", "after-party", "afterparty",
        # iter 183: replaced bare 'social ' with specific phrases. The
        # trailing-space variant was matching FPs like 'social media' /
        # 'social tees' / 'social movement' / 'social striders' (half the
        # 'social' hits in current data were not party-context).
        "social night", "social hour", "social happy hour",
        "social meetup", "social gathering", "social event",
        "social run",      # 'Monday Evening Social Run' (also fitness)
        "social dance",    # 'FREE Latin Dance Social at...'
        "after-work social", "after work social",
        "housewarming", "brunch party", "rooftop party", "loft party",
        "warehouse party", "speakeasy", "cocktail party", "after-hours",
        "underground", "boat party", "block party", "kickback",
        "anniversary party", "release party",
        "drag queen", "drag show", "drag bingo", "drag brunch",
        "queer", "pride", "lgbtq", "gay night", "lesbian night",
        "after hours", "afters", "all night", "all-nighter",
        # iter 177: bare 'bash' (4 chars, word-boundary), 'funday' (6 chars
        # substring). 'Birthday Bash' and 'Sunday Funday' are iconic NYC
        # social-event phrasings that the existing 'party'-based list
        # missed. 'bashful' / 'splash' don't word-boundary-match 'bash';
        # 'Sundayfunday' substrings to 'funday' which is correct (still
        # a party). Tested FP-free.
        "bash", "funday",
    ],
    "outdoors": [
        "park", "outdoor", "garden", "hike", "walk", "picnic", "rooftop",
        "boat", "harbor", "waterfront", "pier ", "beach", "ferry",
        "high line", "domino park", "central park",
        # Nature / birding / cemetery walks (Green-Wood)
        "birding", "bird walk", "nature walk", "tree climbing",
        "kayak", "rowing", "sailing", "fishing",
        "trail", "hiking",
        # iter 175: -ing forms (word-boundary on 'walk' / 'hike' don't
        # match 'walking' / 'hiking' in compound forms), plus common outdoor
        # event types missing from the original list. Kept the leading
        # space on 'walking ' so 'Sleepwalking' doesn't false-positive
        # (substring match needs the boundary).
        " walking", " biking", "bike tour", "walking tour",
        "camping", "bouldering", "climbing",
    ],
    "food": [
        "food festival", "dinner party", "tasting menu", "tasting", "culinary",
        "chef ", "supper club", "natural wine", "wine tasting", "wine bar",
        "cocktail", "smorgasburg", "popup dinner", "pop-up dinner",
        "restaurant week", "food crawl", "speakeasy",
        "tapping", "tap takeover", "beer release", "brewery",
        "pierogi", "fried chicken", "pizza party",
        "happy hour", "brunch",
        # iter 176: common food-event patterns and types missing from
        # original list. '<food> crawl' is iconic NYC; 'cooking class' is
        # the dominant DIY-food event format; 'whiskey'/'cheese' pairings
        # round out the existing 'wine' coverage.
        "bagel crawl", "taco crawl", "coffee crawl", "pizza crawl",
        "burger crawl", "donut crawl", "ramen crawl",
        "cooking class", "pasta class", "baking class",
        "ramen night", "pizza night", "taco night",
        "cheese tasting", "whiskey tasting", "cheese pairing",
    ],
    "games": [
        "board game", "trivia", "backgammon", "chess", "arcade", "game night",
        "mahjong", "poker night", "puzzle night", "gammon", "scrabble",
        "settlers of catan", "game social", "bingo", "card game",
        "the jewish dating game", "backgmmon",  # common misspelling
        "game show", "pub quiz", "quiz night",
        # iter 178: 'Catan Night' / 'Boardgame Bar' missed because only
        # 'board game' (with space) and 'settlers of catan' were listed.
        "catan", "boardgame",
        # iter 180: 'tournament' covers Magic: The Gathering, chess, poker,
        # esports tournaments. Note this also FP-matches music's ' tour'
        # keyword — that's fine, both signals can fire on the same event.
        "tournament",
    ],
    "theater": [
        # NB: bare "theater" / "theatre" are too noisy — Beacon Theatre,
        # Kings Theatre, Webster Hall etc. are music venues that also
        # get tagged. Bare musical-title words ("wicked", "company")
        # clash with venue/adjective uses ("Wicked Willy's bar",
        # "Company NYC"). Require play/show context instead.
        "play opening", "play reading", "broadway", "off-broadway",
        "drama school", "drama club", "stage play", "musical theater",
        "musical theatre", "the musical",
        # Specific NYC theater venues + popular musicals
        # Specific musical names — be constrained: bare "wicked",
        # "hamilton", "company", "phantom", "outsiders" all collide with
        # bar names, neighborhood names, adjective uses. Where the title
        # alone is ambiguous, anchor it ("wicked on broadway", "hamilton
        # the musical"). Unambiguous brand titles stay as-is.
        "wicked on broadway", "wicked the musical",
        "hamilton on broadway", "hamilton the musical",
        "moulin rouge the musical", "back to the future the musical",
        "lion king", "lion king the musical",
        "phantom of the opera",
        "mj the musical", "six the musical",
        "aladdin the musical", "harry potter and the cursed child",
        "tina turner musical", "& juliet",
        "hadestown", "kimberly akimbo", "the outsiders the musical",
        "playwrights horizons", "the public theater", "signature theatre",
        "ny theatre workshop", "joe's pub", "performance art",
    ],
    "comedy": [
        # iter 172: bare 'comedy' substring (6 chars). 'Comedy Open Mic' /
        # 'Dark Comedy Showcase' missed when only specific phrases were
        # listed. 'comedic' / 'comed' don't substring-match (different chars).
        "comedy",
        "comedy show", "improv", "stand-up", "standup", "open mic comedy",
        "comedy night", "sketch show", "comedy club", "comedy cellar",
        "comedy lottery", "comedy competition", "comedy at ", "comedy hour",
        "stand up showcase", "stand-up showcase", "comedy showcase",
        "special taping", "comedy taping",
        "ear hustle live", "drinking game nyc",
        "tight pants comedy", "combat zone 360",
        "qedastoria", "q.e.d.", "qed astoria", "ucb", "caveat",
        "eastville comedy", "carolines", "gotham comedy", "stand up ny",
        "comic ", "comics ", "comedians", "tuesday night laughs",
        "wednesday night laughs", "thursday night laughs",
        "comedy basement", "comedy at the kicker",
    ],
    "dance": [
        "dance class", "dance party", "dance night", "salsa night",
        "swing dance", "ballroom", "tango social",
        "salsa festival", "salsa social", "bachata", "kizomba",
        "vogue ", "ballet ", "dance battle",
        # iter 178: 'Ecstatic Dance' (somatic / wellness-y dance event,
        # popular in NYC), 'Contemporary Dance Show', 'Hip Hop Class' all
        # missed before. Bare 'ecstatic dance' / 'contemporary dance'
        # catch the common shapes.
        "ecstatic dance", "contemporary dance", "modern dance",
        "hip hop class", "hip-hop class",
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
        "zumba", "barre", "spin class", "spin studio",
        "run club", "running club", "weekend run", "morning run",
        "evening run", "night run", "afternoon run", "tuesday night run",
        "thursday night run", "monday night run", "wednesday night run",
        "rise & run", "rise and run", "rise n run", "rise n' run",
        "run & refuel", "run and refuel", "run + refuel",
        "run-prospect park", "social run",
        "social run", "saturday run", "sunday run",
        "group run", "casual run", "track club",
        "runners", "no regrets runners", "lululemon",
        "5k ", "10k ", "marathon training", "marathon",
        "bike ride", "group ride", "cycling club",
        "pickleball", "tennis meetup",
        "sprint", "track meet", "intervals at",
        "mccarren track", "domino park run",
        # broader patterns: "X 5k", "X Half Marathon", any run/runs
        " runs ", " run @", "saturday runs", "sunday runs",
        "half marathon", " 5k!", "yoga class", "yoga flow",
        "boxing class", "spin class", "cycle class",
        # iter 178: bare fitness modalities. All length-4+ substring or
        # word-boundary safe. 'Pilates Class' / 'CrossFit NYC' / 'HIIT
        # Workout' / 'Boot Camp' all fell to ['other'] before.
        "pilates", "crossfit", "hiit", "boot camp", "bootcamp",
    ],
    "movies": [
        "movie", "film screening", "movie screening", "outdoor movie",
        "rooftop movie", "rooftop screening", "indie film",
        # Iter 82: removed bare "premiere" — false-positived on
        # "NYC's Premiere Party" / "Premiere lesbian event" (means
        # "best/first" not "movie premiere"). Replaced with specific
        # phrases.
        "movie premiere", "film premiere", "premiere screening",
        "movie night", "drive-in", "movies under the stars",
    ],
    "celebrities": [
        "celebrity", "in conversation with", "live appearance",
        # Iter 82: removed bare "meet & greet" — false-positived on
        # dog-rescue + brand events ("meet & greet shelter dogs"). The
        # specific phrase "celebrity meet & greet" is what we want.
        "celebrity meet", "celebrity m&g",
        "fireside chat", "with special guest",
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
        "pop-up", "popup", "pop up at", "pop-up at",
        "wedding trends", "beauty pop-up",
        "brand pop-up", "brand pop up", "brand activation",
        "is popping up",
        # Science / themed exploration events
        "astronomy on tap", "science on tap", "philosophy on tap",
        "history on tap", "math on tap", "physics on tap",
        "a conversation with", "in conversation with",
        "rooftop happy hour at",
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
        # iter 174: bare '20s & 30s' (so 'NYC 20s & 30s Hangout' counts)
        # plus 'lock and key' (iconic match-the-keys singles format) and
        # 'bored of dating apps' (a curated NYC singles event series).
        "20s & 30s", "lock and key", "bored of dating apps",
        # Pattern catches: 'Slow Dating', 'Conscious Dating', 'Mindful Dating' —
        # the modern alternatives to speed dating.
        "slow dating", "conscious dating", "mindful dating",
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


_IG_ACCOUNT_TOPIC_HINTS = {
    "books": ("book", "bookclub", "litclub", "library", "poet", "read",
              "writers"),
    "music": ("jazz", "dj", "vinyl", "sound", "band", "music", "concert",
              "rave", "venue", "phono", "tunes", "bowl", "hall", "presents",
              "ballroom", "theatre", "theater"),
    "art": ("art", "gallery", "museum", "studio"),
    "comedy": ("comedy", "improv", "standup", "humor"),
    "food": ("food", "kitchen", "chef", "eats", "supper", "wine", "bar"),
    "fitness": ("running", "run", "fit", "yoga", "wellness", "workout"),
    "outdoors": ("park", "garden", "outdoor", "nature", "hike"),
    "parties": ("party", "social", "club", "rave", "nightlife", "afterhours"),
    "games": ("game", "backgammon", "chess", "bingo", "trivia"),
    "exploration": ("astronomy", "secret", "hidden"),
}


def _ig_account_topic_categories(account: str) -> list[str]:
    """Infer categories from the IG account handle when the title is
    too cryptic to categorize (e.g. '5/21 • caroline...' from a music
    venue's IG roundup). Returns list of category names that match
    substring patterns in the username.
    """
    if not account:
        return []
    u = account.lower()
    cats = []
    for cat, hints in _IG_ACCOUNT_TOPIC_HINTS.items():
        if any(h in u for h in hints):
            cats.append(cat)
    return cats


# Source name → primary category hint. When a venue scraper's source
# label encodes the venue's focus (newyorkcomedyclub → comedy), use it
# to disambiguate cryptic per-event titles (e.g. just a comic's name
# without 'comedy' in it).
_SOURCE_TOPIC_HINTS = {
    "newyorkcomedyclub": "comedy",
    "eastvillecomedy": "comedy",
    "bookclubbar": "books",
    "lizsbookbar": "books",
    "mcnallyjackson": "books",
    "powerhousearena": "books",
    "centerforfiction": "books",
    "brooklyncomedy": "comedy",
    "thebellhouseny": "comedy",
    "nypl": "books",
    "songkick": "music",
    # iter 165: structural music + food fallbacks. dice.fm scraper (iter
    # 101) and music_venues scraper both publish concert listings —
    # cryptic titles like 'caroline (5/21)' should default to music when
    # the title-keyword path produces nothing. smorgasburg (iter 106)
    # publishes only food-market recurrences.
    "dice": "music",
    "music_venues": "music",
    "smorgasburg": "food",
    # iter 182: museum + outdoor source-name fallbacks. Same logic as the
    # other entries — when the categorizer's keyword pass produces nothing
    # for a cryptic title, the source label itself encodes the venue type.
    "museums": "art",
    "nyc_parks": "outdoors",
    "greenwoodcemetery": "exploration",
}


_OUTDOORS_FALSE_POSITIVE_VENUES = (
    "madison square garden",  # MSG — indoor arena, "garden" is a misnomer
    "the garden at madison",
    "barclays center",
    "msg sphere",
    "the box",
    "garden room",  # private venue rooms named "Garden"
)

# Strong-outdoor signals — if any of these appear in the text along with
# an indoor-arena name, KEEP the outdoors tag (genuine outdoor activity at
# or near the arena). Single source of truth shared by the categorizer's
# own outdoor check (below) and normalize._strip_outdoors_indoor_arena.
_OUTDOORS_STRONG_SIGNALS = (
    "rooftop", "pier ", "waterfront", "park ", " park", "beach", "ferry",
    "high line", "domino park", "central park", "prospect park",
    "kayak", "hike", "trail", "outdoor concert", "outdoor movie",
    "outdoors", "outdoor ", "garden party",
)


def infer_categories(title: str, description: str = "", ig_account: str = "",
                     source: str = "") -> list[str]:
    text = f"{title} {description}".lower()
    cats = []
    for cat, keywords in CATEGORY_KEYWORDS.items():
        matched = False
        for kw in keywords:
            # Word-boundary match for short single-word keywords (<=5 chars)
            # to avoid 'gala' matching inside 'Lagala', 'tap' inside 'tape', etc.
            # Multi-word phrases stay as substring matches since their length
            # makes accidental matches negligible.
            if " " in kw or len(kw) > 5:
                if kw in text:
                    matched = True
                    break
            else:
                import re as _re
                if _re.search(rf"\b{_re.escape(kw)}\b", text):
                    matched = True
                    break
        if matched:
            cats.append(cat)
    # Suppress outdoors when the only signal was an indoor-arena name that
    # happens to contain a nature word. Madison Square Garden is the prime
    # offender — "garden" matches but it's an enclosed indoor arena.
    if "outdoors" in cats and any(v in text for v in _OUTDOORS_FALSE_POSITIVE_VENUES):
        # Only drop if no STRONG outdoor signal also present.
        if not any(s in text for s in _OUTDOORS_STRONG_SIGNALS):
            cats = [c for c in cats if c != "outdoors"]
    # Fall back to IG-account handle topic-hints when the title is cryptic
    # (e.g. '5/21 • caroline...' from a music venue's IG roundup). This is
    # structural — derives category from the account's stated focus rather
    # than scanning the title for venue-specific terms.
    #
    # Also augment when title-derived cats are venue-context cats only
    # (outdoors / food). 'Read on the Lawn at Bryant Park' from
    # @reading_rhythms hits 'outdoors' on 'lawn' but should also be 'books'
    # — the venue topic is the user's primary reason for going. Union the
    # ig-account hints when the title cats are weak/venue-only.
    if ig_account:
        if not cats:
            cats = _ig_account_topic_categories(ig_account)
        else:
            _VENUE_CONTEXT_CATS = {"outdoors", "food"}
            if set(cats) <= _VENUE_CONTEXT_CATS:
                acct_cats = _ig_account_topic_categories(ig_account)
                if acct_cats and acct_cats != ["other"]:
                    cats = sorted(set(cats) | set(acct_cats))
    # Source-level topic hint: a venue scraper like newyorkcomedyclub
    # encodes its focus in the source label. Use it as a default
    # category if nothing better matched.
    if (not cats or cats == ["other"]) and source in _SOURCE_TOPIC_HINTS:
        cats = [_SOURCE_TOPIC_HINTS[source]]
    return cats if cats else ["other"]


NYC_NEIGHBORHOODS = {
    "williamsburg": ["williamsburg", "n 6th", "n 7th", "bedford ave", "berry st", "wythe ave", "kent ave"],
    "east williamsburg": ["east williamsburg", "metropolitan ave brooklyn"],
    "east village": [
        "east village", "e 3rd", "e 4th", "e 5th", "e 6th", "e 7th", "e 9th",
        "e 10th st", "e 11th st", "e 12th st", "e 13th st", "st marks",
        "1st ave", "2nd ave", "ave a", "ave b", "ave c",
    ],
    "lower east side": [
        "lower east side", "les", "ludlow", "rivington", "orchard st",
        "delancey", "freeman alley", "essex st", "stanton st", "norfolk st",
    ],
    "bushwick": ["bushwick"],
    "greenpoint": ["greenpoint"],
    "dumbo": ["dumbo"],
    "park slope": ["park slope"],
    "carroll gardens": ["carroll gardens", "smith st", "court st", "smith street"],
    "cobble hill": ["cobble hill"],
    "boerum hill": ["boerum hill", "atlantic ave"],
    "crown heights": ["crown heights", "franklin ave", "kingston ave", "nostrand ave"],
    "bed-stuy": ["bed-stuy", "bedford-stuyvesant", "tompkins ave"],
    "long island city": ["long island city", "lic ", "vernon blvd", "jackson ave", "43rd ave queens"],
    "astoria": ["astoria", "ditmars", "30th ave queens"],
    "soho": ["soho", "spring st", "prince st", "greene st", "mercer st", "wooster st"],
    "noho": ["noho", "great jones st", "lafayette st nyc"],
    "tribeca": ["tribeca", "franklin st", "leonard st", "white st", "harrison st"],
    "chelsea": [
        "chelsea", "w 20th", "w 21st", "w 22nd", "w 23rd", "w 24th",
        "w 25th", "w 26th", "w 27th", "w 28th", "8th ave",
    ],
    "west village": [
        "west village", "bleecker st", "w 4th", "perry st", "christopher st",
        "hudson st", "bedford st", "morton st",
    ],
    "midtown": [
        "midtown", "times square", "rockefeller", "5th ave", "42nd",
        "east 30th", "east 31st", "east 32nd", "east 33rd", "east 34th",
        "east 35th", "east 36th", "east 37th", "east 38th", "east 39th",
        "east 40th", "east 41st", "east 42nd", "east 43rd", "east 44th",
        "east 45th", "east 46th", "east 47th", "east 48th", "east 49th",
        "east 50th",
        "west 30th", "west 31st", "west 32nd", "west 33rd", "west 34th",
        "west 35th", "west 36th", "west 37th", "west 38th", "west 39th",
        "w 38th", "w 39th",
        "e 38th", "e 39th", "e 40th", "e 41st", "e 42nd",
        "e 43rd", "e 44th", "e 45th", "e 46th", "e 47th", "e 48th",
        "e 49th", "e 50th", "park ave",
    ],
    "upper east side": [
        "upper east side", "ues", "museum mile",
        "east 60th", "east 61st", "east 62nd", "east 63rd", "east 64th",
        "east 65th", "east 66th", "east 67th", "east 68th", "east 69th",
        "east 70th", "east 71st", "east 72nd", "east 73rd", "east 74th",
        "east 75th", "east 76th", "east 77th", "east 78th", "east 79th",
        "east 80th", "east 81st", "east 82nd", "east 83rd", "east 84th",
        "east 85th", "east 86th",
        "e 60th", "e 61st", "e 62nd", "e 63rd", "e 64th", "e 65th",
        "e 66th", "e 67th", "e 68th", "e 69th", "e 70th", "e 71st",
        "e 72nd", "e 73rd", "e 74th", "e 75th", "e 76th", "e 77th",
        "e 78th", "e 79th", "e 80th", "e 81st", "e 82nd", "e 83rd",
        "e 84th", "e 85th", "e 86th",
    ],
    "upper west side": [
        "upper west side", "uws", "columbus ave", "amsterdam ave",
        "west 60th", "west 65th", "west 70th", "west 71st", "west 72nd",
        "west 73rd", "west 79th", "west 80th", "west 81st", "west 82nd",
        "west 84th",
        "w 60th", "w 65th", "w 70th", "w 71st", "w 72nd", "w 73rd",
        "w 79th", "w 80th", "w 81st", "w 82nd", "w 84th",
    ],
    "brooklyn heights": ["brooklyn heights"],
    "fort greene": ["fort greene"],
    "prospect heights": ["prospect heights"],
    "gowanus": ["gowanus"],
    "red hook": ["red hook"],
    "fidi": ["fidi", "financial district", "maiden lane", "wall st", "fulton st", "broad st"],
    "harlem": ["harlem", "lenox ave", "malcolm x blvd", "adam clayton powell"],
}


def infer_neighborhood(address: str, *extras: str) -> str | None:
    """Match the address — and any additional context strings (title,
    location.name, etc.) — against the NYC_NEIGHBORHOODS keyword map.
    The audit at iter 72 showed 32 events with `Williamsburg` / `Astoria` /
    `Harlem` in their *title* but no neighborhood inferred, because the
    old call site only passed the address. Accepting *extras lets callers
    fold the title in without changing the keyword map.
    """
    parts = [p for p in (address, *extras) if p]
    if not parts:
        return None
    lower = " ".join(parts).lower()
    for hood, keywords in NYC_NEIGHBORHOODS.items():
        if any(kw in lower for kw in keywords):
            return hood
    if "brooklyn" in lower:
        return "brooklyn"
    if "manhattan" in lower or "new york" in lower or "ny " in lower:
        return "manhattan"
    return None


_WEEKDAY_INDEX = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2, "weds": 2,
    "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

_DAY = r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|tues|wed|weds|thu|thur|thurs|fri|sat|sun)"

# Strong recurring signals — "every X", "weekly on X", "every other X".
# These are unambiguous and worth trusting wherever they appear.
_STRONG_RECURRING_PATTERNS = [
    re.compile(rf"\bevery\s+{_DAY}\b", re.IGNORECASE),
    re.compile(rf"\bweekly\s+(?:on\s+)?{_DAY}", re.IGNORECASE),
    re.compile(rf"\bevery\s+other\s+{_DAY}\b", re.IGNORECASE),
]

# Weak recurring signals — "Tuesday nights", "Sundays at...", "Saturdays".
# These are ambiguous: "Friday night" could just be context describing a
# one-time event. Only trust these in the FIRST 100 chars of the text
# (where a real recurring marker would be), AND only if the text doesn't
# also have a specific-month-day pattern.
_WEAK_RECURRING_PATTERNS = [
    re.compile(rf"\b{_DAY}s?\s+nights?\b", re.IGNORECASE),
    re.compile(rf"\b{_DAY}s?\s+@\s*\d", re.IGNORECASE),  # "Tuesdays @ 7"
    re.compile(rf"\b{_DAY}s\b", re.IGNORECASE),  # bare "Tuesdays" / "Sundays"
    re.compile(rf"\b{_DAY}\s+(?:morning|afternoon|evening)s\b", re.IGNORECASE),
    re.compile(rf"\b(?:on\s+)?{_DAY}s?\s+at\s+(?:the\s+)?\w+", re.IGNORECASE),
]

# Specific-date pattern: presence vetoes weak recurring signals.
_SPECIFIC_DATE_RE = re.compile(
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}|\b\d{1,2}/\d{1,2}|\b\d{1,2}\.\d{1,2}\.\d{2,4}\b",
    re.IGNORECASE,
)

# One-shot signals — these vetoes any recurring expansion. A specific
# artist "returning" / "presenting" / "live" is a single show, not weekly.
_ONE_SHOT_RE = re.compile(
    r"\breturns?\s+(?:to\s+)?(?:nyc|brooklyn|new\s+york)\b|"
    r"\bpresents?\b.*\b(?:live|tour|special|one[\s-]night)\b|"
    r"\bone[\s-]night[\s-]only\b|"
    r"\b(?:single|one)[\s-]time\b|"
    r"\btour\s+stop\b|"
    r"\b(?:opening|closing)\s+(?:night|reception|party)\b|"
    r"\bpremieres?\b|"
    r"\bdebut(?:s|ing)?\b|"
    r"\bfinale\b|"
    r"\bmark\s+your\s+calendars?\b",
    re.IGNORECASE,
)


def detect_recurring_weekday(text: str) -> int | None:
    """If the text mentions a weekly recurring weekday, return its index.

    Returns: 0 (Monday) through 6 (Sunday), or None if not recurring.
    """
    if not text:
        return None

    # One-shot signals veto recurring expansion entirely. "TOKiMONSTA returns
    # to NYC" is not a weekly event even if the post mentions "Friday night".
    if _ONE_SHOT_RE.search(text):
        return None

    # Strong signals trump everything
    for pat in _STRONG_RECURRING_PATTERNS:
        m = pat.search(text)
        if m:
            return _WEEKDAY_INDEX.get(m.group(1).lower())

    # Weak signals: only the first 100 chars (event-content area), and
    # vetoed by any specific-date phrase ("March 27", "5/9", etc.) which
    # makes this clearly a one-time event.
    head = text[:100]
    if _SPECIFIC_DATE_RE.search(text):
        return None
    for pat in _WEAK_RECURRING_PATTERNS:
        m = pat.search(head)
        if m:
            return _WEEKDAY_INDEX.get(m.group(1).lower())

    return None


def expand_recurring_event(event: dict, weekday: int, weeks_ahead: int = 6) -> list[dict]:
    """Generate up to weeks_ahead future occurrences of a weekly event.

    Returns the original event plus N future copies on the same weekday.
    Each copy gets a unique id (date is part of the hash).
    """
    from datetime import datetime, timedelta
    base_date_str = event.get("date", "")
    if not base_date_str:
        return [event]

    try:
        base = datetime.fromisoformat(base_date_str).date()
    except Exception:
        return [event]

    occurrences = [event]
    next_date = base
    while len(occurrences) <= weeks_ahead:
        next_date = next_date + timedelta(days=7)
        days_to_target = (weekday - next_date.weekday()) % 7
        target_date = next_date + timedelta(days=days_to_target)
        if (target_date - base).days >= weeks_ahead * 7:
            break
        # Build a copy with the new date
        new_ev = dict(event)
        new_ev["date"] = target_date.isoformat()
        new_ev["id"] = make_event_id(
            event.get("source", ""),
            event.get("title", ""),
            new_ev["date"],
        )
        new_ev["recurring"] = True
        # Preserve location, categories etc. by reference (deep copy not needed)
        new_ev["location"] = dict(event.get("location", {}))
        new_ev["categories"] = list(event.get("categories", []))
        occurrences.append(new_ev)
    return occurrences


# Detect CTA-only lines like "Tickets at the link in our bio"
# A line is removed if it contains "link in bio" / "tickets in bio" AND
# is mostly just that CTA (no other meaningful content).
_LINK_IN_BIO_RE = re.compile(
    r"\b(?:link|tickets?|details?|info|RSVP|sign\s*up|swipe)\s+in\s+(?:our\s+|my\s+)?bio\b",
    re.IGNORECASE,
)
# Sentence-level CTA at end (after a period/exclamation/question)
_TRAILING_CTA_RE = re.compile(
    r"[\.!?]\s*[^.!?]*\b(?:link|tickets?|details?|info|RSVP|sign\s*up|swipe)\s+in\s+(?:our\s+|my\s+)?bio[^.!?]*[!.\s]*$",
    re.IGNORECASE,
)
_HASHTAG_CLUSTER_RE = re.compile(r"(?:\s|^)#\w[\w]*(?:\s+#\w[\w]*)+\s*$")
_TRAILING_HASHTAG_RE = re.compile(r"\s+#\w[\w]*\s*$")


def clean_description(text: str, max_length: int = 250) -> str:
    """Clean an IG-caption-style description for display.

    - Strip trailing hashtag clusters ("#nyc #brooklyn #events" at the end)
    - Remove "link in bio" / "tickets in bio" CTAs
    - Collapse excessive whitespace
    - Truncate at max_length, breaking at sentence boundary if possible
    """
    if not text:
        return ""

    # Process line by line — drop lines that are pure CTAs
    lines = []
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        # Drop short lines that are mostly CTA
        if _LINK_IN_BIO_RE.search(line) and len(line) < 80:
            continue
        # Drop lines that are JUST hashtags
        non_hashtag = re.sub(r"#\w+|\s+", "", line)
        if not non_hashtag:
            continue
        # Drop lines that are JUST @mentions (collaborator spam at end)
        non_mention = re.sub(r"@\w+|\s+|[,.\-—•]", "", line)
        if not non_mention and "@" in line:
            continue
        # Drop lines that are JUST emojis / decorative chars (5+ emoji in a row)
        non_emoji = re.sub(
            r"[\U0001F300-\U0001FAFF\U00002702-\U000027B0\U0001F000-\U0001F0FF\s\W]+",
            "",
            line,
        )
        if not non_emoji:
            continue
        # Drop lines that are JUST a URL
        if re.fullmatch(r"\s*https?://\S+\s*", line):
            continue
        lines.append(line)
    cleaned = " ".join(lines).strip()

    # Strip raw URLs from inside the description — we already have sourceUrl
    # in the event metadata, so URLs in the desc body are noise.
    cleaned = re.sub(r"\bhttps?://\S+", "", cleaned)
    # Collapse 3+ identical emoji into 1 (e.g., 🔥🔥🔥🔥 → 🔥)
    cleaned = re.sub(
        r"([\U0001F300-\U0001FAFF\U00002702-\U000027B0])\1{2,}",
        r"\1",
        cleaned,
    )

    # Within remaining text, drop sentences that contain "link in bio"
    # but only if they're <60 chars (CTAs) — leave longer sentences alone
    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    sentences = [
        s for s in sentences
        if not (_LINK_IN_BIO_RE.search(s) and len(s) < 60)
    ]
    cleaned = " ".join(sentences).strip()

    # Strip trailing CTA sentence ("...! Check out the link in our bio!")
    cleaned = _TRAILING_CTA_RE.sub("", cleaned).strip()

    # Strip trailing hashtag cluster
    while True:
        new = _HASHTAG_CLUSTER_RE.sub("", cleaned).rstrip()
        if new == cleaned:
            break
        cleaned = new
    for _ in range(20):
        new = _TRAILING_HASHTAG_RE.sub("", cleaned).rstrip()
        if new == cleaned:
            break
        cleaned = new

    # Collapse multiple spaces
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if len(cleaned) <= max_length:
        return cleaned

    # Try to break at a sentence boundary near max_length
    truncated = cleaned[:max_length]
    last_period = max(
        truncated.rfind(". "),
        truncated.rfind("! "),
        truncated.rfind("? "),
    )
    if last_period > max_length * 0.6:
        return truncated[: last_period + 1]
    # Otherwise break at word boundary
    last_space = truncated.rfind(" ")
    if last_space > max_length * 0.7:
        return truncated[:last_space] + "…"
    return truncated + "…"


_TITLE_LEADING_EMOJI_RE = re.compile(
    r"^[\U0001F300-\U0001FAFF\U00002702-\U000027B0\U0001F000-\U0001F0FF\s]+",
)
_TITLE_TRAILING_HASHTAGS_RE = re.compile(
    r"(?:\s+#\w+){2,}\s*$",
)
_TITLE_TRAILING_AT_MENTIONS_RE = re.compile(
    r"(?:\s+@[a-z0-9._]+){3,}\s*$",
    re.IGNORECASE,
)


def clean_title(title: str) -> str:
    """Strip emoji prefixes, trailing hashtag/mention walls, and HTML
    entity noise from event titles.
    """
    if not title:
        return title
    t = title.strip()
    # Decode common HTML entities
    t = t.replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")
    # OCR'd @ glyph: image-OCR sometimes reads the @ symbol on a flyer
    # as "G", "C", or "O" and glues it to the handle, producing
    # "Gbrooklynmuseum", "Chighlinenyc", etc. Detect single uppercase
    # letter followed by 4+ lowercase letters that end in a recognizable
    # venue/place suffix — almost certainly a misread @-handle. Replace
    # the leading cap with a proper @ so downstream link/handle parsing
    # works (e.g. AccountBanner can navigate to the IG profile).
    t = re.sub(
        r"\b[GCOQ]([a-z]{3,}(?:nyc|museum|park|fest|gallery|theatre|theater|"
        r"comedy|library|brewery|bookstore|stadium|hall|cafe|club|bridge|"
        r"jazz|garden|bar))\b",
        r"@\1",
        t,
    )
    # Strip leading emoji/punctuation cluster
    t = _TITLE_LEADING_EMOJI_RE.sub("", t)
    # Strip trailing hashtag wall (3+ hashtags at end)
    t = _TITLE_TRAILING_HASHTAGS_RE.sub("", t)
    # Strip trailing @-mention chain
    t = _TITLE_TRAILING_AT_MENTIONS_RE.sub("", t)
    # Strip trailing " on <Weekday>, <Month> <Day>" date suffix that IG
    # captions append to event names. Example transformations:
    #   "Hive Mind with Allen Aucoin on FRI, JUL 10"  -> "Hive Mind with Allen Aucoin"
    #   "BERTHA: Grateful Drag on SAT, OCT 10"        -> "BERTHA: Grateful Drag"
    #   "Donna The Buffalo on SAT, NOV 7"             -> "Donna The Buffalo"
    # Constrained to short trailing tokens (weekday + month abbreviation)
    # so we don't strip legit "...on Tuesday Night" style titles.
    t = re.sub(
        r"\s+on\s+(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*\.?,?\s+"
        r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+"
        r"\d{1,2}(?:st|nd|rd|th)?\.?\s*$",
        "",
        t,
        flags=re.IGNORECASE,
    )
    # IG captions follow the pattern "EVENT NAME: On <weekday>, <date>,
    # <rest of caption>" — the part before the colon is a clean event
    # name, the part after is a sentence. Truncate at the colon when:
    # 1. The title is longish (>30 chars total) — short titles like
    #    "BERTHA: Grateful Drag" should stay intact, and
    # 2. The text after the colon starts with a caption-fragment opener
    #    (On <weekday>, Finally, Tomorrow, This <weekday>, etc.) AND
    # 3. The text before the colon is at least 8 chars (a meaningful name).
    if len(t) > 30 and ":" in t:
        head, sep, tail = t.partition(":")
        head_stripped = head.strip()
        tail_stripped = tail.strip()
        if len(head_stripped) >= 8 and re.match(
            r"^(?:on\s+(?:mon|tue|wed|thur?|fri|sat|sun)[a-z]*,?|"
            r"finally,|tomorrow,|today,|tonight,|"
            r"this\s+(?:mon|tue|wed|thur?|fri|sat|sun)[a-z]*,)",
            tail_stripped,
            flags=re.IGNORECASE,
        ):
            t = head_stripped
    # Collapse 3+ identical emoji
    t = re.sub(
        r"([\U0001F300-\U0001FAFF\U00002702-\U000027B0])\1{2,}",
        r"\1",
        t,
    )
    # Collapse whitespace
    t = re.sub(r"\s+", " ", t).strip()
    return t


# Default start times by category — when caption has no time, infer from
# event type so events show up in the "Tonight" filter at the right slots.
_DEFAULT_START_BY_CATEGORY = {
    "parties": "20:00",
    "singles": "19:00",
    "nightlife": "21:00",
    "music": "20:00",
    "comedy": "20:00",
    "celebrities": "19:00",
    "theater": "19:30",
    "film": "19:30",
    "movies": "19:30",
    "viewings": "19:30",
    "books": "19:00",
    "food": "19:00",
    "fitness": "07:00",
    "wellness": "10:00",
    "outdoors": "10:00",
}


def infer_default_start_time(categories: list[str], title: str = "", description: str = "") -> str | None:
    """Infer a sensible default start time when none is in the caption.

    Returns None if no confident default — better to show no time than wrong.
    """
    if not categories:
        return None
    text = (title + " " + description).lower()
    # Brunch / breakfast → late morning
    if any(k in text for k in ("brunch", "breakfast", "morning meet")):
        return "11:00"
    # Happy hour / sunset
    if any(k in text for k in ("happy hour", "sunset")):
        return "18:00"
    # Art gallery openings / receptions → 18:00 (standard NYC gallery
    # opening hour). Detect explicit reception/opening text so a date-
    # only eventbrite art listing surfaces with a meaningful default time.
    if any(k in text for k in (
        "opening reception", "open reception", "exhibition opening",
        "open studios", "final open studios", "private view",
    )):
        return "18:00"
    for cat in categories:
        if cat in _DEFAULT_START_BY_CATEGORY:
            return _DEFAULT_START_BY_CATEGORY[cat]
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
    extra_images: list[str] | None = None,
    price: str | None = None,
    categories: list[str] | None = None,
    lat: float | None = None,
    lng: float | None = None,
) -> dict:
    if isinstance(event_date, date):
        date_str = event_date.isoformat()
    else:
        date_str = event_date

    if categories is None:
        categories = infer_categories(title, description, source=source)

    # Apply title cleanup
    cleaned_title = clean_title(title)

    # Infer default start time if missing (lets events show up in "Tonight").
    if not start_time:
        start_time = infer_default_start_time(categories, cleaned_title, description)

    # Filter extra_images to drop the primary image and any duplicates
    extras: list[str] = []
    if extra_images:
        seen = {image_url} if image_url else set()
        for img in extra_images:
            if img and img not in seen:
                extras.append(img)
                seen.add(img)

    location: dict = {
        "name": location_name or "",
        "address": address or "",
        # Fold title + location_name in (iter 72). Many events have an
        # informative title ("The 9:30 Comedy Show - Williamsburg",
        # "Harlem Book Company Pop Up") with no neighborhood-keyword in
        # the bare address. Audit showed 32/116 null-neighborhood events
        # recoverable this way.
        "neighborhood": infer_neighborhood(address or "", location_name or "", cleaned_title or ""),
    }
    # Persist lat/lng when available (IG geo-tag, future geocoding) so
    # ranking can compute true distance to user's home neighborhood.
    if lat is not None and lng is not None:
        try:
            location["lat"] = float(lat)
            location["lng"] = float(lng)
        except Exception:
            pass

    out = {
        "id": make_event_id(source, cleaned_title, date_str),
        "title": cleaned_title,
        "description": clean_description(description, max_length=300) if description else "",
        "date": date_str,
        "startTime": start_time,
        "endTime": end_time,
        "location": location,
        "categories": categories,
        "source": source,
        "sourceUrl": source_url,
        "imageUrl": image_url,
        "price": price or extract_price(f"{title} {description}"),
        "scrapedAt": datetime.now().isoformat(),
    }
    # Only include extraImages when present — keeps non-carousel events lean
    if extras:
        out["extraImages"] = extras[:9]  # cap at 9 (10 slides total) to bound payload
    return out
