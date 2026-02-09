# voice_debugger/widgets/variables.py
"""Variables panel showing current scope."""

from __future__ import annotations

from textual.widgets import RichLog
from rich.text import Text


class VariablesView(RichLog):
    """Displays variables for the current debug scope."""

    DEFAULT_CSS = """
    VariablesView {
        height: 1fr;
        border: solid $primary;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(markup=True, wrap=True, **kwargs)

    def update_variables(self, variables: list[dict]) -> None:
        """Update the displayed variables.

        Args:
            variables: List of dicts with keys: name, value, type.
        """
        self.clear()
        if not variables:
            self.write(Text("No variables in scope.", style="dim italic"))
            return
        for var in variables:
            line = Text()
            line.append(f"  {var.get('name', '?')}", style="bold cyan")
            line.append(" = ", style="dim")
            line.append(f"{var.get('value', '?')}", style="white")
            vtype = var.get("type", "")
            if vtype:
                line.append(f"  ({vtype})", style="dim green")
            self.write(line)
