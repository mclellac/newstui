#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
News TUI  Client - Full script
- Main view: Sections (left) and Headlines (right)
- Story opens in a separate StoryViewScreen when selected
- Persistent theme via ~/.config/news/config.json -> themes/<name>.css
- Robust fetching, retrying, and worker-state handling
"""

from __future__ import annotations

import argparse
import html
import json
import logging
import os
import re
import sys
import time
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Textual imports (conservative, add fallbacks where needed)
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.worker import Worker, WorkerState

from textual.widgets import (
    Header,
    Footer,
    ListItem,
    ListView,
    Static,
    LoadingIndicator,
)

# Markdown & scroll fallbacks for different Textual versions
try:
    from textual.widgets import Markdown  # type: ignore
except Exception:
    Markdown = Static  # type: ignore

try:
    from textual.containers import VerticalScroll  # some versions
except Exception:
    # fallback to Vertical for containing article content if VerticalScroll is missing
    VerticalScroll = Vertical  # type: ignore

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
        cfg = json.load(open(CONFIG_PATH, "r"))
        name = cfg.get("theme")
        if not name:
            return None
        candidate = os.path.join(THEMES_DIR, f"{name}.css")
        if os.path.exists(candidate):
            return candidate
    except Exception as e:
        logger.debug("Failed to read theme config: %s", e)
    return None


# --- Networking helpers ---
def create_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(REQUEST_HEADERS)
    retries = Retry(
        total=5, backoff_factor=0.3, status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retries)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


SESSION = create_session()


def _retryable_fetch(
    url: str, timeout: int = HTTP_TIMEOUT, attempts: int = RETRY_ATTEMPTS
) -> Optional[bytes]:
    delay = INITIAL_RETRY_DELAY
    for attempt in range(1, attempts + 1):
        try:
            logger.debug("Fetching %s (attempt %d/%d)", url, attempt, attempts)
            resp = SESSION.get(url, timeout=timeout)
            resp.raise_for_status()
            logger.debug("Fetched %s OK", url)
            return resp.content
        except requests.RequestException as e:
            logger.debug("Fetch attempt %d failed for %s: %s", attempt, url, e)
            if attempt == attempts:
                logger.warning("All fetch attempts failed for %s", url)
                return None
            time.sleep(delay)
            delay *= 2
    return None


# --- Data models ---
@dataclass
class Story:
    title: str
    url: str
    flag: Optional[str] = None


@dataclass
class Section:
    title: str
    url: str


# --- Utilities ---
def _abs_url(href: str) -> str:
    if not href:
        return ""
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return urljoin(DOMAIN_BASE, href)


def _unique_ordered_stories(items: Iterable[Story]) -> List[Story]:
    seen = set()
    out: List[Story] = []
    for s in items:
        if s.url and s.url not in seen:
            seen.add(s.url)
            out.append(s)
    return out


def _is_placeholder_text(text: str) -> bool:
    if not text:
        return True
    if len(text.split()) < MIN_ARTICLE_WORDS:
        return True
    if PLACEHOLDER_PATTERN.search(text):
        return True
    return False


def _parse_json_node_to_markdown(node: Dict[str, Any]) -> str:
    if not isinstance(node, dict):
        return ""
    node_type = node.get("type")
    tag = node.get("tag")
    content = node.get("content", [])
    if node_type == "text":
        return node.get("content", "")
    child_content = "".join(_parse_json_node_to_markdown(c) for c in content)
    tag_map = {
        "p": f"{child_content.strip()}\n\n",
        "h2": f"## {child_content.strip()}\n\n",
        "h3": f"### {child_content.strip()}\n\n",
        "a": f"[{child_content}]({_abs_url(node.get('attrs', {}).get('href', ''))})",
        "ul": f"{child_content}\n",
        "li": f"- {child_content.strip()}\n",
        "blockquote": "".join(
            f"> {line}\n" for line in child_content.strip().split("\n")
        )
        + "\n",
        "strong": f"**{child_content}**",
        "b": f"**{child_content}**",
        "em": f"*{child_content}*",
        "i": f"*{child_content}*",
    }
    return tag_map.get(tag, child_content)


# --- Scraping/parsing functions ---
def get_sections_combined() -> List[Section]:
    sections_map: Dict[str, Section] = {}
    for url in (HOME_PAGE_URL, SECTIONS_PAGE_URL):
        content = _retryable_fetch(url)
        if not content:
            continue
        try:
            soup = BeautifulSoup(content, "lxml")
            for a in soup.select("nav a[href], a[href^='/lite']"):
                href = _abs_url(a.get("href", ""))
                if "/lite" in href and "/lite/story/" not in href:
                    title = a.get_text(strip=True)
                    if (
                        title
                        and title.lower() not in {"menu", "search"}
                        and title not in sections_map
                    ):
                        sections_map[title] = Section(title=title, url=href)
        except Exception as e:
            logger.debug("Failed parsing sections from %s: %s", url, e)
    return [Section("Home", HOME_PAGE_URL)] + list(sections_map.values())


def get_stories_from_url(url: str) -> List[Story]:
    content = _retryable_fetch(url)
    if not content:
        return []
    try:
        soup = BeautifulSoup(content, "lxml")
        stories: List[Story] = []
        for a in soup.select("a[href*='/lite/story/']"):
            href = _abs_url(a.get("href", ""))
            span = a.find("span")
            flag = span.get_text(strip=True) if span else None
            title = a.get_text(" ", strip=True).replace(flag or "", "").strip()
            if title and href:
                stories.append(Story(title=title, url=href, flag=flag))
        return _unique_ordered_stories(stories)
    except Exception as e:
        logger.error("Failed to parse stories from %s: %s", url, e)
        return []


def get_story_content(url: str) -> Dict[str, Any]:
    content_bytes = _retryable_fetch(url)
    if not content_bytes:
        return {"ok": False, "content": "Failed to fetch article."}
    try:
        soup = BeautifulSoup(content_bytes, "lxml")
        json_script = soup.find("script", id="__NEXT_DATA__")
        if json_script and getattr(json_script, "string", None):
            try:
                data = json.loads(json_script.string)
                article = (
                    data.get("props", {}).get("pageProps", {}).get("articleData", {})
                )
                parts = [f"# {article.get('title', 'No Title')}\n\n"]
                for node in article.get("body", {}).get("parsed", []):
                    parts.append(_parse_json_node_to_markdown(node))
                if more := article.get("moreStories", []):
                    parts.append("\n\n---\n\n## More Stories\n\n")
                    parts.extend(
                        f"- [{s.get('title')}]({_abs_url(s.get('url'))})\n"
                        for s in more
                    )
                full = html.unescape("".join(parts)).strip()
                if len(full.split()) > MIN_ARTICLE_WORDS:
                    return {"ok": True, "content": full}
            except Exception:
                logger.debug(
                    "JSON parse failed for %s; falling back to paragraphs", url
                )
        main = soup.find("main") or soup
        paras = [p.get_text(" ", strip=True) for p in main.find_all("p")]
        candidate = "\n\n".join([p for p in paras if p]).strip()
        if candidate and not _is_placeholder_text(candidate):
            return {"ok": True, "content": candidate}
    except Exception as e:
        logger.error("Failed to parse story content from %s: %s", url, e)
    return {"ok": False, "content": "Could not extract valid article content."}


# --- UI Widgets ---
class SectionListItem(ListItem):
    def __init__(self, section: Section):
        super().__init__()
        self.section = section

    def compose(self) -> ComposeResult:
        yield Static(self.section.title)


class StoryListItem(ListItem):
    def __init__(self, story: Story):
        super().__init__()
        self.story = story

    def compose(self) -> ComposeResult:
        text = self.story.title
        if self.story.flag:
            text = f"[b]{self.story.flag}[/] — {text}"
        yield Static(text)


# --- Story screen (separate) ---
class StoryViewScreen(Screen):
    BINDINGS = [
        Binding("escape,q,b", "app.pop_screen", "Back"),
        Binding("o", "open_in_browser", "Open in browser"),
        Binding("r", "reload_story", "Reload"),
    ]

    def __init__(self, story: Story):
        super().__init__()
        self.story = story

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
        # Title, loading indicator, and scrollable Markdown
        yield Static(self.story.title, classes="pane-title")
        loading = LoadingIndicator(id="story-loading")
        yield loading
        yield VerticalScroll(Markdown("", id="story-markdown"), id="story-scroll")

    def on_mount(self) -> None:
        # hide loading until the worker runs
        try:
            self.query_one("#story-loading", LoadingIndicator).display = False
        except Exception:
            pass
        self.load_story()

    def load_story(self) -> None:
        try:
            self.query_one("#story-loading", LoadingIndicator).display = True
            self.query_one("#story-scroll").display = False
        except Exception:
            pass
        # fetch in worker thread
        self.run_worker(
            lambda: get_story_content(self.story.url), name="story_loader", thread=True
        )

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if getattr(event.worker, "name", None) != "story_loader":
            return

        # Only act when worker finished (SUCCESS) or otherwise finished (non-running).
        if event.state is WorkerState.SUCCESS:
            result = getattr(event.worker, "result", None) or {
                "ok": False,
                "content": "No content",
            }
            try:
                self.query_one("#story-loading", LoadingIndicator).display = False
                self.query_one("#story-scroll").display = True
            except Exception:
                pass
            md = self.query_one("#story-markdown")
            if isinstance(result, dict) and result.get("ok"):
                md.update(result.get("content", ""))
            else:
                msg = (
                    result.get("content", "Unable to load article.")
                    if isinstance(result, dict)
                    else "Unable to load article."
                )
                md.update(f"[b red]{msg}[/]")
        else:
            # worker not SUCCESS; if it's not running/pending treat as failure
            if event.state not in (WorkerState.PENDING, WorkerState.RUNNING):
                try:
                    self.query_one("#story-loading", LoadingIndicator).display = False
                    self.query_one("#story-scroll").display = True
                    md = self.query_one("#story-markdown")
                    md.update("[b red]Unable to load article[/]")
                except Exception:
                    pass

    def action_open_in_browser(self) -> None:
        webbrowser.open(self.story.url)

    def action_reload_story(self) -> None:
        self.load_story()


class NewsApp(App):
    TITLE = "News "
    SUB_TITLE = "News client for abnormies"

    CSS = """
    /* default minimal styling (users can override with theme CSS) */
    Screen { background: $surface; color: $text; }
    Header { background: $primary; color: $text; }
    Footer { background: $primary-darken-1; color: $text; }
    #main { layout: horizontal; height: 1fr; padding: 1; }
    #left { width: 40%; min-width: 30; padding-right: 1; }
    #right { width: 60%; min-width: 60; padding-left: 1; }
    .pane-title { text-style: bold; padding-bottom: 1; }
    ListView { border: none; }
    ListItem { padding: 0 1; }
    ListItem:hover { background: $primary-lighten-2; }
    ListView > ListItem.--highlighted { background: $accent; color: $text; }
    #story-scroll { padding: 1 0; }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("left", "nav_left", "Navigate Left"),
        Binding("right", "nav_right", "Navigate Right"),
    ]

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self.current_section: Optional[Section] = None

    def compose(self) -> ComposeResult:
        yield Header()
        # Main horizontal split: left = sections, right = headlines
        with Horizontal(id="main"):
            with Vertical(id="left"):
                yield Static("Sections", classes="pane-title")
                yield ListView(id="sections-list")
            with Vertical(id="right"):
                yield Static("Headlines", classes="pane-title")
                yield ListView(id="headlines-list")
        yield Footer()

    def on_mount(self) -> None:
        # Start loading sections on mount
        self.run_worker(get_sections_combined, name="sections_loader", thread=True)
        # focus sections list if possible
        try:
            self.query_one("#sections-list").focus()
        except Exception:
            pass

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        name = getattr(event.worker, "name", None)
        # handle only finished SUCCESS states for sections/headlines
        if name == "sections_loader" and event.state is WorkerState.SUCCESS:
            self._handle_sections_loaded(event)
        elif name == "headlines_loader" and event.state is WorkerState.SUCCESS:
            self._handle_headlines_loaded(event)
        elif name == "headlines_loader" and event.state not in (
            WorkerState.PENDING,
            WorkerState.RUNNING,
            WorkerState.SUCCESS,
        ):
            # headlines worker finished but not successful => show empty/failure message
            self._handle_headlines_loaded(event)

    def _handle_sections_loaded(self, event: Worker.StateChanged) -> None:
        view = self.query_one("#sections-list", ListView)
        view.clear()
        sections = getattr(event.worker, "result", None) or [
            Section("Home", HOME_PAGE_URL)
        ]
        for sec in sections:
            view.append(SectionListItem(sec))
        if sections:
            self.current_section = sections[0]
            # load headlines for the first section
            self._load_headlines_for_section(self.current_section)

    def _handle_headlines_loaded(self, event: Worker.StateChanged) -> None:
        view = self.query_one("#headlines-list", ListView)
        view.clear()
        stories = getattr(event.worker, "result", None) or []
        if not stories:
            view.append(ListItem(Static("[i]No headlines available.[/i]")))
            return
        for s in stories:
            view.append(StoryListItem(s))

    def _load_headlines_for_section(self, section: Section) -> None:
        if not section:
            return
        headlines_view = self.query_one("#headlines-list", ListView)
        headlines_view.clear()
        headlines_view.append(ListItem(Static("[i]Loading headlines...[/i]")))
        self.run_worker(
            lambda: get_stories_from_url(section.url),
            name="headlines_loader",
            thread=True,
        )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        # Section selected -> load headlines. Headline selected -> open StoryViewScreen.
        if event.list_view.id == "sections-list":
            if isinstance(event.item, SectionListItem):
                self.current_section = event.item.section
                self._load_headlines_for_section(self.current_section)
        elif event.list_view.id == "headlines-list":
            if isinstance(event.item, StoryListItem):
                # push the story screen (separate view)
                self.push_screen(StoryViewScreen(event.item.story))

    def action_refresh(self) -> None:
        if self.current_section:
            self._load_headlines_for_section(self.current_section)

    def action_nav_left(self) -> None:
        try:
            if self.query_one("#headlines-list").has_focus:
                self.query_one("#sections-list").focus()
        except Exception:
            pass

    def action_nav_right(self) -> None:
        try:
            if self.query_one("#sections-list").has_focus:
                self.query_one("#headlines-list").focus()
        except Exception:
            pass


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

    theme_path: Optional[str] = None
    if args.theme:
        candidate = os.path.join(THEMES_DIR, f"{args.theme}.css")
        if os.path.exists(candidate):
            theme_path = candidate
        else:
            print(
                f"Theme {args.theme} not found at {candidate}; continuing without it.",
                file=sys.stderr,
            )
    else:
        theme_path = load_theme_file_from_config()

    if theme_path:
        NewsApp.CSS_PATH = theme_path
        logger.info("Using theme CSS: %s", theme_path)
    else:
        logger.info("No theme CSS applied; using built-in CSS.")

    try:
        app = NewsApp()
        app.run()
    except Exception as e:
        logger.exception("Application crashed: %s", e)
        print(f"Application crashed: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
