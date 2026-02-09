"""Debug session manager - ties DAP client to UI."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Awaitable

from voice_debugger.debugger.dap_client import DAPClient
from voice_debugger.debugger.adapters import detect_language, get_adapter_config
from voice_debugger.debugger.types import DAPEvent


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
