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
    "preferred_categories": ["books", "art", "music", "games", "outdoors", "food", "parties"],
    "home_neighborhood": "williamsburg",
    "preferred_price": "free",
}

SOURCE_QUALITY = {
    "substack": 1.0,
    "luma": 0.9,
    "partiful": 0.85,
    "nypl": 0.8,
    "museums": 0.8,
    "music_venues": 0.8,
    "instagram": 0.7,
    "meetup": 0.65,
    "eventbrite": 0.6,
    "nyc_parks": 0.7,
    "theskint": 0.9,
    "bookclubbar": 0.8,
    "dice": 0.7,
    "nycforfree": 0.8,
}
