"""Tests for AI orchestrator."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from heyducky.ai.orchestrator import Orchestrator, _smart_threshold, COMPACTION_RATIO
from heyducky.ai.provider import AIResponse, ToolCall


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
    # model_name is a regular (non-async) method
    provider.model_name = Mock(return_value="claude-sonnet-4-5-20250929")
    provider.count_tokens = AsyncMock(return_value=0)
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


@pytest.mark.asyncio
async def test_orchestrator_executes_tool_calls(mock_provider):
    """Orchestrator executes tool calls and feeds results back."""
    # First response has a tool call
    tool_response = AIResponse(
        text="Let me check.",
        tool_calls=[ToolCall(id="t1", name="inspect_variable", arguments={"name": "x"})],
        input_tokens=30,
        output_tokens=15,
    )
    # Second response is the final answer (after tool result)
    final_response = AIResponse(
        text="x is 42.",
        tool_calls=[],
        input_tokens=40,
        output_tokens=10,
    )
    mock_provider.send_message = AsyncMock(side_effect=[tool_response, final_response])

    mock_executor = AsyncMock()
    mock_executor.execute = AsyncMock(return_value="x = 42 (int)")

    orch = Orchestrator(provider=mock_provider, tool_executor=mock_executor)
    resp = await orch.chat("What is x?")

    # Should have called the tool executor
    mock_executor.execute.assert_called_once()
    # Final response should be the one after tool results
    assert resp.text == "x is 42."
    # Provider should have been called twice (initial + after tool result)
    assert mock_provider.send_message.call_count == 2


def test_smart_threshold_known_model():
    """Smart threshold returns 80% of known model context window."""
    threshold = _smart_threshold("claude-sonnet-4-5-20250929")
    assert threshold == int(200_000 * COMPACTION_RATIO)


def test_smart_threshold_unknown_model():
    """Smart threshold falls back to default for unknown models."""
    threshold = _smart_threshold("some-future-model")
    assert threshold == int(200_000 * COMPACTION_RATIO)


@pytest.mark.asyncio
async def test_orchestrator_compacts_when_over_threshold(mock_provider):
    """Orchestrator compacts history when token count exceeds smart threshold."""
    # Smart threshold for sonnet is 160_000, so return a value above it
    mock_provider.count_tokens = AsyncMock(return_value=170_000)

    resp1 = AIResponse(text="First reply.", tool_calls=[], input_tokens=50, output_tokens=20)
    resp2 = AIResponse(text="Second reply.", tool_calls=[], input_tokens=50, output_tokens=20)
    summary_resp = AIResponse(
        text="User was debugging app.py, found null pointer on line 42.",
        tool_calls=[],
        input_tokens=100,
        output_tokens=50,
    )
    final_resp = AIResponse(
        text="Got it.", tool_calls=[], input_tokens=30, output_tokens=10
    )

    mock_provider.send_message = AsyncMock(
        side_effect=[resp1, resp2, summary_resp, final_resp]
    )

    orch = Orchestrator(provider=mock_provider)

    # Build up history: after 2 chats, history = [u1, a1, u2, a2] = 4 messages
    await orch.chat("First message")
    await orch.chat("Second message")

    # Third chat appends user msg -> history = 5, triggers compaction
    result = await orch.chat("Third message")
    assert result.text == "Got it."
    assert orch.compaction_count == 1


@pytest.mark.asyncio
async def test_orchestrator_no_compact_when_disabled(mock_provider):
    """Orchestrator does not compact when compaction is disabled."""
    mock_provider.count_tokens = AsyncMock(return_value=200_000)

    orch = Orchestrator(provider=mock_provider, compaction_enabled=False)

    resp = await orch.chat("Hello")
    assert resp.text == "Yeah, that variable is null."
    mock_provider.count_tokens.assert_not_called()
    assert orch.compaction_count == 0


@pytest.mark.asyncio
async def test_orchestrator_compact_preserves_recent_turns(mock_provider):
    """After compaction, the last user+assistant exchange is preserved."""
    mock_provider.count_tokens = AsyncMock(return_value=170_000)

    summary_resp = AIResponse(
        text="Summary of conversation.",
        tool_calls=[],
        input_tokens=50,
        output_tokens=30,
    )
    final_resp = AIResponse(
        text="Continuing.", tool_calls=[], input_tokens=30, output_tokens=10
    )

    call_count = 0

    async def side_effect(**kwargs):
        nonlocal call_count
        call_count += 1
        messages = kwargs.get("messages", [])
        if call_count == 1:
            # First chat response
            return AIResponse(
                text="First reply.",
                tool_calls=[],
                input_tokens=50,
                output_tokens=20,
            )
        if call_count == 2:
            # Second chat response
            return AIResponse(
                text="Second reply.",
                tool_calls=[],
                input_tokens=50,
                output_tokens=20,
            )
        if call_count == 3:
            # Summary request (compaction)
            return summary_resp
        if call_count == 4:
            # Final chat after compaction
            # History should have: summary_user, summary_asst,
            # prev_user, prev_asst, new_user = 5
            assert len(messages) == 5
            assert "[Previous conversation summary]" in messages[0]["content"]
            return final_resp
        return final_resp

    mock_provider.send_message = AsyncMock(side_effect=side_effect)

    orch = Orchestrator(provider=mock_provider)

    # Build up history: 2 exchanges = 4 messages
    await orch.chat("Build up history")
    await orch.chat("More history")
    # Third chat triggers compaction (history >= 4)
    await orch.chat("This triggers compaction")
    assert orch.compaction_count == 1
