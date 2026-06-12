"""Regression tests for the 2026-06-12 quality-leak fixes.

Locks in the hard-blocks (AI get-rich grift, commercial matchmaking-singles
spam) and the IG-Story fragment filters (date-led, ALLCAPS-neighborhood, OCR
symbol-runs, caption openers, World-Cup schedule spam). Each case is drawn
from a real leak on the deployed feed; the "should survive" cases guard
against over-blocking legitimate events.
"""

import pytest

from scrapers.quality import _is_caption_fragment, is_blocked


def _ev(title, desc="", source="instagram"):
    return {
        "title": title,
        "description": desc,
        "source": source,
        "categories": ["other"],
        "location": {"name": "", "address": ""},
    }


# --- HARD_BLOCK: AI get-rich grift + commercial matchmaking spam -----------

BLOCKED = [
    "AI Side Income Secrets: Build a Profitable Business In A Day",
    "Intelligent Singles Mixer at St. Regis Hotel in NYC!",
    "Ivy League Singles Mixer at St. Regis Hotel in NYC!",
    "NYC Singles Recruitment for High-Net-Worth Matchmaking Clients",
    "Elite Social: An Exclusive Singles & Networking Mixer",
]


@pytest.mark.parametrize("title", BLOCKED)
def test_grift_and_matchmaking_blocked(title):
    assert is_blocked(_ev(title)) is True


# --- _is_caption_fragment: IG-Story garbage shapes -------------------------

FRAGMENTS = [
    # Q3 date-led
    "Friday, June 19 at 7PM",
    "Tuesday, June 16 - 6:00pm DeKalb Library",
    "June 13: Piscator Pop-up",
    "B-J June 16: Dinner at the Grocer",
    # Q4 ALLCAPS neighborhood-prefix + weekday-date
    "PROSPECT HEIGHTS (CITY POINT): Sat, June 13th",
    "LOWER MAN: Tue, June 16th",
    "LIGHTNING SOCIETY: Thu, June 18th",
    # Q5 OCR symbol-run garbage
    "block party on June 20! @ &&",
    "iconic soccer hairstyles @) &",
    "Bock Club BAR [ JUNE",
    # Q6 caption openers / markers
    "We're celebrating 80 years of @penguinclassics",
    "Philips House of Coffee starts tomorrow!",
    "Yarn of the day",
    "Brooklyn on June 22! We are giving away pairs",
    "Featuring: Dolan Morgan",
    # Q8 World Cup schedule spam
    "SAUDI ARABIA v. URUGUAY @ 6pm",
    "ENGLAND v. CROATIA @ 4PM",
]


@pytest.mark.parametrize("title", FRAGMENTS)
def test_story_fragments_dropped(title):
    assert _is_caption_fragment(title, "") is True


# --- Must SURVIVE: legitimate events the filters must not touch ------------

LEGIT = [
    "Book Club Bar — Author Night with Jane Smith",
    "Reading Rhythms Prospect Heights: June 24th",  # clean lu.ma title (no ALLCAPS)
    "Brazil World Cup Watch Party — NYC's Home for Every Game",
    "Summer Lovin' Singles Mixer",  # authentic community singles night
    "The Art of Wanting: A Writer's Salon",
    "Hive Mind with Allen Aucoin",
    "Donna The Buffalo & Assembly of Dust",
    "Global Wellness Day pop-up",
]


@pytest.mark.parametrize("title", LEGIT)
def test_legit_events_survive(title):
    assert not is_blocked(_ev(title))
    assert not _is_caption_fragment(title, "")
