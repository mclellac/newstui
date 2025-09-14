from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set

# --- Constants ---
HOME_PAGE_URL = "https://www.cbc.ca/lite"
SECTIONS_PAGE_URL = "https://www.cbc.ca/lite/sections"
DOMAIN_BASE = "https://www.cbc.ca"
HTTP_TIMEOUT = 15
MIN_ARTICLE_WORDS = 15

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:115.0) "
        "Gecko/20100101 Firefox/115.0"
    )
}
RETRY_ATTEMPTS = 4
INITIAL_RETRY_DELAY = 0.5
PLACEHOLDER_PATTERN = re.compile(r"\b(loading|unable to load|error|retrying)\b", re.I)

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    filename="newstui.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)
logger = logging.getLogger("news")


def enable_debug_log_to_tmp() -> str:
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    pid = os.getpid()
    debug_path = f"/tmp/news_debug_{ts}_{pid}.log"
    fh = logging.FileHandler(debug_path, mode="a")
    fh.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    logging.getLogger().addHandler(fh)
    logger.setLevel(logging.DEBUG)
    logging.getLogger().setLevel(logging.DEBUG)
    logger.debug("Debug logging enabled to %s", debug_path)
    return debug_path


class ConfigManager:
    """Manages application configuration."""

    def __init__(self, config_dir: Path | None = None):
        self.config_dir = config_dir or Path.home() / ".config/news"
        self.config_path = self.config_dir / "config.json"
        self.read_articles_path = self.config_dir / "read_articles.json"
        self.bookmarks_path = self.config_dir / "bookmarks.json"

        self.config: Dict[str, Any] = {}
        self.read_articles: Set[str] = set()
        self.bookmarks: List[Dict] = []

        os.makedirs(self.config_dir, exist_ok=True)
        self._load()

    def _load(self) -> None:
        """Load all configuration files."""
        self.config = self._load_json(self.config_path)
        self.read_articles = set(self._load_json(self.read_articles_path, default=[]))
        self.bookmarks = self._load_json(self.bookmarks_path, default=[])

    def save(self) -> None:
        """Save all configuration files."""
        self._save_json(self.config_path, self.config)
        self._save_json(self.read_articles_path, list(self.read_articles))
        self._save_json(self.bookmarks_path, self.bookmarks)

    def _load_json(self, path: Path, default: Any = None) -> Any:
        if not path.exists():
            return default if default is not None else {}
        try:
            with open(path, "r") as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError):
            return default if default is not None else {}

    def _save_json(self, path: Path, data: Any) -> None:
        try:
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            logger.error("Failed to save to %s: %s", path, e)

    @property
    def theme(self) -> str:
        return self.config.get("theme", "dracula")

    @theme.setter
    def theme(self, theme_name: str) -> None:
        self.config["theme"] = theme_name
        self.save()

    def get_source_config(self, source_name: str) -> Dict[str, Any]:
        return self.config.get("sources", {}).get(source_name, {})

    @property
    def meta_sections(self) -> Dict[str, List[str]]:
        return self.config.get("meta_sections", {})
