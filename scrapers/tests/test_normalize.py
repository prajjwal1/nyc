"""Regression tests for scrapers.normalize.

Locks in:
  - Exact-title same-source dedup (pass 1).
  - Cross-source same-venue same-date merge with shared distinctive tokens
    (iter 65 — songkick + allevents Charlie Puth at MSG should collapse).
  - Same-venue same-date but DIFFERENT titles do NOT merge.
  - `_strip_outdoors_indoor_arena` removes the "outdoors" tag from MSG /
    Barclays events unless a strong outdoor signal is present.
  - `_backfill_neighborhood_from_venue` resolves Liz's Book Bar →
    carroll gardens and Book Club Bar → east village.
"""

import pytest

import scrapers.normalize as normalize
from scrapers.normalize import (
    DEFAULT_MIN_SCORE,
    IG_CURATED_MIN_SCORE,
    _backfill_neighborhood_from_venue,
    _infer_time_from_text,
    _dedup_fuzzy_title,
    _dedup_same_account_recurring,
    _is_distinct_schedule_source,
    _is_shell_event,
    _min_score_floor,
    _strip_outdoors_indoor_arena,
    deduplicate,
)
from scrapers.sources.luma import LUMA_PAGES


def _luma_curator_urls():
    """The hand-curated single-curator lu.ma calendars in LUMA_PAGES —
    lu.ma/<handle>, as opposed to the lu.ma/nyc[/<category>] aggregate feeds."""
    out = []
    for u in LUMA_PAGES:
        if "lu.ma/" not in u:
            continue
        path = u.split("lu.ma/", 1)[1].strip("/")
        if path == "nyc" or path.startswith("nyc/"):
            continue
        out.append(u)
    return out


# ---------------------------------------------------------------------------
# Curated-source survival — regression guard for the lu.ma/philosophy bug:
# a curator calendar added to LUMA_PAGES whose (description-less) events were
# silently dropped by the description-required shell filter because the host
# was never added to user_curated_sources.json. The fix treats ALL lu.ma
# curator calendars as curated automatically, so this can't recur for any
# current OR future curator added to LUMA_PAGES.
# ---------------------------------------------------------------------------


class TestCuratedSourceSurvival:
    def _descless_luma_event(self, url):
        # Mirrors what the luma scraper emits for philosophy: real image +
        # venue, but an EMPTY description.
        return {
            "source": "luma",
            "title": "Philosophy Salon at the Museum",
            "description": "",
            "imageUrl": "https://images.lumacdn.com/x.jpg",
            "location": {"name": "The Met", "address": "1000 5th Ave"},
            "date": "2026-07-15",
            "startTime": "19:00",
            "sourceUrl": url,
        }

    @pytest.mark.parametrize("url", _luma_curator_urls())
    def test_every_luma_curator_calendar_survives_shell_filter(self, url):
        # Every configured lu.ma curator calendar must NOT be shell-dropped
        # when it emits a description-less (but image+venue) event — the
        # exact failure mode that hid lu.ma/philosophy. Adding a new curator
        # to LUMA_PAGES that regresses this will fail here.
        ev = self._descless_luma_event(url)
        assert not _is_shell_event(ev), (
            f"{url}: description-less curator event dropped as shell — "
            f"luma curator calendars must bypass the description-required filter"
        )

    def test_luma_nyc_aggregate_feed_still_requires_description(self):
        # The lu.ma/nyc[/category] AGGREGATE feeds are NOT curator calendars;
        # a description-less event from them should still be shell-dropped
        # (they're aggregator-style and the bypass must not over-reach).
        ev = self._descless_luma_event("https://lu.ma/nyc/social")
        assert _is_shell_event(ev) is True


# ---------------------------------------------------------------------------
# Score-floor — followed/curated events get the lower floor REGARDLESS of
# source (the 2nd half of the philosophy bug: followed lu.ma events sat at
# the 0.55 default and were filtered despite being followed).
# ---------------------------------------------------------------------------


class TestMinScoreFloor:
    def test_followed_non_ig_event_gets_curated_floor(self):
        ev = {"source": "luma", "userFollowing": True}
        assert _min_score_floor(ev, set()) == IG_CURATED_MIN_SCORE

    def test_saved_non_ig_event_gets_curated_floor(self):
        ev = {"source": "eventbrite", "userSaved": True}
        assert _min_score_floor(ev, set()) == IG_CURATED_MIN_SCORE

    def test_plain_non_ig_event_gets_default_floor(self):
        ev = {"source": "eventbrite"}
        assert _min_score_floor(ev, set()) == DEFAULT_MIN_SCORE

    def test_curated_seed_ig_account_gets_curated_floor(self):
        ev = {"source": "instagram", "instagramAccount": "philosophy.nyc"}
        assert _min_score_floor(ev, {"philosophy.nyc"}) == IG_CURATED_MIN_SCORE

    def test_unknown_ig_account_gets_default_floor(self):
        ev = {"source": "instagram", "instagramAccount": "rando"}
        assert _min_score_floor(ev, {"philosophy.nyc"}) == DEFAULT_MIN_SCORE


# ---------------------------------------------------------------------------
# DISTINCT_SCHEDULE_SOURCES — individually-ticketed repeated-title sources
# (brooklyncontra et al.) must bypass BOTH dedup passes (fb-183). The check
# lives in one helper so a future source can't be half-exempted.
# ---------------------------------------------------------------------------


class TestDistinctScheduleSources:
    def test_helper_membership(self, monkeypatch):
        monkeypatch.setattr(normalize, "DISTINCT_SCHEDULE_SOURCES", {"sched"})
        assert _is_distinct_schedule_source({"source": "sched"}) is True
        assert _is_distinct_schedule_source({"source": "other"}) is False

    def test_distinct_source_bypasses_both_passes(self, monkeypatch):
        monkeypatch.setattr(normalize, "DISTINCT_SCHEDULE_SOURCES", {"sched"})
        # Same-account-recurring would collapse near-identical titles across
        # dates (same publisher); fuzzy-title would collapse same-date+venue.
        recurring = [
            {
                "source": "sched",
                "title": "Weekly Social Dance Night",
                "date": "2026-07-01",
                "sourceUrl": "https://sched.org/x",
                "location": {"name": "Hall"},
            },
            {
                "source": "sched",
                "title": "Weekly Social Dance Night",
                "date": "2026-07-08",
                "sourceUrl": "https://sched.org/y",
                "location": {"name": "Hall"},
            },
        ]
        assert len(_dedup_same_account_recurring(recurring)) == 2
        same_day = [
            {
                "source": "sched",
                "title": "Harvest Ball Advanced Dance",
                "date": "2026-09-26",
                "location": {"name": "Hall"},
            },
            {
                "source": "sched",
                "title": "Harvest Ball Evening Dance",
                "date": "2026-09-26",
                "location": {"name": "Hall"},
            },
        ]
        assert len(_dedup_fuzzy_title(same_day)) == 2

    def test_control_source_still_merges(self, monkeypatch):
        # A source NOT in the set must still merge (proves the bypass is the
        # cause, not a broken dedup).
        monkeypatch.setattr(normalize, "DISTINCT_SCHEDULE_SOURCES", {"sched"})
        same_day = [
            {
                "source": "eventbrite",
                "title": "Harvest Ball Advanced Dance",
                "date": "2026-09-26",
                "location": {"name": "Hall"},
            },
            {
                "source": "eventbrite",
                "title": "Harvest Ball Evening Dance",
                "date": "2026-09-26",
                "location": {"name": "Hall"},
            },
        ]
        assert len(_dedup_fuzzy_title(same_day)) == 1


# ---------------------------------------------------------------------------
# deduplicate — exact-key merge plus the cross-source fuzzy merge.
# ---------------------------------------------------------------------------


class TestDeduplicate:
    def test_identical_source_title_date_collapses(self):
        # Two events with the same (source, title, date) merge in pass 1.
        events = [
            {
                "source": "songkick",
                "title": "Test Show",
                "date": "2026-05-30",
                "location": {"name": "Venue X"},
            },
            {
                "source": "songkick",
                "title": "Test Show",
                "date": "2026-05-30",
                "location": {"name": "Venue X"},
            },
        ]
        result = deduplicate(events)
        assert len(result) == 1

    def test_cross_source_same_venue_charlie_puth_merge(self):
        # iter 65: songkick's "Charlie Puth @ Madison Square Garden" and
        # allevents's "Charlie Puth, Daniel Seavey, Ally Salort in New York"
        # — same date, same venue, 2+ shared distinctive tokens (charlie,
        # puth) → cross-source merge.
        events = [
            {
                "source": "songkick",
                "title": "Charlie Puth @ Madison Square Garden",
                "date": "2026-05-29",
                "location": {"name": "Madison Square Garden"},
            },
            {
                "source": "allevents",
                "title": "Charlie Puth, Daniel Seavey, Ally Salort in New York",
                "date": "2026-05-29",
                "location": {"name": "Madison Square Garden"},
            },
        ]
        result = deduplicate(events)
        assert len(result) == 1
        # Both sources retained on the merged record for the "Recommended
        # by N sources" UI.
        sources = set(result[0].get("contributingSources", []))
        assert sources == {"songkick", "allevents"}

    def test_different_venues_same_date_do_not_merge(self):
        # Different titles, different venues, same date → 2 events.
        events = [
            {
                "source": "a",
                "title": "Jazz Night",
                "date": "2026-05-29",
                "location": {"name": "Blue Note"},
            },
            {
                "source": "b",
                "title": "Rock Show",
                "date": "2026-05-29",
                "location": {"name": "Bowery Ballroom"},
            },
        ]
        result = deduplicate(events)
        assert len(result) == 2

    def test_different_dates_same_venue_same_title_do_not_merge(self):
        # Same venue + same title but different dates = two real events
        events = [
            {
                "source": "songkick",
                "title": "Recurring Show",
                "date": "2026-05-29",
                "location": {"name": "Same Venue"},
            },
            {
                "source": "songkick",
                "title": "Recurring Show",
                "date": "2026-06-05",
                "location": {"name": "Same Venue"},
            },
        ]
        result = deduplicate(events)
        assert len(result) == 2

    def test_empty_list_returns_empty(self):
        assert deduplicate([]) == []

    def test_single_event_passes_through(self):
        ev = {
            "source": "songkick",
            "title": "Solo Event",
            "date": "2026-05-29",
            "location": {"name": "Venue"},
        }
        assert deduplicate([ev]) == [ev]


# ---------------------------------------------------------------------------
# _strip_outdoors_indoor_arena — defensive scrub of stale "outdoors" tags
# on MSG / Barclays / other indoor arenas.
# ---------------------------------------------------------------------------


class TestStripOutdoorsIndoorArena:
    def test_msg_loses_outdoors_tag(self):
        ev = {
            "title": "Concert",
            "description": "",
            "categories": ["music", "outdoors"],
            "location": {"name": "Madison Square Garden"},
        }
        _strip_outdoors_indoor_arena([ev])
        assert ev["categories"] == ["music"]

    def test_msg_with_rooftop_keeps_outdoors(self):
        # Strong outdoor signal ("rooftop") preserves the tag even at MSG
        ev = {
            "title": "Concert",
            "description": "rooftop session",
            "categories": ["music", "outdoors"],
            "location": {"name": "Madison Square Garden"},
        }
        _strip_outdoors_indoor_arena([ev])
        assert "outdoors" in ev["categories"]

    def test_barclays_loses_outdoors(self):
        ev = {
            "title": "NBA Game",
            "description": "",
            "categories": ["outdoors"],
            "location": {"name": "Barclays Center"},
        }
        _strip_outdoors_indoor_arena([ev])
        # When the only category was outdoors and it was stripped, the code
        # backfills with "other" so a card without a category isn't created.
        assert "outdoors" not in ev["categories"]
        assert ev["categories"] == ["other"]

    def test_non_arena_keeps_outdoors(self):
        ev = {
            "title": "Picnic",
            "description": "",
            "categories": ["outdoors"],
            "location": {"name": "Prospect Park"},
        }
        _strip_outdoors_indoor_arena([ev])
        assert "outdoors" in ev["categories"]

    def test_no_outdoors_tag_untouched(self):
        # If the event never had outdoors, the function leaves it alone
        ev = {
            "title": "Show",
            "description": "",
            "categories": ["music"],
            "location": {"name": "Madison Square Garden"},
        }
        _strip_outdoors_indoor_arena([ev])
        assert ev["categories"] == ["music"]


# ---------------------------------------------------------------------------
# _backfill_neighborhood_from_venue — venue-name table + address fallback.
# ---------------------------------------------------------------------------


class TestBackfillNeighborhood:
    def test_lizs_book_bar_to_carroll_gardens(self):
        # Bookmanager-powered scrapers (lizsbookbar) lack addresses, so
        # the venue-name → neighborhood table is the only signal.
        events = [
            {
                "title": "Reading",
                "location": {
                    "name": "Liz's Book Bar",
                    "neighborhood": None,
                    "address": "",
                },
            }
        ]
        _backfill_neighborhood_from_venue(events)
        assert events[0]["location"]["neighborhood"] == "carroll gardens"

    def test_book_club_bar_to_east_village(self):
        events = [
            {
                "title": "Lit Talk",
                "location": {
                    "name": "Book Club Bar",
                    "neighborhood": None,
                    "address": "",
                },
            }
        ]
        _backfill_neighborhood_from_venue(events)
        assert events[0]["location"]["neighborhood"] == "east village"

    def test_moma_ps1_to_long_island_city_not_midtown(self):
        # fb-194: "MoMA PS1" contains "moma" as a substring; the bare "moma"
        # table entry maps to midtown. The longest-match lookup + explicit
        # "moma ps1" entry must win → long island city (Queens), not midtown.
        events = [
            {
                "title": "Warm Up: BADSISTA/ TOCCORORO",
                "location": {
                    "name": "MoMA PS1",
                    "neighborhood": "midtown",
                    "address": "22-25 Jackson Ave, Queens, NY 11101",
                },
            }
        ]
        _backfill_neighborhood_from_venue(events)
        assert events[0]["location"]["neighborhood"] == "long island city"

    def test_bare_moma_still_midtown(self):
        # The generic "moma" entry must still resolve MoMA (Manhattan flagship)
        # to midtown — the longest-match change must not regress it.
        events = [
            {
                "title": "Art Opening",
                "location": {"name": "MoMA", "neighborhood": None, "address": ""},
            }
        ]
        _backfill_neighborhood_from_venue(events)
        assert events[0]["location"]["neighborhood"] == "midtown"

    def test_queens_address_backfills_to_queens_not_manhattan(self):
        # fb-194: a Queens address with no neighborhood keyword must resolve
        # to a Queens tag via infer_neighborhood, never "manhattan".
        events = [
            {
                "title": "Beer Garden Party",
                "location": {
                    "name": "Bohemian Beer Garden",
                    "neighborhood": "manhattan",
                    "address": "29-19 24th Ave, Queens, NY",
                },
            }
        ]
        _backfill_neighborhood_from_venue(events)
        assert events[0]["location"]["neighborhood"] == "astoria"

    def test_address_fallback_when_no_venue_match(self):
        # No venue-name match → re-runs infer_neighborhood on address
        events = [
            {
                "title": "Event",
                "location": {
                    "name": "Random Venue",
                    "neighborhood": None,
                    "address": "100 Spring St",
                },
            }
        ]
        _backfill_neighborhood_from_venue(events)
        assert events[0]["location"]["neighborhood"] == "soho"

    def test_stale_neighborhood_cleared_when_no_signal(self):
        # If existing tag isn't derivable from the current keyword list
        # and the venue/address don't yield a new one, the tag is cleared
        # to avoid lying to the user.
        events = [
            {
                "title": "Event",
                "location": {
                    "name": "",
                    "neighborhood": "soho",  # stale
                    "address": "",
                },
            }
        ]
        _backfill_neighborhood_from_venue(events)
        assert events[0]["location"]["neighborhood"] is None

    def test_venue_name_overrides_address(self):
        # Venue lookup is the strongest signal — even if the address
        # would point somewhere else, the venue table wins.
        events = [
            {
                "title": "Reading",
                "location": {
                    "name": "Liz's Book Bar",
                    "neighborhood": None,
                    "address": "100 Spring St",  # would say "soho"
                },
            }
        ]
        _backfill_neighborhood_from_venue(events)
        assert events[0]["location"]["neighborhood"] == "carroll gardens"

    def test_venue_name_explicit_token_beats_table_default(self):
        # fb-189: "New York Comedy Club Upper West Side" maps to 'east
        # village' by table default (the flagship branch), but the name
        # literally names the branch. The explicit token must win.
        events = [
            {
                "title": "Stand-Up Comedy: Carmen Lynch",
                "location": {
                    "name": "New York Comedy Club Upper West Side",
                    "neighborhood": "east village",  # wrong tag currently shipped
                    "address": "236 w 78th street, new york, ny",
                },
            }
        ]
        _backfill_neighborhood_from_venue(events)
        assert events[0]["location"]["neighborhood"] == "upper west side"

    def test_book_club_bar_bushwick_is_bushwick_not_east_village(self):
        # fb-189 canonical case: "Book Club Bar Bushwick, 380 Troutman St"
        # → bushwick, NOT east village (the table default for "book club bar").
        events = [
            {
                "title": 'Indie Press Book Club: "Persona"',
                "location": {
                    "name": "Book Club Bar Bushwick, 380 Troutman Street",
                    "neighborhood": "east village",
                    "address": "197 e 3rd st, new york, ny 10009",
                },
            }
        ]
        _backfill_neighborhood_from_venue(events)
        assert events[0]["location"]["neighborhood"] == "bushwick"

    def test_mcnally_jackson_williamsburg_branch(self):
        # fb-189: "McNally Jackson Williamsburg" → williamsburg, not soho.
        events = [
            {
                "title": "Unusual Appetites Book Club",
                "location": {
                    "name": "McNally Jackson Williamsburg",
                    "neighborhood": "soho",
                    "address": "76 north 4th street",
                },
            }
        ]
        _backfill_neighborhood_from_venue(events)
        assert events[0]["location"]["neighborhood"] == "williamsburg"

    def test_les_abbrev_does_not_match_inside_word(self):
        # fb-189 root cause: the 3-char "les" LES keyword substring-matched
        # inside "fiddlesticks", tagging an Astoria run as Lower East Side.
        # Word-boundary matching + explicit-token precedence fix it.
        events = [
            {
                "title": "Run & Chug - Fiddlesticks Pub",
                "location": {
                    "name": "Astoria Park",
                    "neighborhood": "lower east side",
                    "address": "19 19st, astoria, ny",
                },
            }
        ]
        _backfill_neighborhood_from_venue(events)
        assert events[0]["location"]["neighborhood"] == "astoria"

    def test_no_explicit_token_keeps_table_default(self):
        # Regression guard: a bare "Book Club Bar" (no branch token) must
        # still resolve to the table default 'east village'.
        events = [
            {
                "title": "Lit Talk",
                "location": {
                    "name": "Book Club Bar",
                    "neighborhood": None,
                    "address": "",
                },
            }
        ]
        _backfill_neighborhood_from_venue(events)
        assert events[0]["location"]["neighborhood"] == "east village"

    def test_empty_list_no_error(self):
        # Just shouldn't raise
        _backfill_neighborhood_from_venue([])


# ---------------------------------------------------------------------------
# _infer_time_from_text — body-text start-time inference (fb-186).
# ---------------------------------------------------------------------------


class TestInferTimeFromText:
    def test_doors_at_7pm(self):
        assert _infer_time_from_text("Concert", "doors at 7pm") == "19:00"

    def test_show_starts_8pm(self):
        assert _infer_time_from_text("Show", "show starts 8pm") == "20:00"

    def test_starts_at_with_minutes(self):
        assert _infer_time_from_text("", "starts at 7:30pm") == "19:30"

    def test_doors_open_at_with_minutes(self):
        assert _infer_time_from_text("", "doors open at 7:30pm") == "19:30"

    def test_kicks_off(self):
        assert _infer_time_from_text("", "kicks off at 8pm") == "20:00"

    def test_begins(self):
        assert _infer_time_from_text("", "begins 6:30pm") == "18:30"

    def test_bare_7pm(self):
        # fb-186: bare "7pm" with no keyword cue is filled when unambiguous.
        assert _infer_time_from_text("7pm", "") == "19:00"

    def test_bare_730pm(self):
        assert _infer_time_from_text("7:30pm", "") == "19:30"

    def test_bare_single_time_in_body(self):
        assert _infer_time_from_text("Yoga", "join us at 6:30pm for flow") == "18:30"

    def test_earliest_keyword_match_wins(self):
        # doors precede the show — earliest keyword time wins.
        assert (
            _infer_time_from_text("Party", "doors 8pm, show starts 9pm") == "20:00"
        )

    def test_ambiguous_multi_time_bare_returns_none(self):
        # Two distinct bare times, no keyword cue → ambiguous → no fill.
        assert (
            _infer_time_from_text("", "meet at 7pm then afterparty at 11pm") is None
        )

    def test_range_returns_none(self):
        # "2pm to 5pm" is a range — two distinct times, no start cue.
        assert _infer_time_from_text("", "event from 2pm to 5pm") is None

    def test_no_ampm_returns_none(self):
        assert _infer_time_from_text("", "show at 8") is None

    def test_early_am_below_floor_returns_none(self):
        # 5am is below the 06:00 plausible-start floor.
        assert _infer_time_from_text("", "5am sunrise run") is None

    def test_empty_returns_none(self):
        assert _infer_time_from_text("", "") is None
