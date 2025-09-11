from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from typing import Optional

# --- Configuration ---
HOME_PAGE_URL = "https://www.cbc.ca/lite"
SECTIONS_PAGE_URL = "https://www.cbc.ca/lite/sections"
DOMAIN_BASE = "https://www.cbc.ca"
HTTP_TIMEOUT = 15
MIN_ARTICLE_WORDS = 15

CONFIG_PATH = os.path.expanduser("~/.config/news/config.json")
THEMES_DIR = os.path.expanduser("~/.config/news/themes/")

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


def load_theme_file_from_config() -> Optional[str]:
    """Return path to theme CSS if configured and present; else None."""
    if not os.path.exists(CONFIG_PATH):
        return None
    try:
        with open(CONFIG_PATH, "r") as f:
            cfg = json.load(f)
        name = cfg.get("theme")
        if not name:
            return None

        user_theme_path = os.path.join(THEMES_DIR, f"{name}.tcss")
        if os.path.exists(user_theme_path):
            logger.info(f"Loading user theme: {name}")
            return user_theme_path

    except Exception as e:
        logger.debug("Failed to read theme config: %s", e)

    return None
