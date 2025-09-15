from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from ..datamodels import Section, Story


class Source(ABC):
    """Abstract base class for a news source."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @abstractmethod
    def get_sections(self) -> List[Section]:
        """Return a list of available sections."""
        pass

    @abstractmethod
    def get_stories(self, section: Section) -> List[Story]:
        """Return a list of stories for a given section."""
        pass

    @abstractmethod
    def get_story_content(self, story: Story) -> Dict[str, Any]:
        """Return the content of a story."""
        pass
