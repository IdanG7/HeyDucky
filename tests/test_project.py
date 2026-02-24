# tests/test_project.py
"""Tests for project root detection."""

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
