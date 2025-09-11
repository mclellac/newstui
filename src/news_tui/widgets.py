from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import ListItem, Static

from .datamodels import Section, Story


# --- UI Widgets ---
class SectionListItem(ListItem):
    def __init__(self, section: Section):
        super().__init__()
        self.section = section

    def compose(self) -> ComposeResult:
        yield Static(self.section.title)


class StoryListItem(ListItem):
    def __init__(self, story: Story):
        super().__init__()
        self.story = story

    def compose(self) -> ComposeResult:
        text = self.story.title
        if self.story.flag:
            text = f"[b]{self.story.flag}[/] — {text}"
        yield Static(text)
