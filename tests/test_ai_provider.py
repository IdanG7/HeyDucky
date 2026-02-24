"""Tests for AI provider abstraction."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from heyducky.ai.provider import AIResponse
from heyducky.ai.prompts import DEBUGGER_SYSTEM_PROMPT, humanize_response
from heyducky.ai.functions import DEBUGGER_TOOLS
from heyducky.ai.claude import ClaudeProvider
from heyducky.widgets.conversation import ConversationView


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


def test_system_prompt_includes_conditional_breakpoints():
    """System prompt contains conditional breakpoint guidance."""
    assert "CONDITIONAL BREAKPOINTS" in DEBUGGER_SYSTEM_PROMPT
    assert "x > 10" in DEBUGGER_SYSTEM_PROMPT
    assert "name is None" in DEBUGGER_SYSTEM_PROMPT
    assert "count == 0" in DEBUGGER_SYSTEM_PROMPT


def test_debugger_tools_structure():
    """Tool definitions have required fields."""
    assert len(DEBUGGER_TOOLS) >= 5
    for tool in DEBUGGER_TOOLS:
        assert "name" in tool
        assert "description" in tool
        assert "input_schema" in tool


def test_set_breakpoint_tool_mentions_conditional():
    """set_breakpoint tool description mentions conditional breakpoints."""
    bp_tool = next(t for t in DEBUGGER_TOOLS if t["name"] == "set_breakpoint")
    desc = bp_tool["description"].lower()
    assert "conditional" in desc


def test_ai_response_cost_calculation():
    """Cost calculation uses correct per-token rates."""
    resp = AIResponse(text="", tool_calls=[], input_tokens=1000, output_tokens=500)
    cost = resp.cost("claude")
    assert cost > 0
    assert isinstance(cost, float)


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


def test_add_tool_message_conditional_breakpoint():
    """add_tool_message renders conditional breakpoints with special formatting."""
    view = ConversationView.__new__(ConversationView)
    captured = []
    view.write = lambda msg: captured.append(msg)

    view.add_tool_message(
        "set_breakpoint",
        {"file": "app.py", "line": 42, "condition": "x > 10"},
    )

    assert len(captured) == 1
    text = captured[0]
    plain = text.plain
    assert "breakpoint" in plain
    assert "app.py:42" in plain
    assert "when" in plain
    assert "x > 10" in plain
    # Should NOT have the generic [tool] prefix
    assert "[tool]" not in plain


def test_add_tool_message_regular_tool():
    """add_tool_message renders regular tool calls with generic formatting."""
    view = ConversationView.__new__(ConversationView)
    captured = []
    view.write = lambda msg: captured.append(msg)

    view.add_tool_message("step_over", {})

    assert len(captured) == 1
    text = captured[0]
    plain = text.plain
    assert "[tool] step_over" in plain


def test_add_tool_message_breakpoint_without_condition():
    """add_tool_message renders breakpoints without conditions using generic format."""
    view = ConversationView.__new__(ConversationView)
    captured = []
    view.write = lambda msg: captured.append(msg)

    view.add_tool_message(
        "set_breakpoint",
        {"file": "app.py", "line": 10},
    )

    assert len(captured) == 1
    text = captured[0]
    plain = text.plain
    assert "[tool] set_breakpoint" in plain
