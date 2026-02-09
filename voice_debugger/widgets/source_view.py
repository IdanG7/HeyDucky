# voice_debugger/widgets/source_view.py
"""Source code view widget (placeholder for Milestone 1)."""

from textual.widgets import Static


class SourceView(Static):
    """Displays source code. Placeholder until debugger integration."""

    DEFAULT_CSS = """
    SourceView {
        height: 40%;
        border: solid $primary;
        padding: 1 2;
        color: $text-muted;
    }
    """

    def __init__(self, **kwargs):
        super().__init__("No file loaded. Start a debug session to view source.", **kwargs)
