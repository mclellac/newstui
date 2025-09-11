from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from typing import Optional

# --- Configuration ---
DEFAULT_SOURCE = {
    "name": "CBC Lite",
    "base_url": "https://www.cbc.ca",
    "home_url": "https://www.cbc.ca/lite",
    "sections_url": "https://www.cbc.ca/lite/sections",
}

HTTP_TIMEOUT = 15
MIN_ARTICLE_WORDS = 15

CONFIG_PATH = os.path.expanduser("~/.config/news/config.json")

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


def load_theme_name_from_config() -> Optional[str]:
    """Return theme name if configured and present; else None."""
    if not os.path.exists(CONFIG_PATH):
        return None
    try:
        with open(CONFIG_PATH, "r") as f:
            cfg = json.load(f)
        name = cfg.get("theme")
        if name:
            logger.info(f"Loading theme: {name}")
            return name
    except Exception as e:
        logger.debug("Failed to read theme config: %s", e)

    return None
