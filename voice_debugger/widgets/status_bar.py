# voice_debugger/widgets/status_bar.py
"""Status bar widget showing mic state, provider, and cost."""

from __future__ import annotations

from textual.widgets import Static
from textual.reactive import reactive


class VoiceStatusBar(Static):
    """Status bar showing recording state, AI provider, and session cost."""

    DEFAULT_CSS = """
    VoiceStatusBar {
        height: 3;
        background: $boost;
        padding: 0 2;
        content-align: left middle;
    }
    """

    is_recording = reactive(False)
    provider_name = reactive("Claude")
    session_cost = reactive(0.0)

    def render(self) -> str:
        mic = "[bold red]Recording...[/]" if self.is_recording else "[dim]Press Space to talk[/]"
        cost = f"${self.session_cost:.4f}"
        return f"{mic}  |  Provider: {self.provider_name}  |  Cost: {cost}"
