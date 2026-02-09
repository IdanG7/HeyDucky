# voice_debugger/widgets/project_tree.py
"""Filtered directory tree for project browsing."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from textual.widgets import DirectoryTree


IGNORE_NAMES: frozenset[str] = frozenset({
    # VCS
    ".git", ".svn", ".hg",
    # Python
    "__pycache__", ".venv", "venv", ".eggs", ".mypy_cache", ".ruff_cache",
    ".pytest_cache", ".tox",
    # JS / Node
    "node_modules",
    # Build artifacts
    "build", "dist", "target",
    # IDE
    ".idea", ".vscode", ".vs",
    # OS
    ".DS_Store", "Thumbs.db",
})

IGNORE_EXTENSIONS: frozenset[str] = frozenset({
    ".pyc", ".pyo",
})


class ProjectTree(DirectoryTree):
    """A DirectoryTree that filters out common noise files and directories."""

    DEFAULT_CSS = """
    ProjectTree {
        width: 1fr;
        min-width: 20;
        border: solid $primary;
    }
    """

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        """Filter out ignored files and directories."""
        return [
            p for p in paths
            if p.name not in IGNORE_NAMES
            and p.suffix not in IGNORE_EXTENSIONS
        ]
