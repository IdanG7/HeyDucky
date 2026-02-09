"""DAP message types and wire protocol encoding/decoding."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DAPRequest:
    """A DAP request message."""

    seq: int
    command: str
    arguments: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "seq": self.seq,
            "type": "request",
            "command": self.command,
        }
        if self.arguments:
            d["arguments"] = self.arguments
        return d


@dataclass
class DAPResponse:
    """A DAP response message."""

    seq: int
    request_seq: int
    success: bool
    command: str
    body: dict[str, Any] = field(default_factory=dict)
    message: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> DAPResponse:
        return cls(
            seq=data["seq"],
            request_seq=data.get("request_seq", 0),
            success=data.get("success", True),
            command=data.get("command", ""),
            body=data.get("body", {}),
            message=data.get("message", ""),
        )


@dataclass
class DAPEvent:
    """A DAP event message."""

    seq: int
    event: str
    body: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> DAPEvent:
        return cls(
            seq=data["seq"],
            event=data["event"],
            body=data.get("body", {}),
        )


def encode_message(request: DAPRequest) -> bytes:
    """Encode a DAP request into Content-Length framed bytes."""
    payload = json.dumps(request.to_dict()).encode("utf-8")
    header = f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii")
    return header + payload


def decode_messages(buffer: bytes) -> tuple[list[dict], bytes]:
    """Decode complete DAP messages from a byte buffer.

    Returns:
        Tuple of (list of parsed message dicts, remaining bytes).
    """
    messages: list[dict] = []
    while True:
        sep = buffer.find(b"\r\n\r\n")
        if sep == -1:
            break
        header = buffer[:sep].decode("ascii")
        content_length = int(header.split(": ", 1)[1])
        msg_start = sep + 4
        msg_end = msg_start + content_length
        if len(buffer) < msg_end:
            break  # Incomplete message
        payload = buffer[msg_start:msg_end]
        messages.append(json.loads(payload.decode("utf-8")))
        buffer = buffer[msg_end:]
    return messages, buffer
