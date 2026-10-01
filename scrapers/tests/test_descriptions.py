import asyncio
import copy
import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from scrapers.utils import descriptions


TODAY = date(2026, 10, 1)
TEXT = "Bring a book and meet other readers for a relaxed evening of conversation."


def event(slug="reading1", *, source="luma", day=TODAY, score=0.8, description=""):
    url = (
        f"https://luma.com/{slug}"
        if source == "luma"
        else f"https://www.eventbrite.com/e/reading-party-tickets-{slug}"
    )
    return {
        "id": slug,
        "source": source,
        "sourceUrl": url,
        "title": f"Reading party {slug}",
        "date": day.isoformat(),
        "startTime": "19:00",
        "description": description,
        "score": score,
        "userFollowing": True,
        "account": "reading_rhythms",
        "organizer": "Reading Rhythms",
        "organizerUrl": "https://lu.ma/readingrhythms-manhattan",
        "organizerRefs": [{"platform": "luma", "handle": "reading_rhythms"}],
        "location": {"name": "The Nook", "address": "Brooklyn, NY 11211"},
        "categories": ["books"],
        "imageUrl": f"https://images.example.com/{slug}.jpg",
        "price": "free",
    }


def html_for(row, description=TEXT, *, url=None, day=None):
    data = {
        "@type": "Event",
        "name": row["title"],
        "url": url or row["sourceUrl"],
        "startDate": f"{day or row['date']}T19:00:00-04:00",
        "description": description,
    }
    return f'<script type="application/ld+json">{json.dumps(data)}</script>'


def test_cache_preserves_metadata_and_matches_aliases_but_not_other_occurrences():
    previous = [event(description=TEXT), event("123456789", source="eventbrite", description=TEXT)]
    alias = event()
    alias["sourceUrl"] = "https://lu.ma/reading1/?utm_source=calendar"
    renamed_slug = event("123456789", source="eventbrite")
    renamed_slug["sourceUrl"] = "https://eventbrite.com/e/updated-title-123456789?aff=share"
    existing = event(description="Fresh organizer text takes precedence.")
    next_occurrence = event(day=TODAY + timedelta(days=7))
    unrelated = event("reading2")
    rows = [alias, renamed_slug, existing, next_occurrence, unrelated]
    before = copy.deepcopy(rows)

    assert descriptions.restore_cached_descriptions(rows, previous) == 2

    assert alias["description"] == renamed_slug["description"] == TEXT
    for actual, original in zip(rows, before):
        assert {k: v for k, v in actual.items() if k != "description"} == {
            k: v for k, v in original.items() if k != "description"
        }
    assert rows[2:] == before[2:]


def test_budget_targets_only_top_recommendations_on_upcoming_days(monkeypatch):
    rows = [event(f"reading{i}", score=1 - i / 100) for i in range(41)]
    rows += [event("later", day=TODAY + timedelta(days=7), score=1)]
    rows += [event("past", day=TODAY - timedelta(days=1), score=1)]
    rows += [copy.deepcopy(rows[0])]
    calls = []

    async def fetch(url, **_kwargs):
        calls.append(url)
        return html_for(next(row for row in rows if row["sourceUrl"] == url))

    monkeypatch.setattr(descriptions, "fetch_text", fetch)
    stats = asyncio.run(descriptions.enrich_descriptions(
        rows, candidates=rows, today=TODAY, limit=3,
    ))

    assert calls == [row["sourceUrl"] for row in rows[:3]]
    assert stats["attempted"] == stats["enriched"] == 3
    assert rows[-1]["description"] == TEXT  # raw duplicates reuse the same request
    assert all(not row["description"] for row in rows[3:-1])


def test_inactive_platforms_and_existing_descriptions_make_no_requests(monkeypatch):
    async def unexpected(*_args, **_kwargs):
        raise AssertionError("no detail request should be made")

    monkeypatch.setattr(descriptions, "fetch_text", unexpected)
    rows = [event(), event("123456789", source="eventbrite", description=TEXT)]
    stats = asyncio.run(descriptions.enrich_descriptions(
        rows, candidates=rows, sources={"eventbrite"}, today=TODAY,
    ))
    assert stats["attempted"] == 0
    assert not rows[0]["description"]
    disabled = asyncio.run(descriptions.enrich_descriptions(
        rows, candidates=rows, limit=0, today=TODAY,
    ))
    assert disabled["attempted"] == 0


def test_detail_parser_rejects_siblings_dates_and_non_platform_urls():
    row = event()
    sibling = html_for(event("sibling"))
    assert descriptions._matching_description(sibling, row, row["sourceUrl"]) == ""
    moved = html_for(row, day=(TODAY + timedelta(days=1)).isoformat())
    assert descriptions._matching_description(moved, row, row["sourceUrl"]) == ""
    assert descriptions._matching_description(
        sibling + html_for(row), row, row["sourceUrl"],
    ) == TEXT
    for url in ("https://luma.com.evil.example/reading1", "file:///reading1", "https://user@luma.com/reading1"):
        assert descriptions._event_key({**row, "sourceUrl": url}) is None


def test_rate_limit_stops_only_the_affected_platform(monkeypatch):
    rows = [event(f"reading{i}") for i in range(3)]
    rows += [event(str(123456789 + i), source="eventbrite") for i in range(2)]
    calls = []

    async def fetch(url, **_kwargs):
        calls.append(url)
        if "luma.com" in url:
            response = httpx.Response(429, request=httpx.Request("GET", url))
            response.raise_for_status()
        return html_for(next(row for row in rows if row["sourceUrl"] == url))

    monkeypatch.setattr(descriptions, "fetch_text", fetch)
    stats = asyncio.run(descriptions.enrich_descriptions(rows, candidates=rows, today=TODAY))
    assert sum("luma.com" in url for url in calls) == 1
    assert stats["attempted"] == 3
    assert stats["enriched"] == 2
    assert stats["failed"] == 1
    assert stats["rateLimitedSources"] == ["luma"]
    assert all(not row["description"] for row in rows[:3])
    assert all(row["description"] == TEXT for row in rows[3:])


def test_deadline_retains_completed_descriptions_and_cancels_pending_request(monkeypatch):
    rows = [event("reading1"), event("reading2")]

    async def fetch(url, **_kwargs):
        if url == rows[0]["sourceUrl"]:
            return html_for(rows[0])
        await asyncio.Event().wait()

    monkeypatch.setattr(descriptions, "fetch_text", fetch)
    stats = asyncio.run(descriptions.enrich_descriptions(
        rows, candidates=rows, today=TODAY, max_seconds=0.05,
    ))
    assert stats["deadlineHit"] is True
    assert stats["cancelled"] == 1
    assert stats["enriched"] == 1
    assert rows[0]["description"] == TEXT
    assert not rows[1]["description"]


def test_request_timeout_leaves_event_intact_and_continues(monkeypatch):
    rows = [event("reading1"), event("reading2")]
    first = copy.deepcopy(rows[0])

    async def fetch(url, **_kwargs):
        if url == rows[0]["sourceUrl"]:
            await asyncio.Event().wait()
        return html_for(rows[1])

    monkeypatch.setattr(descriptions, "fetch_text", fetch)
    stats = asyncio.run(descriptions.enrich_descriptions(
        rows, candidates=rows, today=TODAY, request_timeout=0.02,
    ))
    assert rows[0] == first
    assert rows[1]["description"] == TEXT
    assert stats["timedOut"] == stats["failed"] == stats["enriched"] == 1
    assert stats["deadlineHit"] is False


def test_pipeline_rechecks_enriched_text_and_reuses_it_on_next_quick_refresh(monkeypatch):
    from scrapers import normalize, run_all, sanity_check
    from scrapers.utils import engagement, interest_profile, platform_discovery

    today = datetime.now(ZoneInfo("America/New_York")).date()
    good = event("good0001", day=today)
    bad = event("bad00002", day=today)
    bad["title"] = "Community Supper"
    previous = {}
    snapshots = []
    fresh = [good, bad]

    async def scrape():
        return copy.deepcopy(fresh)

    async def fetch(url, **_kwargs):
        if "bad00002" in url:
            return html_for(bad, "Professional networking for finance professionals and investors.")
        return html_for(good)

    monkeypatch.setattr(descriptions, "fetch_text", fetch)
    monkeypatch.setattr(run_all, "ASYNC_SCRAPERS", [("luma", scrape)])
    monkeypatch.setattr(run_all, "SYNC_SCRAPERS", [])
    monkeypatch.setattr(run_all, "SOURCE_ONLY", {"luma"})
    monkeypatch.setattr(run_all, "IG_BROWSER_ONLY", False)
    monkeypatch.setattr(run_all, "IG_PROTECTED_ONLY", False)
    monkeypatch.setattr(run_all, "IG_SAVED_ONLY", True)
    monkeypatch.setattr(run_all, "_load_previous_events_index", lambda _path: previous)
    monkeypatch.setattr(run_all, "_RUN_TELEMETRY", {
        "runCompleted": False, "partialRun": False, "timedOutSources": [], "instagram": {},
    })
    monkeypatch.setattr(run_all, "_write_events", lambda rows, _path: snapshots.append(copy.deepcopy(rows)))
    monkeypatch.setattr(engagement, "apply_engagement", lambda: {"present": False})
    monkeypatch.setattr(interest_profile, "build_profile", lambda: {})
    monkeypatch.setattr(normalize, "_learn_curated_from_saved", lambda _rows: None)
    monkeypatch.setattr(normalize, "_learn_excluded_from_hidden", lambda _rows: None)
    monkeypatch.setattr(platform_discovery, "record_platform_survival", lambda _rows: None)
    monkeypatch.setattr(sanity_check, "main", lambda *_args, **_kwargs: None)

    asyncio.run(run_all.main())

    assert len(snapshots[-1]) == 1
    final = snapshots[-1][0]
    assert final["sourceUrl"] == good["sourceUrl"]
    assert final["description"] == TEXT
    assert final["userFollowing"] is True
    assert final["organizerRefs"] == good["organizerRefs"]
    assert run_all._RUN_TELEMETRY["descriptionEnrichment"]["enriched"] == 2

    previous.update({row["id"]: row for row in snapshots[-1]})
    fresh[:] = [good]

    async def unexpected(*_args, **_kwargs):
        raise AssertionError("a quick refresh should reuse the successful description")

    monkeypatch.setattr(descriptions, "fetch_text", unexpected)
    asyncio.run(run_all.main())
    assert snapshots[-1][0]["description"] == TEXT
    assert run_all._RUN_TELEMETRY["descriptionEnrichment"]["attempted"] == 0
    assert run_all._RUN_TELEMETRY["descriptionEnrichment"]["cachedEvents"] == 1
