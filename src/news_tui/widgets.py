from __future__ import annotations

from datetime import datetime

from textual.app import ComposeResult
from textual.widgets import ListItem, Static
from textual.reactive import reactive

from .datamodels import Section


# --- UI Widgets ---
class SectionListItem(ListItem):
    def __init__(self, section: Section):
        super().__init__()
        self.section = section

    def compose(self) -> ComposeResult:
        yield Static(self.section.title)


class StatusBar(Static):
    theme_name = reactive("default")
    loading_status = reactive("")

    def on_mount(self) -> None:
        self.set_interval(1, self.update_time)

    def update_time(self) -> None:
        time_str = datetime.now().strftime("%H:%M:%S")
        status = f"Theme: {self.theme_name} | {time_str}"
        if self.loading_status:
            status = f"{status} | {self.loading_status}"
        self.update(status)

    def watch_theme_name(self, theme_name: str) -> None:
        self.update_time()

    def watch_loading_status(self, loading_status: str) -> None:
        self.update_time()
