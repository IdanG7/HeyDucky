"""Tests for AI provider abstraction."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from voice_debugger.ai.provider import AIResponse
from voice_debugger.ai.prompts import DEBUGGER_SYSTEM_PROMPT, humanize_response
from voice_debugger.ai.functions import DEBUGGER_TOOLS
from voice_debugger.ai.claude import ClaudeProvider


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
