# heyducky/widgets/source_view.py
"""Source code view with syntax highlighting and debug markers."""

from __future__ import annotations

from pathlib import Path

from textual.reactive import reactive
from textual.widgets import RichLog
from rich.text import Text


class SourceView(RichLog):
    """Displays source code with syntax highlighting, breakpoints, and current line."""

    DEFAULT_CSS = """
    SourceView {
        height: 1fr;
        border: solid $primary;
    }

    SourceView:focus {
        border: solid $accent;
    }
    """

    current_line = reactive(0)

    def __init__(self, **kwargs):
        super().__init__(markup=True, wrap=False, **kwargs)
        self.file_path: str | None = None
        self._source_lines: list[str] = []
        self._source_text: str = ""
        self.breakpoint_lines: set[int] = set()

    def on_mount(self) -> None:
        """Show initial hints."""
        self._refresh_display()

    def load_source(self, file_path: str, content: str | None = None) -> None:
        """Load a source file for display."""
        self.file_path = file_path
        if content is None:
            try:
                content = Path(file_path).read_text()
            except OSError:
                content = f"# Could not read {file_path}"
        self._source_text = content
        self._source_lines = content.split("\n")
        self._refresh_display()

    def set_current_line(self, line: int) -> None:
        """Set the current execution line."""
        self.current_line = line
        self._refresh_display()

    def toggle_breakpoint(self, line: int) -> None:
        """Toggle a breakpoint on a line."""
        if line in self.breakpoint_lines:
            self.breakpoint_lines.discard(line)
        else:
            self.breakpoint_lines.add(line)
        self._refresh_display()

    def _refresh_display(self) -> None:
        """Re-render the source display."""
        self.clear()
        if not self._source_text or not self.file_path:
            self.write(Text.from_markup(
                "[bold]Your Code, Annotated Live[/bold]\n\n"
                "[dim]I'll highlight exactly where your program is and what's\n"
                "happening — breakpoints, current line, everything.\n\n"
                "Pick a file from the tree, or just start debugging\n"
                "and I'll open the right file automatically.\n\n"
                "  [cyan]\u25cf[/cyan]  Breakpoint    [yellow]\u2192[/yellow]  You are here\n\n"
                "Quick keys:\n"
                "  [bold]t[/bold]  Jump between tree & source\n"
                "  [bold]o[/bold]  Switch project\n"
                "  [bold]F5[/bold] Continue  [bold]F10[/bold] Step over  [bold]F11[/bold] Step in[/dim]"
            ))
            return

        # Add file header
        header = Text()
        header.append(f" {Path(self.file_path).name} ", style="bold reverse")
        header.append(f"  {self.file_path}", style="dim")
        self.write(header)
        self.write(Text(""))  # blank separator line

        # Build annotated source with gutter
        for i, line in enumerate(self._source_lines, 1):
            text = Text()
            if i in self.breakpoint_lines:
                text.append("\u25cf ", style="cyan bold")
            else:
                text.append("  ")
            if i == self.current_line:
                text.append("\u2192", style="yellow bold")
            else:
                text.append(" ")
            text.append(f" {i:4d} \u2502 ", style="dim")
            text.append(line)
            self.write(text)
