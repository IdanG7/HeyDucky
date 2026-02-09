# voice_debugger/widgets/conversation.py
"""Conversation view widget for chat display."""

from __future__ import annotations

from textual.widgets import RichLog
from rich.text import Text


class ConversationView(RichLog):
    """Scrollable conversation view showing user/AI messages."""

    DEFAULT_CSS = """
    ConversationView {
        height: 1fr;
        border: solid $accent;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(markup=True, wrap=True, **kwargs)

    def add_user_message(self, text: str) -> None:
        """Add a user message to the conversation."""
        msg = Text()
        msg.append("You: ", style="bold cyan")
        msg.append(text)
        self.write(msg)

    def add_ai_message(self, text: str) -> None:
        """Add an AI response to the conversation."""
        msg = Text()
        msg.append("AI: ", style="bold green")
        msg.append(text)
        self.write(msg)

    def add_system_message(self, text: str) -> None:
        """Add a system/status message."""
        msg = Text()
        msg.append(text, style="dim italic")
        self.write(msg)

    def add_tool_message(self, tool_name: str, args: dict) -> None:
        """Show a tool call (stubbed for now)."""
        msg = Text()
        msg.append(f"  [tool] {tool_name}", style="yellow")
        if args:
            msg.append(f"({args})", style="dim yellow")
        self.write(msg)
