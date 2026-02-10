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

    def on_mount(self) -> None:
        """Show initial hints."""
        self.write(Text.from_markup(
            "[bold]Hey! I'm your debugging partner.[/bold]\n\n"
            "[dim]Press [bold]Space[/bold] and talk to me like a colleague.\n\n"
            "Try saying:\n"
            "  \"What's this function doing?\"\n"
            "  \"Set a breakpoint on line 42\"\n"
            "  \"Show me the git diff\"\n"
            "  \"Step into that call\"\n\n"
            "I can read your code, run git commands, and\n"
            "control the debugger — all by voice.[/dim]\n"
        ))

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
        """Show a tool call with special formatting for conditional breakpoints."""
        msg = Text()
        if tool_name == "set_breakpoint" and args.get("condition"):
            msg.append("  breakpoint ", style="yellow")
            msg.append(f"{args.get('file', '?')}:{args.get('line', '?')}", style="bold yellow")
            msg.append(" when ", style="yellow")
            msg.append(f"{args['condition']}", style="bold magenta")
        else:
            msg.append(f"  [tool] {tool_name}", style="yellow")
            if args:
                msg.append(f"({args})", style="dim yellow")
        self.write(msg)

    def start_ai_stream(self) -> None:
        """Begin streaming an AI response.

        Writes the "AI: " prefix and initializes the stream buffer.
        Subsequent calls to append_ai_chunk() add text incrementally.
        """
        self._stream_buffer = ""
        self._stream_line_index = len(self.lines)
        prefix = Text()
        prefix.append("AI: ", style="bold green")
        self.write(prefix)

    def append_ai_chunk(self, text: str) -> None:
        """Append a text chunk to the current streaming AI response.

        Each chunk is written as a new line entry in the RichLog.
        This provides a simple, correct v1 streaming display.
        """
        self._stream_buffer += text
        if text:
            chunk = Text(text, style="")
            self.write(chunk)

    def finish_ai_stream(self) -> str:
        """Finish the streaming AI response.

        Returns the full accumulated text buffer.
        """
        full_text = getattr(self, "_stream_buffer", "")
        self._stream_buffer = ""
        self._stream_line_index = 0
        return full_text
