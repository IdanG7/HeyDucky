"""TCP file server — serves file reads and directory listings to the local HeyDucky.

Protocol: newline-delimited JSON over TCP.
  Request:  {"cmd": "read_file", "path": "/foo/bar.py"}
  Response: {"ok": true, "content": "..."}

  Request:  {"cmd": "list_dir", "path": "/foo", "recursive": false}
  Response: {"ok": true, "entries": ["bar.py", "sub/"]}

  Request:  {"cmd": "ping"}
  Response: {"ok": true, "project_root": "/home/user/project"}
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

SKIP_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".eggs",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}


class FileServer:
    """Async TCP server that exposes the remote filesystem to HeyDucky."""

    def __init__(self, project_root: str, host: str = "0.0.0.0", port: int = 0):
        self._root = Path(project_root).resolve()
        self._host = host
        self._port = port
        self._server: asyncio.Server | None = None

    @property
    def port(self) -> int:
        if self._server and self._server.sockets:
            return self._server.sockets[0].getsockname()[1]
        return self._port

    async def start(self) -> int:
        """Start the file server. Returns the actual port."""
        self._server = await asyncio.start_server(self._handle_client, self._host, self._port)
        return self.port

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                try:
                    request = json.loads(line.decode())
                except (json.JSONDecodeError, UnicodeDecodeError):
                    self._send(writer, {"ok": False, "error": "Invalid JSON"})
                    continue

                cmd = request.get("cmd", "")
                if cmd == "read_file":
                    response = self._do_read_file(request.get("path", ""))
                elif cmd == "list_dir":
                    response = self._do_list_dir(
                        request.get("path", str(self._root)),
                        request.get("recursive", False),
                    )
                elif cmd == "ping":
                    response = {"ok": True, "project_root": str(self._root)}
                else:
                    response = {"ok": False, "error": f"Unknown command: {cmd}"}

                self._send(writer, response)
                await writer.drain()
        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            writer.close()

    def _send(self, writer: asyncio.StreamWriter, data: dict) -> None:
        writer.write(json.dumps(data).encode() + b"\n")

    def _do_read_file(self, path: str) -> dict:
        try:
            target = Path(path)
            if not target.is_absolute():
                target = self._root / target
            content = target.read_text(errors="replace")
            return {"ok": True, "content": content}
        except OSError as e:
            return {"ok": False, "error": str(e)}

    def _do_list_dir(self, path: str, recursive: bool) -> dict:
        try:
            target = Path(path)
            if not target.is_absolute():
                target = self._root / target
            if not target.is_dir():
                return {"ok": False, "error": f"Not a directory: {path}"}

            entries: list[str] = []
            if recursive:
                for item in sorted(target.rglob("*")):
                    if any(p.name in SKIP_DIRS for p in item.parents):
                        continue
                    if item.name in SKIP_DIRS:
                        continue
                    rel = item.relative_to(target)
                    suffix = "/" if item.is_dir() else ""
                    entries.append(f"{rel}{suffix}")
                    if len(entries) >= 200:
                        entries.append("... (truncated)")
                        break
            else:
                for item in sorted(target.iterdir()):
                    if item.name in SKIP_DIRS or item.name.startswith("."):
                        continue
                    suffix = "/" if item.is_dir() else ""
                    entries.append(f"{item.name}{suffix}")

            return {"ok": True, "entries": entries}
        except OSError as e:
            return {"ok": False, "error": str(e)}
