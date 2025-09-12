from __future__ import annotations

import logging
from typing import Any, Dict, List

from .datamodels import Section, Story
from .sources.base import BaseSource

logger = logging.getLogger("news")


class Fetcher:
    def __init__(self, source: BaseSource):
        self.source = source

    def get_sections(self) -> List[Section]:
        return self.source.get_sections()

    def get_stories(
        self, section: Section, read_articles: set[str], bookmarks: list[dict]
    ) -> List[Story]:
        return self.source.get_stories(section, read_articles, bookmarks)

    def get_story_content(self, story: Story, section: Section) -> Dict[str, Any]:
        return self.source.get_story_content(story, section)
