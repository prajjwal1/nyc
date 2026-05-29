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
    # Bookstore / literary scene (bookclubbar dedup'd — already at line 54)
    "mcnally_jackson",
    "books.are.magic",
    "greenlightbookstore",
    "thestrandbooks",
    # Williamsburg / Greenpoint local
    "yeswilliamsburg",
    "greenpointers",
    "omgreenpoint",
    # Auto-promoted from discovered_accounts: lifetime yield ≥10 events with
    # ≥5 posts scraped. Promoting them to curated (a) protects them from
    # discovery-pool pruning, (b) gives them tier-2 priority in the scrape
    # rotation, (c) qualifies their events for the lower 0.20 MIN_SCORE
    # floor. Avoids letting high-yield accounts churn out of the seed list.
    "nyc_forfree",
    "nycbackgammonclub",
    "nyc_dot",
    "bennysoto",
    "ateazorganic",
    "barnun.life",
    "itsinqueens",
    "dyslmshow",
    "maggie_onthemove",
    "dashwood_books",
    "highlinenyc",
    "wordbookstores",
    "bronx_river",
    "brooklynmagazine",
    "kin_kollective_",
    "downtownnyc",
    "eliescobarnyc",
    "franklinparkreadingseries",
    "secondsrunclub",
    "dannykrivit",
    "hithouse",
    "mamachaempanacha",
    "nitehawkcinema",
    "nyucreativewriting",
    # Second-tier promotions (7-9 lifetime events, ≥10 posts seen) —
    # consistently event-producing NYC accounts that haven't yet hit
    # the 10-event threshold. Same justification as the first tier.
    "bigvisionnyc",
    "chelseapiersfitness",
    "highlineartnyc",
    "nook_bklyn",
    "nyplyounglions",
    "nyculture",
    "reading_rhythms",
    "bigreuse",
    "midnightrunners",
    "greenlightbklyn",
    "litclub.nyc",
    "no.vista",
    "doppelganger_bar_nyc",
    "cysknyc",
    # Third-tier promotions (4-6 lifetime events) — clear NYC event
    # accounts that consistently produce content. Filtered to event-
    # organizing handles (skipped personal influencer / political /
    # health-clinic accounts even when they cleared the yield bar).
    "brooklynbookbodega",
    "philosophy.nyc",
    "queerfeetnyc",
    "open.bookclub",
    "booksaremagicbk",
    "center4fiction",
    "nycsprintcollective",
    "zoomiesrunclub",
    "thenewyorkgames",
    "wnrr_nyc",
    "berryparkbk",
    "joyflowerpotnyc",
    # 2026-05-28 self-improve run: promote user_following signal_accounts
    # to curated so they get the 21-day cooldown auto-revive. (Critic's
    # modified P3; excludes timeoutnewyork — publisher, not venue/curator.
    # Also excludes individual-person accounts per fb-106: only clubs /
    # venues / curators / social brands belong in IG_ACCOUNTS.)
    "anaiswinebk",            # wine bar in BK
    "asianfoundersclub",      # club
    "brightlightorg",         # org
    "brooklynbotanic",        # Brooklyn Botanic Garden
    "brooklynheightsassociation",
    "crownheightscraftclub",  # craft club
    "fortheplotnyc",          # social brand / event series
    "franklinparkbk",         # bar / venue
    "greenpointtrashclub",    # social eco-club
    "likeafriendsaid.nyc",    # social brand
    "quietreading.club",      # book club
    "richardsgamesnyc",       # games series
    "rummikubers",            # games club
    "silentbookclub.nyc",     # book club
    "strangersorfriendsbk",   # social brand
    "yogaspace.nyc",          # yoga studio
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
    "onefinedaynyc",      # daily NYC guide — mix of dated events AND
                          # evergreen "cool place to check out" picks.
                          # Treating IG posts as spots is the safer default;
                          # the Substack RSS still extracts dated events
                          # separately, so we don't lose the time-bound
                          # content.
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
    "lizsbookbar": 0.8,
    "mcnallyjackson": 0.85,
    # Aggregators
    "eventbrite": 0.55,
    "meetup": 0.5,
    "nypl": 0.45,
    "nyc_parks": 0.65,
    "dice": 0.65,
    "nycforfree": 0.75,
    # Generic scraper sources (per-domain quality)
    "generic": 0.6,
    # iter 163: keys must match the actual label produced by
    # generic._domain_source. 'eventbrite.com' and 'lu.ma' were redundant
    # with 'eventbrite' / 'luma' (already covered above; lu.ma also has an
    # alias). '92ny.org' and 'elsewhere' never fired because the labels
    # produced are '92ny' and 'elsewherebrooklyn' respectively.
    "92ny": 0.85,
    "lpr.com": 0.85,
    "elsewherebrooklyn": 0.85,
    "allevents": 0.35,   # major aggregator, weak curation per event
    "songkick": 0.6,     # structured artist/venue listings, strong on music
    "newyorkcomedyclub": 0.55,  # venue calendar; single-venue spam without cap
    "eastvillecomedy": 0.55,
    "thebellhouseny": 0.6,
    # iter 160: source-quality scores for the dedicated scrapers added
    # iter 100-110. Defaults to 0.5 otherwise — too low for high-curation
    # bookstore / venue sources.
    "powerhousearena": 0.8,    # Brooklyn literary bookstore; high curation
    "centerforfiction": 0.85,  # NYC literary institution; rare events
    "brooklyncomedy": 0.6,     # indie comedy venue; high volume, BCC alone
    "smorgasburg": 0.7,        # recurring weekend food market
    "greenwoodcemetery": 0.7,  # historic Brooklyn venue, varied programming
    # (parks.py emits source="nyc_parks" — already covered above; the
    # scraper-name "parks" in run_all is only used for logging.)
}

# Per-source volume caps. Aggregator sources have hundreds of events
# each — without a cap they crowd out user-relevant content
# (IG events, books, social mixers). Top-N by score per source.
SOURCE_VOLUME_CAPS = {
    # Aggregator caps tightened per user 'less is more' direction.
    # These sources dump hundreds of concert-listing events that
    # crowd out social/literary/discovery content. Top-N by score
    # is kept per source — same diversity, less long-tail.
    "allevents": 40,
    "songkick": 25,
    "newyorkcomedyclub": 15,
    "eastvillecomedy": 10,
    "thebellhouseny": 10,
    "meetup": 60,
    # Iter 90: eventbrite pagination now reaches pages 2-3 — yield could
    # grow from ~111 to 200+. Cap at 100 so the top-100 best events
    # bubble up from a deeper pool without dominating the feed.
    "eventbrite": 100,
    # Iter 126: caps for sources that grew significantly this session and
    # could otherwise dominate. nycforfree.py iter-100 rewrite yields ~83
    # future events; mcnallyjackson iter-102 dynamic month URLs yields
    # ~44. Both are user-interested (free events + literary) so the cap is
    # generous, but bounds it so they don't crowd out other content.
    "nycforfree": 40,
    "mcnallyjackson": 30,
    # Iter 155: brooklyncomedy yields 119 raw events (iter 106 Squarespace
    # scraper). Cap at 20 — Brooklyn Comedy Collective programs an
    # enormous indie comedy schedule but the user values diversity over
    # one venue's volume.
    "brooklyncomedy": 20,
    # iter 110 venue scrapers — low-volume but cap defensively.
    "powerhousearena": 15,
    "centerforfiction": 15,
}
