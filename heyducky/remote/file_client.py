"""TCP client for the remote file server.

Used by the local HeyDucky to read files and list directories
on the remote machine where the debug agent is running.
"""

from __future__ import annotations

import asyncio
import json


class RemoteFileClient:
    """Connects to a remote FileServer and provides read/list operations."""

    def __init__(self, host: str, port: int):
        self._host = host
        self._port = port
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    async def connect(self) -> None:
        self._reader, self._writer = await asyncio.open_connection(self._host, self._port)

    async def close(self) -> None:
        if self._writer:
            self._writer.close()

    async def _request(self, data: dict) -> dict:
        if self._writer is None or self._reader is None:
            raise RuntimeError("Not connected — call connect() first")
        payload = json.dumps(data).encode() + b"\n"
        self._writer.write(payload)
        await self._writer.drain()
        line = await self._reader.readline()
        if not line:
            raise ConnectionError("Remote file server closed the connection")
        return json.loads(line.decode())

    async def ping(self) -> str | None:
        """Ping the server. Returns the remote project root, or None on failure."""
        try:
            resp = await self._request({"cmd": "ping"})
            if resp.get("ok"):
                return resp.get("project_root")
        except Exception:
            pass
        return None

    async def read_file(self, path: str) -> str | None:
        """Read a file on the remote machine. Returns content or None on error."""
        try:
            resp = await self._request({"cmd": "read_file", "path": path})
            if resp.get("ok"):
                return resp.get("content", "")
        except Exception:
            pass
        return None

    async def list_dir(self, path: str, recursive: bool = False) -> list[str] | None:
        """List a directory on the remote machine. Returns entries or None on error."""
        try:
            resp = await self._request(
                {
                    "cmd": "list_dir",
                    "path": path,
                    "recursive": recursive,
                }
            )
            if resp.get("ok"):
                return resp.get("entries", [])
        except Exception:
            pass
        return None
