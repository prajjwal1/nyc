import os

IG_USERNAME = os.environ.get("IG_USERNAME", "prajfb")

IG_SESSION_FILE = os.environ.get(
    "IG_SESSION_FILE",
    os.path.expanduser(f"~/.config/instaloader/session-{IG_USERNAME}"),
)

# Seed IG accounts.  In addition, the discovery system harvests the user's
# follows + does BFS through @mentions in captions, so this list grows
# autonomously over time (see scrapers/discover.py).  Accounts that don't
# exist on IG are skipped silently.
IG_ACCOUNTS = list(dict.fromkeys([  # dedupe while preserving order
    # Curated NYC event aggregators
    "theskint",
    "secretnyc",            # was "secret.nyc"; canonical is no-dot
    "timeoutnewyork",
    "onefinedaynyc",
    "nonsensenyc",          # was "nonsense.nyc"; canonical is no-dot
    "thingstodoinnyc",
    "newyorkcity",
    "ilovenynyc",
    "explorenycfree",
    "fomofeed",
    # NYC parks / outdoor
    "nycparks",
    "thehighlinenyc",
    "centralparknyc",
    "domino_park",
    "pier17nyc",
    "brooklynbridgepark",
    "bryantparknyc",
    # Live music venues
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
    "themuseumofmodernart",  # canonical for MoMA — "moma" is a different acct
    "themorganlibrary",
    "cooperhewitt",
    # Bookstores / literary
    "bookclubbar",
    "mcnallyjackson",
    "powerhousearena",
    "strandbookstore",       # was "stranbookstore" (typo)
    "lizsbookbar",
    # Williamsburg creative spaces
    "recessgrove",
    # Comedy clubs
    "thecomedycellar",
    "ucbtheatre",
    "thecaveatnyc",
    "qedastoria",
    "greenpointcomedyclub",
    # Jazz clubs
    "smallsjazzclub",
    "villagevanguard",
    "bluenote.nyc",
    "smokejazzclub",
    # Food / dining
    "infatuation",
    "eaterny",
    # Singles / social (top priority)
    "sipsandstoriesnyc",
    "buzzkillnyc",
    # Alcohol-free nightlife — niche but high-signal for meet-people goal
    # without drinking
    "brightnightssocial",
    "thecuriousbar",
    "soberishfun",
    # Run clubs / fitness
    "midnightrunnersnewyork",
    "northbrooklynrunners",
    "vitalrunclub",
    "nobaddays",
    "nobaddaysrunclub",
    "brooklyntrackclub",
    "dashing.whippets",
    "fastandfriendsrun",
    "empireruns",
    "runfreebk",
    "oldmanrunclub",
    "newyorkroad.runners",
    # Yoga / wellness across the city
    "yogaforthepeople.nyc",
    "modoyoga",
    "humming.puppy",
    "sky_ting",
    "loomyogaclub",
    "yoga_at_the_garden",
    "namaste_nyc",
    # NYC city-curators (broad-mix)
    "donewyorkcity",
    "secret_nyc",
    "secretnyc",
    "exploringnyc",
    "explorenyc",
    # Place / spot accounts — content is "cool spots to check out" rather
    # than dated events. We treat their posts as evergreen recommendations
    # (see IG_SPOTS_ACCOUNTS below).
    "wherethefuckdowego",
    "thishappensnewyork",
    "newyorkguide",
    "newyorker.eats",
    "tastingny",
    "infatuation",  # Already covered above; restated as spot-source
    # Comedy clubs / scenes — live + comedy specifically requested
    "flophousecomedy",
    "greenpointcomedyclub",
    "newyorkcomedyclub",
    "nightofbadideas",
    "comedycellarnyc",
    # Live music / DJ collectives — the community-driven scene
    "recessgroove",
    "recess.nyc",
    "718sessions",
    "nowadays.nyc",
    "musichallofwilliamsburg",
    "bowerypresents",
    # Bookstore / literary scene
    "bookclubbar",
    "mcnally_jackson",
    "books.are.magic",
    "greenlightbookstore",
    "thestrandbooks",
    # Williamsburg / Greenpoint local
    "yeswilliamsburg",
    "greenpointers",
    "omgreenpoint",
]))

# Accounts whose posts are "cool spot" recommendations (places to check
# out, not dated events). Posts from these accounts get marked evergreen
# AND skip the date-required filter — "where to brunch this weekend",
# "best rooftops", "hidden bars", etc. Place-centric content.
IG_SPOTS_ACCOUNTS = frozenset({
    "wherethefuckdowego",
    "thishappensnewyork",
    "newyorkguide",
    "newyorker.eats",
    "tastingny",
    "infatuation",
})

IG_MAX_POSTS_PER_ACCOUNT = int(os.environ.get("IG_MAX_POSTS_PER_ACCOUNT", "20"))
IG_MAX_ACCOUNTS = int(os.environ.get("IG_MAX_ACCOUNTS", "0"))  # 0 = no cap
IG_SLEEP_BETWEEN_ACCOUNTS = float(os.environ.get("IG_SLEEP_BETWEEN_ACCOUNTS", "1.0"))

USER_INTERESTS = {
    # Categories the user actively cares about, ordered by priority
    "preferred_categories": [
        "music", "parties", "singles", "art", "food", "books",
        "outdoors", "exploration", "games", "theater", "dance",
        "comedy", "movies", "viewings", "celebrities", "wellness",
        "fitness", "design", "photography",
    ],
    # Categories that get a strong ranking boost (20s-30s NYC single lifestyle)
    "boost_categories": {
        "singles": 1.5,       # Top priority — user is single
        "music": 1.4,         # Live music
        "parties": 1.35,      # Social parties — meeting new people
        "games": 1.3,         # User actively follows backgammon clubs etc.
        "exploration": 1.25,  # NYC exploration (user wants to discover the city)
        "art": 1.15,
        "food": 1.15,
        "books": 1.15,        # Book club bar, reading rhythms
        "outdoors": 1.1,
        "celebrities": 1.1,
        "viewings": 1.1,
        "movies": 1.05,
        "comedy": 1.15,       # Stand-up / improv (good first-date ideas too)
        "dance": 1.1,
        "wellness": 1.05,
        "fitness": 1.1,       # Run clubs are great for meeting people
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
    "lu.ma": 0.9,        # legacy label; _domain_source now normalizes to "luma"
    "eventbrite.com": 0.55,
    "92ny.org": 0.85,
    "lpr.com": 0.85,
    "elsewhere": 0.85,
    "allevents": 0.5,    # major aggregator, weak curation per event
    "songkick": 0.72,    # structured artist/venue listings, strong on music
}
