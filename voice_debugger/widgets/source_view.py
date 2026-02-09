# voice_debugger/widgets/source_view.py
"""Source code view with syntax highlighting and debug markers."""

from __future__ import annotations

from pathlib import Path

from textual.reactive import reactive
from textual.widgets import Static


class SourceView(Static):
    """Displays source code with syntax highlighting, breakpoints, and current line."""

    DEFAULT_CSS = """
    SourceView {
        height: 1fr;
        border: solid $primary;
        overflow-y: auto;
    }
    """

    current_line = reactive(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.file_path: str | None = None
        self._source_lines: list[str] = []
        self._source_text: str = ""
        self.breakpoint_lines: set[int] = set()

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
        if not self._source_text or not self.file_path:
            self.update("No file loaded. Start a debug session to view source.")
            return

        # Build annotated source with gutter
        lines: list[str] = []
        for i, line in enumerate(self._source_lines, 1):
            bp = "\u25cf " if i in self.breakpoint_lines else "  "
            arrow = "\u2192" if i == self.current_line else " "
            lines.append(f"{bp}{arrow} {i:4d} | {line}")

        self.update("\n".join(lines))
