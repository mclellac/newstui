from __future__ import annotations

from typing import Any, Optional, List

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.command import CommandPalette, Hit, Hits, Provider
from textual.containers import Horizontal, Vertical
from textual.message import Message
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

from .config import (
    HOME_PAGE_URL,
    load_config,
    load_read_articles,
    load_bookmarks,
    save_bookmarks,
    save_read_articles,
    ensure_themes_are_copied,
    load_themes,
    UI_DEFAULTS,
)
from dataclasses import asdict
from .datamodels import Section, Story
from .sources.manager import SourceManager
from .screens import BookmarksScreen, SettingsScreen, StoryViewScreen, ErrorScreen
from .widgets import HeadlineItem, SectionListItem, StatusBar, ErrorMessage


class ThemeProvider(Provider):
    async def search(self, query: str) -> Hits:
        """Search for a theme."""
        matcher = self.matcher(query)

        for theme_name in self.app.themes:
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
        Binding("/", "focus_filter", "Search"),
    ]

    def __init__(
        self,
        theme: Optional[str] = None,
        config: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.current_section: Optional[Section] = None
        self._theme_name = theme or "dracula"
        self.stories: List[Story] = []
        self.read_articles: set[str] = set()
        self.bookmarks: List[dict] = []
        self.config = config or {}
        self.source_manager = SourceManager(self.config)
        sources = self.source_manager.get_all_sources()
        self.source = sources[0] if sources else None
        self.meta_sections = self.config.get("meta_sections", {})
        self.sections: List[Section] = []

    @property
    def theme_name(self) -> str:
        return self._theme_name

    def get_keybinding_style(self) -> str:
        """Return the appropriate keybinding style for the current theme."""
        if self.theme_name.startswith("cbc-"):
            return "white"
        return "$accent"

    def apply_theme_styles(self, screen) -> None:
        """Apply theme-specific styles to a screen."""
        is_cbc = self.theme_name.startswith("cbc-")
        try:
            header = screen.query_one(Header)
            header.set_class(is_cbc, "cbc-header")
        except Exception:
            pass  # Not all screens have a header

        try:
            # The main app screen has a StatusBar, others have a Footer.
            footer = screen.query_one(StatusBar)
            footer.set_class(is_cbc, "cbc-footer")
        except Exception:
            try:
                footer = screen.query_one(Footer)
                footer.set_class(is_cbc, "cbc-footer")
            except Exception:
                pass  # Not all screens have a footer



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
                yield Input(placeholder="Filter headlines...", id="headline-filter")
                yield ListView(id="headlines-list")
        yield StatusBar()

    def on_mount(self) -> None:
        ensure_themes_are_copied()
        self.read_articles = load_read_articles()
        self.bookmarks = load_bookmarks()
        self.screen.bindings = self.BINDINGS

        # Register all themes
        self.themes = load_themes()
        for name, theme in self.themes.items():
            self.register_theme(theme)

        self.theme = self._theme_name
        self.apply_theme_styles(self.screen)

        if not self.source:
            self.push_screen(
                ErrorScreen(
                    "No news sources configured",
                    "Please configure a news source in `~/.config/news/config.json`.",
                )
            )
            return

        # Start loading sections on mount
        self.run_worker(self.source.get_sections, name="sections_loader", thread=True)
        # focus sections list if possible
        try:
            self.query_one("#sections-list").focus()
        except Exception:
            pass

        # Configure the headlines list
        self.query_one("#headlines-list", ListView).cursor_type = "row"

        keybindings_text = self.config.get("ui", {}).get(
            "statusbar_keybindings", UI_DEFAULTS["statusbar_keybindings"]
        )
        self.query_one(StatusBar).set_keybindings(
            keybindings_text.format(color=self.get_keybinding_style())
        )

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
        self.sections = getattr(event.worker, "result", None) or [
            Section("Home", HOME_PAGE_URL)
        ]

        # Filter sections based on config
        enabled_sections = self.config.get("sections")
        if enabled_sections:
            self.sections = [s for s in self.sections if s.title in enabled_sections]

        all_sections_with_meta = self.sections.copy()
        for meta_section_name in self.meta_sections:
            all_sections_with_meta.insert(
                0, Section(title=meta_section_name, url="meta:" + meta_section_name)
            )

        for sec in all_sections_with_meta:
            view.append(SectionListItem(sec))
        if all_sections_with_meta:
            self.current_section = all_sections_with_meta[0]
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

        error = getattr(event.worker, "error", None)
        if error:
            logger.error("Headlines worker failed: %s", error)
            headlines_list.mount(ErrorMessage(f"Failed to load headlines: {error}"))
        else:
            logger.error("Headlines worker failed with no specific error.")
            headlines_list.mount(ErrorMessage("Failed to load headlines."))

        headlines_list.display = True

    def _update_headlines_list(self, stories: List[Story]) -> None:
        """Sorts stories by read status and updates the headlines list."""
        # Sort stories by read status (unread first)
        sorted_stories = sorted(stories, key=lambda s: s.read)

        headlines_list = self.query_one("#headlines-list", ListView)
        headlines_list.clear()

        if not sorted_stories:
            headlines_list.display = False
            return

        for s in sorted_stories:
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
        stories = getattr(event.worker, "result", None) or []
        bookmarked_urls = {b["url"] for b in self.bookmarks}
        for s in stories:
            s.read = s.url in self.read_articles
            s.bookmarked = s.url in bookmarked_urls
        self.stories = stories
        self._update_headlines_list(self.stories)

    def _initiate_headline_load(self, story_loader_callable, title: str) -> None:
        """Shared logic to start loading headlines."""
        self.query_one(StatusBar).loading_status = f"Loading {title}..."
        self.query_one(Input).value = ""
        headlines_list = self.query_one("#headlines-list", ListView)
        headlines_list.clear()
        headlines_list.mount(LoadingIndicator())
        self.run_worker(
            story_loader_callable,
            name="headlines_loader",
            thread=True,
        )

    def _load_headlines_for_section(self, section: Section) -> None:
        if not section:
            return

        if section.url.startswith("meta:"):
            self._load_headlines_for_meta_section(section)
            return

        self._initiate_headline_load(lambda: self.source.get_stories(section), section.title)

    def _load_headlines_for_meta_section(self, section: Section) -> None:
        meta_section_name = section.url.replace("meta:", "")
        section_names = self.meta_sections.get(meta_section_name, [])
        if not section_names:
            return

        def _get_stories():
            all_stories = []
            seen_urls = set()
            for section_name in section_names:
                for s in self.sections:
                    if s.title == section_name:
                        stories = self.source.get_stories(s)
                        for story in stories:
                            if story.url not in seen_urls:
                                all_stories.append(story)
                                seen_urls.add(story.url)
            return all_stories

        self._initiate_headline_load(_get_stories, section.title)

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
        self.push_screen(StoryViewScreen(story, self.source))

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
        if event.input.id == "headline-filter":
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

    def on_input_blur(self, event: Input.Blur) -> None:
        if event.input.id == "headline-filter":
            if not event.input.value:
                event.input.display = False

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "headline-filter":
            if not event.input.value:
                event.input.display = False

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
        """Switch to a new theme."""
        self.theme = theme

    def watch_theme(self, old_theme: str, new_theme: str) -> None:
        """Apply theme-specific styles."""
        if hasattr(self, "screens"):
            for screen in self.screens.values():
                self.apply_theme_styles(screen)

    def action_toggle_left_pane(self) -> None:
        """Toggle the left pane."""
        left_pane = self.query_one("#left")
        left_pane.display = not left_pane.display

    def action_focus_filter(self) -> None:
        """Focus the filter input."""
        filter_input = self.query_one("#headline-filter")
        filter_input.display = True
        filter_input.focus()
