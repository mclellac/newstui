from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from news_tui.datamodels import Section, Story
from news_tui.sources.rss import RSSSource


@pytest.fixture
def rss_source():
    feeds = {
        "Feed 1": "http://feed1.com",
        "Feed 2": "http://feed2.com",
    }
    return RSSSource({"feeds": feeds})


def test_rss_get_sections(rss_source):
    sections = rss_source.get_sections()
    assert len(sections) == 2
    assert sections[0].title == "Feed 1"
    assert sections[0].url == "http://feed1.com"
    assert sections[1].title == "Feed 2"
    assert sections[1].url == "http://feed2.com"


def test_rss_get_stories(rss_source):
    with patch("news_tui.sources.rss.feedparser.parse") as mock_parse:
        mock_feed = MagicMock()
        mock_feed.entries = [
            {
                "title": "Story 1",
                "link": "http://story1.com",
                "summary": "Summary 1",
            },
            {
                "title": "Story 2",
                "link": "http://story2.com",
                "summary": "Summary 2",
            },
        ]
        mock_parse.return_value = mock_feed
        stories = rss_source.get_stories(
            Section(title="Test", url="http://test.com"), set(), []
        )
        assert len(stories) == 2
        assert stories[0].title == "Story 1"
        assert stories[0].summary == "Summary 1"
        assert stories[1].title == "Story 2"
        assert stories[1].summary == "Summary 2"
