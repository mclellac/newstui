from __future__ import annotations

from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Checkbox, ListItem, Static
from textual.reactive import reactive

from .datamodels import Section, Story
from .theme_definitions import THEMES


class SectionCheckbox(Checkbox):
    def __init__(self, label: str, value: bool, section: Section):
        super().__init__(label, value)
        self.section = section


# --- UI Widgets ---
class SectionListItem(ListItem):
    def __init__(self, section: Section):
        super().__init__()
        self.section = section

    def compose(self) -> ComposeResult:
        yield Static(self.section.title)


class HeadlineItem(ListItem):
    def __init__(self, story: Story):
        super().__init__()
        self.story = story

    def compose(self) -> ComposeResult:
        with Horizontal(classes="headline-container"):
            yield Static(self.story.section, classes="headline-section")
            yield Static(self.story.flag or "", classes="headline-flag")
            yield Static(self.story.title, classes="headline-title")


class StatusBar(Static):
    theme_name = reactive("default")
    loading_status = reactive("")

    def on_mount(self) -> None:
        self.set_interval(1, self.update_time)
        self.theme_name = self.app.theme or "default"
        self.watch(self.app, "theme", self._on_app_theme_changed)

    def _on_app_theme_changed(self, theme: str) -> None:
        self.theme_name = theme

    def update_time(self) -> None:
        time_str = datetime.now().strftime("%H:%M:%S")
        status_items = [f"Theme: {self.theme_name}", time_str]
        if self.loading_status:
            status_items.append(self.loading_status)

        key_color = "cyan"
        if self.app.theme in THEMES:
            key_color = THEMES[self.app.theme].accent
        status_items.append(f"[b {key_color}]ctrl+l[/] to toggle sections")

        self.update(" | ".join(status_items))

    def watch_theme_name(self, theme_name: str) -> None:
        self.update_time()

    def watch_loading_status(self, loading_status: str) -> None:
        self.update_time()
