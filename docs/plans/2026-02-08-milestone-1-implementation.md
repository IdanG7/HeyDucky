# Milestone 1: Voice + AI Conversation TUI - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a terminal TUI where you press Space to talk, speech gets transcribed locally via Whisper, and Claude responds as a natural pair-programming partner.

**Architecture:** Textual app with three panels (source placeholder, conversation, status bar). Voice input via sounddevice + faster-whisper running in background threads. AI via Anthropic async SDK with conversational system prompt and stubbed debugger tools. Toggle-to-talk (Space to start, Space to stop) since terminals can't detect key release.

**Tech Stack:** Python 3.10+, Textual, Rich, faster-whisper, sounddevice, numpy, anthropic SDK

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `voice_debugger/__init__.py`
- Create: `voice_debugger/__main__.py`
- Create: `tests/__init__.py`

**Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "voice-debugger"
version = "0.1.0"
description = "Voice-controlled AI debugging assistant"
requires-python = ">=3.10"
dependencies = [
    "textual>=0.50.0",
    "rich>=13.7.0",
    "faster-whisper>=1.0.0",
    "sounddevice>=0.4.6",
    "numpy>=1.26.0",
    "anthropic>=0.40.0",
    "toml>=0.10.2",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "ruff>=0.1.0",
]

[project.scripts]
voice-debugger = "voice_debugger.__main__:main"
```

**Step 2: Create voice_debugger/__init__.py**

```python
"""Voice-controlled AI debugging assistant."""
```

**Step 3: Create voice_debugger/__main__.py**

```python
"""CLI entry point for voice-debugger."""

def main():
    from voice_debugger.app import VoiceDebuggerApp
    app = VoiceDebuggerApp()
    app.run()

if __name__ == "__main__":
    main()
```

**Step 4: Create tests/__init__.py**

Empty file.

**Step 5: Create virtual environment and install**

Run: `cd /Users/idang/Projects/TalkToMe && python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`

**Step 6: Initialize git repo**

Run: `cd /Users/idang/Projects/TalkToMe && git init && echo -e ".venv/\n__pycache__/\n*.egg-info/\n.eggs/\ndist/\nbuild/\n*.pyc\n.ruff_cache/\n" > .gitignore`

**Step 7: Commit**

```bash
git add pyproject.toml voice_debugger/ tests/ .gitignore docs/
git commit -m "feat: initial project scaffolding"
```

---

### Task 2: Configuration Module

**Files:**
- Create: `voice_debugger/config.py`
- Create: `tests/test_config.py`

**Step 1: Write the failing test**

```python
# tests/test_config.py
import os
import tempfile
from pathlib import Path
from voice_debugger.config import Config


def test_default_config():
    """Config has sensible defaults."""
    config = Config()
    assert config.ai_provider == "claude"
    assert config.whisper_model == "base.en"
    assert config.sample_rate == 16000


def test_config_from_dict():
    """Config can be created from a dictionary."""
    config = Config.from_dict({
        "ai": {"provider": "claude", "model": "claude-sonnet-4-5-20250929"},
        "voice": {"whisper_model": "tiny.en", "sample_rate": 16000},
    })
    assert config.ai_model == "claude-sonnet-4-5-20250929"
    assert config.whisper_model == "tiny.en"


def test_config_save_and_load(tmp_path):
    """Config round-trips through TOML file."""
    config_path = tmp_path / "config.toml"
    config = Config()
    config.api_key = "test-key-123"
    config.save(config_path)

    loaded = Config.load(config_path)
    assert loaded.api_key == "test-key-123"
    assert loaded.ai_provider == config.ai_provider


def test_config_load_missing_file():
    """Loading non-existent file returns defaults."""
    config = Config.load(Path("/nonexistent/config.toml"))
    assert config.ai_provider == "claude"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/idang/Projects/TalkToMe && python -m pytest tests/test_config.py -v`
Expected: FAIL (ImportError - module doesn't exist)

**Step 3: Write the implementation**

```python
# voice_debugger/config.py
"""Configuration management for voice-debugger."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path

import toml


DEFAULT_CONFIG_DIR = Path.home() / ".config" / "voice-debugger"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.toml"


@dataclass
class Config:
    """Application configuration."""

    # AI settings
    ai_provider: str = "claude"
    ai_model: str = "claude-sonnet-4-5-20250929"
    api_key: str = ""

    # Voice settings
    whisper_model: str = "base.en"
    sample_rate: int = 16000
    silence_threshold: float = 0.02
    silence_duration: float = 1.5

    @classmethod
    def from_dict(cls, data: dict) -> Config:
        """Create Config from nested dictionary (TOML structure)."""
        ai = data.get("ai", {})
        voice = data.get("voice", {})
        return cls(
            ai_provider=ai.get("provider", "claude"),
            ai_model=ai.get("model", "claude-sonnet-4-5-20250929"),
            api_key=ai.get("api_key", ""),
            whisper_model=voice.get("whisper_model", "base.en"),
            sample_rate=voice.get("sample_rate", 16000),
            silence_threshold=voice.get("silence_threshold", 0.02),
            silence_duration=voice.get("silence_duration", 1.5),
        )

    def to_dict(self) -> dict:
        """Convert to nested dictionary for TOML serialization."""
        return {
            "ai": {
                "provider": self.ai_provider,
                "model": self.ai_model,
                "api_key": self.api_key,
            },
            "voice": {
                "whisper_model": self.whisper_model,
                "sample_rate": self.sample_rate,
                "silence_threshold": self.silence_threshold,
                "silence_duration": self.silence_duration,
            },
        }

    def save(self, path: Path | None = None) -> None:
        """Save config to TOML file."""
        path = path or DEFAULT_CONFIG_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            toml.dump(self.to_dict(), f)

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        """Load config from TOML file. Returns defaults if file missing."""
        path = path or DEFAULT_CONFIG_PATH
        if not path.exists():
            return cls()
        with open(path) as f:
            data = toml.load(f)
        return cls.from_dict(data)
```

**Step 4: Run tests**

Run: `cd /Users/idang/Projects/TalkToMe && python -m pytest tests/test_config.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add voice_debugger/config.py tests/test_config.py
git commit -m "feat: add configuration module with TOML persistence"
```

---

### Task 3: AI Provider Abstraction & System Prompts

**Files:**
- Create: `voice_debugger/ai/__init__.py`
- Create: `voice_debugger/ai/provider.py`
- Create: `voice_debugger/ai/prompts.py`
- Create: `voice_debugger/ai/functions.py`
- Create: `tests/test_ai_provider.py`

**Step 1: Write the failing tests**

```python
# tests/test_ai_provider.py
"""Tests for AI provider abstraction."""

from voice_debugger.ai.provider import AIProvider, AIResponse
from voice_debugger.ai.prompts import DEBUGGER_SYSTEM_PROMPT, humanize_response
from voice_debugger.ai.functions import DEBUGGER_TOOLS


def test_ai_response_dataclass():
    """AIResponse stores text, tool calls, and usage."""
    resp = AIResponse(
        text="Found a bug",
        tool_calls=[],
        input_tokens=10,
        output_tokens=20,
    )
    assert resp.text == "Found a bug"
    assert resp.input_tokens == 10
    assert resp.cost("claude") > 0


def test_humanize_response_removes_ai_isms():
    """humanize_response strips robotic patterns."""
    text = "Certainly! I shall inspect the variable. As an AI, I cannot actually run code."
    result = humanize_response(text)
    assert "Certainly!" not in result
    assert "I shall" not in result
    assert "As an AI" not in result
    assert "I'll" in result


def test_humanize_response_casualizes():
    """humanize_response converts formal to casual."""
    text = "I cannot do that. Let us try something else. I do not know."
    result = humanize_response(text)
    assert "can't" in result
    assert "Let's" in result
    assert "don't" in result


def test_system_prompt_exists():
    """System prompt is a non-empty string with key characteristics."""
    assert len(DEBUGGER_SYSTEM_PROMPT) > 100
    assert "pair" in DEBUGGER_SYSTEM_PROMPT.lower()


def test_debugger_tools_structure():
    """Tool definitions have required fields."""
    assert len(DEBUGGER_TOOLS) >= 5
    for tool in DEBUGGER_TOOLS:
        assert "name" in tool
        assert "description" in tool
        assert "input_schema" in tool


def test_ai_response_cost_calculation():
    """Cost calculation uses correct per-token rates."""
    resp = AIResponse(text="", tool_calls=[], input_tokens=1000, output_tokens=500)
    cost = resp.cost("claude")
    assert cost > 0
    assert isinstance(cost, float)
```

**Step 2: Run tests to verify failure**

Run: `cd /Users/idang/Projects/TalkToMe && python -m pytest tests/test_ai_provider.py -v`
Expected: FAIL (ImportError)

**Step 3: Create ai/__init__.py**

```python
# voice_debugger/ai/__init__.py
"""AI provider modules."""
```

**Step 4: Write provider.py**

```python
# voice_debugger/ai/provider.py
"""Abstract AI provider and response types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


# Approximate per-token costs (USD)
COST_PER_TOKEN = {
    "claude": {"input": 3.0 / 1_000_000, "output": 15.0 / 1_000_000},
}


@dataclass
class ToolCall:
    """A function/tool call from the AI."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class AIResponse:
    """Response from an AI provider."""

    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0

    def cost(self, provider: str) -> float:
        """Calculate cost in USD for this response."""
        rates = COST_PER_TOKEN.get(provider, COST_PER_TOKEN["claude"])
        return (
            self.input_tokens * rates["input"]
            + self.output_tokens * rates["output"]
        )


class AIProvider(ABC):
    """Abstract base for AI providers."""

    @abstractmethod
    async def send_message(
        self,
        messages: list[dict],
        system: str = "",
        tools: list[dict] | None = None,
    ) -> AIResponse:
        """Send messages and get a response."""
        ...

    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier."""
        ...
```

**Step 5: Write prompts.py**

```python
# voice_debugger/ai/prompts.py
"""System prompts and response post-processing."""

DEBUGGER_SYSTEM_PROMPT = """\
You're pair programming with a colleague who's debugging.
You're the one at the keyboard with access to the debugger.

YOUR PERSONALITY:
- Talk like you're on a video call debugging together
- Think out loud - show your reasoning
- Use casual language: "yeah", "hmm", "wait"
- Have opinions and push back when needed
- Get excited when you find bugs
- Admit uncertainty

HOW YOU DEBUG:
- Just do things naturally, don't announce tool use
- Think step-by-step aloud
- Challenge bad assumptions
- Suggest concrete fixes, not generic advice

CRITICAL RULES:
- NEVER say "I'm an AI" or "as an AI assistant"
- Don't apologize excessively
- Keep responses SHORT (2-3 sentences)
- Use contractions always

Available debugger functions (use naturally, don't announce):
- set_breakpoint(file, line, condition?)
- inspect_variable(name)
- step_over() / step_into() / step_out()
- continue_execution()
- evaluate_expression(expr)
- get_call_stack()
"""

_REPLACEMENTS = {
    "Certainly!": "",
    "Certainly,": "",
    "I shall": "I'll",
    "cannot": "can't",
    "do not": "don't",
    "does not": "doesn't",
    "Let us": "Let's",
    "I am": "I'm",
    "As an AI": "",
    "as an AI assistant": "",
    "I cannot actually": "I can't",
}


def humanize_response(text: str) -> str:
    """Remove robotic patterns from AI response."""
    for formal, casual in _REPLACEMENTS.items():
        text = text.replace(formal, casual)
    # Clean up double spaces from removals
    while "  " in text:
        text = text.replace("  ", " ")
    return text.strip()
```

**Step 6: Write functions.py**

```python
# voice_debugger/ai/functions.py
"""Tool/function definitions for debugger operations."""

DEBUGGER_TOOLS = [
    {
        "name": "set_breakpoint",
        "description": "Set a breakpoint at a specific line in a file",
        "input_schema": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "File path"},
                "line": {"type": "integer", "description": "Line number"},
                "condition": {"type": "string", "description": "Optional breakpoint condition"},
            },
            "required": ["file", "line"],
        },
    },
    {
        "name": "inspect_variable",
        "description": "Inspect the value of a variable in the current scope",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Variable name"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "step_over",
        "description": "Execute the current line and move to the next",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "step_into",
        "description": "Step into a function call on the current line",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "step_out",
        "description": "Step out of the current function",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "continue_execution",
        "description": "Resume execution until the next breakpoint",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "evaluate_expression",
        "description": "Evaluate an expression in the current debug context",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "Expression to evaluate"},
            },
            "required": ["expression"],
        },
    },
    {
        "name": "get_call_stack",
        "description": "Get the current call stack",
        "input_schema": {"type": "object", "properties": {}},
    },
]
```

**Step 7: Run tests**

Run: `cd /Users/idang/Projects/TalkToMe && python -m pytest tests/test_ai_provider.py -v`
Expected: All 6 tests PASS

**Step 8: Commit**

```bash
git add voice_debugger/ai/ tests/test_ai_provider.py
git commit -m "feat: add AI provider abstraction, system prompts, and tool definitions"
```

---

### Task 4: Claude Provider Implementation

**Files:**
- Create: `voice_debugger/ai/claude.py`
- Create: `tests/test_claude.py`

**Step 1: Write the failing test**

```python
# tests/test_claude.py
"""Tests for Claude provider (uses mocked API)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from voice_debugger.ai.claude import ClaudeProvider
from voice_debugger.ai.provider import AIResponse


@pytest.fixture
def mock_anthropic():
    """Create a mocked AsyncAnthropic client."""
    with patch("voice_debugger.ai.claude.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client

        # Mock a simple text response
        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="Looks like a null pointer.")]
        mock_response.stop_reason = "end_turn"
        mock_response.usage = MagicMock(input_tokens=50, output_tokens=20)
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        yield mock_client


@pytest.mark.asyncio
async def test_claude_send_message(mock_anthropic):
    """ClaudeProvider sends messages and returns AIResponse."""
    provider = ClaudeProvider(api_key="test-key")
    resp = await provider.send_message(
        messages=[{"role": "user", "content": "What's wrong?"}],
        system="You are a debugger.",
    )
    assert isinstance(resp, AIResponse)
    assert "null pointer" in resp.text
    assert resp.input_tokens == 50
    assert resp.output_tokens == 20


@pytest.mark.asyncio
async def test_claude_handles_tool_use(mock_anthropic):
    """ClaudeProvider extracts tool calls from response."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.id = "tool_123"
    tool_block.name = "inspect_variable"
    tool_block.input = {"name": "x"}

    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "Let me check x."

    mock_response = MagicMock()
    mock_response.content = [text_block, tool_block]
    mock_response.stop_reason = "tool_use"
    mock_response.usage = MagicMock(input_tokens=30, output_tokens=15)
    mock_anthropic.messages.create = AsyncMock(return_value=mock_response)

    provider = ClaudeProvider(api_key="test-key")
    resp = await provider.send_message(
        messages=[{"role": "user", "content": "Check variable x"}],
    )
    assert resp.text == "Let me check x."
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "inspect_variable"
    assert resp.tool_calls[0].arguments == {"name": "x"}


def test_claude_model_name():
    """model_name returns configured model."""
    with patch("voice_debugger.ai.claude.AsyncAnthropic"):
        provider = ClaudeProvider(api_key="k", model="claude-opus-4-6")
        assert provider.model_name() == "claude-opus-4-6"
```

**Step 2: Run tests to verify failure**

Run: `cd /Users/idang/Projects/TalkToMe && python -m pytest tests/test_claude.py -v`
Expected: FAIL (ImportError)

**Step 3: Write the implementation**

```python
# voice_debugger/ai/claude.py
"""Anthropic Claude AI provider."""

from __future__ import annotations

from anthropic import AsyncAnthropic

from voice_debugger.ai.provider import AIProvider, AIResponse, ToolCall


class ClaudeProvider(AIProvider):
    """Anthropic Claude provider."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5-20250929"):
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    async def send_message(
        self,
        messages: list[dict],
        system: str = "",
        tools: list[dict] | None = None,
    ) -> AIResponse:
        """Send messages to Claude and return response."""
        kwargs: dict = {
            "model": self._model,
            "max_tokens": 1024,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        response = await self._client.messages.create(**kwargs)

        # Extract text and tool calls
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=block.input,
                    )
                )

        return AIResponse(
            text=" ".join(text_parts),
            tool_calls=tool_calls,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    def model_name(self) -> str:
        return self._model
```

**Step 4: Run tests**

Run: `cd /Users/idang/Projects/TalkToMe && python -m pytest tests/test_claude.py -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add voice_debugger/ai/claude.py tests/test_claude.py
git commit -m "feat: add Claude provider implementation"
```

---

### Task 5: AI Orchestrator

**Files:**
- Create: `voice_debugger/ai/orchestrator.py`
- Create: `tests/test_orchestrator.py`

**Step 1: Write the failing test**

```python
# tests/test_orchestrator.py
"""Tests for AI orchestrator."""

import pytest
from unittest.mock import AsyncMock, patch
from voice_debugger.ai.orchestrator import Orchestrator
from voice_debugger.ai.provider import AIResponse, ToolCall
from voice_debugger.config import Config


@pytest.fixture
def mock_provider():
    """Create a mock AI provider."""
    provider = AsyncMock()
    provider.send_message = AsyncMock(
        return_value=AIResponse(
            text="Yeah, that variable is null.",
            tool_calls=[],
            input_tokens=50,
            output_tokens=20,
        )
    )
    provider.model_name.return_value = "claude-sonnet-4-5-20250929"
    return provider


@pytest.mark.asyncio
async def test_orchestrator_sends_user_message(mock_provider):
    """Orchestrator sends user message and returns humanized response."""
    orch = Orchestrator(provider=mock_provider)
    resp = await orch.chat("What's wrong with this code?")
    assert resp.text == "Yeah, that variable is null."
    mock_provider.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_orchestrator_builds_message_history(mock_provider):
    """Orchestrator accumulates conversation history."""
    orch = Orchestrator(provider=mock_provider)
    await orch.chat("First message")
    await orch.chat("Second message")

    # Check that second call includes history
    call_args = mock_provider.send_message.call_args_list[1]
    messages = call_args.kwargs.get("messages") or call_args[0][0]
    # Should have: user1, assistant1, user2
    assert len(messages) == 3


@pytest.mark.asyncio
async def test_orchestrator_tracks_cost(mock_provider):
    """Orchestrator tracks cumulative cost."""
    orch = Orchestrator(provider=mock_provider)
    await orch.chat("Hello")
    assert orch.total_cost > 0
    assert orch.total_input_tokens == 50
    assert orch.total_output_tokens == 20


@pytest.mark.asyncio
async def test_orchestrator_handles_tool_calls(mock_provider):
    """Orchestrator returns tool calls for execution."""
    mock_provider.send_message = AsyncMock(
        return_value=AIResponse(
            text="Let me check that.",
            tool_calls=[
                ToolCall(id="t1", name="inspect_variable", arguments={"name": "x"})
            ],
            input_tokens=30,
            output_tokens=15,
        )
    )
    orch = Orchestrator(provider=mock_provider)
    resp = await orch.chat("What is x?")
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "inspect_variable"


def test_orchestrator_reset(mock_provider):
    """Orchestrator reset clears history and cost."""
    orch = Orchestrator(provider=mock_provider)
    orch._history = [{"role": "user", "content": "test"}]
    orch.total_input_tokens = 100
    orch.reset()
    assert orch._history == []
    assert orch.total_input_tokens == 0
    assert orch.total_cost == 0
```

**Step 2: Run tests to verify failure**

Run: `cd /Users/idang/Projects/TalkToMe && python -m pytest tests/test_orchestrator.py -v`
Expected: FAIL (ImportError)

**Step 3: Write the implementation**

```python
# voice_debugger/ai/orchestrator.py
"""AI orchestration - manages conversation, context, and cost."""

from __future__ import annotations

from voice_debugger.ai.provider import AIProvider, AIResponse, COST_PER_TOKEN
from voice_debugger.ai.prompts import DEBUGGER_SYSTEM_PROMPT, humanize_response
from voice_debugger.ai.functions import DEBUGGER_TOOLS


class Orchestrator:
    """Manages conversation with AI provider."""

    def __init__(self, provider: AIProvider):
        self._provider = provider
        self._history: list[dict] = []
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.total_cost: float = 0.0

    async def chat(self, user_message: str) -> AIResponse:
        """Send a user message and get AI response."""
        self._history.append({"role": "user", "content": user_message})

        response = await self._provider.send_message(
            messages=list(self._history),
            system=DEBUGGER_SYSTEM_PROMPT,
            tools=DEBUGGER_TOOLS,
        )

        # Humanize text
        response.text = humanize_response(response.text)

        # Add assistant response to history
        self._history.append({"role": "assistant", "content": response.text})

        # Track usage
        self.total_input_tokens += response.input_tokens
        self.total_output_tokens += response.output_tokens
        self.total_cost += response.cost("claude")

        return response

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
```

**Step 4: Run tests**

Run: `cd /Users/idang/Projects/TalkToMe && python -m pytest tests/test_orchestrator.py -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add voice_debugger/ai/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: add AI orchestrator with conversation management and cost tracking"
```

---

### Task 6: Voice Handler (STT Only)

**Files:**
- Create: `voice_debugger/voice.py`
- Create: `tests/test_voice.py`

**Step 1: Write the failing test**

```python
# tests/test_voice.py
"""Tests for voice handler."""

import numpy as np
import pytest
from unittest.mock import patch, MagicMock
from voice_debugger.voice import VoiceHandler, trim_silence


def test_trim_silence_removes_leading_trailing():
    """trim_silence removes quiet parts from start and end."""
    sr = 16000
    # 0.5s silence + 1s speech + 0.5s silence
    silence = np.zeros(sr // 2, dtype=np.float32)
    speech = np.random.randn(sr).astype(np.float32) * 0.5
    audio = np.concatenate([silence, speech, silence])

    trimmed = trim_silence(audio, threshold=0.02, sr=sr)
    # Trimmed should be shorter than original
    assert len(trimmed) < len(audio)
    # Trimmed should still contain speech
    assert len(trimmed) >= sr * 0.8  # at least most of the speech


def test_trim_silence_all_silent():
    """trim_silence returns empty for pure silence."""
    silence = np.zeros(16000, dtype=np.float32)
    trimmed = trim_silence(silence, threshold=0.02, sr=16000)
    assert len(trimmed) == 0


def test_voice_handler_init():
    """VoiceHandler initializes with config defaults."""
    with patch("voice_debugger.voice.WhisperModel") as mock_whisper:
        handler = VoiceHandler(whisper_model="tiny.en")
        assert handler.sample_rate == 16000
        assert handler._is_recording is False


def test_voice_handler_transcribe():
    """VoiceHandler transcribes audio buffer."""
    with patch("voice_debugger.voice.WhisperModel") as mock_whisper_cls:
        mock_model = MagicMock()
        mock_segment = MagicMock()
        mock_segment.text = " Hello world "
        mock_info = MagicMock()
        mock_model.transcribe.return_value = ([mock_segment], mock_info)
        mock_whisper_cls.return_value = mock_model

        handler = VoiceHandler(whisper_model="tiny.en")
        audio = np.random.randn(16000).astype(np.float32) * 0.5
        result = handler.transcribe(audio)
        assert result == "Hello world"
```

**Step 2: Run tests to verify failure**

Run: `cd /Users/idang/Projects/TalkToMe && python -m pytest tests/test_voice.py -v`
Expected: FAIL (ImportError)

**Step 3: Write the implementation**

```python
# voice_debugger/voice.py
"""Voice input handler - recording and transcription."""

from __future__ import annotations

import threading
from typing import Callable

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel


def trim_silence(
    audio: np.ndarray,
    threshold: float = 0.02,
    sr: int = 16000,
    frame_length: int = 1024,
) -> np.ndarray:
    """Trim leading and trailing silence from audio.

    Args:
        audio: 1D float32 audio array.
        threshold: RMS threshold below which frames are considered silent.
        sr: Sample rate (unused but kept for API clarity).
        frame_length: Number of samples per analysis frame.

    Returns:
        Trimmed audio array, or empty array if all silent.
    """
    if len(audio) == 0:
        return audio

    # Calculate RMS energy per frame
    n_frames = len(audio) // frame_length
    if n_frames == 0:
        rms = np.sqrt(np.mean(audio ** 2))
        return audio if rms > threshold else np.array([], dtype=np.float32)

    frames = audio[: n_frames * frame_length].reshape(n_frames, frame_length)
    rms = np.sqrt(np.mean(frames ** 2, axis=1))

    # Find first and last frames above threshold
    active = np.where(rms > threshold)[0]
    if len(active) == 0:
        return np.array([], dtype=np.float32)

    start = active[0] * frame_length
    end = min((active[-1] + 1) * frame_length, len(audio))
    return audio[start:end]


class VoiceHandler:
    """Handles audio recording and speech-to-text transcription."""

    def __init__(
        self,
        whisper_model: str = "base.en",
        sample_rate: int = 16000,
        silence_threshold: float = 0.02,
    ):
        self.sample_rate = sample_rate
        self.silence_threshold = silence_threshold
        self._model = WhisperModel(whisper_model, device="cpu", compute_type="int8")
        self._is_recording = False
        self._audio_buffer: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()

    def start_recording(self) -> None:
        """Start recording audio from microphone."""
        if self._is_recording:
            return
        self._audio_buffer = []
        self._is_recording = True
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            callback=self._audio_callback,
            blocksize=1024,
        )
        self._stream.start()

    def stop_recording(self) -> np.ndarray:
        """Stop recording and return the audio buffer.

        Returns:
            1D numpy array of recorded audio, trimmed of silence.
        """
        self._is_recording = False
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        with self._lock:
            if not self._audio_buffer:
                return np.array([], dtype=np.float32)
            audio = np.concatenate(self._audio_buffer).flatten()
            self._audio_buffer = []

        return trim_silence(audio, threshold=self.silence_threshold, sr=self.sample_rate)

    def transcribe(self, audio: np.ndarray) -> str:
        """Transcribe audio to text using Whisper.

        Args:
            audio: 1D float32 audio array at self.sample_rate.

        Returns:
            Transcribed text, stripped of whitespace.
        """
        if len(audio) == 0:
            return ""
        segments, _info = self._model.transcribe(audio, beam_size=5, language="en")
        text = " ".join(seg.text for seg in segments)
        return text.strip()

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    def _audio_callback(
        self, indata: np.ndarray, frames: int, time_info: object, status: object
    ) -> None:
        """sounddevice callback - runs in audio thread."""
        if status:
            pass  # Could log status warnings
        if self._is_recording:
            with self._lock:
                self._audio_buffer.append(indata.copy())
```

**Step 4: Run tests**

Run: `cd /Users/idang/Projects/TalkToMe && python -m pytest tests/test_voice.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add voice_debugger/voice.py tests/test_voice.py
git commit -m "feat: add voice handler with recording and Whisper transcription"
```

---

### Task 7: TUI Widgets

**Files:**
- Create: `voice_debugger/widgets/__init__.py`
- Create: `voice_debugger/widgets/source_view.py`
- Create: `voice_debugger/widgets/conversation.py`
- Create: `voice_debugger/widgets/status_bar.py`

**Step 1: Create widgets/__init__.py**

```python
# voice_debugger/widgets/__init__.py
"""TUI widget components."""

from voice_debugger.widgets.source_view import SourceView
from voice_debugger.widgets.conversation import ConversationView
from voice_debugger.widgets.status_bar import VoiceStatusBar

__all__ = ["SourceView", "ConversationView", "VoiceStatusBar"]
```

**Step 2: Write source_view.py (placeholder)**

```python
# voice_debugger/widgets/source_view.py
"""Source code view widget (placeholder for Milestone 1)."""

from textual.widgets import Static


class SourceView(Static):
    """Displays source code. Placeholder until debugger integration."""

    DEFAULT_CSS = """
    SourceView {
        height: 40%;
        border: solid $primary;
        padding: 1 2;
        color: $text-muted;
    }
    """

    def __init__(self, **kwargs):
        super().__init__("No file loaded. Start a debug session to view source.", **kwargs)
```

**Step 3: Write conversation.py**

```python
# voice_debugger/widgets/conversation.py
"""Conversation view widget for chat display."""

from __future__ import annotations

from textual.widgets import RichLog
from rich.text import Text


class ConversationView(RichLog):
    """Scrollable conversation view showing user/AI messages."""

    DEFAULT_CSS = """
    ConversationView {
        height: 1fr;
        border: solid $accent;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(markup=True, wrap=True, **kwargs)

    def add_user_message(self, text: str) -> None:
        """Add a user message to the conversation."""
        msg = Text()
        msg.append("You: ", style="bold cyan")
        msg.append(text)
        self.write(msg)

    def add_ai_message(self, text: str) -> None:
        """Add an AI response to the conversation."""
        msg = Text()
        msg.append("AI: ", style="bold green")
        msg.append(text)
        self.write(msg)

    def add_system_message(self, text: str) -> None:
        """Add a system/status message."""
        msg = Text()
        msg.append(text, style="dim italic")
        self.write(msg)

    def add_tool_message(self, tool_name: str, args: dict) -> None:
        """Show a tool call (stubbed for now)."""
        msg = Text()
        msg.append(f"  [tool] {tool_name}", style="yellow")
        if args:
            msg.append(f"({args})", style="dim yellow")
        self.write(msg)
```

**Step 4: Write status_bar.py**

```python
# voice_debugger/widgets/status_bar.py
"""Status bar widget showing mic state, provider, and cost."""

from __future__ import annotations

from textual.widgets import Static
from textual.reactive import reactive


class VoiceStatusBar(Static):
    """Status bar showing recording state, AI provider, and session cost."""

    DEFAULT_CSS = """
    VoiceStatusBar {
        height: 3;
        background: $boost;
        padding: 0 2;
        content-align: left middle;
    }
    """

    is_recording = reactive(False)
    provider_name = reactive("Claude")
    session_cost = reactive(0.0)

    def render(self) -> str:
        mic = "[bold red]Recording...[/]" if self.is_recording else "[dim]Press Space to talk[/]"
        cost = f"${self.session_cost:.4f}"
        return f"{mic}  |  Provider: {self.provider_name}  |  Cost: {cost}"
```

**Step 5: Verify widgets import cleanly**

Run: `cd /Users/idang/Projects/TalkToMe && python -c "from voice_debugger.widgets import SourceView, ConversationView, VoiceStatusBar; print('OK')"`
Expected: `OK`

**Step 6: Commit**

```bash
git add voice_debugger/widgets/
git commit -m "feat: add TUI widgets - source view, conversation, status bar"
```

---

### Task 8: Main Textual Application

**Files:**
- Create: `voice_debugger/app.py`
- Modify: `voice_debugger/__main__.py`

**Step 1: Write app.py**

```python
# voice_debugger/app.py
"""Main Textual TUI application."""

from __future__ import annotations

import os

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.widgets import Header, Footer
from textual.worker import Worker, get_current_worker

from voice_debugger.config import Config
from voice_debugger.widgets import SourceView, ConversationView, VoiceStatusBar


class VoiceDebuggerApp(App):
    """Voice-controlled AI debugging assistant."""

    TITLE = "Voice Debugger"
    SUB_TITLE = "AI Pair Programming"

    CSS = """
    Screen {
        background: $surface;
    }

    #main-container {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("space", "toggle_recording", "Talk", show=True),
    ]

    def __init__(self):
        super().__init__()
        self.config = Config.load()
        self._voice = None
        self._orchestrator = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            SourceView(id="source-view"),
            ConversationView(id="conversation"),
            VoiceStatusBar(id="status-bar"),
            id="main-container",
        )
        yield Footer()

    def on_mount(self) -> None:
        """Initialize components after mount."""
        conv = self.query_one("#conversation", ConversationView)
        conv.add_system_message("Welcome to Voice Debugger. Press Space to talk.")

        # Lazy-load heavy components
        self._init_components()

    def _init_components(self) -> None:
        """Initialize voice and AI components."""
        # Initialize voice handler in background
        self._init_voice_worker()

        # Initialize AI
        api_key = self.config.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if api_key:
            from voice_debugger.ai.claude import ClaudeProvider
            from voice_debugger.ai.orchestrator import Orchestrator

            provider = ClaudeProvider(api_key=api_key, model=self.config.ai_model)
            self._orchestrator = Orchestrator(provider=provider)
        else:
            conv = self.query_one("#conversation", ConversationView)
            conv.add_system_message(
                "No API key configured. Set ANTHROPIC_API_KEY env var or run with --setup."
            )

    @work(thread=True, exclusive=True, group="voice-init")
    def _init_voice_worker(self) -> None:
        """Load Whisper model in background thread."""
        try:
            from voice_debugger.voice import VoiceHandler

            self._voice = VoiceHandler(
                whisper_model=self.config.whisper_model,
                sample_rate=self.config.sample_rate,
                silence_threshold=self.config.silence_threshold,
            )
            self.call_from_thread(self._on_voice_ready)
        except Exception as e:
            self.call_from_thread(self._on_voice_error, str(e))

    def _on_voice_ready(self) -> None:
        conv = self.query_one("#conversation", ConversationView)
        conv.add_system_message("Voice ready. Press Space to talk.")

    def _on_voice_error(self, error: str) -> None:
        conv = self.query_one("#conversation", ConversationView)
        conv.add_system_message(f"Voice init failed: {error}")

    def action_toggle_recording(self) -> None:
        """Toggle voice recording on/off."""
        if self._voice is None:
            conv = self.query_one("#conversation", ConversationView)
            conv.add_system_message("Voice not ready yet. Please wait...")
            return

        status = self.query_one("#status-bar", VoiceStatusBar)

        if self._voice.is_recording:
            # Stop recording and process
            status.is_recording = False
            self._process_recording()
        else:
            # Start recording
            self._voice.start_recording()
            status.is_recording = True

    @work(thread=True, exclusive=True, group="voice-process")
    def _process_recording(self) -> None:
        """Stop recording, transcribe, and send to AI."""
        audio = self._voice.stop_recording()
        if len(audio) == 0:
            self.call_from_thread(self._show_system_message, "No speech detected.")
            return

        # Transcribe
        transcript = self._voice.transcribe(audio)
        if not transcript:
            self.call_from_thread(self._show_system_message, "Could not transcribe audio.")
            return

        # Show user message
        self.call_from_thread(self._show_user_message, transcript)

        # Send to AI
        if self._orchestrator is None:
            self.call_from_thread(
                self._show_system_message, "No AI provider configured."
            )
            return

        import asyncio
        loop = asyncio.new_event_loop()
        try:
            response = loop.run_until_complete(self._orchestrator.chat(transcript))
        finally:
            loop.close()

        # Show tool calls if any
        for tc in response.tool_calls:
            self.call_from_thread(self._show_tool_call, tc.name, tc.arguments)

        # Show AI response
        self.call_from_thread(self._show_ai_message, response.text)

        # Update cost
        self.call_from_thread(self._update_cost, self._orchestrator.total_cost)

    def _show_user_message(self, text: str) -> None:
        conv = self.query_one("#conversation", ConversationView)
        conv.add_user_message(text)

    def _show_ai_message(self, text: str) -> None:
        conv = self.query_one("#conversation", ConversationView)
        conv.add_ai_message(text)

    def _show_system_message(self, text: str) -> None:
        conv = self.query_one("#conversation", ConversationView)
        conv.add_system_message(text)

    def _show_tool_call(self, name: str, args: dict) -> None:
        conv = self.query_one("#conversation", ConversationView)
        conv.add_tool_message(name, args)

    def _update_cost(self, cost: float) -> None:
        status = self.query_one("#status-bar", VoiceStatusBar)
        status.session_cost = cost
```

**Step 2: Update __main__.py**

```python
# voice_debugger/__main__.py
"""CLI entry point for voice-debugger."""

import argparse


def main():
    parser = argparse.ArgumentParser(
        description="Voice-controlled AI debugging assistant"
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Run first-time setup wizard",
    )
    parser.add_argument(
        "--provider",
        choices=["claude"],
        default="claude",
        help="AI provider to use",
    )
    parser.add_argument(
        "--model",
        help="Specific model to use",
    )
    args = parser.parse_args()

    if args.setup:
        _run_setup()
        return

    from voice_debugger.app import VoiceDebuggerApp

    app = VoiceDebuggerApp()
    app.run()


def _run_setup():
    """Interactive setup wizard."""
    from voice_debugger.config import Config

    print("Voice Debugger Setup")
    print("=" * 40)

    config = Config.load()

    api_key = input(f"Anthropic API key [{config.api_key[:8]}...]: ").strip()
    if api_key:
        config.api_key = api_key

    model = input(f"Model [{config.ai_model}]: ").strip()
    if model:
        config.ai_model = model

    whisper = input(f"Whisper model [{config.whisper_model}]: ").strip()
    if whisper:
        config.whisper_model = whisper

    config.save()
    print(f"\nConfig saved. Run 'voice-debugger' to start.")


if __name__ == "__main__":
    main()
```

**Step 3: Test the app launches**

Run: `cd /Users/idang/Projects/TalkToMe && python -c "from voice_debugger.app import VoiceDebuggerApp; print('Import OK')"`
Expected: `Import OK`

**Step 4: Commit**

```bash
git add voice_debugger/app.py voice_debugger/__main__.py
git commit -m "feat: add main Textual TUI application with voice and AI integration"
```

---

### Task 9: Integration Smoke Test

**Files:**
- Create: `tests/test_app.py`

**Step 1: Write integration test**

```python
# tests/test_app.py
"""Smoke tests for the TUI application."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from textual.pilot import Pilot

from voice_debugger.app import VoiceDebuggerApp


@pytest.fixture
def mock_voice():
    """Mock VoiceHandler to avoid actual audio."""
    with patch("voice_debugger.app.VoiceHandler") as mock_cls:
        mock_handler = MagicMock()
        mock_handler.is_recording = False
        mock_handler.transcribe.return_value = "test transcript"
        mock_handler.stop_recording.return_value = __import__("numpy").zeros(16000, dtype="float32")
        mock_cls.return_value = mock_handler
        yield mock_handler


@pytest.mark.asyncio
async def test_app_starts_and_quits():
    """App starts, shows welcome message, and quits with 'q'."""
    app = VoiceDebuggerApp()
    async with app.run_test() as pilot:
        # Should see the conversation widget
        conv = app.query_one("#conversation")
        assert conv is not None

        # Should see status bar
        status = app.query_one("#status-bar")
        assert status is not None

        # Quit
        await pilot.press("q")


@pytest.mark.asyncio
async def test_app_has_source_view():
    """App shows the source view placeholder."""
    app = VoiceDebuggerApp()
    async with app.run_test():
        source = app.query_one("#source-view")
        assert source is not None
```

**Step 2: Run tests**

Run: `cd /Users/idang/Projects/TalkToMe && python -m pytest tests/test_app.py -v`
Expected: All tests PASS

**Step 3: Run ALL tests**

Run: `cd /Users/idang/Projects/TalkToMe && python -m pytest tests/ -v`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add tests/test_app.py
git commit -m "test: add integration smoke tests for TUI application"
```

---

### Task 10: Manual Testing & Polish

**Step 1: Test the full app manually**

Run: `cd /Users/idang/Projects/TalkToMe && ANTHROPIC_API_KEY=your-key-here python -m voice_debugger`

Verify:
- App launches with header, source view, conversation, status bar, footer
- Welcome message appears in conversation
- Press Space toggles recording (status bar shows "Recording...")
- Press Space again stops recording, transcribes, and sends to Claude
- Claude's response appears in conversation
- Cost updates in status bar
- Press 'q' to quit

**Step 2: Test without API key**

Run: `cd /Users/idang/Projects/TalkToMe && python -m voice_debugger`

Verify: Shows "No API key configured" message.

**Step 3: Test setup wizard**

Run: `cd /Users/idang/Projects/TalkToMe && python -m voice_debugger --setup`

Verify: Interactive prompts work, config saves to `~/.config/voice-debugger/config.toml`.

**Step 4: Fix any issues found during manual testing**

Address bugs, adjust CSS, fix edge cases.

**Step 5: Final commit**

```bash
git add -A
git commit -m "polish: fix issues found during manual testing"
```

---

## Summary

| Task | What | Tests |
|------|------|-------|
| 1 | Project scaffolding | - |
| 2 | Config module | 4 tests |
| 3 | AI provider + prompts + tools | 6 tests |
| 4 | Claude provider | 3 tests |
| 5 | AI orchestrator | 5 tests |
| 6 | Voice handler | 4 tests |
| 7 | TUI widgets | import check |
| 8 | Main app | - |
| 9 | Integration tests | 2 tests |
| 10 | Manual testing | manual |

**Total: 10 tasks, ~24 automated tests**
