from __future__ import annotations

from typing import Any, Optional, List

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.command import CommandPalette, Hit, Hits, Provider
from textual.containers import Horizontal, Vertical
from textual.worker import Worker, WorkerState
from rich.text import Text
from textual.widgets import (
    Header,
    Input,
    ListView,
    Static,
    LoadingIndicator,
    Rule,
)

import logging
from .config import (
    HOME_PAGE_URL,
    load_config,
    load_read_articles,
    load_bookmarks,
    save_bookmarks,
    save_config,
    save_read_articles,
)
from dataclasses import asdict

logger = logging.getLogger("news")
from .datamodels import Section, Story
from .sources.cbc import CBCSource
from .screens import BookmarksScreen, SettingsScreen, StoryViewScreen
from .themes import THEMES
from .widgets import HeadlineItem, SectionListItem, StatusBar


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
        Binding("s", "show_settings", "Settings"),
        Binding("left", "nav_left", "Navigate Left"),
        Binding("right", "nav_right", "Navigate Right"),
        Binding("ctrl+p", "command_palette", "Commands"),
        Binding("ctrl+l", "toggle_left_pane", "Toggle Sections"),
    ]

    def __init__(
        self,
        theme: Optional[str] = None,
        config: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.current_section: Optional[Section] = None
        self._theme_name = theme
        self.stories: List[Story] = []
        self.read_articles: set[str] = set()
        self.bookmarks: List[dict] = []
        self.config = config or {}
        cbc_config = self.config.get("sources", {}).get("cbc", {})
        self.source = CBCSource(cbc_config)
        self.meta_sections = self.config.get("meta_sections", {})

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
                yield ListView(id="headlines-list")
        yield StatusBar()

    def on_mount(self) -> None:
        self.read_articles = load_read_articles()
        self.bookmarks = load_bookmarks()
        self.screen.bindings = self.BINDINGS
        # Start loading sections on mount
        self.run_worker(self.source.get_sections, name="sections_loader", thread=True)
        # focus sections list if possible
        try:
            self.query_one("#sections-list").focus()
        except Exception:
            pass

        # Configure the headlines list
        self.query_one("#headlines-list", ListView).cursor_type = "row"

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

        # Filter sections based on config
        enabled_sections = self.config.get("sections")
        if enabled_sections:
            sections = [s for s in sections if s.title in enabled_sections]

        all_sections = sections.copy()
        for meta_section_name in self.meta_sections:
            all_sections.insert(
                0, Section(title=meta_section_name, url="meta:" + meta_section_name)
            )

        for sec in all_sections:
            view.append(SectionListItem(sec))
        if all_sections:
            self.current_section = all_sections[0]
            # load headlines for the first section
            self._load_headlines_for_section(self.current_section)
        else:
            # No sections, clear headlines
            self.query_one("#headlines-list", ListView).clear()

    def _handle_headlines_error(self, event: Worker.StateChanged) -> None:
        self.query_one(StatusBar).loading_status = "Error loading headlines."
        headlines_list = self.query_one("#headlines-list", ListView)
        try:
            headlines_list.query_one(LoadingIndicator).remove()
        except Exception:
            pass
        headlines_list.display = False

    def _update_headlines_list(self, stories: List[Story]) -> None:
        headlines_list = self.query_one("#headlines-list", ListView)
        headlines_list.clear()
        if not stories:
            headlines_list.display = False
            return
        for s in stories:
            item = HeadlineItem(s)
            if s.read:
                item.add_class("read")
            headlines_list.append(item)
        headlines_list.display = True

    def _handle_headlines_loaded(self, event: Worker.StateChanged) -> None:
        self.query_one(StatusBar).loading_status = ""
        headlines_list = self.query_one("#headlines-list", ListView)
        try:
            headlines_list.query_one(LoadingIndicator).remove()
        except Exception:
            pass
        self.stories = getattr(event.worker, "result", None) or []
        self._update_headlines_list(self.stories)

    def _load_headlines_for_section(self, section: Section) -> None:
        if not section:
            return

        if section.url.startswith("meta:"):
            self._load_headlines_for_meta_section(section)
            return

        self.query_one(StatusBar).loading_status = f"Loading {section.title}..."
        self.query_one(Input).value = ""
        headlines_list = self.query_one("#headlines-list", ListView)
        headlines_list.clear()
        headlines_list.mount(LoadingIndicator())
        self.run_worker(
            lambda: self.source.get_stories(
                section, self.read_articles, self.bookmarks
            ),
            name="headlines_loader",
            thread=True,
        )

    def _load_headlines_for_meta_section(self, section: Section) -> None:
        meta_section_name = section.url.replace("meta:", "")
        section_names = self.meta_sections.get(meta_section_name, [])
        if not section_names:
            return

        self.query_one(StatusBar).loading_status = f"Loading {section.title}..."
        self.query_one(Input).value = ""
        headlines_list = self.query_one("#headlines-list", ListView)
        headlines_list.clear()
        headlines_list.mount(LoadingIndicator())

        def _get_stories():
            all_stories = []
            seen_urls = set()
            all_sections = self.source.get_sections()
            for section_name in section_names:
                for s in all_sections:
                    if s.title == section_name:
                        stories = self.source.get_stories(
                            s, self.read_articles, self.bookmarks
                        )
                        for story in stories:
                            if story.url not in seen_urls:
                                all_stories.append(story)
                                seen_urls.add(story.url)
            return all_stories

        self.run_worker(
            _get_stories,
            name="headlines_loader",
            thread=True,
        )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        # Section selected -> load headlines.
        if event.list_view.id == "sections-list":
            if isinstance(event.item, SectionListItem):
                self.current_section = event.item.section
                self._load_headlines_for_section(self.current_section)
        elif event.list_view.id == "headlines-list":
            if isinstance(event.item, HeadlineItem):
                self._open_story(event.item.story)

    def _open_story(self, story: Story) -> None:
        story.read = True
        self.read_articles.add(story.url)
        save_read_articles(self.read_articles)
        self._update_headlines_list(self.stories)
        self.push_screen(StoryViewScreen(story, self.source, self.current_section))

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
        headlines_list = self.query_one("#headlines-list", ListView)
        if headlines_list.has_focus:
            item = headlines_list.highlighted_child
            if isinstance(item, HeadlineItem):
                self._open_story(item.story)
        else:
            try:
                if self.query_one("#sections-list").has_focus:
                    headlines_list.focus()
            except Exception:
                pass

    def on_input_changed(self, event: Input.Changed) -> None:
        query = event.value.strip().lower()
        if not query:
            self._update_headlines_list(self.stories)
            return
        filtered_stories = [
            s
            for s in self.stories
            if query in s.title.lower()
            or query in s.section.lower()
            or (s.flag and query in s.flag.lower())
        ]
        self._update_headlines_list(filtered_stories)

    def action_bookmark(self) -> None:
        headlines_list = self.query_one("#headlines-list", ListView)
        if not headlines_list.has_focus:
            return
        item = headlines_list.highlighted_child
        if not isinstance(item, HeadlineItem):
            return

        story = item.story
        story.bookmarked = not story.bookmarked
        if story.bookmarked:
            self.bookmarks.append(asdict(story))
        else:
            self.bookmarks = [b for b in self.bookmarks if b["url"] != story.url]
        save_bookmarks(self.bookmarks)
        self._update_headlines_list(self.stories)

    def action_show_bookmarks(self) -> None:
        self.push_screen(BookmarksScreen())

    def action_show_settings(self) -> None:
        """Show the settings screen."""
        self.push_screen(SettingsScreen(), self.on_settings_closed)

    def on_settings_closed(self, _: Any) -> None:
        """Called when settings screen is closed."""
        # reload config and sections
        self.config = load_config()
        self.meta_sections = self.config.get("meta_sections", {})
        self.run_worker(self.source.get_sections, name="sections_loader", thread=True)

    def action_switch_theme(self, theme: str) -> None:
        logger.debug("ACTION_SWITCH_THEME: action started.")
        logger.debug("ACTION_SWITCH_THEME: theme to switch to: %s", theme)
        self.theme = theme
        logger.debug("ACTION_SWITCH_THEME: self.config before modification: %s", self.config)
        self.config["theme"] = theme
        logger.debug("ACTION_SWITCH_THEME: self.config after modification: %s", self.config)
        logger.debug("ACTION_SWITCH_THEME: calling save_config.")
        save_config(self.config)
        logger.debug("ACTION_SWITCH_THEME: action finished.")

    def action_toggle_left_pane(self) -> None:
        """Toggle the left pane."""
        left_pane = self.query_one("#left")
        left_pane.display = not left_pane.display
