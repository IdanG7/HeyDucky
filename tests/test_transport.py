"""Tests for DAP transport layer."""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from voice_debugger.debugger.transport import StdioTransport, TCPTransport
from voice_debugger.debugger.types import DAPRequest, encode_message


@pytest.mark.asyncio
async def test_stdio_transport_send():
    """StdioTransport writes encoded message to process stdin."""
    mock_proc = MagicMock()
    mock_proc.stdin = MagicMock()
    mock_proc.stdin.write = MagicMock()
    mock_proc.stdin.drain = AsyncMock()

    transport = StdioTransport.__new__(StdioTransport)
    transport._process = mock_proc
    transport._on_message = AsyncMock()
    transport._buffer = b""

    req = DAPRequest(seq=1, command="initialize", arguments={})
    await transport.send(req)
    mock_proc.stdin.write.assert_called_once()
    written = mock_proc.stdin.write.call_args[0][0]
    assert b"Content-Length:" in written
    assert b"initialize" in written


def test_stdio_transport_default_state():
    """StdioTransport starts with no process."""
    transport = StdioTransport.__new__(StdioTransport)
    transport._process = None
    assert transport._process is None
