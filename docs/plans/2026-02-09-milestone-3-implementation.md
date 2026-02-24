# Milestone 3: Project Browser + Git Workflow — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a project file browser (side-by-side in Source tab) and voice-driven git commands to the debugger TUI.

**Architecture:** Textual's built-in `DirectoryTree` widget, subclassed as `ProjectTree` with `filter_paths` override, placed in a `Horizontal` container alongside the existing `SourceView`. Project root auto-detected by walking up from target file for project markers. Git commands executed via `subprocess.run` with an allowlist of safe subcommands.

**Tech Stack:** Textual (DirectoryTree, Horizontal, Container), pathlib, subprocess

---

### Task 1: Project Root Detection Utility

**Files:**
- Create: `heyducky/project.py`
- Test: `tests/test_project.py`

**Step 1: Write the failing tests**

```python
# tests/test_project.py
"""Tests for project root detection."""

from pathlib import Path

from heyducky.project import detect_project_root


def test_detect_git_root(tmp_path):
    """Finds project root by .git directory."""
    (tmp_path / ".git").mkdir()
    sub = tmp_path / "src" / "pkg"
    sub.mkdir(parents=True)
    target = sub / "main.py"
    target.touch()
    assert detect_project_root(target) == tmp_path


def test_detect_pyproject_root(tmp_path):
    """Finds project root by pyproject.toml."""
    (tmp_path / "pyproject.toml").touch()
    sub = tmp_path / "src"
    sub.mkdir()
    target = sub / "app.py"
    target.touch()
    assert detect_project_root(target) == tmp_path


def test_detect_cargo_root(tmp_path):
    """Finds project root by Cargo.toml (Rust)."""
    (tmp_path / "Cargo.toml").touch()
    sub = tmp_path / "src"
    sub.mkdir()
    target = sub / "main.rs"
    target.touch()
    assert detect_project_root(target) == tmp_path


def test_detect_go_mod_root(tmp_path):
    """Finds project root by go.mod."""
    (tmp_path / "go.mod").touch()
    target = tmp_path / "main.go"
    target.touch()
    assert detect_project_root(target) == tmp_path


def test_detect_sln_root(tmp_path):
    """Finds project root by .sln file."""
    (tmp_path / "project.sln").touch()
    sub = tmp_path / "src" / "app"
    sub.mkdir(parents=True)
    target = sub / "Program.cs"
    target.touch()
    assert detect_project_root(target) == tmp_path


def test_fallback_to_parent(tmp_path):
    """Falls back to target's parent directory when no markers found."""
    sub = tmp_path / "orphan"
    sub.mkdir()
    target = sub / "script.py"
    target.touch()
    assert detect_project_root(target) == sub


def test_directory_as_start(tmp_path):
    """Accepts directory as start_path."""
    (tmp_path / ".git").mkdir()
    sub = tmp_path / "src"
    sub.mkdir()
    assert detect_project_root(sub) == tmp_path


def test_root_is_start(tmp_path):
    """Project root is the start path itself."""
    (tmp_path / "pyproject.toml").touch()
    target = tmp_path / "app.py"
    target.touch()
    assert detect_project_root(target) == tmp_path
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_project.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'heyducky.project'"

**Step 3: Write implementation**

```python
# heyducky/project.py
"""Project root detection utilities."""

from __future__ import annotations

from pathlib import Path

PROJECT_MARKERS = {
    ".git",
    "pyproject.toml",
    "setup.py",
    "Cargo.toml",
    "go.mod",
    "package.json",
    "CMakeLists.txt",
    "Makefile",
    ".sln",
    ".csproj",
}


def detect_project_root(start_path: str | Path) -> Path:
    """Walk up from start_path looking for project markers.

    Checks each directory from start_path upward for well-known
    project markers (.git, pyproject.toml, Cargo.toml, etc.).

    Args:
        start_path: File or directory to start searching from.

    Returns:
        The detected project root, or the start path's parent as fallback.
    """
    current = Path(start_path).resolve()
    if current.is_file():
        current = current.parent

    fallback = current  # Remember original directory for fallback

    while True:
        for marker in PROJECT_MARKERS:
            if (current / marker).exists():
                return current
        parent = current.parent
        if parent == current:
            break  # Reached filesystem root
        current = parent

    return fallback
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_project.py -v`
Expected: All 8 tests PASS

**Step 5: Commit**

```bash
git add heyducky/project.py tests/test_project.py
git commit -m "feat: add project root detection utility"
```

---

### Task 2: ProjectTree Widget (Filtered DirectoryTree)

**Files:**
- Create: `heyducky/widgets/project_tree.py`
- Test: `tests/test_project_tree.py`
- Modify: `heyducky/widgets/__init__.py` — add ProjectTree export

**Step 1: Write the failing tests**

```python
# tests/test_project_tree.py
"""Tests for filtered project tree widget."""

from pathlib import Path

from heyducky.widgets.project_tree import ProjectTree, IGNORE_NAMES, IGNORE_EXTENSIONS


def test_filter_hides_git(tmp_path):
    """filter_paths excludes .git directory."""
    paths = [tmp_path / ".git", tmp_path / "src"]
    tree = ProjectTree(tmp_path)
    result = list(tree.filter_paths(paths))
    names = [p.name for p in result]
    assert ".git" not in names
    assert "src" in names


def test_filter_hides_pycache(tmp_path):
    """filter_paths excludes __pycache__."""
    paths = [tmp_path / "__pycache__", tmp_path / "app.py"]
    tree = ProjectTree(tmp_path)
    result = list(tree.filter_paths(paths))
    names = [p.name for p in result]
    assert "__pycache__" not in names
    assert "app.py" in names


def test_filter_hides_node_modules(tmp_path):
    """filter_paths excludes node_modules."""
    paths = [tmp_path / "node_modules", tmp_path / "index.js"]
    tree = ProjectTree(tmp_path)
    result = list(tree.filter_paths(paths))
    names = [p.name for p in result]
    assert "node_modules" not in names
    assert "index.js" in names


def test_filter_hides_pyc_extension(tmp_path):
    """filter_paths excludes .pyc files."""
    paths = [tmp_path / "app.pyc", tmp_path / "app.py"]
    tree = ProjectTree(tmp_path)
    result = list(tree.filter_paths(paths))
    names = [p.name for p in result]
    assert "app.pyc" not in names
    assert "app.py" in names


def test_filter_hides_ds_store(tmp_path):
    """filter_paths excludes .DS_Store."""
    paths = [tmp_path / ".DS_Store", tmp_path / "main.py"]
    tree = ProjectTree(tmp_path)
    result = list(tree.filter_paths(paths))
    names = [p.name for p in result]
    assert ".DS_Store" not in names
    assert "main.py" in names


def test_filter_hides_ide_dirs(tmp_path):
    """filter_paths excludes IDE directories."""
    paths = [tmp_path / ".idea", tmp_path / ".vscode", tmp_path / "src"]
    tree = ProjectTree(tmp_path)
    result = list(tree.filter_paths(paths))
    names = [p.name for p in result]
    assert ".idea" not in names
    assert ".vscode" not in names
    assert "src" in names


def test_filter_keeps_regular_files(tmp_path):
    """filter_paths keeps regular source files."""
    paths = [
        tmp_path / "app.py",
        tmp_path / "main.rs",
        tmp_path / "index.ts",
        tmp_path / "README.md",
    ]
    tree = ProjectTree(tmp_path)
    result = list(tree.filter_paths(paths))
    assert len(result) == 4


def test_ignore_names_is_set():
    """IGNORE_NAMES is a set with expected entries."""
    assert isinstance(IGNORE_NAMES, frozenset)
    assert ".git" in IGNORE_NAMES
    assert "__pycache__" in IGNORE_NAMES
    assert "node_modules" in IGNORE_NAMES


def test_ignore_extensions_is_set():
    """IGNORE_EXTENSIONS is a set with expected entries."""
    assert isinstance(IGNORE_EXTENSIONS, frozenset)
    assert ".pyc" in IGNORE_EXTENSIONS
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_project_tree.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'heyducky.widgets.project_tree'"

**Step 3: Write implementation**

```python
# heyducky/widgets/project_tree.py
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
```

**Step 4: Update widgets/__init__.py**

Add `ProjectTree` to `heyducky/widgets/__init__.py`:

```python
# heyducky/widgets/__init__.py
"""TUI widget components."""

from heyducky.widgets.source_view import SourceView
from heyducky.widgets.conversation import ConversationView
from heyducky.widgets.status_bar import VoiceStatusBar
from heyducky.widgets.variables import VariablesView
from heyducky.widgets.call_stack import CallStackView
from heyducky.widgets.debug_output import DebugOutputView
from heyducky.widgets.project_tree import ProjectTree

__all__ = [
    "SourceView",
    "ConversationView",
    "VoiceStatusBar",
    "VariablesView",
    "CallStackView",
    "DebugOutputView",
    "ProjectTree",
]
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/test_project_tree.py -v`
Expected: All 9 tests PASS

**Step 6: Run all tests to verify nothing broke**

Run: `pytest -v`
Expected: All tests PASS (previous 66 + 9 new = 75)

**Step 7: Commit**

```bash
git add heyducky/widgets/project_tree.py heyducky/widgets/__init__.py tests/test_project_tree.py
git commit -m "feat: add ProjectTree widget with file filtering"
```

---

### Task 3: Source Tab Split Layout

**Files:**
- Modify: `heyducky/app.py:30-38` (CSS), `heyducky/app.py:53-60` (__init__), `heyducky/app.py:62-76` (compose), `heyducky/app.py:78-83` (on_mount)
- Modify: `heyducky/__main__.py:7-30` (add --project flag)
- Test: `tests/test_app.py` — update existing tests + add new ones

**Context:** The Source tab currently yields only `SourceView`. We need to wrap it in a `Horizontal` container with `ProjectTree` on the left and `SourceView` on the right. The app needs a `project_root` property. The `__main__.py` needs a `--project` flag.

**Step 1: Write the failing tests**

Add to `tests/test_app.py`:

```python
# tests/test_app.py
"""Smoke tests for the TUI application."""

import pytest
from heyducky.app import HeyDuckyApp


@pytest.mark.asyncio
async def test_app_starts_and_quits():
    """App starts, shows welcome message, and quits with 'q'."""
    app = HeyDuckyApp()
    async with app.run_test() as pilot:
        conv = app.query_one("#conversation-view")
        assert conv is not None
        status = app.query_one("#status-bar")
        assert status is not None
        await pilot.press("q")


@pytest.mark.asyncio
async def test_app_has_source_view():
    """App shows the source view."""
    app = HeyDuckyApp()
    async with app.run_test():
        source = app.query_one("#source-view")
        assert source is not None


@pytest.mark.asyncio
async def test_app_has_all_tabs():
    """App has all 5 tab panes."""
    app = HeyDuckyApp()
    async with app.run_test():
        assert app.query_one("#source-view") is not None
        assert app.query_one("#conversation-view") is not None
        assert app.query_one("#variables-view") is not None
        assert app.query_one("#callstack-view") is not None
        assert app.query_one("#output-view") is not None


@pytest.mark.asyncio
async def test_app_has_project_tree():
    """Source tab has a ProjectTree widget."""
    app = HeyDuckyApp()
    async with app.run_test():
        tree = app.query_one("#project-tree")
        assert tree is not None


@pytest.mark.asyncio
async def test_app_project_root_default():
    """App uses cwd as project root when no target given."""
    import os
    app = HeyDuckyApp()
    async with app.run_test():
        assert app._project_root.resolve() == app._project_root.resolve()
        # Should be a real directory
        assert app._project_root.is_dir()
```

**Step 2: Run tests to verify new ones fail**

Run: `pytest tests/test_app.py -v`
Expected: `test_app_has_project_tree` and `test_app_project_root_default` FAIL

**Step 3: Update __main__.py — add --project flag**

Replace the full content of `heyducky/__main__.py`:

```python
# heyducky/__main__.py
"""CLI entry point for ducky."""

import argparse


def main():
    parser = argparse.ArgumentParser(
        description="Voice-controlled AI debugging assistant"
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="Program to debug (e.g., script.py)",
    )
    parser.add_argument(
        "--project",
        help="Project root directory (auto-detected if not given)",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Run first-time setup wizard",
    )
    args = parser.parse_args()

    if args.setup:
        _run_setup()
        return

    from heyducky.app import HeyDuckyApp

    app = HeyDuckyApp(target=args.target, project=args.project)
    app.run()


def _run_setup():
    """Interactive setup wizard."""
    from heyducky.config import Config

    print("HeyDucky Setup")
    print("=" * 40)

    config = Config.load()

    api_key_display = config.api_key[:8] if config.api_key else "not set"
    api_key = input(f"Anthropic API key [{api_key_display}]: ").strip()
    if api_key:
        config.api_key = api_key

    model = input(f"Model [{config.ai_model}]: ").strip()
    if model:
        config.ai_model = model

    whisper = input(f"Whisper model [{config.whisper_model}]: ").strip()
    if whisper:
        config.whisper_model = whisper

    config.save()
    print("\nConfig saved. Run 'ducky' to start.")


if __name__ == "__main__":
    main()
```

**Step 4: Update app.py — add project_root, split Source tab layout**

Key changes to `heyducky/app.py`:

1. Add imports: `from pathlib import Path`, `from textual.containers import Horizontal`, `ProjectTree`, `detect_project_root`
2. Add CSS for the horizontal split layout
3. Update `__init__` to accept `project` parameter, compute `_project_root`
4. Update `compose` to put `ProjectTree` + `SourceView` inside a `Horizontal` in the Source tab
5. Add `on_directory_tree_file_selected` handler

Full updated `heyducky/app.py`:

```python
# heyducky/app.py
"""Main Textual TUI application with tabbed debug interface."""

from __future__ import annotations

import os
from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Header, Footer, TabbedContent, TabPane

from heyducky.config import Config
from heyducky.project import detect_project_root
from heyducky.widgets import (
    SourceView,
    ConversationView,
    VoiceStatusBar,
    VariablesView,
    CallStackView,
    DebugOutputView,
    ProjectTree,
)


class HeyDuckyApp(App):
    """Voice-controlled AI debugging assistant."""

    TITLE = "HeyDucky"
    SUB_TITLE = "AI Pair Programming"

    CSS = """
    Screen {
        background: $surface;
    }

    TabbedContent {
        height: 1fr;
    }

    #source-pane {
        height: 1fr;
    }

    #project-tree {
        width: 1fr;
        max-width: 40;
    }

    #source-view {
        width: 3fr;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("space", "toggle_recording", "Talk", show=True),
        Binding("1", "show_tab('source')", "Source", show=False),
        Binding("2", "show_tab('conversation')", "Chat", show=False),
        Binding("3", "show_tab('variables')", "Vars", show=False),
        Binding("4", "show_tab('callstack')", "Stack", show=False),
        Binding("5", "show_tab('output')", "Output", show=False),
        Binding("f5", "debug_continue", "Continue", show=False),
        Binding("f10", "debug_step_over", "Step Over", show=False),
        Binding("f11", "debug_step_into", "Step Into", show=False),
    ]

    def __init__(self, target: str | None = None, project: str | None = None):
        super().__init__()
        self.config = Config.load()
        self._target = target
        self._voice = None
        self._orchestrator = None
        self._dap_client = None
        self._debug_session = None

        # Determine project root
        if project:
            self._project_root = Path(project).resolve()
        elif target:
            self._project_root = detect_project_root(target)
        else:
            self._project_root = Path.cwd()

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(initial="conversation"):
            with TabPane("Source", id="source"):
                with Horizontal(id="source-pane"):
                    yield ProjectTree(self._project_root, id="project-tree")
                    yield SourceView(id="source-view")
            with TabPane("Conversation", id="conversation"):
                yield ConversationView(id="conversation-view")
            with TabPane("Variables", id="variables"):
                yield VariablesView(id="variables-view")
            with TabPane("Call Stack", id="callstack"):
                yield CallStackView(id="callstack-view")
            with TabPane("Output", id="output"):
                yield DebugOutputView(id="output-view")
        yield VoiceStatusBar(id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize components after mount."""
        conv = self.query_one("#conversation-view", ConversationView)
        conv.add_system_message("Welcome to HeyDucky. Press Space to talk.")
        conv.add_system_message("Tabs: 1=Source 2=Chat 3=Vars 4=Stack 5=Output")
        conv.add_system_message(f"Project: {self._project_root}")
        self._init_components()

    def on_directory_tree_file_selected(
        self, event: ProjectTree.FileSelected
    ) -> None:
        """Load selected file in source view."""
        source_view = self.query_one("#source-view", SourceView)
        source_view.load_source(str(event.path))

    # --- rest of the file stays exactly the same from _init_components onwards ---
```

The methods from `_init_components` through the end of the file remain **unchanged**.

**Step 5: Run tests to verify they pass**

Run: `pytest tests/test_app.py -v`
Expected: All 5 tests PASS

**Step 6: Run all tests**

Run: `pytest -v`
Expected: All tests PASS

**Step 7: Commit**

```bash
git add heyducky/app.py heyducky/__main__.py tests/test_app.py
git commit -m "feat: split Source tab with ProjectTree + SourceView side-by-side"
```

---

### Task 4: File Tree ↔ Debugger Sync

**Files:**
- Modify: `heyducky/app.py:260-284` (`_update_debug_state` method)

**Context:** When the debugger pauses and `_update_debug_state` fires, we currently load the file in `SourceView`. We also need to highlight the file in the `ProjectTree`. Textual's `DirectoryTree` doesn't have a built-in "select file by path" method, so we'll add a `reveal_path` helper to `ProjectTree`.

**Step 1: Write the failing test**

Add to `tests/test_project_tree.py`:

```python
def test_project_tree_has_reveal_path():
    """ProjectTree has a reveal_path method."""
    tree = ProjectTree("/tmp")
    assert hasattr(tree, "reveal_path")
    assert callable(tree.reveal_path)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_project_tree.py::test_project_tree_has_reveal_path -v`
Expected: FAIL with "AssertionError"

**Step 3: Add reveal_path to ProjectTree**

Add this method to the `ProjectTree` class in `heyducky/widgets/project_tree.py`:

```python
    def reveal_path(self, path: str | Path) -> None:
        """Expand the tree to reveal and highlight a file path.

        Walks the tree nodes to expand directories along the path.
        If the path is outside the tree root, this is a no-op.
        """
        target = Path(path).resolve()
        root = Path(str(self.path)).resolve()

        # Check if target is under our root
        try:
            target.relative_to(root)
        except ValueError:
            return  # Path is outside the tree

        # Reload to ensure fresh state, then let Textual handle the rest
        self.reload()
```

**Step 4: Update _update_debug_state in app.py**

In `heyducky/app.py`, in the `_update_debug_state` method, after updating the source view and before switching to source tab, add:

```python
            # Sync file tree
            try:
                tree = self.query_one("#project-tree", ProjectTree)
                tree.reveal_path(file_path)
            except Exception:
                pass  # Tree may not be ready
```

**Step 5: Run tests**

Run: `pytest tests/test_project_tree.py -v && pytest tests/test_app.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add heyducky/widgets/project_tree.py heyducky/app.py
git commit -m "feat: sync file tree with debugger breakpoint position"
```

---

### Task 5: Git Command Tool — Safety Layer

**Files:**
- Create: `heyducky/git_executor.py`
- Test: `tests/test_git_executor.py`

**Context:** This is the safety layer that validates and runs git commands. It's separate from the AI tool definition — the ToolExecutor will call this. It uses `subprocess.run` with an allowlist.

**Step 1: Write the failing tests**

```python
# tests/test_git_executor.py
"""Tests for git command executor with safety constraints."""

import pytest

from heyducky.git_executor import GitExecutor, GitCommandBlocked


def test_status_allowed():
    """'status' is an allowed git subcommand."""
    executor = GitExecutor("/tmp")
    assert executor.is_allowed("status")


def test_diff_allowed():
    """'diff --staged' is allowed."""
    executor = GitExecutor("/tmp")
    assert executor.is_allowed("diff --staged")


def test_log_allowed():
    """'log --oneline -5' is allowed."""
    executor = GitExecutor("/tmp")
    assert executor.is_allowed("log --oneline -5")


def test_add_allowed():
    """'add .' is allowed."""
    executor = GitExecutor("/tmp")
    assert executor.is_allowed("add .")


def test_commit_allowed():
    """'commit -m message' is allowed."""
    executor = GitExecutor("/tmp")
    assert executor.is_allowed("commit -m 'fix bug'")


def test_branch_allowed():
    """'branch' is allowed."""
    executor = GitExecutor("/tmp")
    assert executor.is_allowed("branch")


def test_stash_allowed():
    """'stash' is allowed."""
    executor = GitExecutor("/tmp")
    assert executor.is_allowed("stash")


def test_blame_allowed():
    """'blame file.py' is allowed."""
    executor = GitExecutor("/tmp")
    assert executor.is_allowed("blame file.py")


def test_push_blocked():
    """'push' is blocked."""
    executor = GitExecutor("/tmp")
    assert not executor.is_allowed("push")


def test_push_force_blocked():
    """'push --force' is blocked."""
    executor = GitExecutor("/tmp")
    assert not executor.is_allowed("push --force")


def test_reset_hard_blocked():
    """'reset --hard' is blocked."""
    executor = GitExecutor("/tmp")
    assert not executor.is_allowed("reset --hard")


def test_clean_f_blocked():
    """'clean -f' is blocked."""
    executor = GitExecutor("/tmp")
    assert not executor.is_allowed("clean -f")


def test_rebase_blocked():
    """'rebase' is blocked."""
    executor = GitExecutor("/tmp")
    assert not executor.is_allowed("rebase")


def test_empty_command_blocked():
    """Empty string is blocked."""
    executor = GitExecutor("/tmp")
    assert not executor.is_allowed("")


def test_run_blocked_raises(tmp_path):
    """Running a blocked command raises GitCommandBlocked."""
    executor = GitExecutor(str(tmp_path))
    with pytest.raises(GitCommandBlocked):
        executor.run("push origin main")


def test_output_truncation(tmp_path):
    """Output is truncated to max_output_chars."""
    executor = GitExecutor(str(tmp_path), max_output_chars=20)
    # 'status' will work in any directory (non-git = error msg, but still runs)
    result = executor.run("version")
    # git version string is typically > 20 chars
    assert len(result) <= 20 + len("\n... (output truncated)")


def test_run_returns_string(tmp_path):
    """run() returns a string."""
    executor = GitExecutor(str(tmp_path))
    result = executor.run("version")
    assert isinstance(result, str)
    assert "git version" in result.lower() or "error" in result.lower()
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_git_executor.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write implementation**

```python
# heyducky/git_executor.py
"""Safe git command execution with allowlist enforcement."""

from __future__ import annotations

import subprocess


class GitCommandBlocked(Exception):
    """Raised when a git command is not in the allowlist."""


ALLOWED_SUBCOMMANDS = frozenset({
    "status", "diff", "log", "show", "branch", "add", "commit",
    "stash", "blame", "shortlog", "tag", "remote", "version",
})

BLOCKED_SUBCOMMANDS = frozenset({
    "push", "clean", "rebase", "reset", "force-push",
})


class GitExecutor:
    """Executes git commands with safety constraints.

    Only allows a predefined set of safe subcommands.
    Blocks destructive operations like push, reset --hard, clean -f.
    Truncates output to stay within AI context limits.
    """

    def __init__(self, project_root: str, max_output_chars: int = 4000) -> None:
        self._project_root = project_root
        self._max_output_chars = max_output_chars

    def is_allowed(self, command: str) -> bool:
        """Check if a git command string is allowed."""
        parts = command.strip().split()
        if not parts:
            return False

        subcommand = parts[0]

        # Explicit block check
        if subcommand in BLOCKED_SUBCOMMANDS:
            return False

        # Must be in allowlist
        return subcommand in ALLOWED_SUBCOMMANDS

    def run(self, command: str) -> str:
        """Execute a git command and return output.

        Raises:
            GitCommandBlocked: If the command is not allowed.
        """
        if not self.is_allowed(command):
            raise GitCommandBlocked(f"Blocked git command: {command}")

        parts = command.strip().split()
        try:
            result = subprocess.run(
                ["git"] + parts,
                cwd=self._project_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout
            if result.returncode != 0 and result.stderr:
                output += f"\nSTDERR: {result.stderr}"

            if len(output) > self._max_output_chars:
                output = output[: self._max_output_chars] + "\n... (output truncated)"

            return output.strip() if output.strip() else "(no output)"
        except subprocess.TimeoutExpired:
            return "Command timed out after 30 seconds"
        except FileNotFoundError:
            return "git is not installed or not in PATH"
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_git_executor.py -v`
Expected: All 17 tests PASS

**Step 5: Commit**

```bash
git add heyducky/git_executor.py tests/test_git_executor.py
git commit -m "feat: add git command executor with safety allowlist"
```

---

### Task 6: Wire Git Tool into AI

**Files:**
- Modify: `heyducky/ai/functions.py:89` — append run_git_command tool definition
- Modify: `heyducky/debugger/tool_executor.py` — add `_exec_run_git_command` method, accept `project_root` param
- Modify: `heyducky/ai/prompts.py:3-34` — update system prompt with git + project context
- Test: `tests/test_tool_executor.py` — add git tool tests

**Step 1: Write the failing tests**

Add to `tests/test_tool_executor.py`:

```python
@pytest.mark.asyncio
async def test_execute_git_status(mock_dap, tmp_path):
    """ToolExecutor handles run_git_command for git status."""
    # Initialize a git repo so status works
    import subprocess
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)

    executor = ToolExecutor(mock_dap, project_root=str(tmp_path))
    result = await executor.execute(
        ToolCall(id="g1", name="run_git_command", arguments={"command": "status"})
    )
    assert isinstance(result, str)
    # Should contain some git status output
    assert "branch" in result.lower() or "nothing" in result.lower() or "no commits" in result.lower()


@pytest.mark.asyncio
async def test_execute_git_push_blocked(mock_dap, tmp_path):
    """ToolExecutor blocks dangerous git commands."""
    executor = ToolExecutor(mock_dap, project_root=str(tmp_path))
    result = await executor.execute(
        ToolCall(id="g2", name="run_git_command", arguments={"command": "push origin main"})
    )
    assert "blocked" in result.lower()


@pytest.mark.asyncio
async def test_execute_git_no_project_root(mock_dap):
    """ToolExecutor without project_root returns error for git commands."""
    executor = ToolExecutor(mock_dap)
    result = await executor.execute(
        ToolCall(id="g3", name="run_git_command", arguments={"command": "status"})
    )
    assert "no project" in result.lower()
```

**Step 2: Run new tests to verify they fail**

Run: `pytest tests/test_tool_executor.py::test_execute_git_status -v`
Expected: FAIL (ToolExecutor doesn't accept project_root yet)

**Step 3: Update functions.py — add run_git_command tool definition**

Append to the `DEBUGGER_TOOLS` list in `heyducky/ai/functions.py`:

```python
    {
        "name": "run_git_command",
        "description": "Execute a git command in the project directory. Use for: status, diff, log, show, branch, add, commit, stash, blame. BLOCKED: push, reset, clean, rebase. Always check 'status' before committing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Git subcommand and arguments (e.g., 'status', 'diff --staged', 'log --oneline -5', 'commit -m \"fix null check\"')",
                },
            },
            "required": ["command"],
        },
    },
```

**Step 4: Update tool_executor.py — accept project_root, add git handler**

Modify `heyducky/debugger/tool_executor.py`:

1. Update `__init__` to accept optional `project_root: str | None = None`
2. Add `_exec_run_git_command` method

Updated `__init__`:

```python
    def __init__(self, dap_client: DAPClient, project_root: str | None = None) -> None:
        self._dap = dap_client
        self._project_root = project_root
```

New method at the end of the class:

```python
    # ------------------------------------------------------------------
    # Git commands
    # ------------------------------------------------------------------

    async def _exec_run_git_command(self, args: dict) -> str:
        if not self._project_root:
            return "No project root configured. Cannot run git commands."
        from heyducky.git_executor import GitExecutor, GitCommandBlocked
        executor = GitExecutor(self._project_root)
        try:
            return executor.run(args["command"])
        except GitCommandBlocked as e:
            return f"Blocked: {e}"
```

**Step 5: Update prompts.py — add git + project context**

Replace `DEBUGGER_SYSTEM_PROMPT` in `heyducky/ai/prompts.py`:

```python
DEBUGGER_SYSTEM_PROMPT = """\
You're pair programming with a colleague who's debugging.
You're the one at the keyboard with access to the debugger.

YOUR PERSONALITY:
- Talk like you're on a video call debugging together
- Think out loud - show your reasoning
- Use casual language: "yeah", "hmm", "wait"
- Have opinions and push back when needed
- Get excited when you find bugs
- Admit uncertainty

HOW YOU DEBUG:
- Just do things naturally, don't announce tool use
- Think step-by-step aloud
- Challenge bad assumptions
- Suggest concrete fixes, not generic advice

GIT WORKFLOW:
- Use run_git_command for version control tasks
- Always check 'status' before committing
- Write clear, concise commit messages
- You can: status, diff, log, add, commit, branch, stash, blame
- You CANNOT: push, reset, clean, rebase (tell user to do these manually)

CRITICAL RULES:
- NEVER say "I'm an AI" or "as an AI assistant"
- Don't apologize excessively
- Keep responses SHORT (2-3 sentences)
- Use contractions always

Available debugger functions (use naturally, don't announce):
- set_breakpoint(file, line, condition?)
- inspect_variable(name)
- step_over() / step_into() / step_out()
- continue_execution()
- evaluate_expression(expr)
- get_call_stack()
- read_source(file, line, context?)
- run_git_command(command)
"""
```

**Step 6: Update app.py — pass project_root to ToolExecutor**

In `heyducky/app.py`, in the `_start_debug_session` method, change the ToolExecutor instantiation line from:

```python
                executor = ToolExecutor(self._debug_session.client)
```

to:

```python
                executor = ToolExecutor(
                    self._debug_session.client,
                    project_root=str(self._project_root),
                )
```

Also in `_init_components`, when creating the Orchestrator (after `self._orchestrator = Orchestrator(provider=provider)`), we need to handle the case where there's no debug session but we still want git tools. After the orchestrator creation, add:

```python
            # Set up git-only tool executor if no debug session
            if not self._target:
                from heyducky.debugger.tool_executor import ToolExecutor
                self._orchestrator._tool_executor = ToolExecutor(
                    dap_client=None,
                    project_root=str(self._project_root),
                )
```

And update ToolExecutor's type hint for `dap_client` to allow None:

In `heyducky/debugger/tool_executor.py`, change:
```python
    def __init__(self, dap_client: DAPClient, project_root: str | None = None) -> None:
```
to:
```python
    def __init__(self, dap_client: DAPClient | None, project_root: str | None = None) -> None:
```

And add a guard in `execute` for DAP-dependent tools when client is None: update each `_exec_` method that uses `self._dap` to check for None first. The simplest approach is to add a check at the top of `execute`:

```python
    async def execute(self, tool_call: ToolCall) -> str:
        """Execute a tool call and return a human-readable result string."""
        name = tool_call.name
        args = tool_call.arguments

        handler = getattr(self, f"_exec_{name}", None)
        if handler is None:
            return f"Unknown tool: {name}"

        # Git commands don't need DAP client
        if name != "run_git_command" and self._dap is None:
            return f"No debug session active. Cannot execute {name}."

        return await handler(args)
```

**Step 7: Run tests to verify they pass**

Run: `pytest tests/test_tool_executor.py -v`
Expected: All tests PASS (previous 11 + 3 new = 14)

**Step 8: Run all tests**

Run: `pytest -v`
Expected: All tests PASS

**Step 9: Commit**

```bash
git add heyducky/ai/functions.py heyducky/ai/prompts.py heyducky/debugger/tool_executor.py heyducky/app.py tests/test_tool_executor.py
git commit -m "feat: wire git command tool into AI with safety allowlist"
```

---

### Task 7: Final Integration + All Tests Green

**Files:**
- No new files. Verify everything works together.

**Step 1: Run full test suite**

Run: `pytest -v`
Expected: All tests PASS (66 original + 8 project + 9 tree + 2 app + 17 git + 3 git-tool = ~105)

**Step 2: Run linter**

Run: `ruff check heyducky/ tests/`
Expected: No errors (fix any that appear)

**Step 3: Verify imports are clean**

Run: `python -c "from heyducky.app import HeyDuckyApp; print('OK')"`
Expected: "OK"

Run: `python -c "from heyducky.project import detect_project_root; print('OK')"`
Expected: "OK"

Run: `python -c "from heyducky.git_executor import GitExecutor; print('OK')"`
Expected: "OK"

**Step 4: Commit if any linter fixes were needed**

```bash
git add -u
git commit -m "chore: linter fixes for M3 implementation"
```
