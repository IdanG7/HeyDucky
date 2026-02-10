# tests/test_source_view.py
"""Tests for upgraded source view widget."""

from unittest.mock import patch

from rich.text import Text

from voice_debugger.widgets.source_view import SourceView


def test_source_view_load_content():
    """SourceView can load source content."""
    view = SourceView()
    view.load_source("test.py", "x = 1\ny = 2\nz = 3\n")
    assert view.file_path == "test.py"
    assert view._source_lines == ["x = 1", "y = 2", "z = 3", ""]


def test_source_view_set_current_line():
    """SourceView tracks current execution line."""
    view = SourceView()
    view.load_source("test.py", "a\nb\nc\n")
    view.set_current_line(2)
    assert view.current_line == 2


def test_source_view_toggle_breakpoint():
    """SourceView tracks breakpoints."""
    view = SourceView()
    view.load_source("test.py", "a\nb\nc\n")
    view.toggle_breakpoint(2)
    assert 2 in view.breakpoint_lines
    view.toggle_breakpoint(2)
    assert 2 not in view.breakpoint_lines


def test_source_view_no_source_loaded():
    """SourceView shows placeholder when no source loaded."""
    view = SourceView()
    assert view.file_path is None
    assert view._source_lines == []


def test_refresh_display_includes_filename():
    """_refresh_display includes the filename in the output when a file is loaded."""
    view = SourceView()
    view.load_source("/home/user/project/main.py", "x = 1\n")

    written: list[Text] = []
    with patch.object(view, "clear"), patch.object(
        view, "write", side_effect=lambda t: written.append(t)
    ):
        view._refresh_display()

    # The first written item should be the header containing the filename
    assert len(written) >= 1
    header_text = written[0].plain
    assert "main.py" in header_text


def test_refresh_display_header_shows_short_and_full_path():
    """The filename header shows both the short name and full path."""
    view = SourceView()
    full_path = "/home/user/project/utils/helpers.py"
    view.load_source(full_path, "def helper():\n    pass\n")

    written: list[Text] = []
    with patch.object(view, "clear"), patch.object(
        view, "write", side_effect=lambda t: written.append(t)
    ):
        view._refresh_display()

    header_text = written[0].plain
    # Header should contain the short filename
    assert "helpers.py" in header_text
    # Header should also contain the full path
    assert full_path in header_text
