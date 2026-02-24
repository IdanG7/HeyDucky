"""Remote debug agent — starts a debug adapter and file server on the remote machine.

This module provides:
- ``get_adapter_command(language)`` — shared adapter command lookup used by both
  the headless agent and the GUI relay.
- ``RemoteAgent`` — headless mode: starts debugpy in listen mode + file server.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

from heyducky.remote.file_server import FileServer

ADAPTER_COMMANDS: dict[str, list[str]] = {
    "python": [sys.executable, "-m", "debugpy.adapter"],
}

LISTEN_COMMANDS: dict[str, list[str]] = {
    "python": [
        sys.executable,
        "-m",
        "debugpy",
        "--listen",
        "{host}:{port}",
        "--wait-for-client",
        "{program}",
    ],
}


def get_adapter_command(language: str) -> list[str] | None:
    """Return the stdio adapter command for a given language.

    Used by the GUI relay to spawn a debug adapter subprocess.
    """
    return ADAPTER_COMMANDS.get(language)


def detect_language(program: str) -> str | None:
    ext_map = {
        ".py": "python",
        ".c": "cpp",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".go": "go",
        ".rs": "rust",
    }
    return ext_map.get(Path(program).suffix.lower())


class RemoteAgent:
    """Headless remote agent — runs debugpy in listen mode + file server."""

    def __init__(
        self,
        program: str,
        language: str | None = None,
        host: str = "0.0.0.0",
        dap_port: int = 5678,
        file_port: int = 0,
    ):
        self.program = str(Path(program).resolve())
        self.language = language or detect_language(program)
        self.host = host
        self.dap_port = dap_port
        self.file_port = file_port
        self._project_root = str(Path(program).resolve().parent)
        self._file_server: FileServer | None = None
        self._adapter_proc: subprocess.Popen | None = None

    async def start(self) -> tuple[int, int]:
        """Start file server + debug adapter. Returns (dap_port, file_port)."""
        self._file_server = FileServer(self._project_root, host=self.host, port=self.file_port)
        actual_file_port = await self._file_server.start()
        self._start_adapter()
        return self.dap_port, actual_file_port

    def _start_adapter(self) -> None:
        template = LISTEN_COMMANDS.get(self.language)
        if template is None:
            raise ValueError(
                f"Remote agent for {self.language!r} is not yet supported. "
                f"Currently supported: {', '.join(LISTEN_COMMANDS)}"
            )
        cmd = [
            part.format(host=self.host, port=self.dap_port, program=self.program)
            for part in template
        ]
        self._adapter_proc = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)

    async def wait(self) -> int:
        """Block until the debug adapter process exits. Returns its exit code."""
        if self._adapter_proc is None:
            return 0
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._adapter_proc.wait)

    async def stop(self) -> None:
        if self._adapter_proc and self._adapter_proc.poll() is None:
            self._adapter_proc.terminate()
            self._adapter_proc.wait(timeout=5)
        if self._file_server:
            await self._file_server.stop()
