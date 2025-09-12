from __future__ import annotations

from typing import Any, Optional, List

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.command import CommandPalette, Hit, Hits, Provider
from textual.containers import Horizontal, Vertical
from textual.worker import Worker, WorkerState
from rich.text import Text
from textual.widgets import (
    DataTable,
    Header,
    Input,
    ListView,
    Static,
    LoadingIndicator,
    Rule,
)

from .config import (
    HOME_PAGE_URL,
    load_read_articles,
    save_read_articles,
    load_bookmarks,
    save_bookmarks,
)
from dataclasses import asdict
from .datamodels import Section, Story
from .fetcher import Fetcher
from .sources.base import BaseSource
from .screens import StoryViewScreen, BookmarksScreen, HelpScreen
from .themes import THEMES
from .widgets import SectionListItem, StatusBar


class ThemeProvider(Provider):
    async def search(self, query: str) -> Hits:
        """Search for a theme."""
        matcher = self.matcher(query)

        for theme_name in THEMES:
            score = matcher.match(theme_name)
            if score > 0:
                yield Hit(
                    score,
                    matcher.highlight(f"Switch to {theme_name} theme"),
                    self.app.action_switch_theme(theme_name),
                )


class NewsApp(App):
    TITLE = "News "
    SUB_TITLE = "News client for abnormies"

    CSS_PATH = "app.css"

    COMMANDS = App.COMMANDS | {ThemeProvider}

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("b", "bookmark", "Bookmark"),
        Binding("B", "show_bookmarks", "Show Bookmarks"),
        Binding("h", "show_help", "Help"),
        Binding("left", "nav_left", "Navigate Left"),
        Binding("right", "nav_right", "Navigate Right"),
        Binding("ctrl+p", "command_palette", "Commands"),
    ]

    def __init__(
        self,
        theme: Optional[str] = None,
        source: Optional[BaseSource] = None,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.current_section: Optional[Section] = None
        self._theme_name = theme
        self.stories: List[Story] = []
        self.read_articles: set[str] = set()
        self.bookmarks: List[dict] = []
        self.fetcher = Fetcher(source)

    def compose(self) -> ComposeResult:
        yield Header()
        # Main horizontal split: left = sections, right = headlines
        with Horizontal(id="main"):
            with Vertical(id="left"):
                yield Static("Sections", classes="pane-title")
                yield ListView(id="sections-list")
            yield Rule(orientation="vertical")
            with Vertical(id="right"):
                yield Static("Headlines", classes="pane-title")
                yield Input(placeholder="Filter headlines...")
                yield DataTable(id="headlines-table")
                yield Rule()
                yield Static("Summary", classes="pane-title")
                yield Static(id="summary-text", classes="summary-text")
        yield StatusBar()

    def on_mount(self) -> None:
        self.read_articles = load_read_articles()
        self.bookmarks = load_bookmarks()
        self.screen.bindings = self.BINDINGS
        # Start loading sections on mount
        self.run_worker(self.fetcher.get_sections, name="sections_loader", thread=True)
        # focus sections list if possible
        try:
            self.query_one("#sections-list").focus()
        except Exception:
            pass

        # Configure the headlines table
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        table.add_column("Flag", width=10)
        table.add_column("Title")
        table.add_column("story", width=0)

        # Register all themes
        for name, theme in THEMES.items():
            self.register_theme(theme)

        # Set the theme
        self.theme = self._theme_name

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        name = getattr(event.worker, "name", None)
        # handle only finished SUCCESS states for sections/headlines
        if name == "sections_loader" and event.state is WorkerState.SUCCESS:
            self._handle_sections_loaded(event)
        elif name == "headlines_loader" and event.state is WorkerState.SUCCESS:
            self._handle_headlines_loaded(event)
        elif name == "headlines_loader" and event.state is WorkerState.ERROR:
            self._handle_headlines_error(event)
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

    def _handle_headlines_error(self, event: Worker.StateChanged) -> None:
        self.query_one(StatusBar).loading_status = "Error loading headlines."
        table = self.query_one(DataTable)
        try:
            table.query_one(LoadingIndicator).remove()
        except Exception:
            pass
        table.visible = False

    def _update_headlines_table(self, stories: List[Story]) -> None:
        table = self.query_one(DataTable)
        table.clear()
        if not stories:
            table.visible = False
            return
        for s in stories:
            flag = s.flag or ""
            if s.bookmarked:
                flag = f"B {flag}".strip()

            style = "dim" if s.read else ""
            table.add_row(
                Text(flag, style=style),
                Text(s.title, style=style),
                s,
                key=s.url,
            )
        table.visible = True

    def _handle_headlines_loaded(self, event: Worker.StateChanged) -> None:
        self.query_one(StatusBar).loading_status = ""
        table = self.query_one(DataTable)
        try:
            table.query_one(LoadingIndicator).remove()
        except Exception:
            pass
        self.stories = getattr(event.worker, "result", None) or []
        self._update_headlines_table(self.stories)

    def _load_headlines_for_section(self, section: Section) -> None:
        if not section:
            return
        self.query_one(StatusBar).loading_status = f"Loading {section.title}..."
        self.query_one(Input).value = ""
        table = self.query_one(DataTable)
        table.clear()
        table.mount(LoadingIndicator())
        self.run_worker(
            lambda: self.fetcher.get_stories(
                section, self.read_articles, self.bookmarks
            ),
            name="headlines_loader",
            thread=True,
        )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        # Section selected -> load headlines.
        if event.list_view.id == "sections-list":
            if isinstance(event.item, SectionListItem):
                self.current_section = event.item.section
                self._load_headlines_for_section(self.current_section)

    def _open_story(self, story: Story) -> None:
        story.read = True
        self.read_articles.add(story.url)
        save_read_articles(self.read_articles)
        self._update_headlines_table(self.stories)
        self.push_screen(StoryViewScreen(story, self.fetcher, self.current_section))

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        summary_text = self.query_one("#summary-text", Static)
        story = event.control.get_row(event.row_key)[-1]
        if story and story.summary:
            summary_text.update(story.summary)
        else:
            summary_text.update("No summary available.")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        # Headline selected -> open StoryViewScreen.
        story = event.control.get_row(event.row_key)[-1]
        if story:
            self._open_story(story)

    def action_refresh(self) -> None:
        if self.current_section:
            self._load_headlines_for_section(self.current_section)

    def action_nav_left(self) -> None:
        try:
            if self.query_one("#headlines-table").has_focus:
                self.query_one("#sections-list").focus()
        except Exception:
            pass

    def action_nav_right(self) -> None:
        table = self.query_one("#headlines-table")
        if table.has_focus:
            row_index = table.cursor_row
            story = table.get_row_at(row_index)[-1]
            if story:
                self._open_story(story)
        else:
            try:
                if self.query_one("#sections-list").has_focus:
                    table.focus()
            except Exception:
                pass

    def on_input_changed(self, event: Input.Changed) -> None:
        query = event.value.strip().lower()
        if not query:
            self._update_headlines_table(self.stories)
            return
        filtered_stories = [
            s for s in self.stories if query in s.title.lower()
        ]
        self._update_headlines_table(filtered_stories)

    def action_bookmark(self) -> None:
        table = self.query_one(DataTable)
        if not table.has_focus:
            return
        row_index = table.cursor_row
        story = table.get_row_at(row_index)[-1]
        if not story:
            return

        story.bookmarked = not story.bookmarked
        if story.bookmarked:
            self.bookmarks.append(asdict(story))
        else:
            self.bookmarks = [b for b in self.bookmarks if b["url"] != story.url]
        save_bookmarks(self.bookmarks)
        self._update_headlines_table(self.stories)

    def action_show_bookmarks(self) -> None:
        self.push_screen(BookmarksScreen())

    def action_show_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_switch_theme(self, theme: str) -> None:
        self.theme = theme
