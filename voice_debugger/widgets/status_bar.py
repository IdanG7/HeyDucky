# voice_debugger/widgets/status_bar.py
"""Status bar widget showing mic state, debug state, provider, and cost."""

from __future__ import annotations

from textual.widgets import Static
from textual.reactive import reactive


class VoiceStatusBar(Static):
    """Status bar showing recording state, debug state, AI provider, and session cost."""

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
    debug_state = reactive("idle")
    debug_file = reactive("")
    debug_line = reactive(0)
    compaction_count = reactive(0)

    def render(self) -> str:
        mic = "[bold red]Recording...[/]" if self.is_recording else "[dim]Space: Talk[/]"
        cost = f"${self.session_cost:.4f}"

        if self.debug_state == "paused":
            dbg = f"[bold yellow]Paused[/] at {self.debug_file}:{self.debug_line}"
        elif self.debug_state == "running":
            dbg = "[bold green]Running[/]"
        elif self.debug_state == "stopped":
            dbg = "[dim]Stopped[/]"
        else:
            dbg = "[dim]No debug session[/]"

        compact = f"  |  [dim]Compacted {self.compaction_count}x[/]" if self.compaction_count else ""
        return f"{mic}  |  {dbg}  |  {self.provider_name}  |  {cost}{compact}"
