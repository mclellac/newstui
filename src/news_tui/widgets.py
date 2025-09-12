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
        status_items = [f"Theme: {self.theme_name}", time_str]
        if self.loading_status:
            status_items.append(self.loading_status)

        bindings = self.app.screen.bindings
        shown_bindings = [b for b in bindings.values() if b.show]
        bindings_text = " | ".join(
            f"[b cyan]{b.key}[/] {b.description}" for b in shown_bindings
        )
        status_items.append(bindings_text)

        self.update(" | ".join(status_items))

    def watch_theme_name(self, theme_name: str) -> None:
        self.update_time()

    def watch_loading_status(self, loading_status: str) -> None:
        self.update_time()
