"""Regression tests for scrapers.utils.event_parser.

This module locks in the current behavior of the title/category/neighborhood
parsers. The behaviors here have been iterated on ~65 times in the last
few weeks and each rule is load-bearing — every test failure should be
treated as a deliberate behavior change, not noise.

If a test breaks because a rule changed intentionally, update the test
and document the iteration that changed the behavior. If a test breaks
unexpectedly, that's a regression.
"""

import pytest

from scrapers.utils.event_parser import (
    CATEGORY_KEYWORDS,
    NYC_NEIGHBORHOODS,
    clean_title,
    infer_categories,
    infer_default_start_time,
    infer_neighborhood,
    parse_iso_to_local,
    parse_offers_price,
)


# ---------------------------------------------------------------------------
# clean_title — 20+ cases covering emoji prefix, hashtag walls, OCR @-fix,
# trailing weekday-date suffix, and the new (iter 64) colon-fragment
# truncation.
# ---------------------------------------------------------------------------


class TestCleanTitle:
    def test_passes_through_clean_title(self):
        assert clean_title("Charlie Puth Concert") == "Charlie Puth Concert"

    def test_trims_whitespace(self):
        assert clean_title("   Trim me   ") == "Trim me"

    def test_returns_empty_for_empty(self):
        assert clean_title("") == ""

    def test_returns_none_for_none(self):
        assert clean_title(None) is None

    def test_decodes_html_amp(self):
        assert clean_title("Title &amp; Subtitle") == "Title & Subtitle"

    def test_decodes_html_apostrophe(self):
        assert clean_title("Don&#39;t Stop") == "Don't Stop"

    def test_decodes_html_quote(self):
        assert clean_title("She said &quot;hi&quot;") == 'She said "hi"'

    def test_strips_leading_emoji(self):
        assert clean_title("✨ Event Tonight") == "Event Tonight"

    def test_strips_leading_celebration_emoji_cluster(self):
        assert clean_title("🎉🎉🎉 New Year Bash") == "New Year Bash"

    def test_strips_trailing_hashtag_wall(self):
        # 3+ trailing hashtags get stripped
        assert clean_title("Hashtag Wall #nyc #brooklyn #fun") == "Hashtag Wall"

    def test_strips_trailing_weekday_month_date_suffix(self):
        assert (
            clean_title("Hive Mind with Allen Aucoin on FRI, JUL 10")
            == "Hive Mind with Allen Aucoin"
        )

    def test_strips_trailing_date_suffix_compact_form(self):
        assert clean_title("Donna The Buffalo on SAT, NOV 7") == "Donna The Buffalo"

    def test_strips_trailing_date_suffix_with_st_ordinal(self):
        assert (
            clean_title("Some Show on FRI, JUL 11th") == "Some Show"
        )

    def test_does_not_strip_legit_on_tuesday_night_phrase(self):
        # The trailing-date stripper is constrained to weekday + month-day,
        # so "...on Tuesday Night" is preserved.
        title = "Open Mic Tuesday Night"
        assert clean_title(title) == title

    def test_keeps_short_colon_title(self):
        # BERTHA: Grateful Drag is 21 chars (<30), so colon truncation
        # is gated off — entire title preserved.
        assert clean_title("BERTHA: Grateful Drag") == "BERTHA: Grateful Drag"

    def test_keeps_qa_colon_title(self):
        # Q&A: A Conversation with Author — tail does NOT start with a
        # caption opener ("a conversation"), so colon truncation skips.
        title = "Q&A: A Conversation with Author"
        assert clean_title(title) == title

    def test_truncates_at_colon_when_tail_is_caption_opener(self):
        # iter 64: GETTING UNSTUCK: On Sunday, 6/7, @x will host...
        # Long title (>30 chars) + tail starts with "on <weekday>," →
        # truncate at colon to just the event name.
        raw = "GETTING UNSTUCK: On Sunday, 6/7, @x will host us at the park for a workshop"
        assert clean_title(raw) == "GETTING UNSTUCK"

    def test_truncates_at_colon_when_tail_starts_finally(self):
        # iter 64 covers "Finally," as a caption opener too
        raw = "GETTING UNSTUCK: Finally, on Saturday we gather"
        assert clean_title(raw) == "GETTING UNSTUCK"

    def test_truncates_at_colon_when_tail_starts_tonight(self):
        raw = "BIG NIGHT OUT: Tonight, we celebrate the launch of the new gallery space"
        assert clean_title(raw) == "BIG NIGHT OUT"

    def test_ocr_at_glyph_fix_brooklynmuseum(self):
        # OCR'd "@" as "G" followed by lowercase venue name
        assert clean_title("Gbrooklynmuseum opens new wing") == "@brooklynmuseum opens new wing"

    def test_ocr_at_glyph_fix_highlinenyc(self):
        assert clean_title("Chighlinenyc party") == "@highlinenyc party"

    def test_strips_trailing_at_mention_chain(self):
        # 3+ trailing @-mentions form a "collab tag wall"
        cleaned = clean_title("Real Title @one @two @three @four")
        assert cleaned == "Real Title"

    def test_collapses_repeated_emoji_in_body(self):
        # After leading-emoji strip, repeated emoji inside body collapse
        out = clean_title("Cool Show 🔥🔥🔥🔥 Tonight")
        # 4 fires collapse to 1
        assert out == "Cool Show 🔥 Tonight"

    def test_collapses_whitespace(self):
        assert clean_title("Multiple    spaces   between") == "Multiple spaces between"


# ---------------------------------------------------------------------------
# infer_categories — books, music, parties, singles, comedy, fitness,
# outdoors, art, and the MSG-outdoors suppression / rooftop-survival rules.
# ---------------------------------------------------------------------------


class TestInferCategories:
    def test_books_book_club(self):
        assert "books" in infer_categories("Book Club at Liz's", "")

    def test_music_live_jazz(self):
        assert "music" in infer_categories("Live Jazz Night", "")

    def test_parties_block_party(self):
        assert "parties" in infer_categories("Block Party in Bushwick", "")

    def test_singles_speed_dating(self):
        cats = infer_categories("Speed Dating NYC", "")
        assert "singles" in cats

    def test_singles_mixer_also_tagged_parties(self):
        # "mixer" hits parties keywords too — accepted as current behavior
        cats = infer_categories("Speed Dating NYC + Singles Mixer", "")
        assert "singles" in cats
        assert "parties" in cats

    def test_comedy_stand_up(self):
        assert "comedy" in infer_categories("Stand-Up Comedy at the Cellar", "")

    def test_fitness_run_club(self):
        assert "fitness" in infer_categories("Morning Run Club", "")

    def test_outdoors_picnic_central_park(self):
        assert "outdoors" in infer_categories("Picnic at Central Park", "")

    def test_art_opening_at_moma(self):
        assert "art" in infer_categories("Art Opening at MoMA", "")

    def test_msg_outdoors_suppression(self):
        # iter 61: "Charlie Puth @ Madison Square Garden" should NOT
        # get the outdoors tag despite "garden" appearing in the venue
        # name. MSG is an indoor arena and "garden" is a misnomer.
        cats = infer_categories("Charlie Puth @ Madison Square Garden", "")
        assert "music" in cats
        assert "outdoors" not in cats

    def test_msg_rooftop_keeps_outdoors(self):
        # Strong outdoor signal (rooftop / pier) in the description should
        # override the MSG suppression rule.
        cats = infer_categories("Charlie Puth @ Madison Square Garden", "rooftop afterparty")
        assert "outdoors" in cats

    def test_rooftop_pier_keeps_outdoors(self):
        # Rooftop + pier are strong outdoor signals; MSG is not in the text.
        cats = infer_categories("Iration @ The Rooftop at Pier 17", "")
        assert "music" in cats
        assert "outdoors" in cats

    def test_unmatched_falls_back_to_other(self):
        assert infer_categories("Random unmatched text", "") == ["other"]

    def test_empty_falls_back_to_other(self):
        assert infer_categories("", "") == ["other"]

    def test_ig_account_hint_books(self):
        # Cryptic title + IG account suggests topic. brooklyn_books
        # has 'book' substring → books.
        cats = infer_categories("5/21 mystery event", "", ig_account="brooklyn_books")
        assert "books" in cats

    def test_source_hint_songkick_music(self):
        # Cryptic title from songkick (music venue scraper) → music
        cats = infer_categories("Artist Name", "", source="songkick")
        assert cats == ["music"]

    def test_source_hint_newyorkcomedyclub_comedy(self):
        cats = infer_categories("Some Comic", "", source="newyorkcomedyclub")
        assert cats == ["comedy"]


# ---------------------------------------------------------------------------
# infer_neighborhood — keyword-based address inference, plus the borough/city
# fallback. Covers the specific iter-fixes (Broadway removed from soho list,
# Smith St → Carroll Gardens, etc.)
# ---------------------------------------------------------------------------


class TestInferNeighborhood:
    def test_williamsburg_n_6th(self):
        assert infer_neighborhood("123 N 6th St Brooklyn") == "williamsburg"

    def test_east_village_st_marks(self):
        assert infer_neighborhood("100 St Marks Place") == "east village"

    def test_lower_east_side_ludlow(self):
        assert infer_neighborhood("123 Ludlow St") == "lower east side"

    def test_soho_spring_st(self):
        assert infer_neighborhood("100 Spring St") == "soho"

    def test_broadway_no_longer_matches_soho(self):
        # Broadway was removed from the soho keyword list — 1501 Broadway
        # is Times Square (midtown), not SoHo. Confirm it returns None
        # (not soho) since none of the other midtown keywords match a
        # bare "1501 Broadway" with no other context.
        assert infer_neighborhood("1501 Broadway") is None

    def test_midtown_west_33rd(self):
        assert infer_neighborhood("100 West 33rd Street") == "midtown"

    def test_upper_east_side_east_61st(self):
        assert infer_neighborhood("2 East 61st Street") == "upper east side"

    def test_upper_west_side_columbus_ave(self):
        assert infer_neighborhood("100 Columbus Ave") == "upper west side"

    def test_crown_heights_kingston_ave(self):
        assert infer_neighborhood("105 Kingston Avenue") == "crown heights"

    def test_carroll_gardens_smith_street(self):
        assert infer_neighborhood("315 Smith Street, Brooklyn") == "carroll gardens"

    def test_fidi_wall_st(self):
        assert infer_neighborhood("100 Wall St") == "fidi"

    def test_brooklyn_borough_fallback(self):
        assert infer_neighborhood("Brooklyn") == "brooklyn"

    def test_manhattan_borough_fallback(self):
        assert infer_neighborhood("Manhattan") == "manhattan"

    def test_new_york_string_fallback(self):
        assert infer_neighborhood("New York") == "manhattan"

    def test_empty_returns_none(self):
        assert infer_neighborhood("") is None

    def test_none_returns_none(self):
        assert infer_neighborhood(None) is None

    def test_no_match_returns_none(self):
        # An address with no neighborhood/borough keyword
        assert infer_neighborhood("Mars") is None

    # fb-194: Queens venues previously fell through to "manhattan" because a
    # Queens address ("22-25 Jackson Ave, Queens, NY 11101") also contains
    # "New York"/"NY". A borough token now wins before the manhattan fallback,
    # and Queens neighborhood keywords give finer granularity.
    def test_moma_ps1_address_long_island_city(self):
        assert infer_neighborhood("22-25 Jackson Ave, Queens, NY 11101") == "long island city"

    def test_lic_zip_11101(self):
        assert infer_neighborhood("5-25 46th Rd, NY 11101") == "long island city"

    def test_forest_hills_stadium(self):
        assert infer_neighborhood("1 Tennis Pl, Forest Hills, NY") == "forest hills"

    def test_rockaway_beach(self):
        assert infer_neighborhood("108-10 Rockaway Beach Dr., Rockaway Beach, NY") == "rockaway"

    def test_flushing_meadows(self):
        assert infer_neighborhood("Flushing Meadows Corona Park, Queens, NY") == "flushing"

    def test_queens_borough_fallback_not_manhattan(self):
        # A bare Queens address with no neighborhood keyword must resolve to
        # "queens", NOT "manhattan" (the regression fb-194 fixes).
        assert infer_neighborhood("70-10 Grand Avenue, Queens, NY 11378") == "queens"

    def test_queens_beats_new_york_fallthrough(self):
        # "New York" present but Queens borough token wins.
        assert infer_neighborhood("41 Seaver Way, New York, NY (Queens)") == "flushing"

    def test_bronx_borough_fallback(self):
        assert infer_neighborhood("Crotona Park, Bronx, NY") == "bronx"


# ---------------------------------------------------------------------------
# parse_iso_to_local — UTC conversion to ET, date-only handling, malformed
# input. Note the current return format is (date, "HH:MM"), NOT "HH:MM:SS".
# ---------------------------------------------------------------------------


class TestParseIsoToLocal:
    def test_utc_z_suffix_converts_to_et(self):
        # 23:00Z is 19:00 ET (winter EST -5; summer EDT -4). 2026-05-28 is
        # in DST so UTC-4 → 19:00 ET.
        assert parse_iso_to_local("2026-05-28T23:00:00Z") == ("2026-05-28", "19:00")

    def test_explicit_offset(self):
        # ET +00:00 offset is also UTC
        assert parse_iso_to_local("2026-05-28T23:00:00+00:00") == ("2026-05-28", "19:00")

    def test_date_only_returns_none_time(self):
        # iter 45: date-only inputs should NOT default to 00:00 — that was
        # making every JSON-LD-date-only event show "12:00 AM" which is
        # worse than showing no time at all.
        assert parse_iso_to_local("2026-05-28") == ("2026-05-28", None)

    def test_empty_returns_none_tuple(self):
        assert parse_iso_to_local("") == (None, None)

    def test_none_returns_none_tuple(self):
        assert parse_iso_to_local(None) == (None, None)

    def test_naive_iso_passes_through(self):
        # No timezone → treated as local; we get the same date + HH:MM
        result = parse_iso_to_local("2026-05-28T18:30:00")
        assert result == ("2026-05-28", "18:30")

    def test_malformed_falls_back_to_slice(self):
        # Fallback path: when fromisoformat raises, use legacy slice.
        # Garbage but with date prefix returns the slice
        result = parse_iso_to_local("2026-05-28Tnonsense")
        # Either parses or falls back; current behavior: date slice + a
        # time slice.
        assert result[0] == "2026-05-28"


# ---------------------------------------------------------------------------
# parse_offers_price — JSON-LD offers parsing (dict / list / lowPrice /
# Free string / None).
# ---------------------------------------------------------------------------


class TestParseOffersPrice:
    def test_dict_with_price(self):
        assert parse_offers_price({"price": "25"}) == "$25"

    def test_list_returns_first_paid(self):
        # Returns the first non-zero price seen
        assert parse_offers_price([{"price": "15"}, {"price": "25"}]) == "$15"

    def test_low_price_fallback(self):
        # AggregateOffer style — lowPrice instead of price
        assert parse_offers_price([{"lowPrice": "30"}]) == "$30"

    def test_free_string(self):
        # Non-numeric "Free" string
        assert parse_offers_price({"price": "Free"}) == "free"

    def test_zero_int_means_free(self):
        assert parse_offers_price({"price": 0}) == "free"

    def test_zero_string_means_free(self):
        assert parse_offers_price({"price": "0"}) == "free"

    def test_decimal_formatted_trims_zeros(self):
        # "25.00" → "$25" (trailing zero stripped by :g format)
        assert parse_offers_price({"price": "25.00"}) == "$25"

    def test_decimal_keeps_significant_decimals(self):
        assert parse_offers_price({"price": "25.50"}) == "$25.5"

    def test_none_returns_unknown(self):
        assert parse_offers_price(None) == "unknown"

    def test_string_returns_unknown(self):
        # Bare string (not list/dict) is unparseable
        assert parse_offers_price("not a list") == "unknown"

    def test_empty_list_returns_unknown(self):
        assert parse_offers_price([]) == "unknown"

    def test_free_takes_precedence_over_no_paid(self):
        # Multiple offers where one is free, no paid → "free"
        assert parse_offers_price([{"price": "0"}, {"price": ""}]) == "free"

    def test_paid_takes_precedence_over_free(self):
        # Mixed: free option + paid option → paid (the actual cost)
        assert parse_offers_price([{"price": "0"}, {"price": "25"}]) == "$25"


# ---------------------------------------------------------------------------
# infer_default_start_time — category defaults plus explicit time-of-day
# hints from title text.
# ---------------------------------------------------------------------------


class TestInferDefaultStartTime:
    def test_fitness_default(self):
        assert infer_default_start_time(["fitness"]) == "07:00"

    def test_parties_default(self):
        assert infer_default_start_time(["parties"]) == "20:00"

    def test_music_default(self):
        assert infer_default_start_time(["music"]) == "20:00"

    def test_comedy_default(self):
        assert infer_default_start_time(["comedy"]) == "20:00"

    def test_books_default(self):
        assert infer_default_start_time(["books"]) == "19:00"

    def test_wellness_default(self):
        assert infer_default_start_time(["wellness"]) == "10:00"

    def test_opening_reception_overrides_category(self):
        # "opening reception" in the text returns 18:00 regardless of category
        assert infer_default_start_time(["art"], "Opening Reception", "") == "18:00"

    def test_brunch_overrides_to_late_morning(self):
        assert infer_default_start_time(["food"], "Brunch with friends", "") == "11:00"

    def test_happy_hour_overrides(self):
        assert infer_default_start_time(["music"], "Rooftop Happy Hour", "") == "18:00"

    def test_empty_categories_returns_none(self):
        assert infer_default_start_time([]) is None

    def test_unknown_category_returns_none(self):
        # 'other' not in the default-by-category table
        assert infer_default_start_time(["other"]) is None
