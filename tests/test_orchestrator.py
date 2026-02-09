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
