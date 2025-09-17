#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Optional

from .app import NewsApp
from .config import load_config, load_themes, setup_logging

logger = logging.getLogger("news")


# --- Entrypoint ---
def main() -> None:
    parser = argparse.ArgumentParser(description="News TUI Client")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    # Load themes to populate help text
    available_themes = load_themes()
    parser.add_argument(
        "--theme",
        type=str,
        help=f"Set theme for this run. Available: {', '.join(available_themes.keys())}",
    )
    args = parser.parse_args()

    debug_path = setup_logging(args.debug)
    if debug_path:
        print(f"Debug logging enabled: {debug_path}", file=sys.stderr)

    config = load_config()
    theme_name = args.theme or config.get("theme") or "dracula"

    if theme_name not in available_themes:
        print(f"Theme '{theme_name}' not found, falling back to dracula.", file=sys.stderr)
        theme_name = "dracula"

    logger.info("Using theme: %s", theme_name)

    try:
        app = NewsApp(theme=theme_name, config=config)
        app.run()
    except Exception as e:
        logger.exception("Application crashed: %s", e)
        print(f"Application crashed: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
