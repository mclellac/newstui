from __future__ import annotations

import logging
from typing import Any, Dict, List

import feedparser
from bs4 import BeautifulSoup

from ..datamodels import Section, Story
from .base import BaseSource

logger = logging.getLogger("news")


class RSSSource(BaseSource):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.feeds = self.config.get("feeds", {})

    def get_sections(self) -> List[Section]:
        return [Section(title, url) for title, url in self.feeds.items()]

    def get_stories(
        self, section: Section, read_articles: set[str], bookmarks: list[dict]
    ) -> List[Story]:
        stories = []
        feed = feedparser.parse(section.url)
        bookmarked_urls = {b["url"] for b in bookmarks}
        for entry in feed.entries:
            summary_html = entry.get("summary", "")
            summary_text = BeautifulSoup(summary_html, "lxml").get_text()
            stories.append(
                Story(
                    title=entry["title"],
                    url=entry["link"],
                    summary=summary_text,
                    read=entry["link"] in read_articles,
                    bookmarked=entry["link"] in bookmarked_urls,
                )
            )
        return stories

    def get_story_content(self, story: Story, section: Section) -> Dict[str, Any]:
        # The story object from feedparser might have the full content.
        # We need to re-fetch the feed and find the entry.
        feed = feedparser.parse(section.url)
        for entry in feed.entries:
            if entry.link == story.url:
                if "content" in entry:
                    content = "\n".join(
                        [c.value for c in entry.content if "value" in c]
                    )
                    soup = BeautifulSoup(content, "lxml")
                    return {"ok": True, "content": soup.get_text()}
                elif "summary" in entry:
                    soup = BeautifulSoup(entry.summary, "lxml")
                    return {"ok": True, "content": soup.get_text()}
        return {"ok": False, "content": "No content found."}
