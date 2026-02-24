# Memory System, Settings Screen & Conversation Compaction

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add conversation compaction to prevent context overflow, a settings modal for user customization, and upgrade the history screen with date grouping and search.

**Architecture:** Client-side compaction using Claude's `count_tokens` API to monitor usage, triggering a summarization call when threshold is exceeded. Settings stored in existing TOML config. History screen upgraded with date-grouped `OptionList` and search `Input`. All features wired into the existing `app.py` event loop.

**Tech Stack:** Python 3.10+, Textual TUI framework, Anthropic SDK 0.79.0, pytest with asyncio_mode=auto

**Test runner:** `/Users/idang/Projects/TalkToMe/.venv/bin/pytest`

**Key context:**
- Config at `heyducky/config.py` — dataclass with `from_dict`/`to_dict`/`save`/`load`
- Orchestrator at `heyducky/ai/orchestrator.py` — manages `_history` list, calls `_provider.send_message`
- ClaudeProvider at `heyducky/ai/claude.py` — wraps `AsyncAnthropic`, has `_client` and `_model`
- AIProvider abstract base at `heyducky/ai/provider.py` — defines `send_message` and `model_name`
- ChatHistory at `heyducky/chat_history.py` — JSON-per-session in `~/.config/ducky/history/`
- HistoryScreen at `heyducky/widgets/history_screen.py` — ModalScreen with OptionList
- App at `heyducky/app.py` — main TUI, bindings, wires everything together

---

## Task 1: Add Compaction Config Fields

**Files:**
- Modify: `heyducky/config.py`
- Test: `tests/test_config.py`

**Step 1: Write failing tests for new config fields**

Add to `tests/test_config.py`:

```python
def test_config_compaction_defaults():
    """Config has compaction defaults."""
    config = Config()
    assert config.compaction_enabled is True
    assert config.compaction_threshold == 100_000
    assert config.max_compactions == 5


def test_config_compaction_from_dict():
    """Config reads compaction settings from dict."""
    config = Config.from_dict({
        "ai": {
            "compaction_enabled": False,
            "compaction_threshold": 80000,
            "max_compactions": 3,
        },
    })
    assert config.compaction_enabled is False
    assert config.compaction_threshold == 80000
    assert config.max_compactions == 3


def test_config_compaction_round_trip(tmp_path):
    """Compaction settings survive save/load cycle."""
    config_path = tmp_path / "config.toml"
    config = Config()
    config.compaction_threshold = 75000
    config.compaction_enabled = False
    config.save(config_path)

    loaded = Config.load(config_path)
    assert loaded.compaction_threshold == 75000
    assert loaded.compaction_enabled is False
```

**Step 2: Run tests to verify they fail**

Run: `/Users/idang/Projects/TalkToMe/.venv/bin/pytest tests/test_config.py -v`
Expected: FAIL — `Config` has no attribute `compaction_enabled`

**Step 3: Add compaction fields to Config**

In `heyducky/config.py`, add to the `Config` dataclass:

```python
@dataclass
class Config:
    # AI settings
    ai_provider: str = "claude"
    ai_model: str = "claude-sonnet-4-5-20250929"
    api_key: str = ""
    compaction_enabled: bool = True
    compaction_threshold: int = 100_000
    max_compactions: int = 5

    # Voice settings
    whisper_model: str = "base.en"
    sample_rate: int = 16000
    silence_threshold: float = 0.02
    silence_duration: float = 1.5
```

Update `from_dict`:
```python
compaction_enabled=ai.get("compaction_enabled", True),
compaction_threshold=ai.get("compaction_threshold", 100_000),
max_compactions=ai.get("max_compactions", 5),
```

Update `to_dict` — add under `"ai"`:
```python
"compaction_enabled": self.compaction_enabled,
"compaction_threshold": self.compaction_threshold,
"max_compactions": self.max_compactions,
```

**Step 4: Run tests to verify they pass**

Run: `/Users/idang/Projects/TalkToMe/.venv/bin/pytest tests/test_config.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add heyducky/config.py tests/test_config.py
git commit -m "feat: add compaction config fields (enabled, threshold, max)"
```

---

## Task 2: Add `count_tokens` to AIProvider and ClaudeProvider

**Files:**
- Modify: `heyducky/ai/provider.py`
- Modify: `heyducky/ai/claude.py`
- Test: `tests/test_ai_provider.py`

**Step 1: Write failing test**

Add to `tests/test_ai_provider.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from heyducky.ai.claude import ClaudeProvider


@pytest.mark.asyncio
async def test_claude_count_tokens():
    """ClaudeProvider.count_tokens returns token count from API."""
    provider = ClaudeProvider(api_key="test-key")

    # Mock the count_tokens call
    mock_result = MagicMock()
    mock_result.input_tokens = 1500
    provider._client.messages.count_tokens = AsyncMock(return_value=mock_result)

    messages = [{"role": "user", "content": "hello"}]
    count = await provider.count_tokens(messages, system="You are helpful.")
    assert count == 1500
    provider._client.messages.count_tokens.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `/Users/idang/Projects/TalkToMe/.venv/bin/pytest tests/test_ai_provider.py::test_claude_count_tokens -v`
Expected: FAIL — `ClaudeProvider` has no method `count_tokens`

**Step 3: Add `count_tokens` to AIProvider and ClaudeProvider**

In `heyducky/ai/provider.py`, add to `AIProvider`:

```python
@abstractmethod
async def count_tokens(
    self,
    messages: list[dict],
    system: str = "",
    tools: list[dict] | None = None,
) -> int:
    """Count input tokens for the given messages."""
    ...
```

In `heyducky/ai/claude.py`, add to `ClaudeProvider`:

```python
async def count_tokens(
    self,
    messages: list[dict],
    system: str = "",
    tools: list[dict] | None = None,
) -> int:
    """Count input tokens using the Anthropic API."""
    kwargs: dict = {
        "model": self._model,
        "messages": messages,
    }
    if system:
        kwargs["system"] = system
    if tools:
        kwargs["tools"] = tools

    result = await self._client.messages.count_tokens(**kwargs)
    return result.input_tokens
```

**Step 4: Run test to verify it passes**

Run: `/Users/idang/Projects/TalkToMe/.venv/bin/pytest tests/test_ai_provider.py::test_claude_count_tokens -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `/Users/idang/Projects/TalkToMe/.venv/bin/pytest -v`
Expected: ALL PASS (check no existing tests broke due to abstract method addition — if `mock_provider` in other test files is an `AsyncMock`, it will auto-satisfy the new abstract method)

**Step 6: Commit**

```bash
git add heyducky/ai/provider.py heyducky/ai/claude.py tests/test_ai_provider.py
git commit -m "feat: add count_tokens to AI provider for compaction monitoring"
```

---

## Task 3: Implement Client-Side Compaction in Orchestrator

**Files:**
- Modify: `heyducky/ai/orchestrator.py`
- Test: `tests/test_orchestrator.py`

**Step 1: Write failing tests for compaction**

Add to `tests/test_orchestrator.py`:

```python
@pytest.mark.asyncio
async def test_orchestrator_compacts_when_over_threshold(mock_provider):
    """Orchestrator compacts history when token count exceeds threshold."""
    # count_tokens returns over threshold
    mock_provider.count_tokens = AsyncMock(return_value=110_000)

    # First call: normal response
    # Second call (compaction summary): summary response
    # Third call (after compaction, re-send): final response
    normal_resp = AIResponse(text="Sure.", tool_calls=[], input_tokens=50, output_tokens=20)
    summary_resp = AIResponse(
        text="User was debugging app.py, found null pointer on line 42.",
        tool_calls=[], input_tokens=100, output_tokens=50,
    )
    final_resp = AIResponse(text="Got it.", tool_calls=[], input_tokens=30, output_tokens=10)

    mock_provider.send_message = AsyncMock(side_effect=[normal_resp, summary_resp, final_resp])

    orch = Orchestrator(provider=mock_provider)
    orch._compaction_enabled = True
    orch._compaction_threshold = 100_000

    # First chat builds up history
    resp1 = await orch.chat("First message")
    assert resp1.text == "Sure."

    # Second chat should trigger compaction (count_tokens returns 110k)
    resp2 = await orch.chat("Second message")
    assert resp2.text == "Got it."
    assert orch.compaction_count == 1


@pytest.mark.asyncio
async def test_orchestrator_no_compact_when_disabled(mock_provider):
    """Orchestrator does not compact when compaction is disabled."""
    mock_provider.count_tokens = AsyncMock(return_value=200_000)

    orch = Orchestrator(provider=mock_provider)
    orch._compaction_enabled = False

    resp = await orch.chat("Hello")
    assert resp.text == "Yeah, that variable is null."
    mock_provider.count_tokens.assert_not_called()
    assert orch.compaction_count == 0


@pytest.mark.asyncio
async def test_orchestrator_compact_preserves_recent_turns(mock_provider):
    """After compaction, the last user+assistant exchange is preserved."""
    mock_provider.count_tokens = AsyncMock(return_value=110_000)

    summary_resp = AIResponse(
        text="Summary of conversation.", tool_calls=[], input_tokens=50, output_tokens=30,
    )
    final_resp = AIResponse(text="Continuing.", tool_calls=[], input_tokens=30, output_tokens=10)

    call_count = 0
    async def side_effect(**kwargs):
        nonlocal call_count
        call_count += 1
        messages = kwargs.get("messages", [])
        # First call: normal chat -> builds history
        if call_count == 1:
            return AIResponse(text="First reply.", tool_calls=[], input_tokens=50, output_tokens=20)
        # Second call: compaction summary request
        if call_count == 2:
            return summary_resp
        # Third call: after compaction, check that history was compacted
        if call_count == 3:
            # History should have: summary, last-user, last-assistant, new-user
            assert len(messages) == 4
            assert messages[0]["role"] == "user"  # summary injected as user context
            return final_resp
        return final_resp

    mock_provider.send_message = AsyncMock(side_effect=side_effect)

    orch = Orchestrator(provider=mock_provider)
    orch._compaction_enabled = True
    orch._compaction_threshold = 100_000

    await orch.chat("Build up history")
    await orch.chat("This triggers compaction")
    assert orch.compaction_count == 1
```

**Step 2: Run tests to verify they fail**

Run: `/Users/idang/Projects/TalkToMe/.venv/bin/pytest tests/test_orchestrator.py -v -k "compact"`
Expected: FAIL — `Orchestrator` has no `compaction_count`, `_compaction_enabled`, etc.

**Step 3: Implement compaction in Orchestrator**

Replace `heyducky/ai/orchestrator.py` with:

```python
"""AI orchestration - manages conversation, context, and cost."""

from __future__ import annotations

from typing import TYPE_CHECKING

from heyducky.ai.provider import AIProvider, AIResponse
from heyducky.ai.prompts import DEBUGGER_SYSTEM_PROMPT, humanize_response
from heyducky.ai.functions import DEBUGGER_TOOLS

if TYPE_CHECKING:
    from heyducky.debugger.tool_executor import ToolExecutor

COMPACTION_PROMPT = """\
Summarize this debugging conversation concisely. Preserve:
1) Files being debugged and breakpoint positions
2) Variables and their values that were discussed
3) Bugs identified and fixes applied or suggested
4) User preferences and constraints mentioned
5) Next steps the user wanted to take
6) Any git operations performed

Format as a concise paragraph. Do NOT use bullet points.
"""


class Orchestrator:
    """Manages conversation with AI provider."""

    def __init__(
        self,
        provider: AIProvider,
        tool_executor: ToolExecutor | None = None,
        compaction_enabled: bool = True,
        compaction_threshold: int = 100_000,
        max_compactions: int = 5,
    ):
        self._provider = provider
        self._tool_executor = tool_executor
        self._history: list[dict] = []
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.total_cost: float = 0.0
        self._compaction_enabled = compaction_enabled
        self._compaction_threshold = compaction_threshold
        self._max_compactions = max_compactions
        self.compaction_count: int = 0
        self._on_compaction: callable | None = None  # callback for UI notification

    async def chat(self, user_message: str) -> AIResponse:
        """Send a user message and get AI response, executing tool calls if needed."""
        self._history.append({"role": "user", "content": user_message})

        # Check if compaction is needed before sending
        if self._compaction_enabled and len(self._history) >= 4:
            await self._compact_if_needed()

        # Loop to handle tool calls
        max_rounds = 5
        for _ in range(max_rounds):
            response = await self._provider.send_message(
                messages=list(self._history),
                system=DEBUGGER_SYSTEM_PROMPT,
                tools=DEBUGGER_TOOLS,
            )

            response.text = humanize_response(response.text)
            self._track_usage(response)

            # Add assistant response to history
            if response.tool_calls:
                content = []
                if response.text:
                    content.append({"type": "text", "text": response.text})
                for tc in response.tool_calls:
                    content.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments,
                    })
                self._history.append({"role": "assistant", "content": content})

                # Execute tool calls if we have an executor
                if self._tool_executor:
                    tool_results = []
                    for tc in response.tool_calls:
                        result = await self._tool_executor.execute(tc)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tc.id,
                            "content": result,
                        })
                    self._history.append({"role": "user", "content": tool_results})
                    continue  # Get Claude's follow-up response
                else:
                    return response  # No executor, return with tool calls for caller
            else:
                self._history.append({"role": "assistant", "content": response.text})
                return response

        return response  # Safety: return last response if max rounds hit

    async def _compact_if_needed(self) -> None:
        """Check token count and compact conversation if over threshold."""
        if self.compaction_count >= self._max_compactions:
            return  # Don't compact beyond limit

        try:
            token_count = await self._provider.count_tokens(
                messages=self._history,
                system=DEBUGGER_SYSTEM_PROMPT,
                tools=DEBUGGER_TOOLS,
            )
        except Exception:
            return  # Skip compaction on error

        if token_count < self._compaction_threshold:
            return

        # Preserve the last user+assistant exchange + current new user message
        # History is: [...older..., user, assistant, ..., new_user_msg]
        # Keep last 3 messages (previous user, previous assistant, new user)
        preserved = self._history[-3:] if len(self._history) >= 3 else self._history[:]
        to_compact = self._history[:-3] if len(self._history) > 3 else self._history[:]

        if not to_compact:
            return

        # Ask the AI to summarize the older history
        summary_response = await self._provider.send_message(
            messages=to_compact + [{"role": "user", "content": COMPACTION_PROMPT}],
            system="You are a conversation summarizer. Be concise and thorough.",
        )
        self._track_usage(summary_response)

        summary_text = summary_response.text

        # Replace history with: summary context + preserved recent messages
        self._history = [
            {"role": "user", "content": f"[Previous conversation summary]: {summary_text}"},
            {"role": "assistant", "content": "Got it, I have the context. Let's continue."},
        ] + preserved

        self.compaction_count += 1

        # Notify UI if callback is set
        if self._on_compaction:
            self._on_compaction(self.compaction_count, token_count)

    def _track_usage(self, response: AIResponse) -> None:
        """Track token usage and cost."""
        self.total_input_tokens += response.input_tokens
        self.total_output_tokens += response.output_tokens
        self.total_cost += response.cost("claude")

    def add_tool_result(self, tool_call_id: str, result: str) -> None:
        """Add a tool result to conversation history."""
        self._history.append({
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_call_id,
                    "content": result,
                }
            ],
        })

    def reset(self) -> None:
        """Clear conversation history and cost tracking."""
        self._history = []
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        self.compaction_count = 0
```

**Step 4: Run compaction tests**

Run: `/Users/idang/Projects/TalkToMe/.venv/bin/pytest tests/test_orchestrator.py -v -k "compact"`
Expected: PASS

**Step 5: Run full orchestrator tests**

Run: `/Users/idang/Projects/TalkToMe/.venv/bin/pytest tests/test_orchestrator.py -v`
Expected: ALL PASS (existing tests should still work — compaction only triggers when `_compaction_enabled` is True AND history >= 4 messages AND `count_tokens` returns over threshold. The mock_provider's `count_tokens` defaults to an `AsyncMock` returning `MagicMock()` which won't be >= threshold.)

Note: If existing tests fail because `mock_provider.count_tokens` is auto-called and returns a truthy MagicMock, you may need to set `mock_provider.count_tokens = AsyncMock(return_value=0)` in the `mock_provider` fixture.

**Step 6: Commit**

```bash
git add heyducky/ai/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: add client-side conversation compaction to orchestrator"
```

---

## Task 4: Wire Compaction Config into App

**Files:**
- Modify: `heyducky/app.py`

**Step 1: Update Orchestrator instantiation in `_init_components`**

In `heyducky/app.py`, where the Orchestrator is created (~line 212), pass compaction config:

```python
self._orchestrator = Orchestrator(
    provider=provider,
    compaction_enabled=self.config.compaction_enabled,
    compaction_threshold=self.config.compaction_threshold,
    max_compactions=self.config.max_compactions,
)
```

**Step 2: Add compaction notification callback**

After creating the orchestrator, set the callback:

```python
self._orchestrator._on_compaction = self._on_compaction_occurred
```

Add a method to `HeyDuckyApp`:

```python
def _on_compaction_occurred(self, count: int, token_count: int) -> None:
    """Notify user that conversation was compacted."""
    self.call_from_thread(
        self._show_system_message,
        f"Context compacted ({count}x) — was {token_count:,} tokens. Conversation summary preserved.",
    )
```

**Step 3: Run full test suite**

Run: `/Users/idang/Projects/TalkToMe/.venv/bin/pytest -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add heyducky/app.py
git commit -m "feat: wire compaction config into app with UI notification"
```

---

## Task 5: Add Date Grouping to ChatHistory

**Files:**
- Modify: `heyducky/chat_history.py`
- Create: `tests/test_chat_history.py`

**Step 1: Write failing tests**

Create `tests/test_chat_history.py`:

```python
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

    # Create sessions with different dates
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
    # "help" appears only in first session preview
    assert len(results_all) >= 1


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
```

**Step 2: Run tests to verify they fail**

Run: `/Users/idang/Projects/TalkToMe/.venv/bin/pytest tests/test_chat_history.py -v`
Expected: FAIL on `sessions_grouped_by_date` and `search_sessions` (methods don't exist yet). Basic tests should pass.

**Step 3: Add `sessions_grouped_by_date` and `search_sessions` to ChatHistory**

In `heyducky/chat_history.py`, add these methods to the `ChatHistory` class:

```python
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
```

**Step 4: Run tests**

Run: `/Users/idang/Projects/TalkToMe/.venv/bin/pytest tests/test_chat_history.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add heyducky/chat_history.py tests/test_chat_history.py
git commit -m "feat: add date-grouped sessions and search to ChatHistory"
```

---

## Task 6: Upgrade HistoryScreen with Date Grouping and Search

**Files:**
- Modify: `heyducky/widgets/history_screen.py`

**Step 1: Rewrite HistoryScreen**

Replace `heyducky/widgets/history_screen.py` with:

```python
# heyducky/widgets/history_screen.py
"""Modal screen for browsing chat history with date grouping and search."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, OptionList
from textual.widgets.option_list import Option, Separator

from heyducky.chat_history import ChatHistory


class HistoryScreen(ModalScreen[Path | None]):
    """Modal screen showing past chat sessions grouped by date with search.

    Returns the path of the selected session, or None if cancelled.
    """

    DEFAULT_CSS = """
    HistoryScreen {
        align: center middle;
    }

    #history-container {
        width: 70;
        height: 80%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }

    #history-title {
        text-align: center;
        text-style: bold;
        width: 100%;
        margin-bottom: 1;
    }

    #history-search {
        margin-bottom: 1;
    }

    #history-hint {
        text-align: center;
        color: $text-muted;
        width: 100%;
        margin-bottom: 1;
    }

    #history-list {
        height: 1fr;
    }

    #history-empty {
        text-align: center;
        color: $text-muted;
        margin-top: 3;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Close", show=True),
        Binding("enter", "select_session", "Open", show=True),
    ]

    def __init__(self, chat_history: ChatHistory):
        super().__init__()
        self._chat_history = chat_history
        self._sessions: list[dict] = []
        self._filtered_sessions: list[dict] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="history-container"):
            yield Label("Chat History", id="history-title")
            yield Input(placeholder="Search conversations...", id="history-search")
            yield Label(
                "Enter=open  Escape=close",
                id="history-hint",
            )
            yield OptionList(id="history-list")

    def on_mount(self) -> None:
        self._sessions = self._chat_history.list_sessions()
        self._filtered_sessions = list(self._sessions)
        self._rebuild_list()
        try:
            self.query_one("#history-search", Input).focus()
        except Exception:
            pass

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter sessions as user types in search."""
        query = event.value.strip()
        if query:
            self._filtered_sessions = self._chat_history.search_sessions(query)
        else:
            self._filtered_sessions = list(self._sessions)
        self._rebuild_list()

    def _rebuild_list(self) -> None:
        """Rebuild the option list with date-grouped sessions."""
        option_list = self.query_one("#history-list", OptionList)
        option_list.clear_options()

        if not self._filtered_sessions:
            option_list.add_option(Option("No conversations found.", id="empty"))
            return

        # Group by date
        groups = self._group_by_date(self._filtered_sessions)
        first_group = True
        for group_name, sessions in groups.items():
            if not first_group:
                option_list.add_option(Separator())
            first_group = False
            # Add group header as a disabled separator-style option
            option_list.add_option(Separator())
            option_list.add_option(Option(f"  {group_name}", disabled=True))
            option_list.add_option(Separator())

            for s in sessions:
                created = s["created"][:16].replace("T", " ") if s["created"] else "?"
                count = s["message_count"]
                preview = s["preview"][:45]
                label = f"  {created}  ({count} msgs)  {preview}"
                option_list.add_option(Option(label, id=s["session_id"]))

    def _group_by_date(self, sessions: list[dict]) -> dict[str, list[dict]]:
        """Group sessions into date buckets using ChatHistory helper if available."""
        try:
            # Use ChatHistory's grouping but with our filtered list
            from datetime import datetime, timezone, timedelta

            now = datetime.now(timezone.utc)
            today = now.date()
            yesterday = today - timedelta(days=1)
            week_ago = today - timedelta(days=7)

            groups: dict[str, list[dict]] = {}
            for s in sessions:
                created = s.get("created", "")
                try:
                    dt = datetime.fromisoformat(created).date()
                except (ValueError, TypeError):
                    groups.setdefault("Older", []).append(s)
                    continue

                if dt == today:
                    groups.setdefault("Today", []).append(s)
                elif dt == yesterday:
                    groups.setdefault("Yesterday", []).append(s)
                elif dt >= week_ago:
                    groups.setdefault("This Week", []).append(s)
                else:
                    groups.setdefault("Older", []).append(s)

            # Return in display order, omitting empty groups
            ordered = {}
            for key in ["Today", "Yesterday", "This Week", "Older"]:
                if key in groups:
                    ordered[key] = groups[key]
            return ordered
        except Exception:
            return {"All": sessions}

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        """User double-clicked or pressed Enter on a session."""
        option_id = event.option_id
        if option_id and option_id != "empty":
            self._dismiss_session(option_id)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_select_session(self) -> None:
        """Select the highlighted session."""
        try:
            option_list = self.query_one("#history-list", OptionList)
            idx = option_list.highlighted
            if idx is not None:
                option = option_list.get_option_at_index(idx)
                if option.id and option.id != "empty" and not option.disabled:
                    self._dismiss_session(option.id)
        except Exception:
            pass

    def _dismiss_session(self, session_id: str) -> None:
        """Find and dismiss with the session path."""
        for s in self._sessions:
            if s["session_id"] == session_id:
                self.dismiss(s["path"])
                return
```

**Step 2: Run full test suite**

Run: `/Users/idang/Projects/TalkToMe/.venv/bin/pytest -v`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add heyducky/widgets/history_screen.py
git commit -m "feat: upgrade history screen with date grouping and search"
```

---

## Task 7: Create Settings Screen

**Files:**
- Create: `heyducky/widgets/settings_screen.py`
- Modify: `heyducky/widgets/__init__.py`
- Modify: `heyducky/app.py`

**Step 1: Create the Settings Screen widget**

Create `heyducky/widgets/settings_screen.py`:

```python
# heyducky/widgets/settings_screen.py
"""Modal settings screen for user configuration."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Collapsible, Input, Label, Select, Switch

from heyducky.config import Config


class SettingsScreen(ModalScreen[Config | None]):
    """Settings screen that returns updated Config or None if cancelled."""

    DEFAULT_CSS = """
    SettingsScreen {
        align: center middle;
    }

    #settings-container {
        width: 70;
        height: 85%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
        overflow-y: auto;
    }

    #settings-title {
        text-align: center;
        text-style: bold;
        width: 100%;
        margin-bottom: 1;
    }

    .settings-label {
        margin-top: 1;
        margin-bottom: 0;
    }

    .settings-hint {
        color: $text-muted;
        margin-bottom: 1;
    }

    #settings-buttons {
        margin-top: 2;
        height: auto;
        align: center middle;
    }

    #settings-buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    def __init__(self, config: Config):
        super().__init__()
        self._config = config

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-container"):
            yield Label("Settings", id="settings-title")

            with Collapsible(title="AI Configuration", collapsed=False):
                yield Label("API Key:", classes="settings-label")
                yield Input(
                    value=self._config.api_key,
                    password=True,
                    placeholder="sk-ant-...",
                    id="setting-api-key",
                )
                yield Label(
                    "Your Anthropic API key. Stored locally.",
                    classes="settings-hint",
                )

                yield Label("Model:", classes="settings-label")
                yield Select(
                    [
                        ("Claude Sonnet 4.5", "claude-sonnet-4-5-20250929"),
                        ("Claude Haiku 3.5", "claude-haiku-3-5-20241022"),
                    ],
                    value=self._config.ai_model,
                    id="setting-model",
                    allow_blank=False,
                )

                yield Label("Auto-Compaction:", classes="settings-label")
                yield Switch(
                    value=self._config.compaction_enabled,
                    id="setting-compaction",
                )
                yield Label(
                    "Automatically summarize long conversations to stay within context limits.",
                    classes="settings-hint",
                )

                yield Label("Compaction Threshold (tokens):", classes="settings-label")
                yield Input(
                    value=str(self._config.compaction_threshold),
                    id="setting-compaction-threshold",
                    type="integer",
                )
                yield Label(
                    "Compact when conversation exceeds this many tokens. Default: 100,000.",
                    classes="settings-hint",
                )

            with Collapsible(title="Voice Configuration"):
                yield Label("Whisper Model:", classes="settings-label")
                yield Select(
                    [
                        ("tiny.en (fastest, least accurate)", "tiny.en"),
                        ("base.en (balanced)", "base.en"),
                        ("small.en (best quality, slower)", "small.en"),
                    ],
                    value=self._config.whisper_model,
                    id="setting-whisper",
                    allow_blank=False,
                )

                yield Label("Silence Threshold:", classes="settings-label")
                yield Input(
                    value=str(self._config.silence_threshold),
                    id="setting-silence-threshold",
                )
                yield Label(
                    "Volume level below which audio is considered silence. Default: 0.02.",
                    classes="settings-hint",
                )

                yield Label("Silence Duration (seconds):", classes="settings-label")
                yield Input(
                    value=str(self._config.silence_duration),
                    id="setting-silence-duration",
                )
                yield Label(
                    "How long silence must last before stopping recording. Default: 1.5s.",
                    classes="settings-hint",
                )

            with Horizontal(id="settings-buttons"):
                yield Button("Save", variant="primary", id="settings-save")
                yield Button("Cancel", variant="default", id="settings-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "settings-save":
            self._save_and_dismiss()
        elif event.button.id == "settings-cancel":
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _save_and_dismiss(self) -> None:
        """Read all form values, build a new Config, and dismiss."""
        try:
            new_config = Config(
                ai_provider=self._config.ai_provider,
                ai_model=self.query_one("#setting-model", Select).value,
                api_key=self.query_one("#setting-api-key", Input).value,
                compaction_enabled=self.query_one("#setting-compaction", Switch).value,
                compaction_threshold=int(
                    self.query_one("#setting-compaction-threshold", Input).value or "100000"
                ),
                max_compactions=self._config.max_compactions,
                whisper_model=self.query_one("#setting-whisper", Select).value,
                sample_rate=self._config.sample_rate,
                silence_threshold=float(
                    self.query_one("#setting-silence-threshold", Input).value or "0.02"
                ),
                silence_duration=float(
                    self.query_one("#setting-silence-duration", Input).value or "1.5"
                ),
            )
            self.dismiss(new_config)
        except (ValueError, TypeError):
            # If parsing fails, don't dismiss — user can fix values
            pass
```

**Step 2: Add to widgets `__init__.py`**

In `heyducky/widgets/__init__.py`, add:

```python
from heyducky.widgets.settings_screen import SettingsScreen
```

And add `"SettingsScreen"` to `__all__`.

**Step 3: Wire into app.py**

In `heyducky/app.py`:

1. Add import: `from heyducky.widgets import SettingsScreen` (already imported via `__init__`)
2. Add binding: `Binding("s", "show_settings", "Settings", show=False, priority=True)`
3. Add action:

```python
def action_show_settings(self) -> None:
    """Open the settings screen."""
    self.push_screen(
        SettingsScreen(self.config),
        callback=self._on_settings_saved,
    )

def _on_settings_saved(self, result: Config | None) -> None:
    """Apply and persist updated settings."""
    if result is None:
        return

    result.save()
    self.config = result

    conv = self.query_one("#conversation-view", ConversationView)
    conv.add_system_message("Settings saved.")

    # Update orchestrator compaction settings if it exists
    if self._orchestrator:
        self._orchestrator._compaction_enabled = result.compaction_enabled
        self._orchestrator._compaction_threshold = result.compaction_threshold
        self._orchestrator._max_compactions = result.max_compactions
```

4. Update the on_mount hints to mention settings:
   In the `on_mount` method, update the keybinding hint line:

```python
conv.add_system_message(
    "1-5 switch tabs | t tree/source | o open project | h history | s settings"
)
```

**Step 4: Run full test suite**

Run: `/Users/idang/Projects/TalkToMe/.venv/bin/pytest -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add heyducky/widgets/settings_screen.py heyducky/widgets/__init__.py heyducky/app.py
git commit -m "feat: add settings modal screen with AI and voice configuration"
```

---

## Task 8: Add Compaction Indicator to Status Bar

**Files:**
- Modify: `heyducky/widgets/status_bar.py`

**Step 1: Add compaction_count reactive to VoiceStatusBar**

In `heyducky/widgets/status_bar.py`, add a reactive:

```python
compaction_count = reactive(0)
```

Update the `render` method to show compaction count when > 0:

```python
def render(self) -> str:
    mic = "[bold red]Recording...[/]" if self.is_recording else "[dim]Space: Talk[/]"
    cost = f"${self.session_cost:.4f}"

    if self.debug_state == "paused":
        dbg = f"[bold yellow]Paused[/] at {self.debug_file}:{self.debug_line}"
    elif self.debug_state == "running":
        dbg = "[bold green]Running[/]"
    elif self.debug_state == "stopped":
        dbg = "[dim]Stopped[/]"
    else:
        dbg = "[dim]No debug session[/]"

    compact = f"  |  [dim]Compacted {self.compaction_count}x[/]" if self.compaction_count else ""

    return f"{mic}  |  {dbg}  |  {self.provider_name}  |  {cost}{compact}"
```

**Step 2: Wire compaction callback in app.py**

Update `_on_compaction_occurred` in `app.py` to also update status bar:

```python
def _on_compaction_occurred(self, count: int, token_count: int) -> None:
    """Notify user that conversation was compacted."""
    self.call_from_thread(
        self._show_system_message,
        f"Context compacted ({count}x) — was {token_count:,} tokens. Conversation summary preserved.",
    )
    self.call_from_thread(self._update_compaction_count, count)

def _update_compaction_count(self, count: int) -> None:
    self.query_one("#status-bar", VoiceStatusBar).compaction_count = count
```

**Step 3: Run full test suite**

Run: `/Users/idang/Projects/TalkToMe/.venv/bin/pytest -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add heyducky/widgets/status_bar.py heyducky/app.py
git commit -m "feat: show compaction count in status bar"
```

---

## Task 9: Final Integration Test & Polish

**Files:**
- All modified files

**Step 1: Run full test suite**

Run: `/Users/idang/Projects/TalkToMe/.venv/bin/pytest -v`
Expected: ALL PASS

**Step 2: If any tests fail, fix them**

Common issues to watch for:
- `mock_provider` fixture may need `count_tokens = AsyncMock(return_value=0)` added
- `OptionList.get_option_at_index` might differ in Textual version — check API
- `Select` widget might need `allow_blank` parameter check for Textual version

**Step 3: Manual smoke test**

Run: `cd /Users/idang/Projects/TalkToMe && .venv/bin/python -m heyducky`

Verify:
- App launches without errors
- Press `s` — settings modal opens with AI and voice sections
- Press `h` — history modal shows date-grouped sessions with search bar
- Press `Escape` to close modals
- Status bar shows normally

**Step 4: Final commit if any polish was needed**

```bash
git add -A
git commit -m "chore: polish and integration fixes for memory/settings/compaction"
```

---

## Summary of Changes

| File | Change |
|------|--------|
| `heyducky/config.py` | Added `compaction_enabled`, `compaction_threshold`, `max_compactions` fields |
| `heyducky/ai/provider.py` | Added abstract `count_tokens` method |
| `heyducky/ai/claude.py` | Implemented `count_tokens` using Anthropic API |
| `heyducky/ai/orchestrator.py` | Added client-side compaction with summary preservation |
| `heyducky/chat_history.py` | Added `sessions_grouped_by_date` and `search_sessions` methods |
| `heyducky/widgets/history_screen.py` | Upgraded with date grouping, search input, improved UX |
| `heyducky/widgets/settings_screen.py` | **New** — Modal settings screen with Collapsible sections |
| `heyducky/widgets/status_bar.py` | Added compaction count display |
| `heyducky/widgets/__init__.py` | Added `SettingsScreen` export |
| `heyducky/app.py` | Wired compaction, settings keybinding, updated hints |
| `tests/test_config.py` | Added compaction config tests |
| `tests/test_ai_provider.py` | Added `count_tokens` test |
| `tests/test_orchestrator.py` | Added compaction tests |
| `tests/test_chat_history.py` | **New** — ChatHistory tests including date grouping and search |
