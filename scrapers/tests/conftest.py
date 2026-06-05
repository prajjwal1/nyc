"""Shared pytest fixtures for scraper utility tests.

Keep this lean: tests are about locking in the behavior of pure utility
functions, so heavy fixtures (real scraped data, network responses) belong
elsewhere. Only minimal in-memory dicts here.
"""

import pytest


@pytest.fixture
def base_event():
    """Minimal valid event dict — fields most normalize functions touch."""
    return {
        "source": "test",
        "title": "Sample Event",
        "date": "2026-06-01",
        "description": "",
        "categories": ["other"],
        "location": {"name": "", "address": "", "neighborhood": None},
    }


@pytest.fixture
def sample_events():
    """A handful of distinct events with realistic fields for normalize tests."""
    return [
        {
            "source": "songkick",
            "title": "Charlie Puth @ Madison Square Garden",
            "date": "2026-05-29",
            "description": "Charlie Puth live at MSG",
            "categories": ["music"],
            "location": {"name": "Madison Square Garden", "address": "4 Pennsylvania Plaza"},
        },
        {
            "source": "allevents",
            "title": "Charlie Puth, Daniel Seavey, Ally Salort in New York",
            "date": "2026-05-29",
            "description": "Charlie Puth with openers",
            "categories": ["music"],
            "location": {"name": "Madison Square Garden", "address": "4 Pennsylvania Plaza"},
        },
        {
            "source": "lizsbookbar",
            "title": "Author Reading",
            "date": "2026-06-02",
            "description": "Author event",
            "categories": ["books"],
            "location": {"name": "Liz's Book Bar", "address": "", "neighborhood": None},
        },
    ]
