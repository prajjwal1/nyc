# Source Pool Report — 2026-09-08 2135

## Probe summary
- Lu.ma topics probed: 3 | added: 0 | all 3 were unverified because outbound connections failed before an HTTP response
- URLs promoted from `discovered_urls`: 0
- Accounts promoted: 0
- Dead-URL retests: 1 | resurrected: 0 | result unresolved because outbound connections failed
- Net-new calendars meeting today's gate (>=5 upcoming, >=80% exclusion-clean/on-taste): 0 verified

## Proposals

None. The source-add gate could not be satisfied honestly in this run. Both the project HTTP client and direct `curl` failed at connection establishment, including the allowed escalated retry. These are connectivity failures, not zero-yield results, and no unverified source should be added.

The current source architecture is also newer than the static-list assumptions in the curator brief: Lu.ma and Eventbrite use bounded dynamic frontiers in `scrapers/utils/platform_discovery.py`; `LUMA_PAGES` is only a compatibility constant containing the NYC discovery URL. A source that already appears in `platform_frontier(...)` is not a net-new calendar even when it is absent from `GENERIC_URLS`.

## Candidate queue — do not add until a connected re-probe

These are non-duplicate calendar URLs surfaced by external search and absent from the repository, spanning the demonstrated `book`/`read` and `run`/Brooklyn interest areas. They are intentionally not proposals because current yield, parser compatibility, and the >=80% clean/on-taste ratio could not be measured.

### C1: `https://theworldsboroughbookshop.com/events/list/upcoming-events`
- **Interest area**: books/read; independent Queens bookstore events
- **Duplicate check**: no repository match; distinct from McNally Jackson, Strand, Ripped Bodice, Book Club Bar, Liz's Book Bar, and the library feeds
- **Exclusion precheck**: no account or host match in `user_excluded_sources.json`; the available search result showed no excluded title hint, but the full inventory was unreachable
- **Required next probe**: `scrapers.sources.generic.scrape_url`; require >=5 today-onwards events and >=80% clean/on-taste

### C2: `https://www.brooklynrunningco.com/blogs/news/events-calendar/`
- **Interest area**: run + Brooklyn; community runs and local running events
- **Duplicate check**: no repository match; distinct from Brooklyn Track Club, North Brooklyn Runners, NYRR-derived/Meetup searches, and the generic Eventbrite run searches
- **Exclusion precheck**: no account or host match; no obvious club/rave/AI/speed-dating signal in the source identity, but the full title inventory was unreachable
- **Required next probe**: `scrapers.sources.generic.scrape_url`; require >=5 today-onwards events and >=80% clean/on-taste

### C3: `https://NYCRuns.com/races`
- **Interest area**: run; NYC race calendar
- **Duplicate check**: no repository match; distinct from the existing run-club venue calendars and Meetup/Eventbrite topic searches
- **Exclusion precheck**: no account or host match; indexed sample titles (`NYCRUNS Falling Leaves Half Marathon`, `NYCRUNS Great Gobble 5K`, `NYCRUNS Haunted Island 10K`) contain no excluded title hints, but the full inventory was unreachable
- **Required next probe**: `scrapers.sources.generic.scrape_url`; require >=5 today-onwards events and >=80% clean/on-taste

### C4: `https://www.eventbrite.com/cc/writing-community-4261073`
- **Interest area**: books/read/social; recurring writing-community events
- **Duplicate check**: no repository match
- **Exclusion precheck**: no account or host match; indexed `Writers United Open Mic + Storytelling` instances contain no excluded title hints, but the full collection was unreachable
- **Required next probe**: verify >=5 today-onwards events and >=80% clean/on-taste; note that the Eventbrite classifier recognizes `/cc/` as `collection`, while `eventbrite.scrape()` currently fetches only `organizer` and `event` frontier kinds, so a verified collection needs either collection-frontier support or a generic-parser proof before adding

## State audits

### Topic-driven Lu.ma
- `run` -> `https://lu.ma/nyc/run`: connectivity failure; no yield conclusion
- `book`/`read` -> `https://lu.ma/nyc/books`: connectivity failure; no yield conclusion
- `club` -> `https://lu.ma/nyc/social`: connectivity failure; no yield conclusion
- `ny`, `nyc`, `bk`, and `brooklyn` are geographic terms already covered by the active `https://lu.ma/nyc` discover catalog rather than distinct topics.
- `ai` was not probed because the durable exclusion policy explicitly rejects AI-themed events.

### High-yield URL promotion
- Historical `url_health.json` entries use `events_emitted_total` and `last_event_count`, not the brief's `events_yielded` field.
- `https://luma.com/NoobsRPG` (last historical count 20), `https://luma.com/maayanadin` (20), and `https://lu.ma/thecollaboratory` (8) were reviewed. All are already selected by the dynamic Lu.ma frontier, so adding them to another list would not be a net-new source. Fresh taste/exclusion inventories could not be obtained.
- The `http://luma.com/thecollaboratory` row is a duplicate URL variant, not another source.

### Account promotion and co-mention BFS
- Joining `account_quality.json` to `discovered_accounts.json` found no account outside `IG_ACCOUNTS` that simultaneously has `events_emitted >= 5` and discovery score `>= 0.45`.
- The latest discovered-account rows have `discovered_via` values such as `user_saved_post` and `suggested_for:*`; none supplies the required `mentioned_by in signal_accounts` evidence for a co-mention promotion.
- The tempting high-score tail is dominated by individual comedians/people and is disallowed by fb-106 even apart from the missing yield qualification.

### Dead URL retest
- `https://www.eventbrite.com/o/79666346913`: last recorded as 6 failures and 0 successes (2026-07-22); retest ended in `ConnectError` before an HTTP response. It remains unresolved and must not be labeled dead or resurrected from this run.
- README-listed blocked sources (Bandsintown, Resident Advisor, Time Out, Tixr, and DICE city pages) were not re-probed.

## Directives addressed
- fb-216: discovery and exclusion checks were completed, and four non-duplicate candidates across two demonstrated-interest areas were queued. The shipping criterion is **not met** because zero candidates could be live-verified at >=5 upcoming events and >=80% clean/on-taste, and therefore no net-new normalized events can be claimed.
- Durable fb-153: `scrapers/data/user_excluded_sources.json` was checked before each candidate assessment. Exact account matches: none. Host fragments: none configured. Full `title_hints` sweeps remain pending because candidate inventories could not be fetched.
- Durable fb-106: no IG accounts were proposed; individual-person candidates in the discovery tail were rejected.

## Probes that failed (don't add)
- `https://lu.ma/nyc/run`: connection failed before HTTP response; not a zero-yield result
- `https://lu.ma/nyc/books`: connection failed before HTTP response; not a zero-yield result
- `https://lu.ma/nyc/social`: connection failed before HTTP response; not a zero-yield result
- `https://theworldsboroughbookshop.com/events/list/upcoming-events`: connection failed before HTTP response
- `https://www.brooklynrunningco.com/blogs/news/events-calendar/`: connection failed before HTTP response
- `https://NYCRuns.com/races`: connection failed before HTTP response
- `https://www.eventbrite.com/cc/writing-community-4261073`: connection failed before HTTP response
- `https://www.eventbrite.com/o/79666346913`: connection failed before HTTP response

## Open questions for the Critic
- Re-run C1-C4 from a network-enabled or residential-IP worker before the apply phase. Do not count search-index visibility or the September 4 feed snapshot as a live probe.
- If C4 qualifies, should the ingestion change teach `eventbrite.scrape()` to fetch `collection` frontier items, or should the URL be handled by the generic scraper? A config-only addition is inert under the current dynamic adapter.
- Today's requested three-source gain should be explicitly deferred rather than weakened: the saved feed is dated 2026-09-04 and is useful for candidate discovery, but it cannot prove 2026-09-08 live yield.
