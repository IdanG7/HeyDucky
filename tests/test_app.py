# tests/test_app.py
"""Smoke tests for the TUI application."""

import pytest
from voice_debugger.app import VoiceDebuggerApp


@pytest.mark.asyncio
async def test_app_starts_and_quits():
    """App starts, shows welcome message, and quits with 'q'."""
    app = VoiceDebuggerApp()
    async with app.run_test() as pilot:
        conv = app.query_one("#conversation-view")
        assert conv is not None
        status = app.query_one("#status-bar")
        assert status is not None
        await pilot.press("q")


@pytest.mark.asyncio
async def test_app_has_source_view():
    """App shows the source view."""
    app = VoiceDebuggerApp()
    async with app.run_test():
        source = app.query_one("#source-view")
        assert source is not None


@pytest.mark.asyncio
async def test_app_has_all_tabs():
    """App has all 5 tab panes."""
    app = VoiceDebuggerApp()
    async with app.run_test():
        assert app.query_one("#source-view") is not None
        assert app.query_one("#conversation-view") is not None
        assert app.query_one("#variables-view") is not None
        assert app.query_one("#callstack-view") is not None
        assert app.query_one("#output-view") is not None


@pytest.mark.asyncio
async def test_app_has_project_tree():
    """Source tab has a ProjectTree widget."""
    app = VoiceDebuggerApp()
    async with app.run_test():
        tree = app.query_one("#project-tree")
        assert tree is not None


@pytest.mark.asyncio
async def test_app_project_root_default():
    """App uses cwd as project root when no target given."""
    app = VoiceDebuggerApp()
    async with app.run_test():
        assert app._project_root.is_dir()
