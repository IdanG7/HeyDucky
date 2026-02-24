# heyducky/widgets/variables.py
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
        self._watched: list[str] = []

    def add_watch(self, name: str) -> None:
        """Add a variable to the watch list."""
        if name not in self._watched:
            self._watched.append(name)

    def remove_watch(self, name: str) -> None:
        """Remove a variable from the watch list."""
        self._watched = [w for w in self._watched if w != name]

    def on_mount(self) -> None:
        """Show initial hints."""
        self.write(Text.from_markup(
            "[bold]Variables at a Glance[/bold]\n\n"
            "[dim]When you hit a breakpoint, I'll show every variable\n"
            "in scope — names, values, and types, updated live.\n\n"
            "  [cyan]name[/cyan] = value  [dim green](type)[/dim green]\n\n"
            "Ask me things like:\n"
            "  \"What's the value of response?\"\n"
            "  \"Why is count still zero?\"[/dim]"
        ))

    def update_variables(self, variables: list[dict]) -> None:
        """Update the displayed variables.

        Args:
            variables: List of dicts with keys: name, value, type.
        """
        self.clear()

        # Show watched variables section first
        if self._watched:
            self.write(Text("\u2003Watched", style="bold underline"))
            for name in self._watched:
                matched = [v for v in variables if v.get("name") == name]
                line = Text()
                if matched:
                    var = matched[0]
                    line.append(f"  \u25c9 {name}", style="bold cyan")
                    line.append(" = ", style="dim")
                    line.append(f"{var.get('value', '?')}", style="white")
                    vtype = var.get("type", "")
                    if vtype:
                        line.append(f"  ({vtype})", style="dim green")
                else:
                    line.append(f"  \u25c9 {name}", style="dim cyan")
                    line.append(" = ", style="dim")
                    line.append("<not in scope>", style="dim italic")
                self.write(line)
            self.write(Text(""))  # separator

        # Show all scope variables
        if not variables and not self._watched:
            self.write(Text("No variables in scope.", style="dim italic"))
            return
        if variables:
            self.write(Text("\u2003Scope", style="bold underline"))
            for var in variables:
                line = Text()
                line.append(f"  {var.get('name', '?')}", style="bold cyan")
                line.append(" = ", style="dim")
                line.append(f"{var.get('value', '?')}", style="white")
                vtype = var.get("type", "")
                if vtype:
                    line.append(f"  ({vtype})", style="dim green")
                self.write(line)
