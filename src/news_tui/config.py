from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, Optional

# --- Configuration ---
HOME_PAGE_URL = "https://www.cbc.ca/lite"
SECTIONS_PAGE_URL = "https://www.cbc.ca/lite/sections"
DOMAIN_BASE = "https://www.cbc.ca"
HTTP_TIMEOUT = 15
MIN_ARTICLE_WORDS = 15

CONFIG_PATH = os.path.expanduser("~/.config/news/config.json")
READ_ARTICLES_FILE = os.path.expanduser("~/.config/news/read_articles.json")
BOOKMARKS_FILE = os.path.expanduser("~/.config/news/bookmarks.json")

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


def load_read_articles() -> set[str]:
    """Load the set of read article URLs from the config file."""
    if not os.path.exists(READ_ARTICLES_FILE):
        return set()
    try:
        with open(READ_ARTICLES_FILE, "r") as f:
            return set(json.load(f))
    except (IOError, json.JSONDecodeError):
        return set()


def save_read_articles(read_articles: set[str]) -> None:
    """Save the set of read article URLs to the config file."""
    try:
        with open(READ_ARTICLES_FILE, "w") as f:
            json.dump(list(read_articles), f)
    except IOError:
        pass


def load_bookmarks() -> list[dict]:
    """Load the list of bookmarked articles from the config file."""
    if not os.path.exists(BOOKMARKS_FILE):
        return []
    try:
        with open(BOOKMARKS_FILE, "r") as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError):
        return []


def save_bookmarks(bookmarks: list[dict]) -> None:
    """Save the list of bookmarked articles to the config file."""
    try:
        with open(BOOKMARKS_FILE, "w") as f:
            json.dump(bookmarks, f)
    except IOError:
        pass


def load_config() -> Dict[str, Any]:
    """Load the main configuration file."""
    if not os.path.exists(CONFIG_PATH):
        logger.info("Config file not found at %s", CONFIG_PATH)
        return {}
    try:
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)
            logger.info("Loaded config from %s", CONFIG_PATH)
            return config
    except (IOError, json.JSONDecodeError) as e:
        logger.error("Failed to load config from %s: %s", CONFIG_PATH, e)
        return {}


def save_config(config: Dict[str, Any]) -> None:
    """Save the main configuration file."""
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2)
        logger.info("Saved config to %s", CONFIG_PATH)
    except IOError as e:
        logger.error("Failed to save config to %s: %s", CONFIG_PATH, e)


def load_theme_name_from_config() -> Optional[str]:
    """Return theme name if configured and present; else None."""
    config = load_config()
    return config.get("theme")
