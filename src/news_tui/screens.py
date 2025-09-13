from __future__ import annotations

import logging
import webbrowser

from textual.app import ComposeResult
from textual.binding import Binding

logger = logging.getLogger("news")
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.screen import Screen
from textual.worker import Worker, WorkerState
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    LoadingIndicator,
    Static,
)

from .config import load_bookmarks, save_config
from .datamodels import Section, Story
from .sources.cbc import CBCSource
from .themes import THEMES

from textual.widgets import MarkdownViewer


# --- Story screen (separate) ---
class StoryViewScreen(Screen):
    class StoryContentLoaded(Message):
        """Posted when the story content is loaded."""

        def __init__(self, content: dict) -> None:
            self.content = content
            super().__init__()
            logger.debug("StoryContentLoaded message created with content: %s", content)

    BINDINGS = [
        Binding("escape,q,b,left", "app.pop_screen", "Back"),
        Binding("o", "open_in_browser", "Open in browser"),
        Binding("r", "reload_story", "Reload"),
    ]

    def __init__(self, story: Story, source: CBCSource, section: Section):
        super().__init__()
        self.story = story
        self.source = source
        self.section = section
        logger.debug("StoryViewScreen initialized for story: %s", self.story.url)

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
        loading = LoadingIndicator(id="story-loading")
        yield loading
        yield VerticalScroll(MarkdownViewer(id="story-markdown"), id="story-scroll")

    def on_mount(self) -> None:
        self.title = self.story.title
        try:
            self.query_one("#story-loading", LoadingIndicator).display = False
        except Exception as e:
            logger.error("Error hiding loading indicator on mount: %s", e)
        self.load_story()

    def load_story(self) -> None:
        logger.debug("LOAD_STORY: Starting to load story: %s", self.story.url)
        try:
            self.query_one("#story-loading", LoadingIndicator).display = True
            self.query_one("#story-scroll").display = False
            logger.debug("LOAD_STORY: Loading indicator displayed.")
        except Exception as e:
            logger.error("LOAD_STORY: Error managing loading indicators: %s", e)
        self.run_worker(self.fetch_story_content, name="story_loader", thread=True)
        logger.debug("LOAD_STORY: Worker started.")

    def fetch_story_content(self) -> None:
        """Fetch story content in a worker."""
        logger.debug("FETCH_STORY_CONTENT: Worker running for: %s", self.story.url)
        try:
            content = self.source.get_story_content(self.story, self.section)
            logger.debug("FETCH_STORY_CONTENT: Content fetched: %s", content)
            self.post_message(self.StoryContentLoaded(content))
            logger.debug("FETCH_STORY_CONTENT: StoryContentLoaded message posted.")
        except Exception as e:
            logger.exception("FETCH_STORY_CONTENT: Exception while fetching content: %s", e)

    def on_story_content_loaded(self, message: StoryContentLoaded) -> None:
        """Handle StoryContentLoaded message."""
        logger.debug("ON_STORY_CONTENT_LOADED: Message received: %s", message)
        self.query_one("#story-loading", LoadingIndicator).display = False
        self.query_one("#story-scroll").display = True

        result = message.content
        md = self.query_one(MarkdownViewer)

        error_color = "red"
        if self.app.theme in THEMES:
            error_color = THEMES[self.app.theme].error

        logger.debug("ON_STORY_CONTENT_LOADED: Updating markdown view with result: %s", result)
        if isinstance(result, dict) and result.get("ok"):
            content_to_render = result.get("content", "")
            logger.debug("ON_STORY_CONTENT_LOADED: Rendering success content (len: %d)", len(content_to_render))
            md.go(content_to_render)
        else:
            msg = (
                result.get("content", "Unable to load article.")
                if isinstance(result, dict)
                else "Unable to load article."
            )
            logger.error("ON_STORY_CONTENT_LOADED: Rendering failure content: %s", msg)
            md.go(f"[b {error_color}]{msg}[/]")
        logger.debug("ON_STORY_CONTENT_LOADED: Finished updating markdown view.")


    def action_open_in_browser(self) -> None:
        webbrowser.open(self.story.url)

    def on_markdown_viewer_link_clicked(self, event: MarkdownViewer.LinkClicked) -> None:
        """Handle clicks on links in Markdown."""
        self.run_worker(lambda: webbrowser.open(event.href), thread=True)

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


class SettingsScreen(Screen):
    """Screen for app settings."""

    BINDINGS = [
        Binding("escape,q", "app.pop_screen", "Back"),
    ]

    class SectionsLoaded(Message):
        def __init__(self, sections: list[Section]):
            self.sections = sections
            super().__init__()

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
        with Horizontal(id="settings-container"):
            with Vertical(id="settings-left"):
                yield Label("Sections")
                yield ListView(id="sections-list")
            with Vertical(id="settings-right"):
                yield Label("Meta Sections")
                yield Input(placeholder="Meta section name", id="meta-section-name")
                yield Label("Constituent Sections")
                yield ListView(id="meta-sections-constituents")
                yield Button("Create Meta Section", id="create-meta-section")
        yield Button("Save", id="save-settings")

    def on_mount(self) -> None:
        """Load sections and populate lists."""
        self.title = "Settings"
        self.run_worker(self.load_sections, name="load_settings_sections", thread=True)

    def load_sections(self) -> None:
        """Load sections in a worker."""
        all_sections = self.app.source.get_sections()
        self.post_message(self.SectionsLoaded(all_sections))

    def on_settings_screen_sections_loaded(
        self, message: SettingsScreen.SectionsLoaded
    ) -> None:
        sections_list = self.query_one("#sections-list", ListView)
        meta_constituents_list = self.query_one("#meta-sections-constituents", ListView)

        enabled_sections = self.app.config.get("sections", [])
        if not enabled_sections:  # if not configured, enable all by default
            enabled_sections = [s.title for s in message.sections]

        for section in message.sections:
            is_enabled = section.title in enabled_sections
            cb = Checkbox(section.title, is_enabled)
            # monkey patch the section object to the checkbox
            # this is not ideal, but it's a quick way to get it working
            # A better way would be to create a custom widget that holds the section
            setattr(cb, "section", section)
            item = ListItem(cb)
            sections_list.append(item)

            # also populate the list for meta sections
            cb_meta = Checkbox(section.title, False)
            setattr(cb_meta, "section", section)
            item_meta = ListItem(cb_meta)
            meta_constituents_list.append(item_meta)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-settings":
            self.save_settings()
        elif event.button.id == "create-meta-section":
            self.create_meta_section()

    def save_settings(self) -> None:
        # Get selected sections
        sections_list = self.query_one("#sections-list", ListView)
        enabled_sections = []
        for item in sections_list.children:
            checkbox = item.query_one(Checkbox)
            if checkbox.value:
                enabled_sections.append(getattr(checkbox, "section").title)

        # Update config
        config = self.app.config
        config["sections"] = enabled_sections

        save_config(config)
        self.app.notify("Settings saved!")
        self.app.pop_screen()
        # The app should reload sections based on the new config.

    def create_meta_section(self) -> None:
        meta_section_name_input = self.query_one("#meta-section-name")
        meta_section_name = meta_section_name_input.value.strip()
        if not meta_section_name:
            self.app.notify("Meta section name cannot be empty.", severity="error")
            return

        constituents_list = self.query_one("#meta-sections-constituents", ListView)
        selected_sections = []
        for item in constituents_list.children:
            checkbox = item.query_one(Checkbox)
            if checkbox.value:
                selected_sections.append(getattr(checkbox, "section").title)

        if not selected_sections:
            self.app.notify(
                "Select at least one section for the meta section.", severity="error"
            )
            return

        config = self.app.config
        if "meta_sections" not in config:
            config["meta_sections"] = {}
        config["meta_sections"][meta_section_name] = selected_sections
        save_config(config)
        self.app.notify(f"Meta section '{meta_section_name}' created.")
        meta_section_name_input.value = ""
        for item in constituents_list.children:
            item.query_one(Checkbox).value = False
