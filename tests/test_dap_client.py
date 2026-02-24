"""Tests for DAP client."""

from unittest.mock import AsyncMock

import pytest

from heyducky.debugger.dap_client import DAPClient


@pytest.fixture
def mock_transport():
    """Create a mock transport."""
    transport = AsyncMock()
    transport.send = AsyncMock()
    transport.start = AsyncMock()
    transport.close = AsyncMock()
    return transport


@pytest.fixture
def client(mock_transport):
    """Create a DAPClient with mock transport."""
    c = DAPClient.__new__(DAPClient)
    c._transport = mock_transport
    c._seq = 1
    c._pending: dict = {}
    c._event_handlers: dict = {}
    c.state = "idle"
    c.current_file = None
    c.current_line = None
    c.thread_id = None
    c.breakpoints: dict = {}
    return c


@pytest.mark.asyncio
async def test_client_send_request(client, mock_transport):
    """Client sends request and tracks pending responses."""

    # Simulate response coming back
    async def fake_send(req):
        # Simulate the response arriving
        response_data = {
            "seq": 1,
            "type": "response",
            "request_seq": req.seq,
            "success": True,
            "command": req.command,
            "body": {},
        }
        await client._handle_message(response_data)

    mock_transport.send = fake_send
    resp = await client.send_request("initialize", {"clientID": "test"})
    assert resp.success is True
    assert resp.command == "initialize"


@pytest.mark.asyncio
async def test_client_event_handling(client):
    """Client dispatches events to registered handlers."""
    handler = AsyncMock()
    client.on_event("stopped", handler)

    event_data = {
        "seq": 5,
        "type": "event",
        "event": "stopped",
        "body": {"reason": "breakpoint", "threadId": 1},
    }
    await client._handle_message(event_data)
    handler.assert_called_once()


def test_client_initial_state(client):
    """Client starts in idle state."""
    assert client.state == "idle"
    assert client.current_file is None
    assert client.current_line is None
