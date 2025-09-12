from __future__ import annotations

from typing import Any, Dict

from .sources.base import BaseSource
from .sources.cbc import CBCSource
from .sources.rss import RSSSource

SOURCES = {"cbc": CBCSource, "rss": RSSSource}


def get_source(config: Dict[str, Any]) -> BaseSource:
    source_name = config.get("source", "cbc")
    source_config = config.get("sources", {}).get(source_name, {})
    source_class = SOURCES.get(source_name)
    if not source_class:
        raise ValueError(f"Unknown source: {source_name}")
    return source_class(source_config)
