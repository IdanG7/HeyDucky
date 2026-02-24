"""Tests for the DAP relay — bidirectional stdio-to-TCP message bridge."""

import asyncio
import json
import sys

import pytest

from heyducky.debugger.types import decode_messages
from heyducky.remote.relay import DAPRelay


def _make_dap_bytes(msg: dict) -> bytes:
    """Encode a dict as a Content-Length framed DAP message."""
    payload = json.dumps(msg).encode("utf-8")
    header = f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii")
    return header + payload


# We use a small Python script as a fake "adapter" that reads a DAP request
# from stdin and echoes back a DAP response on stdout.
ECHO_ADAPTER = [
    sys.executable,
    "-c",
    (
        "import sys, json\n"
        "while True:\n"
        "    header = ''\n"
        "    while True:\n"
        "        line = sys.stdin.buffer.readline()\n"
        "        if not line:\n"
        "            sys.exit(0)\n"
        "        header += line.decode('ascii')\n"
        "        if header.endswith('\\r\\n\\r\\n'):\n"
        "            break\n"
        "    length = int(header.split(': ', 1)[1].strip())\n"
        "    body = sys.stdin.buffer.read(length)\n"
        "    msg = json.loads(body)\n"
        "    resp = {'seq': msg['seq'], 'type': 'response',\n"
        "            'request_seq': msg['seq'], 'success': True,\n"
        "            'command': msg.get('command', ''), 'body': {'echo': True}}\n"
        "    payload = json.dumps(resp).encode('utf-8')\n"
        "    out = f'Content-Length: {len(payload)}\\r\\n\\r\\n'.encode('ascii') + payload\n"
        "    sys.stdout.buffer.write(out)\n"
        "    sys.stdout.buffer.flush()\n"
    ),
]


@pytest.fixture
async def relay():
    """Start a DAPRelay with the echo adapter and yield (relay, port)."""
    messages = []

    def on_message(direction, msg):
        messages.append((direction, msg))

    r = DAPRelay(
        adapter_cmd=ECHO_ADAPTER,
        host="127.0.0.1",
        port=0,
        on_message=on_message,
    )
    port = await r.start()
    yield r, port, messages
    await r.stop()


@pytest.mark.asyncio
async def test_relay_forwards_request_and_response(relay):
    """Send a DAP request through the relay and get the echo response back."""
    _r, port, _messages = relay

    reader, writer = await asyncio.open_connection("127.0.0.1", port)

    request = {
        "seq": 1,
        "type": "request",
        "command": "initialize",
        "arguments": {"clientID": "test"},
    }
    writer.write(_make_dap_bytes(request))
    await writer.drain()

    # Read the echoed response
    buf = b""
    for _ in range(20):
        chunk = await asyncio.wait_for(reader.read(4096), timeout=3.0)
        if not chunk:
            break
        buf += chunk
        msgs, buf = decode_messages(buf)
        if msgs:
            resp = msgs[0]
            assert resp["type"] == "response"
            assert resp["success"] is True
            assert resp["command"] == "initialize"
            assert resp["body"]["echo"] is True
            break
    else:
        pytest.fail("Did not receive response from relay")

    writer.close()


@pytest.mark.asyncio
async def test_relay_logs_messages(relay):
    """Verify the on_message callback captures messages flowing through."""
    _r, port, messages = relay

    reader, writer = await asyncio.open_connection("127.0.0.1", port)

    request = {
        "seq": 1,
        "type": "request",
        "command": "threads",
    }
    writer.write(_make_dap_bytes(request))
    await writer.drain()

    # Wait for the response to flow back
    buf = b""
    for _ in range(20):
        chunk = await asyncio.wait_for(reader.read(4096), timeout=3.0)
        if not chunk:
            break
        buf += chunk
        msgs, buf = decode_messages(buf)
        if msgs:
            break

    await asyncio.sleep(0.1)

    # Check logged messages
    directions = [d for d, _ in messages if d in ("client->adapter", "adapter->client")]
    assert "client->adapter" in directions
    assert "adapter->client" in directions

    writer.close()


@pytest.mark.asyncio
async def test_relay_rejects_second_client(relay):
    """Only one client connection should be accepted."""
    _r, port, _messages = relay

    _reader1, writer1 = await asyncio.open_connection("127.0.0.1", port)
    await asyncio.sleep(0.1)

    reader2, writer2 = await asyncio.open_connection("127.0.0.1", port)
    rejection = await asyncio.wait_for(reader2.read(4096), timeout=2.0)
    assert b"Only one client" in rejection

    writer1.close()
    writer2.close()


@pytest.mark.asyncio
async def test_relay_multiple_requests(relay):
    """Send multiple requests and verify all responses come back."""
    _r, port, _messages = relay

    reader, writer = await asyncio.open_connection("127.0.0.1", port)

    for seq in range(1, 4):
        request = {
            "seq": seq,
            "type": "request",
            "command": f"cmd{seq}",
        }
        writer.write(_make_dap_bytes(request))
    await writer.drain()

    # Read all 3 responses
    buf = b""
    all_responses = []
    for _ in range(50):
        try:
            chunk = await asyncio.wait_for(reader.read(4096), timeout=3.0)
        except asyncio.TimeoutError:
            break
        if not chunk:
            break
        buf += chunk
        msgs, buf = decode_messages(buf)
        all_responses.extend(msgs)
        if len(all_responses) >= 3:
            break

    assert len(all_responses) == 3
    for i, resp in enumerate(all_responses, 1):
        assert resp["request_seq"] == i
        assert resp["command"] == f"cmd{i}"

    writer.close()


@pytest.mark.asyncio
async def test_relay_client_connected_status(relay):
    """Status callback fires when client connects and disconnects."""
    _r, port, messages = relay

    _reader, writer = await asyncio.open_connection("127.0.0.1", port)
    await asyncio.sleep(0.2)

    status_events = [m for d, m in messages if d == "status"]
    connected = [e for e in status_events if e.get("event") == "client_connected"]
    assert len(connected) == 1

    writer.close()
    await asyncio.sleep(1.0)

    status_events = [m for d, m in messages if d == "status"]
    disconnected = [e for e in status_events if e.get("event") == "client_disconnected"]
    assert len(disconnected) >= 1


@pytest.mark.asyncio
async def test_relay_attach_inject():
    """Verify attach_inject merges processId into the attach request."""
    captured = []

    # Use an echo adapter that returns the request body so we can inspect it
    r = DAPRelay(
        adapter_cmd=ECHO_ADAPTER,
        host="127.0.0.1",
        port=0,
        on_message=lambda d, m: captured.append((d, m)),
        attach_inject={"processId": 9999, "customArg": "hello"},
    )
    port = await r.start()

    _reader, writer = await asyncio.open_connection("127.0.0.1", port)

    # Send an attach request WITHOUT processId
    request = {
        "seq": 1,
        "type": "request",
        "command": "attach",
        "arguments": {"justMyCode": False},
    }
    writer.write(_make_dap_bytes(request))
    await writer.drain()
    await asyncio.sleep(0.2)

    # Check that the relay injected processId before forwarding
    forwarded = [m for d, m in captured if d == "client->adapter" and m.get("command") == "attach"]
    assert len(forwarded) == 1
    assert forwarded[0]["arguments"]["processId"] == 9999
    assert forwarded[0]["arguments"]["customArg"] == "hello"
    assert forwarded[0]["arguments"]["justMyCode"] is False

    writer.close()
    await r.stop()


@pytest.mark.asyncio
async def test_get_adapter_command():
    """get_adapter_command returns a command for python and None for unknown."""
    from heyducky.remote.agent import get_adapter_command

    cmd = get_adapter_command("python")
    assert cmd is not None
    assert "debugpy" in " ".join(cmd)

    assert get_adapter_command("unknown_lang") is None
