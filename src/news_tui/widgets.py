from __future__ import annotations

from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Checkbox, ListItem, Static
from textual.reactive import reactive
from rich.text import Text

from .datamodels import Section, Story


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
    loading_status = reactive("")
    keybinding_hint = reactive("")

    def on_mount(self) -> None:
        self.update_display()

    def set_keybindings(self, hint: str) -> None:
        """Set the keybinding hint text."""
        self.keybinding_hint = hint

    def update_display(self) -> None:
        """Update the status bar display."""
        status_items = []
        if self.loading_status:
            status_items.append(self.loading_status)

        if self.keybinding_hint:
            status_items.append(self.keybinding_hint)

        self.update(" | ".join(status_items))

    def watch_loading_status(self, loading_status: str) -> None:
        self.update_display()

    def watch_keybinding_hint(self, keybinding_hint: str) -> None:
        self.update_display()


class ErrorMessage(Static):
    def __init__(self, message: str):
        super().__init__(Text(message, style="bold red"))
