"""Transport layer for DAP communication (stdio and TCP)."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable

from heyducky.debugger.types import DAPRequest, decode_messages, encode_message


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
