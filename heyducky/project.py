"""Project root detection utilities."""

from __future__ import annotations

from pathlib import Path

# Markers that are exact file/directory names
_EXACT_MARKERS = {
    ".git",
    "pyproject.toml",
    "setup.py",
    "Cargo.toml",
    "go.mod",
    "package.json",
    "CMakeLists.txt",
    "Makefile",
}

# Markers that are file extensions (matched via glob)
_EXTENSION_MARKERS = {
    ".sln",
    ".csproj",
}

PROJECT_MARKERS = _EXACT_MARKERS | _EXTENSION_MARKERS


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
        for marker in _EXACT_MARKERS:
            if (current / marker).exists():
                return current
        for ext in _EXTENSION_MARKERS:
            if any(current.glob(f"*{ext}")):
                return current
        parent = current.parent
        if parent == current:
            break  # Reached filesystem root
        current = parent

    return fallback
