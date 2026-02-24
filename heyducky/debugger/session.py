"""Debug session manager - ties DAP client to UI."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Awaitable

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
        self._path_map: dict[str, str] = {}
        self.is_remote: bool = False

    @property
    def client(self) -> DAPClient | None:
        return self._dap_client

    @property
    def path_map(self) -> dict[str, str]:
        return self._path_map

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

    async def start_attach(
        self,
        host: str,
        port: int,
        language: str,
        path_map: dict[str, str] | None = None,
    ) -> None:
        """Attach to a remote debug adapter over TCP.

        The remote machine should already be running a DAP-compatible server
        (e.g. ``debugpy --listen 0.0.0.0:5678 --wait-for-client script.py``).
        """
        self.language = language
        self.is_remote = True
        self._path_map = path_map or {}

        adapter = get_adapter_config(language)
        attach_args: dict = dict(adapter.attach_args) if adapter else {}

        self._dap_client = DAPClient()

        self._dap_client.on_event("stopped", self._on_stopped)
        self._dap_client.on_event("output", self._on_output_event)
        self._dap_client.on_event("terminated", self._on_terminated)

        await self._dap_client.start_tcp(host, port)
        await self._dap_client.initialize()
        await self._dap_client.attach(**attach_args)
        await self._dap_client.configuration_done()

    async def stop(self) -> None:
        """Stop the debug session."""
        if self._dap_client:
            await self._dap_client.disconnect()
            self._dap_client = None

    def _detect_language(self, program: str) -> str | None:
        return detect_language(program)

    def _translate_path(self, remote_path: str) -> str:
        """Map a remote file path to its local equivalent."""
        for remote_prefix, local_prefix in self._path_map.items():
            if remote_path.startswith(remote_prefix):
                return remote_path.replace(remote_prefix, local_prefix, 1)
        return remote_path

    async def _on_stopped(self, event: DAPEvent) -> None:
        """Handle debugger stopped event."""
        if self._on_state_change and self._dap_client:
            resp = await self._dap_client.get_stack_trace()
            frames = resp.body.get("stackFrames", [])
            if frames:
                top = frames[0]
                source = top.get("source", {})
                file_path = source.get("path", "") if isinstance(source, dict) else ""
                line = top.get("line", 0)
                if self.is_remote:
                    file_path = self._translate_path(file_path)
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
