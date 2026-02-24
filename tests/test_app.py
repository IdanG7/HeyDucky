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
    app = HeyDuckyApp()
    async with app.run_test():
        assert app._project_root.is_dir()


@pytest.mark.asyncio
async def test_build_editor_context_no_file():
    """Returns empty string when no file is open."""
    app = HeyDuckyApp()
    async with app.run_test():
        ctx = app._build_editor_context()
        assert ctx == ""


@pytest.mark.asyncio
async def test_build_editor_context_with_file():
    """Returns context with file path, line, and code snippet."""
    app = HeyDuckyApp()
    async with app.run_test():
        from heyducky.widgets.source_view import SourceView

        source = app.query_one("#source-view", SourceView)
        source.load_source("/tmp/test.py", "line1\nline2\nline3\nline4\nline5\n")
        source.set_current_line(3)
        source.breakpoint_lines = {1, 5}

        ctx = app._build_editor_context()
        assert "/tmp/test.py" in ctx
        assert "line 3" in ctx
        assert "breakpoints: 1, 5" in ctx
        assert "line3" in ctx
        # Current line should be marked with >>
        assert ">>" in ctx


@pytest.mark.asyncio
async def test_build_editor_context_file_no_line():
    """Returns context without line number when no execution line set."""
    app = HeyDuckyApp()
    async with app.run_test():
        from heyducky.widgets.source_view import SourceView

        source = app.query_one("#source-view", SourceView)
        source.load_source("/tmp/test.py", "hello\nworld\n")

        ctx = app._build_editor_context()
        assert "/tmp/test.py" in ctx
        assert "line " not in ctx.split("]")[0]  # no line in the header
        assert "hello" in ctx
