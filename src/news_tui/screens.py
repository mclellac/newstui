from __future__ import annotations

import webbrowser

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.worker import Worker, WorkerState
from textual.widgets import Footer, Header, LoadingIndicator, Static

from .datamodels import Story
from .fetcher import Fetcher
from .config import load_bookmarks
from .themes import THEMES
from textual.widgets import DataTable

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


# --- Story screen (separate) ---
class StoryViewScreen(Screen):
    BINDINGS = [
        Binding("escape,q,b,left", "app.pop_screen", "Back"),
        Binding("o", "open_in_browser", "Open in browser"),
        Binding("r", "reload_story", "Reload"),
    ]

    def __init__(self, story: Story, fetcher: Fetcher, section: Section):
        super().__init__()
        self.story = story
        self.fetcher = fetcher
        self.section = section

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
        # loading indicator and scrollable Markdown
        loading = LoadingIndicator(id="story-loading")
        yield loading
        yield VerticalScroll(Markdown("", id="story-markdown"), id="story-scroll")

    def on_mount(self) -> None:
        self.title = self.story.title
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
            lambda: self.fetcher.get_story_content(self.story, self.section),
            name="story_loader",
            thread=True,
        )

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if getattr(event.worker, "name", None) != "story_loader":
            return

        error_color = "red"
        if self.app.theme in THEMES:
            error_color = THEMES[self.app.theme].error

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
                md.update(f"[b {error_color}]{msg}[/]")
        else:
            # worker not SUCCESS; if it's not running/pending treat as failure
            if event.state not in (WorkerState.PENDING, WorkerState.RUNNING):
                try:
                    self.query_one("#story-loading", LoadingIndicator).display = False
                    self.query_one("#story-scroll").display = True
                    md = self.query_one("#story-markdown")
                    md.update(f"[b {error_color}]Unable to load article[/]")
                except Exception:
                    pass

    def action_open_in_browser(self) -> None:
        webbrowser.open(self.story.url)

    def on_markdown_link_clicked(self, event: Markdown.LinkClicked) -> None:
        """Handle clicks on links in Markdown."""
        webbrowser.open(event.href)

    def action_reload_story(self) -> None:
        self.load_story()


class BookmarksScreen(Screen):
    BINDINGS = [
        Binding("escape,q,b,left", "app.pop_screen", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
        yield DataTable()

    def on_mount(self) -> None:
        self.title = "Bookmarks"
        table = self.query_one(DataTable)
        table.add_column("Title", width=50)
        table.add_column("Summary")
        bookmarks = load_bookmarks()
        for b in bookmarks:
            table.add_row(b["title"], b["summary"] or "")


class HelpScreen(Screen):
    BINDINGS = [
        Binding("escape,q,h,left", "app.pop_screen", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
        yield Static("Keybindings", classes="pane-title")
        yield Static(
            "q: Quit\n"
            "r: Refresh\n"
            "b: Bookmark\n"
            "B: Show Bookmarks\n"
            "h: Help\n"
            "o: Open in browser\n"
            "left: Navigate Left\n"
            "right: Navigate Right\n"
            "ctrl+p: Command Palette"
        )
