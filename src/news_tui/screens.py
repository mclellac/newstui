from __future__ import annotations

import webbrowser

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
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

    def __init__(self, story: Story, source: CBCSource, section: Section):
        super().__init__()
        self.story = story
        self.source = source
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
            lambda: self.source.get_story_content(self.story, self.section),
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
        with VerticalScroll(id="settings"):
            yield Label("Sections")
            yield ListView(id="sections-list")

            yield Label("Meta Sections")
            yield Input(placeholder="Meta section name", id="meta-section-name")
            yield Label("Constituent Sections")
            yield ListView(id="meta-sections-constituents")
            yield Button("Create Meta Section", id="create-meta-section")

            yield Button("Save", id="save-settings")

    def on_mount(self) -> None:
        """Load sections and populate lists."""
        self.title = "Settings"
        self.run_worker(self.load_sections, name="load_settings_sections")

    async def load_sections(self) -> None:
        """Load sections in a worker."""
        all_sections = await self.app.run_in_executor(
            None, self.app.source.get_sections
        )
        self.post_message(self.SectionsLoaded(all_sections))

    async def on_settings_screen_sections_loaded(
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
