import os

IG_USERNAME = os.environ.get("IG_USERNAME", "prajfb")

IG_SESSION_FILE = os.environ.get(
    "IG_SESSION_FILE",
    os.path.expanduser(f"~/.config/instaloader/session-{IG_USERNAME}"),
)

IG_ACCOUNTS = [
    "theskint",
    "nycparks",
    "secret.nyc",
    "timeoutnewyork",
    "brooklynmuseum",
    "metmuseum",
    "whitneymuseum",
    "sofarsounds",
    "nonsense.nyc",
    "onefinedaynyc",
]

IG_MAX_POSTS_PER_ACCOUNT = 12

USER_INTERESTS = {
    "preferred_categories": ["music", "parties", "art", "food", "books", "outdoors", "games"],
    # Categories that get an extra ranking boost (20s-30s NYC lifestyle)
    "boost_categories": {"music": 1.3, "parties": 1.2, "art": 1.1, "food": 1.1},
    "home_neighborhood": "williamsburg",
    "preferred_price": "free",
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
    "meetup": 0.5,    # lots of language exchanges, dance classes, etc
    "nypl": 0.45,     # mostly kids/educational programs
    "nyc_parks": 0.65,
    "dice": 0.65,
    "nycforfree": 0.75,
}
