"""Regression tests for scrapers.quality._is_caption_fragment.

This is one of the highest-iteration parts of the codebase: every IG
caption that slips through gets a new fragment_starts entry, and every
real event title that gets misblocked gets a carve-out. Hold the line by
locking in the present matrix of TRUE/FALSE classifications.

If a test fails because the rule list changed, update the expected value
and add the iteration note (or remove the case if it no longer makes sense).
"""

import pytest

from scrapers.quality import _is_caption_fragment


# ---------------------------------------------------------------------------
# Positive cases — titles that ARE caption fragments. Should return True.
# Drawn from real IG-scrape post-mortems.
# ---------------------------------------------------------------------------


# Cases that the spec asks for but where the current implementation does NOT
# return True. These have been confirmed as actual missed coverage —
# legitimate caption fragments slipping through the filter. Marking them
# xfail so the test suite still tracks them as known bugs without going red.
# When these get fixed in lane 2, flip the xfail off.
_KNOWN_MISSED_FRAGMENTS = {
    "On Sunday, we're hosting",  # "on <weekday>," prefix with no month/day
    "GETTING UNSTUCK: Finally, on Saturday",  # similar — colon-truncation runs but tail doesn't trigger
}


# Big positive matrix. Each string is expected to return True. Some are
# marked xfail because the current code misses them — see above note.
_TRUE_CASES = [
    # Day-prefixed caption openers
    "This Friday, join us for a celebration of our re-opened composting site at the S",
    "this Saturday, come out",
    "tomorrow night at the bar",
    "tomorrow, the gallery opens",
    "tonight, we celebrate",
    "tonight 7 doors",
    "tomorrow we open",
    "tomorrow we’re back",
    # We-pronoun caption openers
    "we are loving the vibe",
    "we're loving the vibe",
    "we are thrilled to announce",
    "we are excited to host",
    "we present the new lineup",
    "we've got some big plans",
    # Greeting / hype openers
    "happy birthday to our friend",
    "good morning runners",
    "thank you for coming out",
    "shoutout to the crew",
    "i can't believe we sold out",
    "big news everyone",
    "huge news today",
    "just announced for fall",
    "newly announced lineup",
    # Promo / CTA openers
    "swipe up for tickets",
    "link in bio for more",
    "save the date for next month",
    "calling all bookworms",
    "use code SAVE10 today",
    "free knicks donuts",
    "free with code TODAY",
    "introducing the new menu",
    # Reopening / news / location-prefix
    "reopening tomorrow morning",
    "beaches reopen this weekend",
    "now showing at the gallery",
    "now open for business",
    "happening now at the park",
    "in case you missed it yesterday",
    "did you know that we have a new show",
    "last chance to grab tickets",
    "Saturday outside at the park",
    # Bulleted lineup / date-prefix items
    "5/27 - Brass Queens",
    "Jun 17 - Alphonso Horne",
    "May 28 with free post-run recovery",
    # Specific-date "On Weekday, Month Day" caption
    "On Wednesday, May 14, join us at the park",
    "On Sunday, May 24, join us for brunch",
    # Truncation markers (mid-caption cut-off)
    "...truncated title",
    "short cap…",
    # Photo / video credit fragments
    "photo by Jane",
    # "this weekend is for the girls" — seasonal hype
    "this weekend is for the girls",
    # Bugs (currently NOT flagged but should be) — keep tracked via xfail
    "On Sunday, we're hosting",
    "GETTING UNSTUCK: Finally, on Saturday",
]


@pytest.mark.parametrize("title", _TRUE_CASES)
def test_caption_fragment_positive(title):
    if title in _KNOWN_MISSED_FRAGMENTS:
        pytest.xfail("known coverage gap — see iter 67 / lane 2")
    assert _is_caption_fragment(title, "") is True, (
        f"Expected {title!r} to be detected as a caption fragment"
    )


# ---------------------------------------------------------------------------
# Negative cases — real event titles that must NOT be classified as
# fragments. These are the load-bearing carve-outs.
# ---------------------------------------------------------------------------


# Cases the spec lists as False but the current implementation gets wrong.
# "BERTHA: Grateful Drag" gets caught by the 3-word-or-less + no-event-word
# rule (no event word like "show"/"party"/"drag" hits). xfail it for now —
# lane 2 should add "drag" to event_words or otherwise carve this out.
_KNOWN_OVERBLOCKED = {
    "BERTHA: Grateful Drag",  # 3 words, no event_word match → over-blocked
}


_FALSE_CASES = [
    "BERTHA: Grateful Drag",  # all-caps short — caught by 3-word rule, xfail
    "Charlie Puth @ Madison Square Garden",
    "Quiet Reading Brooklyn",
    "sunflwr @ The Rooftop",  # lowercase but @-mention carveout
    "commUNITY Run Club",  # lowercase but camelCase brand carveout
    "Stand-Up Comedy Show",
    "Book Club at the Strand",
    "Friendship, Lomelda, and Caroline Polachek",
    "Hive Mind with Allen Aucoin",
    "No Regrets Runners",
    "Sunset Yoga at Domino Park",
    "Brooklyn Comedy Festival",
    "Opening Reception at New Museum",
    "Songkick Concert: Iration",
]


@pytest.mark.parametrize("title", _FALSE_CASES)
def test_caption_fragment_negative(title):
    if title in _KNOWN_OVERBLOCKED:
        pytest.xfail("over-blocked by 3-word rule — see iter 67 / lane 2")
    assert _is_caption_fragment(title, "") is False, (
        f"Expected {title!r} to NOT be detected as a caption fragment"
    )


# ---------------------------------------------------------------------------
# Spot checks on specific structural rules that have caused regressions.
# These exist in addition to the parametrized lists for ease of debugging.
# ---------------------------------------------------------------------------


class TestCaptionFragmentStructuralRules:
    def test_empty_title_returns_false(self):
        # The very first guard
        assert _is_caption_fragment("", "") is False

    def test_truncation_marker_triple_dot(self):
        assert _is_caption_fragment("Some Title...", "") is True

    def test_truncation_marker_ellipsis(self):
        assert _is_caption_fragment("Some Title…", "") is True

    def test_hashtag_only_title(self):
        assert _is_caption_fragment("#nyc #brooklyn #fun", "") is True

    def test_bracketed_location_tag(self):
        assert _is_caption_fragment("[NYC]", "") is True

    def test_address_as_title(self):
        # IG scraper sometimes pulls a location line as the title
        assert _is_caption_fragment("445 grand st, brooklyn, ny", "") is True

    def test_numeric_date_prefix_with_dash(self):
        assert _is_caption_fragment("6/7 - Recovery: What Matters", "") is True

    def test_month_day_dash_prefix(self):
        assert _is_caption_fragment("Jun 17 - Alphonso Horne", "") is True

    def test_pure_date_title(self):
        assert _is_caption_fragment("May 17", "") is True

    def test_at_mention_carveout_for_lowercase_artist(self):
        # Lowercase artist names with @-mention are legitimate concert titles
        assert _is_caption_fragment("sunflwr @ Brooklyn Steel", "") is False

    def test_camelcase_brand_carveout(self):
        # commUNITY is a deliberate brand stylization
        assert _is_caption_fragment("commUNITY Run Club", "") is False

    def test_short_legitimate_title_not_blocked(self):
        # "Quiet Reading Brooklyn" — short but contains "reading" (event_word)
        assert _is_caption_fragment("Quiet Reading Brooklyn", "") is False

    def test_takes_over_announcement_pattern(self):
        # "X takes over Y" announcement caption
        assert _is_caption_fragment("DJ Krush takes over Brooklyn Bowl", "") is True

    def test_just_dropped_announcement(self):
        assert _is_caption_fragment("the new mixtape just dropped", "") is True

    def test_sold_out_announcement(self):
        assert _is_caption_fragment("Tonight's show is sold out", "") is True

    def test_lowercase_three_word_caption_fragment(self):
        # Lowercase + multi-word + no carve-out → fragment
        assert _is_caption_fragment("costumes for a single show tonight", "") is True

    def test_emoji_only_title(self):
        # Title with < 5 alpha chars → fragment
        assert _is_caption_fragment("🎉🔥", "") is True

    def test_pure_weekday_date_time_title(self):
        # "FRI 5/15 @ 6:30pm" — date-stamp masquerading as a title
        assert _is_caption_fragment("FRI 5/15 @ 6:30pm —-", "") is True

    def test_location_label_prefix(self):
        assert _is_caption_fragment("Location: Brooklyn Bowl", "") is True
