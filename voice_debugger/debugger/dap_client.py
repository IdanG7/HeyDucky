"""Generic DAP client for debugging any language."""

from __future__ import annotations

import asyncio
import pathlib
from typing import Any, Callable, Awaitable

from voice_debugger.debugger.types import DAPRequest, DAPResponse, DAPEvent
from voice_debugger.debugger.transport import BaseTransport, StdioTransport, TCPTransport


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
        future: asyncio.Future[DAPResponse] = asyncio.get_running_loop().create_future()
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
            "clientID": "voice-debugger",
            "clientName": "Voice Debugger",
            "adapterID": "voice-debugger",
            "pathFormat": "path",
            "linesStartAt1": True,
            "columnsStartAt1": True,
        })
        return resp

    async def launch(self, program: str, **kwargs) -> DAPResponse:
        """Launch a program for debugging."""
        args: dict[str, Any] = {
            "program": program,
            "cwd": str(pathlib.Path(program).parent),
        }
        args.update(kwargs)
        resp = await self.send_request("launch", args)
        return resp

    async def configuration_done(self) -> DAPResponse:
        """Signal that configuration is complete."""
        self.state = "running"
        return await self.send_request("configurationDone")

    async def set_breakpoint(
        self, file: str, line: int, condition: str = ""
    ) -> DAPResponse:
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
        return await self.send_request(
            "variables", {"variablesReference": variables_reference}
        )

    async def evaluate(
        self, expression: str, frame_id: int | None = None
    ) -> DAPResponse:
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
