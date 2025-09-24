from __future__ import annotations

import webbrowser

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.screen import Screen
from textual.worker import Worker, WorkerState
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    LoadingIndicator,
    Markdown,
    Select,
    Static,
    TabbedContent,
    TabPane,
)

import os
from .config import (
    CONFIG_PATH,
    load_bookmarks,
    save_bookmarks,
    save_config,
    logger,
    load_themes,
)
from .datamodels import Section, Story
from .sources.base import Source
from .widgets import SectionCheckbox, StatusBar

# Markdown & scroll fallbacks for different Textual versions
MarkdownWidget = Markdown

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
        Binding("down", "scroll_down", "Scroll Down"),
        Binding("up", "scroll_up", "Scroll Up"),
    ]

    def __init__(self, story: Story, source: Source):
        super().__init__()
        self.story = story
        self.source = source

    def compose(self) -> ComposeResult:
        yield Header()
        yield StatusBar()
        # loading indicator and scrollable Markdown
        loading = LoadingIndicator(id="story-loading")
        yield loading
        yield VerticalScroll(
            MarkdownWidget("", id="story-markdown"),
            id="story-scroll",
        )

    def on_mount(self) -> None:
        self.title = self.story.title
        # hide loading until the worker runs
        try:
            self.query_one("#story-loading", LoadingIndicator).display = False
        except Exception:
            pass
        self.query_one("#story-scroll").focus()
        self.load_story()
        self.app.apply_theme_styles(self)

        keybinding_style = self.app.get_keybinding_style()
        self.query_one(StatusBar).set_keybindings(
            f"[b {keybinding_style}]up/down[/] to scroll, [b {keybinding_style}]o[/] to open"
        )

    def load_story(self) -> None:
        try:
            self.query_one("#story-loading", LoadingIndicator).display = True
            self.query_one("#story-scroll").display = False
        except Exception:
            pass
        # fetch in worker thread
        self.run_worker(
            lambda: self.source.get_story_content(self.story),
            name="story_loader",
            thread=True,
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
                content = result.get("content", "")
                md.update(content)
                word_count = len(content.split())
                time_to_read = max(1, round(word_count / 200))
                self.sub_title = f"~{time_to_read} min read"
            else:
                msg = (
                    result.get("content", "Unable to load article.")
                    if isinstance(result, dict)
                    else "Unable to load article."
                )
                md.styles.color = "$error"
                md.update(f"[b]{msg}[/b]")
        else:
            # worker not SUCCESS; if it's not running/pending treat as failure
            if event.state not in (WorkerState.PENDING, WorkerState.RUNNING):
                try:
                    self.query_one("#story-loading", LoadingIndicator).display = False
                    self.query_one("#story-scroll").display = True
                    md = self.query_one("#story-markdown")
                    md.styles.color = "$error"
                    error = getattr(event.worker, "error", None)
                    if error:
                        logger.error("Story loader worker failed: %s", error)
                        md.update(f"[b]Unable to load article: {error}[/b]")
                    else:
                        logger.error("Story loader worker failed with no specific error.")
                        md.update("[b]Unable to load article[/b]")
                except Exception:
                    pass

    def action_open_in_browser(self) -> None:
        webbrowser.open(self.story.url)

    def action_reload_story(self) -> None:
        self.load_story()

    def action_scroll_down(self) -> None:
        self.query_one("#story-scroll").scroll_down()

    def action_scroll_up(self) -> None:
        self.query_one("#story-scroll").scroll_up()


class ErrorScreen(Screen):
    def __init__(self, title: str, message: str):
        super().__init__()
        self.title = title
        self.message = message

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(self.title, classes="error-title")
        yield Markdown(self.message)
        yield Footer()

    def on_mount(self) -> None:
        self.bind("q", "quit", "Quit")


class BookmarksScreen(Screen):
    BINDINGS = [
        Binding("escape,q,b,left", "app.pop_screen", "Back"),
        Binding("d", "delete_bookmark", "Delete"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
        yield DataTable(id="bookmarks-table")

    def on_mount(self) -> None:
        self.title = "Bookmarks"
        self.bookmarks = load_bookmarks()
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        table.add_column("Title", key="title")
        for bookmark in self.bookmarks:
            table.add_row(bookmark["title"], key=bookmark["url"])
        self.app.apply_theme_styles(self)

    def action_delete_bookmark(self) -> None:
        """Delete the selected bookmark."""
        table = self.query_one(DataTable)
        if not table.is_valid_row_index(table.cursor_row):
            return

        row_key = table.get_row_key(table.cursor_row)
        url_to_delete = str(row_key.value)

        # Remove the bookmark from the list
        self.bookmarks = [b for b in self.bookmarks if b["url"] != url_to_delete]

        # Save the updated bookmarks list
        save_bookmarks(self.bookmarks)

        # Remove the row from the table
        table.remove_row_at(table.cursor_row)

        self.app.notify("Bookmark deleted.")


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
        with TabbedContent(id="settings-tabs"):
            with TabPane("Sections", id="sections-tab"):
                yield ListView(id="sections-list")
            with TabPane("Meta Sections", id="meta-sections-tab"):
                with Vertical():
                    yield Label("Meta Section Name", classes="settings-label")
                    yield Input(placeholder="e.g. My Awesome Feed", id="meta-section-name")
                    yield Label("Constituent Sections", classes="settings-label")
                    yield ListView(id="meta-sections-constituents")
                    yield Button(
                        "Create Meta Section",
                        id="create-meta-section",
                        classes="settings-button",
                    )
            with TabPane("Theme", id="theme-tab"):
                yield Select([], id="theme-select", prompt="Select a theme")
            with TabPane("Layout", id="layout-tab"):
                yield Select(
                    [("Default", "default"), ("Compact", "compact")],
                    id="layout-select",
                    prompt="Select an article list layout",
                )
        yield Button("Save", id="save-settings", classes="settings-button")

    def on_mount(self) -> None:
        """Load sections and populate lists."""
        self.title = "Settings"
        self.run_worker(self.load_sections, name="load_settings_sections", thread=True)

        # Set theme selector
        theme_select = self.query_one("#theme-select", Select)
        themes = load_themes()
        theme_select.set_options([(theme, theme) for theme in themes.keys()])
        if self.app.theme_name in themes:
            theme_select.value = self.app.theme_name
        else:
            theme_select.clear()

        # Set layout selector
        layout_select = self.query_one("#layout-select", Select)
        layout_select.value = self.app.config.get("layout", "default")
        self.app.apply_theme_styles(self)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "meta-section-name":
            constituents_list = self.query_one("#meta-sections-constituents", ListView)
            if event.value:
                constituents_list.add_class("highlight-list")
            else:
                constituents_list.remove_class("highlight-list")

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "theme-select":
            self.app.theme = event.value

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
            cb = SectionCheckbox(section.title, is_enabled, section=section)
            item = ListItem(cb)
            sections_list.append(item)

            # also populate the list for meta sections
            cb_meta = SectionCheckbox(section.title, False, section=section)
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
            checkbox = item.query_one(SectionCheckbox)
            if checkbox.value:
                enabled_sections.append(checkbox.section.title)

        # Get selected theme
        theme_select = self.query_one("#theme-select", Select)
        selected_theme = theme_select.value
        if selected_theme is Select.BLANK:
            selected_theme = None

        # Get selected layout
        layout_select = self.query_one("#layout-select", Select)
        selected_layout = layout_select.value

        # Update config
        config = self.app.config
        config["sections"] = enabled_sections
        config["theme"] = selected_theme
        config["layout"] = selected_layout

        save_config(config)
        self.app.notify("Settings saved!")

        # Visual feedback for save
        save_button = self.query_one("#save-settings", Button)
        save_button.add_class("saved")
        self.app.set_timer(2, lambda: save_button.remove_class("saved"))

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
            checkbox = item.query_one(SectionCheckbox)
            if checkbox.value:
                selected_sections.append(checkbox.section.title)

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
        for checkbox in constituents_list.query(SectionCheckbox):
            checkbox.value = False
