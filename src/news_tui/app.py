from __future__ import annotations

from typing import Any, Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.command import CommandPalette, Hit, Hits, Provider
from textual.containers import Horizontal, Vertical
from textual.worker import Worker, WorkerState
from textual.widgets import Footer, Header, ListItem, ListView, Static, LoadingIndicator, Rule

from .config import HOME_PAGE_URL
from .datamodels import Section
from .fetcher import get_sections_combined, get_stories_from_url
from .screens import StoryViewScreen
from .themes import THEMES
from .widgets import SectionListItem, StoryListItem


class ThemeProvider(Provider):
    async def get_hits(self, query: str) -> Hits:
        for theme_name in THEMES:
            if query in theme_name:
                yield Hit(
                    1,
                    self.app.action_switch_theme(theme_name),
                    f"Switch to {theme_name} theme",
                )


class NewsApp(App):
    TITLE = "News "
    SUB_TITLE = "News client for abnormies"

    CSS_PATH = "app.css"

    COMMANDS = App.COMMANDS | {ThemeProvider}

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("left", "nav_left", "Navigate Left"),
        Binding("right", "nav_right", "Navigate Right"),
        Binding("ctrl+p", "command_palette", "Commands"),
    ]

    def __init__(self, theme: Optional[str] = None, **kwargs: Any):
        super().__init__(**kwargs)
        self.current_section: Optional[Section] = None
        self._theme_name = theme

    def compose(self) -> ComposeResult:
        yield Header()
        # Main horizontal split: left = sections, right = headlines
        with Horizontal(id="main"):
            with Vertical(id="left"):
                yield Static("Sections", classes="pane-title")
                yield ListView(id="sections-list")
            yield Rule(direction="vertical")
            with Vertical(id="right"):
                yield Static("Headlines", classes="pane-title")
                yield ListView(id="headlines-list")
        yield Footer()

    def on_mount(self) -> None:
        self.screen.bindings = self.BINDINGS
        # Start loading sections on mount
        self.run_worker(get_sections_combined, name="sections_loader", thread=True)
        # focus sections list if possible
        try:
            self.query_one("#sections-list").focus()
        except Exception:
            pass
        # Register all themes
        for name, theme in THEMES.items():
            self.register_theme(theme)

        # Set the theme if one was provided
        if self._theme_name and self._theme_name in THEMES:
            self.theme = self._theme_name
        else:
            self.theme = "dracula"

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
        view = self.query_one("#headlines-list", ListView)
        try:
            view.query_one(LoadingIndicator).remove()
        except Exception:
            pass
        view.append(
            ListItem(
                Static(
                    "[b red]Error loading headlines.[/b red]\n\n"
                    "Please check your internet connection and try again."
                )
            )
        )

    def _handle_headlines_loaded(self, event: Worker.StateChanged) -> None:
        view = self.query_one("#headlines-list", ListView)
        try:
            view.query_one(LoadingIndicator).remove()
        except Exception:
            pass
        stories = getattr(event.worker, "result", None) or []
        if not stories:
            view.append(
                ListItem(Static("[i]No headlines available for this section.[/i]"))
            )
            return
        for s in stories:
            view.append(StoryListItem(s))

    def _load_headlines_for_section(self, section: Section) -> None:
        if not section:
            return
        headlines_view = self.query_one("#headlines-list", ListView)
        headlines_view.clear()
        headlines_view.mount(LoadingIndicator())
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

    def action_switch_theme(self, theme: str) -> None:
        self.theme = theme
