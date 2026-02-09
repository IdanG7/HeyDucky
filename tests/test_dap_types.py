"""Tests for DAP message types."""

from voice_debugger.debugger.types import (
    DAPRequest,
    DAPResponse,
    DAPEvent,
    encode_message,
    decode_messages,
)


def test_dap_request_serialization():
    """DAPRequest serializes to correct JSON structure."""
    req = DAPRequest(seq=1, command="initialize", arguments={"clientID": "test"})
    d = req.to_dict()
    assert d["seq"] == 1
    assert d["type"] == "request"
    assert d["command"] == "initialize"
    assert d["arguments"]["clientID"] == "test"


def test_dap_response_from_dict():
    """DAPResponse parses from dict."""
    data = {
        "seq": 1,
        "type": "response",
        "request_seq": 1,
        "success": True,
        "command": "initialize",
        "body": {"supportsConfigurationDoneRequest": True},
    }
    resp = DAPResponse.from_dict(data)
    assert resp.success is True
    assert resp.command == "initialize"
    assert resp.body["supportsConfigurationDoneRequest"] is True


def test_dap_event_from_dict():
    """DAPEvent parses from dict."""
    data = {
        "seq": 5,
        "type": "event",
        "event": "stopped",
        "body": {"reason": "breakpoint", "threadId": 1},
    }
    event = DAPEvent.from_dict(data)
    assert event.event == "stopped"
    assert event.body["reason"] == "breakpoint"


def test_encode_message():
    """encode_message produces Content-Length framed bytes."""
    req = DAPRequest(seq=1, command="next", arguments={"threadId": 1})
    encoded = encode_message(req)
    assert encoded.startswith(b"Content-Length: ")
    assert b"\r\n\r\n" in encoded
    # JSON payload after header
    payload = encoded.split(b"\r\n\r\n", 1)[1]
    import json
    parsed = json.loads(payload)
    assert parsed["command"] == "next"


def test_decode_messages_single():
    """decode_messages extracts one complete message from buffer."""
    import json
    payload = json.dumps({"seq": 1, "type": "event", "event": "initialized", "body": {}})
    raw = f"Content-Length: {len(payload)}\r\n\r\n{payload}".encode()
    messages, remaining = decode_messages(raw)
    assert len(messages) == 1
    assert messages[0]["event"] == "initialized"
    assert remaining == b""


def test_decode_messages_partial():
    """decode_messages handles incomplete messages."""
    partial = b"Content-Length: 100\r\n\r\n{\"partial"
    messages, remaining = decode_messages(partial)
    assert len(messages) == 0
    assert remaining == partial


def test_decode_messages_multiple():
    """decode_messages extracts multiple messages from buffer."""
    import json
    msg1 = json.dumps({"seq": 1, "type": "event", "event": "initialized", "body": {}})
    msg2 = json.dumps({"seq": 2, "type": "event", "event": "stopped", "body": {"reason": "entry"}})
    raw = (
        f"Content-Length: {len(msg1)}\r\n\r\n{msg1}"
        f"Content-Length: {len(msg2)}\r\n\r\n{msg2}"
    ).encode()
    messages, remaining = decode_messages(raw)
    assert len(messages) == 2
    assert remaining == b""
