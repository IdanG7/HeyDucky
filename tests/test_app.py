# tests/test_app.py
"""Smoke tests for the TUI application."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from voice_debugger.app import VoiceDebuggerApp


@pytest.fixture
def mock_voice():
    """Mock VoiceHandler to avoid actual audio."""
    with patch("voice_debugger.app.VoiceHandler") as mock_cls:
        mock_handler = MagicMock()
        mock_handler.is_recording = False
        mock_handler.transcribe.return_value = "test transcript"
        mock_handler.stop_recording.return_value = __import__("numpy").zeros(16000, dtype="float32")
        mock_cls.return_value = mock_handler
        yield mock_handler


@pytest.mark.asyncio
async def test_app_starts_and_quits():
    """App starts, shows welcome message, and quits with 'q'."""
    app = VoiceDebuggerApp()
    async with app.run_test() as pilot:
        # Should see the conversation widget
        conv = app.query_one("#conversation")
        assert conv is not None

        # Should see status bar
        status = app.query_one("#status-bar")
        assert status is not None

        # Quit
        await pilot.press("q")


@pytest.mark.asyncio
async def test_app_has_source_view():
    """App shows the source view placeholder."""
    app = VoiceDebuggerApp()
    async with app.run_test():
        source = app.query_one("#source-view")
        assert source is not None
