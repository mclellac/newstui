#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Optional

from .app import NewsApp
from .config import THEMES_DIR, enable_debug_log_to_tmp, load_theme_file_from_config

logger = logging.getLogger("news")


# --- Entrypoint ---
def main() -> None:
    parser = argparse.ArgumentParser(description="News TUI Client")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--theme",
        type=str,
        help="Temporarily set theme (CSS file name without .css) for this run",
    )
    args = parser.parse_args()

    if args.debug:
        debug_path = enable_debug_log_to_tmp()
        print(f"Debug logging enabled: {debug_path}", file=sys.stderr)

    theme_css_path: Optional[str] = None
    if args.theme:
        user_theme_path = os.path.join(THEMES_DIR, f"{args.theme}.css")
        if os.path.exists(user_theme_path):
            theme_css_path = user_theme_path
        else:
            print(
                f"Theme {args.theme} not found; continuing without it.",
                file=sys.stderr,
            )
    else:
        theme_css_path = load_theme_file_from_config()

    if theme_css_path:
        logger.info("Using theme CSS: %s", theme_css_path)
    else:
        logger.info("No theme CSS applied; using built-in CSS.")

    try:
        app = NewsApp(css_path=theme_css_path)
        app.run()
    except Exception as e:
        logger.exception("Application crashed: %s", e)
        print(f"Application crashed: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
