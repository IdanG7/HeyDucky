# heyducky/widgets/debug_output.py
"""Debug output panel showing program stdout/stderr."""

from __future__ import annotations

from textual.widgets import RichLog
from rich.text import Text


class DebugOutputView(RichLog):
    """Displays program output from the debug session."""

    DEFAULT_CSS = """
    DebugOutputView {
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
            "[bold]Live Program Output[/bold]\n\n"
            "[dim]Everything your program prints shows up here in real time.\n\n"
            "  [white]Normal output[/white]\n"
            "  [red]Errors and warnings[/red]\n\n"
            "Run: [bold]ducky my_script.py[/bold]\n"
            "Then ask me about anything you see.[/dim]"
        ))

    def add_stdout(self, text: str) -> None:
        """Add program stdout."""
        self.write(Text(text))

    def add_stderr(self, text: str) -> None:
        """Add program stderr."""
        self.write(Text(text, style="red"))
