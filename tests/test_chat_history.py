"""Tests for chat history persistence."""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from heyducky.chat_history import ChatHistory


@pytest.fixture
def history_dir(tmp_path):
    return tmp_path / "history"


@pytest.fixture
def chat_history(history_dir):
    return ChatHistory(history_dir=history_dir)


def test_add_and_load_messages(chat_history, history_dir):
    """Messages are saved to disk and can be loaded back."""
    chat_history.add("user", "Hello")
    chat_history.add("assistant", "Hi there!")

    sessions = chat_history.list_sessions()
    assert len(sessions) == 1
    assert sessions[0]["message_count"] == 2

    messages = chat_history.load_session(sessions[0]["path"])
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["content"] == "Hi there!"


def test_new_session(chat_history):
    """new_session starts a fresh session."""
    chat_history.add("user", "First session")
    first_id = chat_history.session_id

    chat_history.new_session()
    chat_history.add("user", "Second session")
    second_id = chat_history.session_id

    assert first_id != second_id
    sessions = chat_history.list_sessions()
    assert len(sessions) == 2


def test_sessions_grouped_by_date(history_dir):
    """Sessions are grouped into Today/Yesterday/This Week/Older."""
    now = datetime.now(timezone.utc)

    _create_session(history_dir, "today", now)
    _create_session(history_dir, "yesterday", now - timedelta(days=1))
    _create_session(history_dir, "this_week", now - timedelta(days=3))
    _create_session(history_dir, "old", now - timedelta(days=30))

    ch = ChatHistory(history_dir=history_dir)
    groups = ch.sessions_grouped_by_date()

    assert "Today" in groups
    assert "Yesterday" in groups
    assert "This Week" in groups
    assert "Older" in groups
    assert len(groups["Today"]) == 1
    assert len(groups["Older"]) == 1


def test_search_sessions(history_dir):
    """Search finds sessions by content."""
    ch = ChatHistory(history_dir=history_dir)
    ch.add("user", "Help me debug the async handler")
    ch.new_session()
    ch.add("user", "What is a variable scope")

    results = ch.search_sessions("async")
    assert len(results) == 1
    assert "async" in results[0]["preview"].lower()

    results_all = ch.search_sessions("help")
    assert len(results_all) >= 1


def test_export_current_markdown_empty(chat_history):
    """export_current_markdown returns empty string when no messages."""
    assert chat_history.export_current_markdown() == ""


def test_export_current_markdown_formats_messages(chat_history):
    """export_current_markdown formats user and assistant messages correctly."""
    chat_history.add("user", "What is this bug?")
    chat_history.add("assistant", "It looks like a null pointer.")

    md = chat_history.export_current_markdown()

    assert "**You:** What is this bug?" in md
    assert "**AI:** It looks like a null pointer." in md


def test_export_current_markdown_includes_session_id(chat_history):
    """export_current_markdown includes the session_id in the header."""
    chat_history.add("user", "Hello")

    md = chat_history.export_current_markdown()

    assert f"# Debug Session: {chat_history.session_id}" in md


def test_export_current_markdown_ends_with_footer(chat_history):
    """export_current_markdown ends with 'Exported from HeyDucky'."""
    chat_history.add("user", "Hello")

    md = chat_history.export_current_markdown()

    assert md.endswith("*Exported from HeyDucky*")


def _create_session(history_dir: Path, name: str, created: datetime):
    """Helper: create a fake session file with a specific created date."""
    history_dir.mkdir(parents=True, exist_ok=True)
    session_id = name
    data = {
        "session_id": session_id,
        "created": created.isoformat(),
        "message_count": 1,
        "preview": f"Session {name}",
        "messages": [
            {"role": "user", "content": f"Session {name}", "timestamp": created.isoformat()}
        ],
    }
    (history_dir / f"{session_id}.json").write_text(json.dumps(data))
