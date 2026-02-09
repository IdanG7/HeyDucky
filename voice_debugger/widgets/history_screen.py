# voice_debugger/widgets/history_screen.py
"""Modal screen for browsing chat history with date grouping and search."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, OptionList
from textual.widgets.option_list import Option

from voice_debugger.chat_history import ChatHistory


class HistoryScreen(ModalScreen[Path | None]):
    """Modal screen showing past chat sessions grouped by date with search.

    Returns the path of the selected session, or None if cancelled.
    """

    DEFAULT_CSS = """
    HistoryScreen {
        align: center middle;
    }

    #history-container {
        width: 70;
        height: 80%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }

    #history-title {
        text-align: center;
        text-style: bold;
        width: 100%;
        margin-bottom: 1;
    }

    #history-search {
        margin-bottom: 1;
    }

    #history-hint {
        text-align: center;
        color: $text-muted;
        width: 100%;
        margin-bottom: 1;
    }

    #history-list {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Close", show=True),
        Binding("enter", "select_session", "Open", show=True),
    ]

    def __init__(self, chat_history: ChatHistory):
        super().__init__()
        self._chat_history = chat_history
        self._sessions: list[dict] = []
        self._filtered_sessions: list[dict] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="history-container"):
            yield Label("Chat History", id="history-title")
            yield Input(placeholder="Search conversations...", id="history-search")
            yield Label(
                "Enter=open  Escape=close",
                id="history-hint",
            )
            yield OptionList(id="history-list")

    def on_mount(self) -> None:
        self._sessions = self._chat_history.list_sessions()
        self._filtered_sessions = list(self._sessions)
        self._rebuild_list()
        try:
            self.query_one("#history-search", Input).focus()
        except Exception:
            pass

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter sessions as user types in search."""
        query = event.value.strip()
        if query:
            self._filtered_sessions = self._chat_history.search_sessions(query)
        else:
            self._filtered_sessions = list(self._sessions)
        self._rebuild_list()

    def _rebuild_list(self) -> None:
        """Rebuild the option list with date-grouped sessions."""
        option_list = self.query_one("#history-list", OptionList)
        option_list.clear_options()

        if not self._filtered_sessions:
            option_list.add_option(
                Option("No conversations found.", id="empty", disabled=True)
            )
            return

        groups = self._group_by_date(self._filtered_sessions)
        first_group = True
        for group_name, sessions in groups.items():
            if not first_group:
                option_list.add_option(None)
            first_group = False
            option_list.add_option(Separator())
            option_list.add_option(Option(f"  {group_name}", disabled=True))
            option_list.add_option(Separator())

            for s in sessions:
                created = (
                    s["created"][:16].replace("T", " ") if s["created"] else "?"
                )
                count = s["message_count"]
                preview = s["preview"][:45]
                label = f"  {created}  ({count} msgs)  {preview}"
                option_list.add_option(Option(label, id=s["session_id"]))

    def _group_by_date(self, sessions: list[dict]) -> dict[str, list[dict]]:
        """Group sessions into date buckets."""
        now = datetime.now(timezone.utc)
        today = now.date()
        yesterday = today - timedelta(days=1)
        week_ago = today - timedelta(days=7)

        groups: dict[str, list[dict]] = {}
        for s in sessions:
            created = s.get("created", "")
            try:
                dt = datetime.fromisoformat(created).date()
            except (ValueError, TypeError):
                groups.setdefault("Older", []).append(s)
                continue

            if dt == today:
                groups.setdefault("Today", []).append(s)
            elif dt == yesterday:
                groups.setdefault("Yesterday", []).append(s)
            elif dt >= week_ago:
                groups.setdefault("This Week", []).append(s)
            else:
                groups.setdefault("Older", []).append(s)

        ordered = {}
        for key in ["Today", "Yesterday", "This Week", "Older"]:
            if key in groups:
                ordered[key] = groups[key]
        return ordered

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        """User double-clicked or pressed Enter on a session."""
        option_id = event.option_id
        if option_id and option_id != "empty":
            self._dismiss_session(option_id)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_select_session(self) -> None:
        """Select the highlighted session."""
        try:
            option_list = self.query_one("#history-list", OptionList)
            idx = option_list.highlighted
            if idx is not None:
                option = option_list.get_option_at_index(idx)
                if option.id and option.id != "empty" and not option.disabled:
                    self._dismiss_session(option.id)
        except Exception:
            pass

    def _dismiss_session(self, session_id: str) -> None:
        """Find and dismiss with the session path."""
        for s in self._sessions:
            if s["session_id"] == session_id:
                self.dismiss(s["path"])
                return
