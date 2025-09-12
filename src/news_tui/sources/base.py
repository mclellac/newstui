from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Dict, Any

from ..datamodels import Section, Story


class BaseSource(ABC):
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @abstractmethod
    def get_sections(self) -> List[Section]:
        ...

    @abstractmethod
    def get_stories(
        self, section: Section, read_articles: set[str], bookmarks: list[dict]
    ) -> List[Story]:
        ...

    @abstractmethod
    def get_story_content(self, story: Story, section: Section) -> Dict[str, Any]:
        ...
