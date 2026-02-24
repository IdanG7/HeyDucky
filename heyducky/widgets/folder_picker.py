# heyducky/widgets/folder_picker.py
"""Modal folder picker screen using DirectoryTree."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DirectoryTree, Label


class _FolderTree(DirectoryTree):
    """Directory tree that only shows directories (no files)."""

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [p for p in paths if p.is_dir() and not p.name.startswith(".")]


class FolderPickerScreen(ModalScreen[Path | None]):
    """Modal screen for picking a project folder.

    The tree starts at the user's home directory so you can browse
    to any project folder, like Finder / Explorer.
    Enter expands/collapses folders. Press 'l' or click Load to confirm.

    Returns the selected Path on dismiss, or None if cancelled.
    """

    DEFAULT_CSS = """
    FolderPickerScreen {
        align: center middle;
    }

    #folder-picker-container {
        width: 70;
        height: 85%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }

    #folder-picker-title {
        text-align: center;
        text-style: bold;
        width: 100%;
    }

    #folder-picker-selected {
        text-align: center;
        width: 100%;
        margin-bottom: 1;
    }

    #folder-picker-hint {
        text-align: center;
        color: $text-muted;
        width: 100%;
        margin-bottom: 1;
    }

    #folder-tree {
        height: 1fr;
    }

    #folder-picker-buttons {
        height: auto;
        align: center middle;
        margin-top: 1;
    }

    #folder-picker-buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel", show=True),
        Binding("l", "load_folder", "Load", show=True, priority=True),
    ]

    def __init__(self, start_path: Path | None = None):
        super().__init__()
        self._start_path = start_path or Path.home()
        self._selected_path: Path = self._start_path

    def compose(self) -> ComposeResult:
        with Vertical(id="folder-picker-container"):
            yield Label("Select Project Folder", id="folder-picker-title")
            yield Label(
                f"Selected: {self._start_path}",
                id="folder-picker-selected",
            )
            yield Label(
                "Navigate with arrows  l=load highlighted folder  Escape=cancel",
                id="folder-picker-hint",
            )
            yield _FolderTree(Path.home(), id="folder-tree")
            with Horizontal(id="folder-picker-buttons"):
                yield Button("Load", id="folder-load-btn", variant="primary")
                yield Button("Cancel", id="folder-cancel-btn")

    def on_mount(self) -> None:
        self.query_one("#folder-tree").focus()

    def on_directory_tree_cursor_changed(self, event: DirectoryTree.NodeHighlighted) -> None:
        """Update the selected label as the cursor moves."""
        if event.node and event.node.data and event.node.data.path.is_dir():
            self._selected_path = event.node.data.path
            label = self.query_one("#folder-picker-selected", Label)
            label.update(f"Selected: {event.node.data.path}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "folder-load-btn":
            self.dismiss(self._get_cursor_path())
        elif event.button.id == "folder-cancel-btn":
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _get_cursor_path(self) -> Path:
        """Return the path under the tree cursor, falling back to selected."""
        tree = self.query_one("#folder-tree", _FolderTree)
        node = tree.cursor_node
        if node and node.data and node.data.path.is_dir():
            return node.data.path
        return self._selected_path

    def action_load_folder(self) -> None:
        """Load whichever folder the cursor is hovering over."""
        self.dismiss(self._get_cursor_path())
