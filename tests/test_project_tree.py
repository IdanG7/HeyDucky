# tests/test_project_tree.py
"""Tests for filtered project tree widget."""

from pathlib import Path

from voice_debugger.widgets.project_tree import ProjectTree, IGNORE_NAMES, IGNORE_EXTENSIONS


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
    """IGNORE_NAMES is a frozenset with expected entries."""
    assert isinstance(IGNORE_NAMES, frozenset)
    assert ".git" in IGNORE_NAMES
    assert "__pycache__" in IGNORE_NAMES
    assert "node_modules" in IGNORE_NAMES


def test_ignore_extensions_is_set():
    """IGNORE_EXTENSIONS is a frozenset with expected entries."""
    assert isinstance(IGNORE_EXTENSIONS, frozenset)
    assert ".pyc" in IGNORE_EXTENSIONS


def test_project_tree_has_reveal_path():
    """ProjectTree has a reveal_path method."""
    tree = ProjectTree("/tmp")
    assert hasattr(tree, "reveal_path")
    assert callable(tree.reveal_path)
