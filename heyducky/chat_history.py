# heyducky/chat_history.py
"""Chat history persistence — save and load conversations."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_HISTORY_DIR = Path.home() / ".config" / "ducky" / "history"


class ChatHistory:
    """Saves and loads conversation sessions as JSON files."""

    def __init__(self, history_dir: Path | None = None):
        self._dir = history_dir or DEFAULT_HISTORY_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._messages: list[dict] = []
        self._session_id: str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        self._session_file = self._dir / f"{self._session_id}.json"

    @property
    def session_id(self) -> str:
        return self._session_id

    def add(self, role: str, content: str) -> None:
        """Append a message and persist to disk."""
        entry = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._messages.append(entry)
        self._save()

    def _save(self) -> None:
        """Write current session to disk."""
        data = {
            "session_id": self._session_id,
            "created": self._messages[0]["timestamp"] if self._messages else "",
            "message_count": len(self._messages),
            "preview": self._messages[0]["content"][:80] if self._messages else "",
            "messages": self._messages,
        }
        self._session_file.write_text(json.dumps(data, indent=2))

    def list_sessions(self) -> list[dict]:
        """Return all saved sessions, newest first.

        Each dict has: session_id, created, message_count, preview, path.
        """
        sessions = []
        for f in sorted(self._dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(f.read_text())
                sessions.append(
                    {
                        "session_id": data.get("session_id", f.stem),
                        "created": data.get("created", ""),
                        "message_count": data.get("message_count", 0),
                        "preview": data.get("preview", ""),
                        "path": f,
                    }
                )
            except (json.JSONDecodeError, OSError):
                continue
        return sessions

    def load_session(self, path: Path) -> list[dict]:
        """Load messages from a saved session file."""
        data = json.loads(path.read_text())
        return data.get("messages", [])

    def new_session(self) -> None:
        """Start a fresh session (e.g. when user presses Space for new chat)."""
        if self._messages:
            self._save()  # Ensure current session is saved
        self._messages = []
        self._session_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        self._session_file = self._dir / f"{self._session_id}.json"

    def sessions_grouped_by_date(self) -> dict[str, list[dict]]:
        """Return sessions grouped into date buckets: Today, Yesterday, This Week, Older."""
        from datetime import timedelta

        now = datetime.now(timezone.utc)
        today = now.date()
        yesterday = today - timedelta(days=1)
        week_ago = today - timedelta(days=7)

        groups: dict[str, list[dict]] = {
            "Today": [],
            "Yesterday": [],
            "This Week": [],
            "Older": [],
        }

        for session in self.list_sessions():
            created = session.get("created", "")
            try:
                dt = datetime.fromisoformat(created).date()
            except (ValueError, TypeError):
                groups["Older"].append(session)
                continue

            if dt == today:
                groups["Today"].append(session)
            elif dt == yesterday:
                groups["Yesterday"].append(session)
            elif dt >= week_ago:
                groups["This Week"].append(session)
            else:
                groups["Older"].append(session)

        return {k: v for k, v in groups.items() if v}

    def export_current_markdown(self) -> str:
        """Export current session as markdown text."""
        if not self._messages:
            return ""
        lines = [f"# Debug Session: {self._session_id}", ""]
        for msg in self._messages:
            role = msg["role"]
            content = msg["content"]
            if role == "user":
                lines.append(f"**You:** {content}")
                lines.append("")
            elif role == "assistant":
                lines.append(f"**AI:** {content}")
                lines.append("")
        lines.append("---")
        lines.append("*Exported from HeyDucky*")
        return "\n".join(lines)

    def search_sessions(self, query: str) -> list[dict]:
        """Search session previews and message content for a query string."""
        query_lower = query.lower()
        results = []
        for session in self.list_sessions():
            if query_lower in session.get("preview", "").lower():
                results.append(session)
                continue
            try:
                messages = self.load_session(session["path"])
                for msg in messages:
                    if query_lower in msg.get("content", "").lower():
                        results.append(session)
                        break
            except Exception:
                continue
        return results
