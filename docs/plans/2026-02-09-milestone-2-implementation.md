# Milestone 2: Debug Any Program with Voice - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a generic DAP debugger client to the voice-controlled TUI so users can debug Python, C++, Go, and Rust programs with voice commands, viewing source, variables, call stack, and output in a tabbed interface.

**Architecture:** Custom DAP client (~200 lines) speaks JSON-over-stdio/TCP to any debug adapter. Tabbed Textual TUI with 5 tabs (Source, Conversation, Variables, Call Stack, Output). AI tool calls now execute real debugger operations via a ToolExecutor bridge. Adapter registry maps languages to adapter launch commands.

**Tech Stack:** Python 3.10+, Textual, Rich (Syntax highlighting), debugpy, DAP protocol (JSON + Content-Length framing)

---

### Task 1: DAP Message Types

**Files:**
- Create: `heyducky/debugger/__init__.py`
- Create: `heyducky/debugger/types.py`
- Create: `tests/test_dap_types.py`

**Step 1: Write the failing test**

```python
# tests/test_dap_types.py
"""Tests for DAP message types."""

from heyducky.debugger.types import (
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
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/idang/Projects/TalkToMe && .venv/bin/python -m pytest tests/test_dap_types.py -v`
Expected: FAIL (ImportError)

**Step 3: Write the implementation**

```python
# heyducky/debugger/__init__.py
"""Debug adapter protocol modules."""
```

```python
# heyducky/debugger/types.py
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
```

**Step 4: Run tests**

Run: `cd /Users/idang/Projects/TalkToMe && .venv/bin/python -m pytest tests/test_dap_types.py -v`
Expected: All 7 tests PASS

**Step 5: Commit**

```bash
git add heyducky/debugger/ tests/test_dap_types.py
git commit -m "feat: add DAP message types and wire protocol encoding"
```

---

### Task 2: DAP Transport Layer

**Files:**
- Create: `heyducky/debugger/transport.py`
- Create: `tests/test_transport.py`

**Step 1: Write the failing test**

```python
# tests/test_transport.py
"""Tests for DAP transport layer."""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from heyducky.debugger.transport import StdioTransport, TCPTransport
from heyducky.debugger.types import DAPRequest, encode_message


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
```

**Step 2: Run test to verify failure**

Run: `cd /Users/idang/Projects/TalkToMe && .venv/bin/python -m pytest tests/test_transport.py -v`
Expected: FAIL (ImportError)

**Step 3: Write the implementation**

```python
# heyducky/debugger/transport.py
"""Transport layer for DAP communication (stdio and TCP)."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Callable, Awaitable

from heyducky.debugger.types import DAPRequest, encode_message, decode_messages


class BaseTransport(ABC):
    """Abstract base for DAP transports."""

    def __init__(self, on_message: Callable[[dict], Awaitable[None]]):
        self._on_message = on_message
        self._buffer = b""

    @abstractmethod
    async def start(self, **kwargs) -> None:
        """Start the transport connection."""
        ...

    @abstractmethod
    async def send(self, request: DAPRequest) -> None:
        """Send a DAP request."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close the transport."""
        ...

    async def _process_buffer(self) -> None:
        """Parse complete messages from the read buffer."""
        messages, self._buffer = decode_messages(self._buffer)
        for msg in messages:
            await self._on_message(msg)


class StdioTransport(BaseTransport):
    """DAP transport over subprocess stdin/stdout."""

    def __init__(self, on_message: Callable[[dict], Awaitable[None]]):
        super().__init__(on_message)
        self._process: asyncio.subprocess.Process | None = None
        self._reader_task: asyncio.Task | None = None

    async def start(self, command: list[str], **kwargs) -> None:
        """Launch debug adapter as subprocess."""
        self._process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._reader_task = asyncio.create_task(self._read_loop())

    async def send(self, request: DAPRequest) -> None:
        """Send a request to the adapter's stdin."""
        if self._process is None or self._process.stdin is None:
            raise RuntimeError("Transport not started")
        data = encode_message(request)
        self._process.stdin.write(data)
        await self._process.stdin.drain()

    async def close(self) -> None:
        """Terminate the adapter process."""
        if self._reader_task:
            self._reader_task.cancel()
        if self._process:
            self._process.terminate()
            await self._process.wait()

    async def _read_loop(self) -> None:
        """Read from adapter stdout and dispatch messages."""
        try:
            while self._process and self._process.stdout:
                chunk = await self._process.stdout.read(4096)
                if not chunk:
                    break
                self._buffer += chunk
                await self._process_buffer()
        except asyncio.CancelledError:
            pass


class TCPTransport(BaseTransport):
    """DAP transport over TCP socket."""

    def __init__(self, on_message: Callable[[dict], Awaitable[None]]):
        super().__init__(on_message)
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._reader_task: asyncio.Task | None = None

    async def start(self, host: str = "127.0.0.1", port: int = 0, **kwargs) -> None:
        """Connect to debug adapter over TCP."""
        self._reader, self._writer = await asyncio.open_connection(host, port)
        self._reader_task = asyncio.create_task(self._read_loop())

    async def send(self, request: DAPRequest) -> None:
        """Send a request over TCP."""
        if self._writer is None:
            raise RuntimeError("Transport not started")
        data = encode_message(request)
        self._writer.write(data)
        await self._writer.drain()

    async def close(self) -> None:
        """Close the TCP connection."""
        if self._reader_task:
            self._reader_task.cancel()
        if self._writer:
            self._writer.close()

    async def _read_loop(self) -> None:
        """Read from TCP socket and dispatch messages."""
        try:
            while self._reader:
                chunk = await self._reader.read(4096)
                if not chunk:
                    break
                self._buffer += chunk
                await self._process_buffer()
        except asyncio.CancelledError:
            pass
```

**Step 4: Run tests**

Run: `cd /Users/idang/Projects/TalkToMe && .venv/bin/python -m pytest tests/test_transport.py -v`
Expected: All 2 tests PASS

**Step 5: Commit**

```bash
git add heyducky/debugger/transport.py tests/test_transport.py
git commit -m "feat: add stdio and TCP transports for DAP communication"
```

---

### Task 3: DAP Client Core

**Files:**
- Create: `heyducky/debugger/dap_client.py`
- Create: `tests/test_dap_client.py`

**Step 1: Write the failing test**

```python
# tests/test_dap_client.py
"""Tests for DAP client."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from heyducky.debugger.dap_client import DAPClient
from heyducky.debugger.types import DAPResponse, DAPEvent


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
```

**Step 2: Run test to verify failure**

Run: `cd /Users/idang/Projects/TalkToMe && .venv/bin/python -m pytest tests/test_dap_client.py -v`
Expected: FAIL (ImportError)

**Step 3: Write the implementation**

```python
# heyducky/debugger/dap_client.py
"""Generic DAP client for debugging any language."""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Awaitable

from heyducky.debugger.types import DAPRequest, DAPResponse, DAPEvent
from heyducky.debugger.transport import BaseTransport, StdioTransport, TCPTransport


class DAPClient:
    """Debug Adapter Protocol client.

    Communicates with any DAP-compliant debug adapter over stdio or TCP.
    """

    def __init__(self, transport: BaseTransport | None = None):
        self._transport = transport
        self._seq = 1
        self._pending: dict[int, asyncio.Future[DAPResponse]] = {}
        self._event_handlers: dict[str, list[Callable]] = {}

        # Debugger state
        self.state: str = "idle"  # idle, running, paused, stopped
        self.current_file: str | None = None
        self.current_line: int | None = None
        self.thread_id: int | None = None
        self.breakpoints: dict[str, list[int]] = {}  # file -> [lines]

    async def start_stdio(self, command: list[str]) -> None:
        """Start a debug adapter as a subprocess."""
        self._transport = StdioTransport(on_message=self._handle_message)
        await self._transport.start(command=command)

    async def start_tcp(self, host: str, port: int) -> None:
        """Connect to a debug adapter over TCP."""
        self._transport = TCPTransport(on_message=self._handle_message)
        await self._transport.start(host=host, port=port)

    async def send_request(
        self, command: str, arguments: dict[str, Any] | None = None
    ) -> DAPResponse:
        """Send a DAP request and wait for the response."""
        if self._transport is None:
            raise RuntimeError("No transport connected")

        seq = self._seq
        self._seq += 1

        request = DAPRequest(seq=seq, command=command, arguments=arguments or {})
        future: asyncio.Future[DAPResponse] = asyncio.get_event_loop().create_future()
        self._pending[seq] = future

        await self._transport.send(request)
        return await future

    def on_event(self, event_name: str, handler: Callable) -> None:
        """Register a handler for a specific DAP event."""
        self._event_handlers.setdefault(event_name, []).append(handler)

    async def _handle_message(self, data: dict) -> None:
        """Route incoming messages to the appropriate handler."""
        msg_type = data.get("type")

        if msg_type == "response":
            resp = DAPResponse.from_dict(data)
            future = self._pending.pop(resp.request_seq, None)
            if future and not future.done():
                future.set_result(resp)

        elif msg_type == "event":
            event = DAPEvent.from_dict(data)
            await self._dispatch_event(event)

    async def _dispatch_event(self, event: DAPEvent) -> None:
        """Dispatch an event to registered handlers."""
        # Update internal state for key events
        if event.event == "stopped":
            self.state = "paused"
            self.thread_id = event.body.get("threadId")
        elif event.event == "continued":
            self.state = "running"
        elif event.event == "terminated":
            self.state = "stopped"

        for handler in self._event_handlers.get(event.event, []):
            await handler(event)

    # --- High-level debugger operations ---

    async def initialize(self) -> DAPResponse:
        """Send the DAP initialize request."""
        self.state = "initializing"
        resp = await self.send_request("initialize", {
            "clientID": "ducky",
            "clientName": "HeyDucky",
            "adapterID": "ducky",
            "pathFormat": "path",
            "linesStartAt1": True,
            "columnsStartAt1": True,
        })
        return resp

    async def launch(self, program: str, **kwargs) -> DAPResponse:
        """Launch a program for debugging."""
        args = {"program": program, "cwd": str(__import__("pathlib").Path(program).parent)}
        args.update(kwargs)
        resp = await self.send_request("launch", args)
        return resp

    async def configuration_done(self) -> DAPResponse:
        """Signal that configuration is complete."""
        self.state = "running"
        return await self.send_request("configurationDone")

    async def set_breakpoint(self, file: str, line: int, condition: str = "") -> DAPResponse:
        """Set a breakpoint at the given file and line."""
        lines = self.breakpoints.setdefault(file, [])
        if line not in lines:
            lines.append(line)

        breakpoint_defs = [{"line": ln} for ln in lines]
        if condition:
            breakpoint_defs[-1]["condition"] = condition

        resp = await self.send_request("setBreakpoints", {
            "source": {"path": file},
            "breakpoints": breakpoint_defs,
        })
        return resp

    async def continue_execution(self, thread_id: int | None = None) -> DAPResponse:
        """Resume execution."""
        tid = thread_id or self.thread_id or 1
        self.state = "running"
        return await self.send_request("continue", {"threadId": tid})

    async def step_over(self, thread_id: int | None = None) -> DAPResponse:
        """Step over the current line."""
        tid = thread_id or self.thread_id or 1
        self.state = "running"
        return await self.send_request("next", {"threadId": tid})

    async def step_into(self, thread_id: int | None = None) -> DAPResponse:
        """Step into the current line."""
        tid = thread_id or self.thread_id or 1
        self.state = "running"
        return await self.send_request("stepIn", {"threadId": tid})

    async def step_out(self, thread_id: int | None = None) -> DAPResponse:
        """Step out of the current function."""
        tid = thread_id or self.thread_id or 1
        self.state = "running"
        return await self.send_request("stepOut", {"threadId": tid})

    async def get_stack_trace(self, thread_id: int | None = None) -> DAPResponse:
        """Get the call stack for a thread."""
        tid = thread_id or self.thread_id or 1
        return await self.send_request("stackTrace", {"threadId": tid})

    async def get_scopes(self, frame_id: int) -> DAPResponse:
        """Get scopes for a stack frame."""
        return await self.send_request("scopes", {"frameId": frame_id})

    async def get_variables(self, variables_reference: int) -> DAPResponse:
        """Get variables for a scope."""
        return await self.send_request("variables", {"variablesReference": variables_reference})

    async def evaluate(self, expression: str, frame_id: int | None = None) -> DAPResponse:
        """Evaluate an expression."""
        args: dict[str, Any] = {"expression": expression, "context": "repl"}
        if frame_id is not None:
            args["frameId"] = frame_id
        return await self.send_request("evaluate", args)

    async def disconnect(self) -> None:
        """Disconnect from the debug adapter."""
        try:
            await self.send_request("disconnect", {"terminateDebuggee": True})
        except Exception:
            pass
        if self._transport:
            await self._transport.close()
        self.state = "stopped"
```

**Step 4: Run tests**

Run: `cd /Users/idang/Projects/TalkToMe && .venv/bin/python -m pytest tests/test_dap_client.py -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add heyducky/debugger/dap_client.py tests/test_dap_client.py
git commit -m "feat: add generic DAP client with debugger operations"
```

---

### Task 4: Adapter Registry

**Files:**
- Create: `heyducky/debugger/adapters.py`
- Create: `tests/test_adapters.py`

**Step 1: Write the failing test**

```python
# tests/test_adapters.py
"""Tests for debug adapter registry."""

import pytest
from heyducky.debugger.adapters import (
    AdapterConfig,
    ADAPTER_REGISTRY,
    detect_language,
    get_adapter_config,
)


def test_adapter_registry_has_python():
    """Registry includes Python adapter."""
    assert "python" in ADAPTER_REGISTRY
    cfg = ADAPTER_REGISTRY["python"]
    assert cfg.transport == "stdio"
    assert "debugpy" in " ".join(cfg.command)


def test_adapter_registry_has_cpp():
    """Registry includes C++ adapter."""
    assert "cpp" in ADAPTER_REGISTRY


def test_adapter_registry_has_go():
    """Registry includes Go adapter."""
    assert "go" in ADAPTER_REGISTRY


def test_adapter_registry_has_rust():
    """Registry includes Rust adapter."""
    assert "rust" in ADAPTER_REGISTRY


def test_detect_language_python():
    """Detects Python from .py extension."""
    assert detect_language("script.py") == "python"
    assert detect_language("/path/to/main.py") == "python"


def test_detect_language_cpp():
    """Detects C++ from .cpp/.c/.h extensions."""
    assert detect_language("main.cpp") == "cpp"
    assert detect_language("lib.c") == "cpp"


def test_detect_language_go():
    """Detects Go from .go extension."""
    assert detect_language("main.go") == "go"


def test_detect_language_rust():
    """Detects Rust from .rs extension."""
    assert detect_language("main.rs") == "rust"


def test_detect_language_unknown():
    """Returns None for unknown extensions."""
    assert detect_language("file.xyz") is None


def test_get_adapter_config():
    """get_adapter_config returns config for known languages."""
    cfg = get_adapter_config("python")
    assert isinstance(cfg, AdapterConfig)
    assert cfg.transport == "stdio"


def test_get_adapter_config_unknown():
    """get_adapter_config returns None for unknown languages."""
    assert get_adapter_config("brainfuck") is None
```

**Step 2: Run test to verify failure**

Run: `cd /Users/idang/Projects/TalkToMe && .venv/bin/python -m pytest tests/test_adapters.py -v`
Expected: FAIL (ImportError)

**Step 3: Write the implementation**

```python
# heyducky/debugger/adapters.py
"""Debug adapter registry - maps languages to adapter launch configs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AdapterConfig:
    """Configuration for launching a debug adapter."""

    command: list[str]
    transport: str = "stdio"  # "stdio" or "tcp"
    host: str = "127.0.0.1"
    port: int = 0
    launch_args: dict[str, Any] = field(default_factory=dict)


ADAPTER_REGISTRY: dict[str, AdapterConfig] = {
    "python": AdapterConfig(
        command=["python", "-m", "debugpy.adapter"],
        transport="stdio",
        launch_args={"justMyCode": False, "console": "internalConsole"},
    ),
    "cpp": AdapterConfig(
        command=["lldb-dap"],
        transport="stdio",
    ),
    "go": AdapterConfig(
        command=["dlv", "dap"],
        transport="stdio",
    ),
    "rust": AdapterConfig(
        command=["codelldb"],
        transport="tcp",
        port=13000,
    ),
}

_EXTENSION_MAP: dict[str, str] = {
    ".py": "python",
    ".c": "cpp",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".h": "cpp",
    ".hpp": "cpp",
    ".go": "go",
    ".rs": "rust",
}


def detect_language(file_path: str) -> str | None:
    """Detect programming language from file extension."""
    ext = Path(file_path).suffix.lower()
    return _EXTENSION_MAP.get(ext)


def get_adapter_config(language: str) -> AdapterConfig | None:
    """Get adapter configuration for a language."""
    return ADAPTER_REGISTRY.get(language)
```

**Step 4: Run tests**

Run: `cd /Users/idang/Projects/TalkToMe && .venv/bin/python -m pytest tests/test_adapters.py -v`
Expected: All 12 tests PASS

**Step 5: Commit**

```bash
git add heyducky/debugger/adapters.py tests/test_adapters.py
git commit -m "feat: add debug adapter registry for Python, C++, Go, Rust"
```

---

### Task 5: Upgraded Source View Widget

**Files:**
- Modify: `heyducky/widgets/source_view.py`
- Create: `tests/test_source_view.py`

**Step 1: Write the failing test**

```python
# tests/test_source_view.py
"""Tests for upgraded source view widget."""

import pytest
from heyducky.widgets.source_view import SourceView


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
```

**Step 2: Run test to verify failure**

Run: `cd /Users/idang/Projects/TalkToMe && .venv/bin/python -m pytest tests/test_source_view.py -v`
Expected: FAIL (SourceView has no load_source method)

**Step 3: Rewrite source_view.py**

```python
# heyducky/widgets/source_view.py
"""Source code view with syntax highlighting and debug markers."""

from __future__ import annotations

from pathlib import Path

from rich.syntax import Syntax
from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static


class SourceView(Static):
    """Displays source code with syntax highlighting, breakpoints, and current line."""

    DEFAULT_CSS = """
    SourceView {
        height: 1fr;
        border: solid $primary;
        overflow-y: auto;
    }
    """

    current_line = reactive(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.file_path: str | None = None
        self._source_lines: list[str] = []
        self._source_text: str = ""
        self.breakpoint_lines: set[int] = set()

    def load_source(self, file_path: str, content: str | None = None) -> None:
        """Load a source file for display."""
        self.file_path = file_path
        if content is None:
            try:
                content = Path(file_path).read_text()
            except OSError:
                content = f"# Could not read {file_path}"
        self._source_text = content
        self._source_lines = content.split("\n")
        self._refresh_display()

    def set_current_line(self, line: int) -> None:
        """Set the current execution line."""
        self.current_line = line
        self._refresh_display()

    def toggle_breakpoint(self, line: int) -> None:
        """Toggle a breakpoint on a line."""
        if line in self.breakpoint_lines:
            self.breakpoint_lines.discard(line)
        else:
            self.breakpoint_lines.add(line)
        self._refresh_display()

    def _refresh_display(self) -> None:
        """Re-render the source display."""
        if not self._source_text or not self.file_path:
            self.update("No file loaded. Start a debug session to view source.")
            return

        # Build annotated source with gutter
        lines: list[str] = []
        for i, line in enumerate(self._source_lines, 1):
            bp = "\u25cf " if i in self.breakpoint_lines else "  "
            arrow = "\u2192" if i == self.current_line else " "
            lines.append(f"{bp}{arrow} {i:4d} | {line}")

        self.update("\n".join(lines))
```

**Step 4: Run tests**

Run: `cd /Users/idang/Projects/TalkToMe && .venv/bin/python -m pytest tests/test_source_view.py -v`
Expected: All 4 tests PASS

**Step 5: Run ALL tests for regressions**

Run: `cd /Users/idang/Projects/TalkToMe && .venv/bin/python -m pytest tests/ -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add heyducky/widgets/source_view.py tests/test_source_view.py
git commit -m "feat: upgrade source view with debug markers and line tracking"
```

---

### Task 6: Variables, Call Stack, and Debug Output Widgets

**Files:**
- Create: `heyducky/widgets/variables.py`
- Create: `heyducky/widgets/call_stack.py`
- Create: `heyducky/widgets/debug_output.py`
- Modify: `heyducky/widgets/__init__.py`

**Step 1: Write the widgets**

```python
# heyducky/widgets/variables.py
"""Variables panel showing current scope."""

from __future__ import annotations

from textual.widgets import RichLog
from rich.text import Text


class VariablesView(RichLog):
    """Displays variables for the current debug scope."""

    DEFAULT_CSS = """
    VariablesView {
        height: 1fr;
        border: solid $primary;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(markup=True, wrap=True, **kwargs)

    def update_variables(self, variables: list[dict]) -> None:
        """Update the displayed variables.

        Args:
            variables: List of dicts with keys: name, value, type.
        """
        self.clear()
        if not variables:
            self.write(Text("No variables in scope.", style="dim italic"))
            return
        for var in variables:
            line = Text()
            line.append(f"  {var.get('name', '?')}", style="bold cyan")
            line.append(f" = ", style="dim")
            line.append(f"{var.get('value', '?')}", style="white")
            vtype = var.get("type", "")
            if vtype:
                line.append(f"  ({vtype})", style="dim green")
            self.write(line)
```

```python
# heyducky/widgets/call_stack.py
"""Call stack panel showing stack frames."""

from __future__ import annotations

from textual.widgets import RichLog
from rich.text import Text


class CallStackView(RichLog):
    """Displays the current call stack."""

    DEFAULT_CSS = """
    CallStackView {
        height: 1fr;
        border: solid $primary;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(markup=True, wrap=True, **kwargs)

    def update_frames(self, frames: list[dict]) -> None:
        """Update the displayed stack frames.

        Args:
            frames: List of dicts with keys: name, source (path), line.
        """
        self.clear()
        if not frames:
            self.write(Text("No stack frames.", style="dim italic"))
            return
        for i, frame in enumerate(frames):
            line = Text()
            marker = "\u25b6 " if i == 0 else "  "
            style = "bold" if i == 0 else ""
            name = frame.get("name", "?")
            source = frame.get("source", {})
            path = source.get("path", "?") if isinstance(source, dict) else str(source)
            lineno = frame.get("line", "?")
            line.append(f"{marker}{name}", style=style)
            line.append(f"  {path}:{lineno}", style="dim")
            self.write(line)
```

```python
# heyducky/widgets/debug_output.py
"""Debug output panel showing program stdout/stderr."""

from __future__ import annotations

from textual.widgets import RichLog
from rich.text import Text


class DebugOutputView(RichLog):
    """Displays program output from the debug session."""

    DEFAULT_CSS = """
    DebugOutputView {
        height: 1fr;
        border: solid $primary;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(markup=True, wrap=True, **kwargs)

    def add_stdout(self, text: str) -> None:
        """Add program stdout."""
        self.write(Text(text))

    def add_stderr(self, text: str) -> None:
        """Add program stderr."""
        self.write(Text(text, style="red"))
```

**Step 2: Update widgets/__init__.py**

```python
# heyducky/widgets/__init__.py
"""TUI widget components."""

from heyducky.widgets.source_view import SourceView
from heyducky.widgets.conversation import ConversationView
from heyducky.widgets.status_bar import VoiceStatusBar
from heyducky.widgets.variables import VariablesView
from heyducky.widgets.call_stack import CallStackView
from heyducky.widgets.debug_output import DebugOutputView

__all__ = [
    "SourceView",
    "ConversationView",
    "VoiceStatusBar",
    "VariablesView",
    "CallStackView",
    "DebugOutputView",
]
```

**Step 3: Verify imports**

Run: `cd /Users/idang/Projects/TalkToMe && .venv/bin/python -c "from heyducky.widgets import VariablesView, CallStackView, DebugOutputView; print('OK')"`
Expected: `OK`

**Step 4: Run ALL tests**

Run: `cd /Users/idang/Projects/TalkToMe && .venv/bin/python -m pytest tests/ -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add heyducky/widgets/
git commit -m "feat: add variables, call stack, and debug output widgets"
```

---

### Task 7: Tabbed TUI Layout

**Files:**
- Modify: `heyducky/app.py`
- Modify: `heyducky/widgets/status_bar.py`

This is the biggest change — replacing the simple vertical layout with a tabbed interface using Textual's `TabbedContent`.

**Step 1: Update status_bar.py to show debug state**

```python
# heyducky/widgets/status_bar.py
"""Status bar widget showing mic state, debug state, provider, and cost."""

from __future__ import annotations

from textual.widgets import Static
from textual.reactive import reactive


class VoiceStatusBar(Static):
    """Status bar showing recording state, debug state, AI provider, and session cost."""

    DEFAULT_CSS = """
    VoiceStatusBar {
        height: 3;
        background: $boost;
        padding: 0 2;
        content-align: left middle;
    }
    """

    is_recording = reactive(False)
    provider_name = reactive("Claude")
    session_cost = reactive(0.0)
    debug_state = reactive("idle")
    debug_file = reactive("")
    debug_line = reactive(0)

    def render(self) -> str:
        mic = "[bold red]Recording...[/]" if self.is_recording else "[dim]Space: Talk[/]"
        cost = f"${self.session_cost:.4f}"

        if self.debug_state == "paused":
            dbg = f"[bold yellow]Paused[/] at {self.debug_file}:{self.debug_line}"
        elif self.debug_state == "running":
            dbg = "[bold green]Running[/]"
        elif self.debug_state == "stopped":
            dbg = "[dim]Stopped[/]"
        else:
            dbg = "[dim]No debug session[/]"

        return f"{mic}  |  {dbg}  |  {self.provider_name}  |  {cost}"
```

**Step 2: Rewrite app.py with tabbed layout**

```python
# heyducky/app.py
"""Main Textual TUI application with tabbed debug interface."""

from __future__ import annotations

import os

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer, TabbedContent, TabPane

from heyducky.config import Config
from heyducky.widgets import (
    SourceView,
    ConversationView,
    VoiceStatusBar,
    VariablesView,
    CallStackView,
    DebugOutputView,
)


class HeyDuckyApp(App):
    """Voice-controlled AI debugging assistant."""

    TITLE = "HeyDucky"
    SUB_TITLE = "AI Pair Programming"

    CSS = """
    Screen {
        background: $surface;
    }

    TabbedContent {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("space", "toggle_recording", "Talk", show=True),
        Binding("1", "show_tab('source')", "Source", show=False),
        Binding("2", "show_tab('conversation')", "Chat", show=False),
        Binding("3", "show_tab('variables')", "Vars", show=False),
        Binding("4", "show_tab('callstack')", "Stack", show=False),
        Binding("5", "show_tab('output')", "Output", show=False),
        Binding("f5", "debug_continue", "Continue", show=False),
        Binding("f10", "debug_step_over", "Step Over", show=False),
        Binding("f11", "debug_step_into", "Step Into", show=False),
    ]

    def __init__(self, target: str | None = None):
        super().__init__()
        self.config = Config.load()
        self._target = target
        self._voice = None
        self._orchestrator = None
        self._dap_client = None

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(initial="conversation"):
            with TabPane("Source", id="source"):
                yield SourceView(id="source-view")
            with TabPane("Conversation", id="conversation"):
                yield ConversationView(id="conversation-view")
            with TabPane("Variables", id="variables"):
                yield VariablesView(id="variables-view")
            with TabPane("Call Stack", id="callstack"):
                yield CallStackView(id="callstack-view")
            with TabPane("Output", id="output"):
                yield DebugOutputView(id="output-view")
        yield VoiceStatusBar(id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize components after mount."""
        conv = self.query_one("#conversation-view", ConversationView)
        conv.add_system_message("Welcome to HeyDucky. Press Space to talk.")
        conv.add_system_message("Tabs: 1=Source 2=Chat 3=Vars 4=Stack 5=Output")
        self._init_components()

    def _init_components(self) -> None:
        """Initialize voice and AI components."""
        self._init_voice_worker()

        api_key = self.config.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if api_key:
            from heyducky.ai.claude import ClaudeProvider
            from heyducky.ai.orchestrator import Orchestrator

            provider = ClaudeProvider(api_key=api_key, model=self.config.ai_model)
            self._orchestrator = Orchestrator(provider=provider)
        else:
            conv = self.query_one("#conversation-view", ConversationView)
            conv.add_system_message(
                "No API key configured. Set ANTHROPIC_API_KEY env var or run with --setup."
            )

    @work(thread=True, exclusive=True, group="voice-init")
    def _init_voice_worker(self) -> None:
        """Load Whisper model in background thread."""
        try:
            from heyducky.voice import VoiceHandler

            self._voice = VoiceHandler(
                whisper_model=self.config.whisper_model,
                sample_rate=self.config.sample_rate,
                silence_threshold=self.config.silence_threshold,
            )
            self.call_from_thread(self._on_voice_ready)
        except Exception as e:
            self.call_from_thread(self._on_voice_error, str(e))

    def _on_voice_ready(self) -> None:
        conv = self.query_one("#conversation-view", ConversationView)
        conv.add_system_message("Voice ready. Press Space to talk.")

    def _on_voice_error(self, error: str) -> None:
        conv = self.query_one("#conversation-view", ConversationView)
        conv.add_system_message(f"Voice init failed: {error}")

    def action_show_tab(self, tab_id: str) -> None:
        """Switch to a tab by id."""
        self.query_one(TabbedContent).active = tab_id

    def action_toggle_recording(self) -> None:
        """Toggle voice recording on/off."""
        if self._voice is None:
            conv = self.query_one("#conversation-view", ConversationView)
            conv.add_system_message("Voice not ready yet. Please wait...")
            return

        status = self.query_one("#status-bar", VoiceStatusBar)

        if self._voice.is_recording:
            status.is_recording = False
            self._process_recording()
        else:
            self._voice.start_recording()
            status.is_recording = True

    def action_debug_continue(self) -> None:
        """Continue debug execution."""
        if self._dap_client:
            self._run_debug_action("continue_execution")

    def action_debug_step_over(self) -> None:
        """Step over in debugger."""
        if self._dap_client:
            self._run_debug_action("step_over")

    def action_debug_step_into(self) -> None:
        """Step into in debugger."""
        if self._dap_client:
            self._run_debug_action("step_into")

    @work(thread=True, exclusive=True, group="debug-action")
    def _run_debug_action(self, action: str) -> None:
        """Execute a debug action in a worker thread."""
        import asyncio
        client = self._dap_client
        if client is None:
            return
        coro = getattr(client, action)()
        asyncio.run(coro)

    @work(thread=True, exclusive=True, group="voice-process")
    def _process_recording(self) -> None:
        """Stop recording, transcribe, and send to AI."""
        audio = self._voice.stop_recording()
        if len(audio) == 0:
            self.call_from_thread(self._show_system_message, "No speech detected.")
            return

        transcript = self._voice.transcribe(audio)
        if not transcript:
            self.call_from_thread(self._show_system_message, "Could not transcribe audio.")
            return

        self.call_from_thread(self._show_user_message, transcript)

        if self._orchestrator is None:
            self.call_from_thread(self._show_system_message, "No AI provider configured.")
            return

        import asyncio
        response = asyncio.run(self._orchestrator.chat(transcript))

        # Handle tool calls
        for tc in response.tool_calls:
            self.call_from_thread(self._show_tool_call, tc.name, tc.arguments)

        self.call_from_thread(self._show_ai_message, response.text)
        self.call_from_thread(self._update_cost, self._orchestrator.total_cost)

    def _show_user_message(self, text: str) -> None:
        self.query_one("#conversation-view", ConversationView).add_user_message(text)

    def _show_ai_message(self, text: str) -> None:
        self.query_one("#conversation-view", ConversationView).add_ai_message(text)

    def _show_system_message(self, text: str) -> None:
        self.query_one("#conversation-view", ConversationView).add_system_message(text)

    def _show_tool_call(self, name: str, args: dict) -> None:
        self.query_one("#conversation-view", ConversationView).add_tool_message(name, args)

    def _update_cost(self, cost: float) -> None:
        self.query_one("#status-bar", VoiceStatusBar).session_cost = cost
```

**Step 3: Update __main__.py to accept target program**

```python
# heyducky/__main__.py
"""CLI entry point for ducky."""

import argparse


def main():
    parser = argparse.ArgumentParser(
        description="Voice-controlled AI debugging assistant"
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="Program to debug (e.g., script.py)",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Run first-time setup wizard",
    )
    args = parser.parse_args()

    if args.setup:
        _run_setup()
        return

    from heyducky.app import HeyDuckyApp

    app = HeyDuckyApp(target=args.target)
    app.run()


def _run_setup():
    """Interactive setup wizard."""
    from heyducky.config import Config

    print("HeyDucky Setup")
    print("=" * 40)

    config = Config.load()

    api_key_display = config.api_key[:8] if config.api_key else "not set"
    api_key = input(f"Anthropic API key [{api_key_display}]: ").strip()
    if api_key:
        config.api_key = api_key

    model = input(f"Model [{config.ai_model}]: ").strip()
    if model:
        config.ai_model = model

    whisper = input(f"Whisper model [{config.whisper_model}]: ").strip()
    if whisper:
        config.whisper_model = whisper

    config.save()
    print("\nConfig saved. Run 'ducky' to start.")


if __name__ == "__main__":
    main()
```

**Step 4: Update integration tests for new widget IDs**

The tests in `tests/test_app.py` reference `#conversation` and `#status-bar`. The conversation ID changed to `#conversation-view`. Update the test.

```python
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
```

**Step 5: Run ALL tests**

Run: `cd /Users/idang/Projects/TalkToMe && .venv/bin/python -m pytest tests/ -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add heyducky/app.py heyducky/__main__.py heyducky/widgets/status_bar.py tests/test_app.py
git commit -m "feat: add tabbed TUI layout with debug panels and keyboard shortcuts"
```

---

### Task 8: Tool Executor (Bridge AI to Debugger)

**Files:**
- Create: `heyducky/debugger/tool_executor.py`
- Create: `tests/test_tool_executor.py`
- Modify: `heyducky/ai/functions.py` (add read_source tool)

**Step 1: Write the failing test**

```python
# tests/test_tool_executor.py
"""Tests for tool executor bridging AI tool calls to debugger."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from heyducky.debugger.tool_executor import ToolExecutor
from heyducky.ai.provider import ToolCall
from heyducky.debugger.types import DAPResponse


@pytest.fixture
def mock_dap():
    """Create a mock DAP client."""
    client = AsyncMock()
    client.set_breakpoint = AsyncMock(
        return_value=DAPResponse(seq=1, request_seq=1, success=True, command="setBreakpoints", body={
            "breakpoints": [{"verified": True, "line": 10}]
        })
    )
    client.step_over = AsyncMock(
        return_value=DAPResponse(seq=2, request_seq=2, success=True, command="next", body={})
    )
    client.continue_execution = AsyncMock(
        return_value=DAPResponse(seq=3, request_seq=3, success=True, command="continue", body={})
    )
    client.evaluate = AsyncMock(
        return_value=DAPResponse(seq=4, request_seq=4, success=True, command="evaluate", body={
            "result": "42", "type": "int"
        })
    )
    client.get_stack_trace = AsyncMock(
        return_value=DAPResponse(seq=5, request_seq=5, success=True, command="stackTrace", body={
            "stackFrames": [{"name": "main", "line": 10, "source": {"path": "test.py"}}]
        })
    )
    return client


@pytest.mark.asyncio
async def test_execute_set_breakpoint(mock_dap):
    """ToolExecutor handles set_breakpoint tool call."""
    executor = ToolExecutor(mock_dap)
    result = await executor.execute(
        ToolCall(id="t1", name="set_breakpoint", arguments={"file": "test.py", "line": 10})
    )
    mock_dap.set_breakpoint.assert_called_once_with("test.py", 10, "")
    assert "verified" in result.lower() or "set" in result.lower()


@pytest.mark.asyncio
async def test_execute_step_over(mock_dap):
    """ToolExecutor handles step_over."""
    executor = ToolExecutor(mock_dap)
    result = await executor.execute(
        ToolCall(id="t2", name="step_over", arguments={})
    )
    mock_dap.step_over.assert_called_once()


@pytest.mark.asyncio
async def test_execute_inspect_variable(mock_dap):
    """ToolExecutor handles inspect_variable via evaluate."""
    executor = ToolExecutor(mock_dap)
    result = await executor.execute(
        ToolCall(id="t3", name="inspect_variable", arguments={"name": "x"})
    )
    mock_dap.evaluate.assert_called_once_with("x", None)
    assert "42" in result


@pytest.mark.asyncio
async def test_execute_unknown_tool(mock_dap):
    """ToolExecutor handles unknown tool names gracefully."""
    executor = ToolExecutor(mock_dap)
    result = await executor.execute(
        ToolCall(id="t4", name="nonexistent_tool", arguments={})
    )
    assert "unknown" in result.lower()
```

**Step 2: Run test to verify failure**

Run: `cd /Users/idang/Projects/TalkToMe && .venv/bin/python -m pytest tests/test_tool_executor.py -v`
Expected: FAIL (ImportError)

**Step 3: Write the implementation**

```python
# heyducky/debugger/tool_executor.py
"""Bridge between AI tool calls and DAP client operations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from heyducky.debugger.dap_client import DAPClient
    from heyducky.ai.provider import ToolCall


class ToolExecutor:
    """Executes AI tool calls against the DAP client."""

    def __init__(self, dap_client: DAPClient):
        self._dap = dap_client

    async def execute(self, tool_call: ToolCall) -> str:
        """Execute a tool call and return a human-readable result string."""
        name = tool_call.name
        args = tool_call.arguments

        handler = getattr(self, f"_exec_{name}", None)
        if handler is None:
            return f"Unknown tool: {name}"
        return await handler(args)

    async def _exec_set_breakpoint(self, args: dict) -> str:
        resp = await self._dap.set_breakpoint(
            args["file"], args["line"], args.get("condition", "")
        )
        if resp.success:
            bps = resp.body.get("breakpoints", [])
            verified = all(bp.get("verified", False) for bp in bps)
            status = "verified" if verified else "pending"
            return f"Breakpoint set at {args['file']}:{args['line']} ({status})"
        return f"Failed to set breakpoint: {resp.message}"

    async def _exec_inspect_variable(self, args: dict) -> str:
        resp = await self._dap.evaluate(args["name"], None)
        if resp.success:
            val = resp.body.get("result", "?")
            vtype = resp.body.get("type", "")
            return f"{args['name']} = {val}" + (f" ({vtype})" if vtype else "")
        return f"Could not inspect {args['name']}: {resp.message}"

    async def _exec_step_over(self, args: dict) -> str:
        await self._dap.step_over()
        return "Stepped over"

    async def _exec_step_into(self, args: dict) -> str:
        await self._dap.step_into()
        return "Stepped into"

    async def _exec_step_out(self, args: dict) -> str:
        await self._dap.step_out()
        return "Stepped out"

    async def _exec_continue_execution(self, args: dict) -> str:
        await self._dap.continue_execution()
        return "Continuing execution"

    async def _exec_evaluate_expression(self, args: dict) -> str:
        resp = await self._dap.evaluate(args["expression"], None)
        if resp.success:
            return f"Result: {resp.body.get('result', '?')}"
        return f"Evaluation failed: {resp.message}"

    async def _exec_get_call_stack(self, args: dict) -> str:
        resp = await self._dap.get_stack_trace()
        if resp.success:
            frames = resp.body.get("stackFrames", [])
            lines = []
            for f in frames:
                source = f.get("source", {})
                path = source.get("path", "?") if isinstance(source, dict) else "?"
                lines.append(f"  {f.get('name', '?')} at {path}:{f.get('line', '?')}")
            return "Call stack:\n" + "\n".join(lines) if lines else "Empty call stack"
        return f"Could not get call stack: {resp.message}"

    async def _exec_read_source(self, args: dict) -> str:
        file_path = args["file"]
        line = args.get("line", 1)
        context = args.get("context", 10)
        try:
            content = Path(file_path).read_text()
            lines = content.split("\n")
            start = max(0, line - context - 1)
            end = min(len(lines), line + context)
            snippet = []
            for i, l in enumerate(lines[start:end], start + 1):
                marker = ">>>" if i == line else "   "
                snippet.append(f"{marker} {i:4d} | {l}")
            return "\n".join(snippet)
        except OSError as e:
            return f"Could not read {file_path}: {e}"
```

**Step 4: Add read_source tool to functions.py**

Append to the DEBUGGER_TOOLS list in `heyducky/ai/functions.py`:

```python
    {
        "name": "read_source",
        "description": "Read source code around a specific line in a file",
        "input_schema": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "File path"},
                "line": {"type": "integer", "description": "Center line number"},
                "context": {"type": "integer", "description": "Lines of context (default 10)"},
            },
            "required": ["file", "line"],
        },
    },
```

**Step 5: Run tests**

Run: `cd /Users/idang/Projects/TalkToMe && .venv/bin/python -m pytest tests/test_tool_executor.py -v`
Expected: All 4 tests PASS

**Step 6: Run ALL tests**

Run: `cd /Users/idang/Projects/TalkToMe && .venv/bin/python -m pytest tests/ -v`
Expected: All tests PASS

**Step 7: Commit**

```bash
git add heyducky/debugger/tool_executor.py heyducky/ai/functions.py tests/test_tool_executor.py
git commit -m "feat: add tool executor bridging AI tool calls to DAP debugger"
```

---

### Task 9: Orchestrator Tool Execution Loop

**Files:**
- Modify: `heyducky/ai/orchestrator.py`
- Modify: `tests/test_orchestrator.py`

This upgrades the orchestrator to actually execute tool calls and feed results back to Claude, enabling multi-turn tool use.

**Step 1: Write the new test**

Add to `tests/test_orchestrator.py`:

```python
@pytest.mark.asyncio
async def test_orchestrator_executes_tool_calls(mock_provider):
    """Orchestrator executes tool calls and feeds results back."""
    # First response has a tool call
    tool_response = AIResponse(
        text="Let me check.",
        tool_calls=[ToolCall(id="t1", name="inspect_variable", arguments={"name": "x"})],
        input_tokens=30,
        output_tokens=15,
    )
    # Second response is the final answer (after tool result)
    final_response = AIResponse(
        text="x is 42.",
        tool_calls=[],
        input_tokens=40,
        output_tokens=10,
    )
    mock_provider.send_message = AsyncMock(side_effect=[tool_response, final_response])

    mock_executor = AsyncMock()
    mock_executor.execute = AsyncMock(return_value="x = 42 (int)")

    orch = Orchestrator(provider=mock_provider, tool_executor=mock_executor)
    resp = await orch.chat("What is x?")

    # Should have called the tool executor
    mock_executor.execute.assert_called_once()
    # Final response should be the one after tool results
    assert resp.text == "x is 42."
    # Provider should have been called twice (initial + after tool result)
    assert mock_provider.send_message.call_count == 2
```

**Step 2: Update the Orchestrator**

```python
# heyducky/ai/orchestrator.py
"""AI orchestration - manages conversation, context, and cost."""

from __future__ import annotations

from typing import TYPE_CHECKING

from heyducky.ai.provider import AIProvider, AIResponse
from heyducky.ai.prompts import DEBUGGER_SYSTEM_PROMPT, humanize_response
from heyducky.ai.functions import DEBUGGER_TOOLS

if TYPE_CHECKING:
    from heyducky.debugger.tool_executor import ToolExecutor


class Orchestrator:
    """Manages conversation with AI provider."""

    def __init__(self, provider: AIProvider, tool_executor: ToolExecutor | None = None):
        self._provider = provider
        self._tool_executor = tool_executor
        self._history: list[dict] = []
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.total_cost: float = 0.0

    async def chat(self, user_message: str) -> AIResponse:
        """Send a user message and get AI response, executing tool calls if needed."""
        self._history.append({"role": "user", "content": user_message})

        # Loop to handle tool calls
        max_rounds = 5
        for _ in range(max_rounds):
            response = await self._provider.send_message(
                messages=list(self._history),
                system=DEBUGGER_SYSTEM_PROMPT,
                tools=DEBUGGER_TOOLS,
            )

            response.text = humanize_response(response.text)
            self._track_usage(response)

            # Add assistant response to history
            if response.tool_calls:
                content = []
                if response.text:
                    content.append({"type": "text", "text": response.text})
                for tc in response.tool_calls:
                    content.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments,
                    })
                self._history.append({"role": "assistant", "content": content})

                # Execute tool calls if we have an executor
                if self._tool_executor:
                    tool_results = []
                    for tc in response.tool_calls:
                        result = await self._tool_executor.execute(tc)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tc.id,
                            "content": result,
                        })
                    self._history.append({"role": "user", "content": tool_results})
                    continue  # Get Claude's follow-up response
                else:
                    return response  # No executor, return with tool calls for caller
            else:
                self._history.append({"role": "assistant", "content": response.text})
                return response

        return response  # Safety: return last response if max rounds hit

    def _track_usage(self, response: AIResponse) -> None:
        """Track token usage and cost."""
        self.total_input_tokens += response.input_tokens
        self.total_output_tokens += response.output_tokens
        self.total_cost += response.cost("claude")

    def add_tool_result(self, tool_call_id: str, result: str) -> None:
        """Add a tool result to conversation history."""
        self._history.append({
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_call_id,
                    "content": result,
                }
            ],
        })

    def reset(self) -> None:
        """Clear conversation history and cost tracking."""
        self._history = []
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
```

**Step 3: Update existing orchestrator tests to pass tool_executor=None**

The existing fixture creates `Orchestrator(provider=mock_provider)`. Since `tool_executor` defaults to `None`, existing tests should still pass without changes. Verify.

**Step 4: Run ALL tests**

Run: `cd /Users/idang/Projects/TalkToMe && .venv/bin/python -m pytest tests/ -v`
Expected: All tests PASS (including new test)

**Step 5: Commit**

```bash
git add heyducky/ai/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: add tool execution loop to orchestrator for multi-turn AI debugging"
```

---

### Task 10: Debug Session Manager

**Files:**
- Create: `heyducky/debugger/session.py`
- Create: `tests/test_session.py`

This ties the DAP client, adapter registry, and UI updates together.

**Step 1: Write the failing test**

```python
# tests/test_session.py
"""Tests for debug session manager."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
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
```

**Step 2: Write the implementation**

```python
# heyducky/debugger/session.py
"""Debug session manager - ties DAP client to UI."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Awaitable, Any

from heyducky.debugger.dap_client import DAPClient
from heyducky.debugger.adapters import detect_language, get_adapter_config
from heyducky.debugger.types import DAPEvent


class DebugSession:
    """Manages a debug session lifecycle."""

    def __init__(
        self,
        on_state_change: Callable[..., Awaitable[None]] | None = None,
        on_output: Callable[[str, str], Awaitable[None]] | None = None,
    ):
        self._dap_client: DAPClient | None = None
        self._on_state_change = on_state_change
        self._on_output = on_output
        self.program: str | None = None
        self.language: str | None = None

    @property
    def client(self) -> DAPClient | None:
        return self._dap_client

    async def start(self, program: str) -> None:
        """Start a debug session for the given program."""
        self.program = str(Path(program).resolve())
        self.language = self._detect_language(program)

        if self.language is None:
            raise ValueError(f"Could not detect language for {program}")

        adapter = get_adapter_config(self.language)
        if adapter is None:
            raise ValueError(f"No debug adapter configured for {self.language}")

        self._dap_client = DAPClient()

        # Register event handlers
        self._dap_client.on_event("stopped", self._on_stopped)
        self._dap_client.on_event("output", self._on_output_event)
        self._dap_client.on_event("terminated", self._on_terminated)

        # Start transport
        if adapter.transport == "stdio":
            await self._dap_client.start_stdio(adapter.command)
        else:
            await self._dap_client.start_tcp(adapter.host, adapter.port)

        # Initialize
        await self._dap_client.initialize()
        await self._dap_client.launch(self.program, **adapter.launch_args)
        await self._dap_client.configuration_done()

    async def stop(self) -> None:
        """Stop the debug session."""
        if self._dap_client:
            await self._dap_client.disconnect()
            self._dap_client = None

    def _detect_language(self, program: str) -> str | None:
        return detect_language(program)

    async def _on_stopped(self, event: DAPEvent) -> None:
        """Handle debugger stopped event."""
        if self._on_state_change and self._dap_client:
            # Get stack trace to find current location
            resp = await self._dap_client.get_stack_trace()
            frames = resp.body.get("stackFrames", [])
            if frames:
                top = frames[0]
                source = top.get("source", {})
                file_path = source.get("path", "") if isinstance(source, dict) else ""
                line = top.get("line", 0)
                self._dap_client.current_file = file_path
                self._dap_client.current_line = line
            await self._on_state_change("paused", frames)

    async def _on_output_event(self, event: DAPEvent) -> None:
        """Handle program output."""
        if self._on_output:
            category = event.body.get("category", "stdout")
            text = event.body.get("output", "")
            await self._on_output(category, text)

    async def _on_terminated(self, event: DAPEvent) -> None:
        """Handle debugger terminated."""
        if self._on_state_change:
            await self._on_state_change("terminated", [])
```

**Step 3: Run tests**

Run: `cd /Users/idang/Projects/TalkToMe && .venv/bin/python -m pytest tests/test_session.py -v`
Expected: All 2 tests PASS

**Step 4: Commit**

```bash
git add heyducky/debugger/session.py tests/test_session.py
git commit -m "feat: add debug session manager connecting DAP client to UI"
```

---

### Task 11: Wire Debug Session into App

**Files:**
- Modify: `heyducky/app.py`

This connects the debug session to the TUI — when a target program is provided, start a debug session and update the UI on debugger events.

**Step 1: Update app.py _init_components to start debug session**

Add to `_init_components()` after AI setup:

```python
        # Start debug session if target provided
        if self._target:
            self._start_debug_session()
```

Add the debug session methods to the class:

```python
    @work(thread=True, exclusive=True, group="debug-session")
    def _start_debug_session(self) -> None:
        """Start a debug session for the target program."""
        import asyncio
        from heyducky.debugger.session import DebugSession
        from heyducky.debugger.tool_executor import ToolExecutor

        async def run():
            self._debug_session = DebugSession(
                on_state_change=self._on_debug_state_change,
                on_output=self._on_debug_output,
            )
            await self._debug_session.start(self._target)

            # Connect tool executor to orchestrator
            if self._orchestrator and self._debug_session.client:
                executor = ToolExecutor(self._debug_session.client)
                self._orchestrator._tool_executor = executor

        try:
            asyncio.run(run())
            self.call_from_thread(
                self._show_system_message,
                f"Debug session started for {self._target}",
            )
        except Exception as e:
            self.call_from_thread(
                self._show_system_message,
                f"Failed to start debug session: {e}",
            )

    async def _on_debug_state_change(self, state: str, frames: list) -> None:
        """Handle debugger state changes (called from async context)."""
        self.call_from_thread(self._update_debug_state, state, frames)

    async def _on_debug_output(self, category: str, text: str) -> None:
        """Handle program output."""
        self.call_from_thread(self._add_debug_output, category, text)

    def _update_debug_state(self, state: str, frames: list) -> None:
        """Update UI with debug state."""
        status = self.query_one("#status-bar", VoiceStatusBar)
        status.debug_state = state

        if state == "paused" and frames:
            top = frames[0]
            source = top.get("source", {})
            file_path = source.get("path", "") if isinstance(source, dict) else ""
            line = top.get("line", 0)

            status.debug_file = file_path
            status.debug_line = line

            # Update source view
            source_view = self.query_one("#source-view", SourceView)
            source_view.load_source(file_path)
            source_view.set_current_line(line)

            # Update call stack
            stack_view = self.query_one("#callstack-view", CallStackView)
            stack_view.update_frames(frames)

            # Switch to source tab
            self.query_one(TabbedContent).active = "source"

    def _add_debug_output(self, category: str, text: str) -> None:
        """Add program output to the output panel."""
        output = self.query_one("#output-view", DebugOutputView)
        if category == "stderr":
            output.add_stderr(text)
        else:
            output.add_stdout(text)
```

Also add import for `TabbedContent` and all new widgets, plus add `_debug_session = None` in `__init__`.

**Step 2: Run ALL tests**

Run: `cd /Users/idang/Projects/TalkToMe && .venv/bin/python -m pytest tests/ -v`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add heyducky/app.py
git commit -m "feat: wire debug session into TUI with event-driven UI updates"
```

---

### Task 12: Add debugpy dependency and test program

**Files:**
- Modify: `pyproject.toml` (add debugpy)
- Create: `test_programs/buggy.py`

**Step 1: Update pyproject.toml**

Add `"debugpy>=1.8.0"` to the dependencies list.

**Step 2: Create test program**

```python
# test_programs/buggy.py
"""A simple buggy program for testing the debugger."""


def calculate_average(numbers):
    """Calculate the average of a list of numbers."""
    total = 0
    for num in numbers:
        total += num
    # Bug: should divide by len(numbers), not len(numbers) - 1
    return total / (len(numbers) - 1)


def process_data(data):
    """Process a list of data items."""
    results = []
    for item in data:
        if item > 0:
            results.append(item * 2)
        else:
            # Bug: appending None instead of 0
            results.append(None)
    return results


def main():
    """Main function with bugs to find."""
    numbers = [10, 20, 30, 40, 50]
    avg = calculate_average(numbers)
    print(f"Average: {avg}")

    data = [5, -3, 10, 0, -1, 7]
    processed = process_data(data)
    print(f"Processed: {processed}")

    # Bug: will crash when None is in the list
    total = sum(processed)
    print(f"Total: {total}")


if __name__ == "__main__":
    main()
```

**Step 3: Install updated dependencies**

Run: `cd /Users/idang/Projects/TalkToMe && .venv/bin/pip install -e ".[dev]"`

**Step 4: Commit**

```bash
git add pyproject.toml test_programs/
git commit -m "feat: add debugpy dependency and test program for debugging"
```

---

### Task 13: Run ALL tests and final verification

**Step 1: Run complete test suite**

Run: `cd /Users/idang/Projects/TalkToMe && .venv/bin/python -m pytest tests/ -v`
Expected: All tests PASS

**Step 2: Verify import chain**

Run: `cd /Users/idang/Projects/TalkToMe && .venv/bin/python -c "from heyducky.debugger.session import DebugSession; from heyducky.debugger.tool_executor import ToolExecutor; from heyducky.debugger.dap_client import DAPClient; print('All imports OK')"`
Expected: `All imports OK`

**Step 3: Commit any fixes**

```bash
git add -A && git commit -m "fix: address issues found during final verification"
```

---

## Summary

| Task | What | Tests |
|------|------|-------|
| 1 | DAP message types + wire protocol | 7 tests |
| 2 | Stdio + TCP transports | 2 tests |
| 3 | DAP client core | 3 tests |
| 4 | Adapter registry (Python, C++, Go, Rust) | 12 tests |
| 5 | Upgraded source view | 4 tests |
| 6 | Variables, call stack, output widgets | import check |
| 7 | Tabbed TUI layout + keybindings | 3 tests (updated) |
| 8 | Tool executor (AI -> debugger bridge) | 4 tests |
| 9 | Orchestrator tool execution loop | 1 test (+ existing) |
| 10 | Debug session manager | 2 tests |
| 11 | Wire session into app | regression check |
| 12 | debugpy dep + test program | - |
| 13 | Final verification | full suite |

**Total: 13 tasks, ~38 new tests**
