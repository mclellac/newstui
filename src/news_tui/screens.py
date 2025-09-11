from __future__ import annotations

import webbrowser

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.worker import Worker, WorkerState
from textual.widgets import Footer, Header, LoadingIndicator, Static

from .datamodels import Story
from .fetcher import get_story_content

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

    def __init__(self, story: Story):
        super().__init__()
        self.story = story

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
        self._toggle_loading(False)
        self.load_story()

    def load_story(self) -> None:
        self._toggle_loading(True)
        # fetch in worker thread
        self.run_worker(
            lambda: get_story_content(self.story.url), name="story_loader", thread=True
        )

    def _toggle_loading(self, loading: bool) -> None:
        try:
            self.query_one("#story-loading", LoadingIndicator).display = loading
            self.query_one("#story-scroll").display = not loading
        except NoMatches:
            pass

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if getattr(event.worker, "name", None) != "story_loader":
            return

        # Stop loading when worker is done
        if event.state not in (WorkerState.PENDING, WorkerState.RUNNING):
            self._toggle_loading(False)

        if event.state is WorkerState.SUCCESS:
            result = getattr(event.worker, "result", None) or {
                "ok": False,
                "content": "No content",
            }
            try:
                md = self.query_one("#story-markdown")
                if isinstance(result, dict) and result.get("ok"):
                    md.update(result.get("content", ""))
                else:
                    msg = (
                        result.get("content", "Unable to load article.")
                        if isinstance(result, dict)
                        else "Unable to load article."
                    )
                    md.update(f"[b red]{msg}[/]")
            except NoMatches:
                pass  # Should not happen
        elif event.state is WorkerState.ERROR:
            try:
                md = self.query_one("#story-markdown")
                md.update("[b red]Unable to load article[/]")
            except NoMatches:
                pass  # Should not happen

    def action_open_in_browser(self) -> None:
        webbrowser.open(self.story.url)

    def action_reload_story(self) -> None:
        self.load_story()
