from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Dict

from textual.theme import Theme

# --- Theme Configuration ---
DEFAULT_THEMES_PATH = Path(__file__).parent.parent.parent / "config/news/themes.json"
USER_THEMES_PATH = Path.home() / ".config/news/themes.json"

# Global themes dictionary
THEMES: Dict[str, Theme] = {}


def load_themes() -> Dict[str, Theme]:
    """
    Load themes from the user's config file, creating it from defaults if it
    doesn't exist.
    """
    if not USER_THEMES_PATH.exists():
        os.makedirs(USER_THEMES_PATH.parent, exist_ok=True)
        shutil.copy(DEFAULT_THEMES_PATH, USER_THEMES_PATH)

    themes = {}
    try:
        with open(USER_THEMES_PATH, "r") as f:
            themes_data = json.load(f)
        for name, definition in themes_data.items():
            themes[name] = Theme(name=name, **definition)
    except (IOError, json.JSONDecodeError):
        # Fallback to default themes if user file is corrupted
        with open(DEFAULT_THEMES_PATH, "r") as f:
            themes_data = json.load(f)
        for name, definition in themes_data.items():
            themes[name] = Theme(name=name, **definition)

    return themes


# Load themes on module import
THEMES = load_themes()
