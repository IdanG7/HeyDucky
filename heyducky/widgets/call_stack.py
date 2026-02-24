# heyducky/widgets/call_stack.py
"""Call stack panel showing stack frames."""

from __future__ import annotations

from textual.widgets import RichLog
from rich.text import Text


class CallStackView(RichLog):
    """Displays the current call stack."""

    DEFAULT_CSS = """
    CallStackView {
        height: 1fr;
        border: solid $primary;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(markup=True, wrap=True, **kwargs)

    def on_mount(self) -> None:
        """Show initial hints."""
        self.write(Text.from_markup(
            "[bold]How Did We Get Here?[/bold]\n\n"
            "[dim]I'll trace the path your code took to reach this point —\n"
            "every function call, file, and line number.\n\n"
            "  [bold]\u25b6[/bold] current_function  [dim]file.py:42[/dim]\n"
            "    called_from       [dim]main.py:10[/dim]\n\n"
            "Ask me:\n"
            "  \"Where am I right now?\"\n"
            "  \"How did I get to this function?\"[/dim]"
        ))

    def update_frames(self, frames: list[dict]) -> None:
        """Update the displayed stack frames.

        Args:
            frames: List of dicts with keys: name, source (path), line.
        """
        self.clear()
        if not frames:
            self.write(Text("No stack frames.", style="dim italic"))
            return
        for i, frame in enumerate(frames):
            line = Text()
            marker = "\u25b6 " if i == 0 else "  "
            style = "bold" if i == 0 else ""
            name = frame.get("name", "?")
            source = frame.get("source", {})
            path = source.get("path", "?") if isinstance(source, dict) else str(source)
            lineno = frame.get("line", "?")
            line.append(f"{marker}{name}", style=style)
            line.append(f"  {path}:{lineno}", style="dim")
            self.write(line)
