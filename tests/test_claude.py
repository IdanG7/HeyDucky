"""Tests for Claude provider (uses mocked API)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from heyducky.ai.claude import ClaudeProvider
from heyducky.ai.provider import AIResponse


@pytest.fixture
def mock_anthropic():
    """Create a mocked AsyncAnthropic client."""
    with patch("heyducky.ai.claude.AsyncAnthropic") as mock_cls:
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
    with patch("heyducky.ai.claude.AsyncAnthropic"):
        provider = ClaudeProvider(api_key="k", model="claude-opus-4-6")
        assert provider.model_name() == "claude-opus-4-6"
