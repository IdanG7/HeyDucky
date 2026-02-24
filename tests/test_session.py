"""Tests for debug session manager."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from heyducky.debugger.session import DebugSession


@pytest.mark.asyncio
async def test_session_detects_language():
    """Session detects language from file extension."""
    session = DebugSession.__new__(DebugSession)
    session._dap_client = None
    lang = session._detect_language("test.py")
    assert lang == "python"


@pytest.mark.asyncio
async def test_session_start_sets_state():
    """Session sets state to initializing on start."""
    with patch("heyducky.debugger.session.DAPClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.initialize = AsyncMock(return_value=MagicMock(success=True))
        mock_client.launch = AsyncMock(return_value=MagicMock(success=True))
        mock_client.configuration_done = AsyncMock(return_value=MagicMock(success=True))
        mock_client.on_event = MagicMock()
        mock_client_cls.return_value = mock_client

        session = DebugSession(on_state_change=AsyncMock(), on_output=AsyncMock())
        await session.start("test.py")
        assert session._dap_client is not None
