from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from .cache import Cache
from .config import CACHE_DIR, CACHE_TTL
from .datamodels import Section, Story
from .sources.cbc import CBCSource

logger = logging.getLogger("news")


class Fetcher:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.cache = Cache(cache_dir=CACHE_DIR, ttl=CACHE_TTL)
        cbc_config = self.config.get("sources", {}).get("cbc", {})
        self.source = CBCSource(config=cbc_config, cache=self.cache)

    def get_sections(self) -> List[Section]:
        return self.source.get_sections()

    def get_stories(
        self, section: Section, read_articles: set[str], bookmarks: list[dict]
    ) -> List[Story]:
        return self.source.get_stories(section, read_articles, bookmarks)

    def get_story_content(self, story: Story, section: Section) -> Dict[str, Any]:
        return self.source.get_story_content(story, section)

    def get_stories_for_meta_section(
        self,
        section_names: List[str],
        read_articles: set[str],
        bookmarks: list[dict],
    ) -> List[Story]:
        all_stories = []
        seen_urls = set()

        all_sections = self.get_sections()
        section_map = {s.title: s for s in all_sections}

        sections_to_fetch = [section_map[name] for name in section_names if name in section_map]

        with ThreadPoolExecutor() as executor:
            future_to_section = {
                executor.submit(self.get_stories, s, read_articles, bookmarks): s
                for s in sections_to_fetch
            }
            for future in as_completed(future_to_section):
                section = future_to_section[future]
                try:
                    stories = future.result()
                    for story in stories:
                        if story.url not in seen_urls:
                            all_stories.append(story)
                            seen_urls.add(story.url)
                except Exception as e:
                    logger.error("Failed to fetch stories for section %s: %s", section.title, e)

        return all_stories
