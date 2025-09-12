from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from news_tui.datamodels import Section, Story
from news_tui.sources.cbc import CBCSource


@pytest.fixture
def cbc_source():
    return CBCSource({})


def test_cbc_get_sections(cbc_source):
    with patch("news_tui.sources.cbc.CBCSource._retryable_fetch") as mock_fetch:
        mock_fetch.return_value = b"""
            <nav>
                <a href="/lite/world">World</a>
                <a href="/lite/canada">Canada</a>
            </nav>
        """
        sections = cbc_source.get_sections()
        assert len(sections) == 3  # Home, World, Canada
        assert sections[0].title == "Home"
        assert sections[1].title == "World"
        assert sections[2].title == "Canada"


def test_cbc_get_stories(cbc_source):
    with patch("news_tui.sources.cbc.CBCSource._retryable_fetch") as mock_fetch:
        mock_fetch.return_value = b"""
            <a href="/lite/story/123">
                <span>New</span>
                Test Story 1
            </a>
            <p>Summary 1</p>
            <a href="/lite/story/456">
                Test Story 2
            </a>
            <p>Summary 2</p>
        """
        stories = cbc_source.get_stories(
            Section(title="Test", url="http://test.com"), set(), []
        )
        assert len(stories) == 2
        assert stories[0].title == "Test Story 1"
        assert stories[0].flag == "New"
        assert stories[0].summary == "Summary 1"
        assert stories[1].title == "Test Story 2"
        assert stories[1].flag is None
        assert stories[1].summary == "Summary 2"
