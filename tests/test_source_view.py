# tests/test_source_view.py
"""Tests for upgraded source view widget."""

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
