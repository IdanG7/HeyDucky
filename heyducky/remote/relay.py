"""DAP Relay — bridges a local debug adapter (stdio) to a remote TUI client (TCP).

The relay spawns a debug adapter subprocess, communicating with it over
stdin/stdout, and exposes a TCP server that accepts one client connection
(the HeyDucky TUI). DAP messages are forwarded bidirectionally.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any

from heyducky.debugger.types import decode_messages

log = logging.getLogger(__name__)


class DAPRelay:
    """Bidirectional DAP message relay: stdio subprocess <-> TCP client."""

    def __init__(
        self,
        adapter_cmd: list[str],
        host: str = "0.0.0.0",
        port: int = 0,
        on_message: Callable[[str, dict], Any] | None = None,
        attach_inject: dict[str, Any] | None = None,
    ):
        """
        Args:
            adapter_cmd: Command to spawn the debug adapter (e.g. ["python", "-m", "debugpy.adapter"]).
            host: Interface to listen on.
            port: TCP port (0 = auto-assign).
            on_message: Optional callback ``(direction, msg_dict)`` for logging.
                        direction is "client->adapter" or "adapter->client".
            attach_inject: Extra arguments to merge into the DAP ``attach`` request
                           before forwarding to the adapter (e.g. ``{"processId": 1234}``).
        """
        self._adapter_cmd = adapter_cmd
        self._host = host
        self._port = port
        self._on_message = on_message
        self._attach_inject = attach_inject or {}

        self._server: asyncio.Server | None = None
        self._adapter_proc: asyncio.subprocess.Process | None = None
        self._client_writer: asyncio.StreamWriter | None = None
        self._tasks: list[asyncio.Task] = []
        self._client_connected = asyncio.Event()

    @property
    def port(self) -> int:
        if self._server and self._server.sockets:
            return self._server.sockets[0].getsockname()[1]
        return self._port

    @property
    def is_client_connected(self) -> bool:
        return self._client_writer is not None

    async def start(self) -> int:
        """Start the adapter subprocess and TCP server. Returns the actual TCP port."""
        self._adapter_proc = await asyncio.create_subprocess_exec(
            *self._adapter_cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._server = await asyncio.start_server(self._handle_client, self._host, self._port)
        return self.port

    async def stop(self) -> None:
        """Stop the relay, killing the adapter and closing connections."""
        for task in self._tasks:
            task.cancel()
        if self._client_writer:
            self._client_writer.close()
            self._client_writer = None
        if self._adapter_proc:
            try:
                self._adapter_proc.terminate()
                await asyncio.wait_for(self._adapter_proc.wait(), timeout=5)
            except (ProcessLookupError, asyncio.TimeoutError):
                self._adapter_proc.kill()
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    async def wait_for_adapter(self) -> int:
        """Wait for the adapter subprocess to exit. Returns exit code."""
        if self._adapter_proc is None:
            return 0
        return await self._adapter_proc.wait()

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Accept one TUI client and start relaying."""
        if self._client_writer is not None:
            writer.write(b"Only one client connection is allowed.\n")
            await writer.drain()
            writer.close()
            return

        self._client_writer = writer
        peer = writer.get_extra_info("peername")
        log.info("TUI client connected from %s", peer)
        self._client_connected.set()

        if self._on_message:
            self._on_message("status", {"event": "client_connected", "peer": str(peer)})

        task_tcp = asyncio.create_task(self._relay_tcp_to_stdio(reader))
        task_stdio = asyncio.create_task(self._relay_stdio_to_tcp())
        self._tasks.extend([task_tcp, task_stdio])

        try:
            # When either direction ends (e.g. client disconnects), cancel the other
            _done, pending = await asyncio.wait(
                [task_tcp, task_stdio], return_when=asyncio.FIRST_COMPLETED
            )
            for t in pending:
                t.cancel()
        except asyncio.CancelledError:
            task_tcp.cancel()
            task_stdio.cancel()
        finally:
            self._client_writer = None
            self._client_connected.clear()
            if self._on_message:
                self._on_message("status", {"event": "client_disconnected"})

    async def _relay_tcp_to_stdio(self, reader: asyncio.StreamReader) -> None:
        """Forward DAP messages from TCP client -> adapter stdin.

        Messages are decoded so we can intercept the ``attach`` request and
        inject extra arguments (like processId) before forwarding.
        """
        proc = self._adapter_proc
        if proc is None or proc.stdin is None:
            return

        buffer = b""
        try:
            while True:
                chunk = await reader.read(4096)
                if not chunk:
                    break
                buffer += chunk
                msgs, buffer = decode_messages(buffer)
                for msg in msgs:
                    if (
                        self._attach_inject
                        and msg.get("type") == "request"
                        and msg.get("command") == "attach"
                    ):
                        args = msg.get("arguments", {})
                        args.update(self._attach_inject)
                        msg["arguments"] = args

                    if self._on_message:
                        self._on_message("client->adapter", msg)

                    payload = json.dumps(msg).encode("utf-8")
                    frame = f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii") + payload
                    proc.stdin.write(frame)
                    await proc.stdin.drain()
        except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError):
            pass

    async def _relay_stdio_to_tcp(self) -> None:
        """Forward raw bytes from adapter stdout -> TCP client."""
        proc = self._adapter_proc
        if proc is None or proc.stdout is None:
            return

        buffer = b""
        try:
            while True:
                chunk = await proc.stdout.read(4096)
                if not chunk:
                    break
                if self._client_writer is None:
                    continue
                self._client_writer.write(chunk)
                await self._client_writer.drain()

                if self._on_message:
                    buffer += chunk
                    msgs, buffer = decode_messages(buffer)
                    for msg in msgs:
                        self._on_message("adapter->client", msg)
        except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError):
            pass
