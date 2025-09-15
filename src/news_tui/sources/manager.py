from __future__ import annotations

from typing import Any, Dict, List, Type

from .base import Source
from .cbc import CBCSource

# In the future, we could auto-discover sources, but for now, we'll hardcode them.
AVAILABLE_SOURCES: Dict[str, Type[Source]] = {
    "cbc": CBCSource,
}


class SourceManager:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.sources: Dict[str, Source] = {}
        self._load_sources()

    def _load_sources(self) -> None:
        """Load all available sources."""
        source_config = self.config.get("sources", {})
        for name, source_class in AVAILABLE_SOURCES.items():
            if name in source_config:
                self.sources[name] = source_class(source_config[name])

    def get_source(self, name: str) -> Source | None:
        """Get a source by name."""
        return self.sources.get(name)

    def get_all_sources(self) -> List[Source]:
        """Get a list of all loaded sources."""
        return list(self.sources.values())
