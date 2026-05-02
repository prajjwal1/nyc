import os

IG_USERNAME = os.environ.get("IG_USERNAME", "prajfb")

IG_SESSION_FILE = os.environ.get(
    "IG_SESSION_FILE",
    os.path.expanduser(f"~/.config/instaloader/session-{IG_USERNAME}"),
)

IG_ACCOUNTS = [
    # Curated NYC event aggregators
    "theskint",
    "secret.nyc",
    "timeoutnewyork",
    "onefinedaynyc",
    "nonsense.nyc",
    "thingstodoinnyc",
    "newyorkcity",
    "ilovenynyc",
    # NYC parks / outdoor
    "nycparks",
    "thehighlinenyc",
    "centralparknyc",
    "domino_park",
    "pier17nyc",
    # Live music venues (top user interest)
    "sofarsounds",
    "elsewherebrooklyn",
    "houseofyesnyc",
    "knockdowncenter",
    "brooklynbowl",
    "rockwoodmusichall",
    "mercurylounge",
    "littlefieldnyc",
    "publicrecords",
    "littlewolfny",
    # Cultural institutions
    "brooklynmuseum",
    "metmuseum",
    "whitneymuseum",
    "newmuseum",
    "moma",
    "newmuseum",
    "themorganlibrary",
    "cooperhewitt",
    # Bookstores / literary
    "bookclubbar",
    "mcnallyjacksonbooks",
    "powerhousearena",
    "stranbookstore",
    # Food / dining culture
    "infatuation",
    "eaterny",
    # Art galleries / openings
    "artnewyork",
    "see.you.in.nyc",
]

IG_MAX_POSTS_PER_ACCOUNT = 12

USER_INTERESTS = {
    # Categories the user actively cares about, ordered by priority
    "preferred_categories": [
        "music", "parties", "singles", "art", "food", "books",
        "outdoors", "exploration", "games", "theater", "dance",
        "comedy", "movies", "viewings", "celebrities", "wellness",
        "design", "photography",
    ],
    # Categories that get a strong ranking boost (20s-30s NYC single lifestyle)
    "boost_categories": {
        "singles": 1.5,       # Top priority — user is single
        "music": 1.4,         # Live music
        "parties": 1.35,      # Social parties — meeting new people
        "exploration": 1.25,  # NYC exploration (user wants to discover the city)
        "art": 1.15,
        "food": 1.15,
        "outdoors": 1.1,
        "celebrities": 1.1,
        "viewings": 1.1,
        "movies": 1.05,
        "comedy": 1.1,
        "dance": 1.1,
        "wellness": 1.05,
    },
    "home_neighborhood": "williamsburg",
    "preferred_price": "free",
    # Times the user is most likely to attend events
    "preferred_days": ["friday", "saturday", "sunday", "thursday"],
    "preferred_hour_range": [17, 23],  # 5pm to 11pm
}

SOURCE_QUALITY = {
    # Instagram is user-curated (accounts the user follows) — highest priority
    "instagram": 1.0,
    # Curated newsletters and event platforms with strong taste
    "substack": 0.95,
    "partiful": 0.95,
    "luma": 0.9,
    "theskint": 0.85,
    # Museum / venue official sources
    "museums": 0.78,
    "music_venues": 0.78,
    "bookclubbar": 0.8,
    # Aggregators
    "eventbrite": 0.55,
    "meetup": 0.5,
    "nypl": 0.45,
    "nyc_parks": 0.65,
    "dice": 0.65,
    "nycforfree": 0.75,
    # Generic scraper sources (per-domain quality)
    "generic": 0.6,
    "lu.ma": 0.9,
    "eventbrite.com": 0.55,
    "92ny.org": 0.85,
    "lpr.com": 0.85,
    "elsewhere": 0.85,
}
