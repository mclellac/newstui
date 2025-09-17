from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, Optional
import importlib.resources
import shutil

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

# Default UI settings
UI_DEFAULTS = {
    "statusbar_keybindings": "[b cyan]ctrl+l[/] to toggle sections",
}

# --- Logging ---
logger = logging.getLogger("news")

def setup_logging(debug: bool = False) -> Optional[str]:
    """Configure logging."""
    if not debug:
        logging.basicConfig(level=logging.CRITICAL, handlers=[logging.NullHandler()])
        return None

    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    pid = os.getpid()
    debug_path = f"/tmp/news_debug_{ts}_{pid}.log"

    # Use basicConfig to set up the root logger with a file handler
    logging.basicConfig(
        level=logging.DEBUG,
        filename=debug_path,
        filemode="a",
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )

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


def ensure_config_file_exists() -> None:
    """Copy the default config file if the user's config file is not found."""
    if not os.path.exists(CONFIG_PATH):
        logger.info("Config file not found at %s, creating default.", CONFIG_PATH)
        try:
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            with importlib.resources.path("config.news", "config.json") as default_config_path:
                shutil.copy(default_config_path, CONFIG_PATH)
        except (IOError, OSError) as e:
            logger.error("Failed to create default config file: %s", e)

def load_config() -> Dict[str, Any]:
    """Load the main configuration file."""
    ensure_config_file_exists()
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


from textual.theme import Theme
from .default_themes import DEFAULT_THEMES

def load_themes() -> dict[str, Theme]:
    """Load themes from default and user config."""
    config = load_config()
    user_theme_defs = config.get("themes", {})

    # Start with default themes
    themes = DEFAULT_THEMES.copy()

    # Create Theme objects from user definitions and merge them
    for name, definition in user_theme_defs.items():
        try:
            # Add the 'name' to the definition dict before creating the Theme
            definition['name'] = name
            themes[name] = Theme.from_dict(definition)
        except Exception as e:
            # Ignore invalid theme definitions
            logger.warning("Ignoring invalid theme definition for '%s': %s", name, e)
            pass

    return themes


def load_theme_name_from_config() -> Optional[str]:
    """Return theme name if configured and present; else None."""
    config = load_config()
    return config.get("theme")


def ensure_themes_are_copied() -> None:
    """Copy built-in themes to the user's config directory."""
    themes_dir = os.path.join(os.path.dirname(CONFIG_PATH), "themes")
    os.makedirs(themes_dir, exist_ok=True)

    try:
        theme_files = importlib.resources.files("news_tui.packaged_themes")
        for theme_file in theme_files.iterdir():
            if theme_file.is_file() and theme_file.name.endswith(".css"):
                dest_path = os.path.join(themes_dir, theme_file.name)
                if not os.path.exists(dest_path):
                    with importlib.resources.as_file(theme_file) as theme_file_path:
                        shutil.copy(theme_file_path, dest_path)
                        logger.info(f"Copied theme '{theme_file.name}' to '{dest_path}'")
    except ModuleNotFoundError:
        logger.error("Could not find the 'news_tui.packaged_themes' module to copy themes from.")
