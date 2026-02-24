"""Tests for streaming AI responses.

Covers:
- StreamEvent dataclass
- ClaudeProvider.stream_message() (mocked)
- Orchestrator.chat_streaming() with text-only, tool calls, tool execution loop
- ConversationView streaming methods
- Integration of streaming in the app flow
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from heyducky.ai.provider import AIResponse, StreamEvent, ToolCall
from heyducky.ai.orchestrator import Orchestrator
from heyducky.widgets.conversation import ConversationView


# ---------------------------------------------------------------------------
# StreamEvent dataclass tests
# ---------------------------------------------------------------------------

class TestStreamEvent:
    """Tests for the StreamEvent dataclass."""

    def test_text_event(self):
        """StreamEvent with type='text' stores text delta."""
        event = StreamEvent(type="text", text="Hello")
        assert event.type == "text"
        assert event.text == "Hello"
        assert event.tool_call is None
        assert event.response is None

    def test_tool_call_event(self):
        """StreamEvent with type='tool_call' stores tool call."""
        tc = ToolCall(id="t1", name="inspect_variable", arguments={"name": "x"})
        event = StreamEvent(type="tool_call", tool_call=tc)
        assert event.type == "tool_call"
        assert event.tool_call.name == "inspect_variable"
        assert event.text == ""

    def test_done_event(self):
        """StreamEvent with type='done' stores full AIResponse."""
        resp = AIResponse(text="Done.", tool_calls=[], input_tokens=10, output_tokens=5)
        event = StreamEvent(type="done", response=resp)
        assert event.type == "done"
        assert event.response.text == "Done."
        assert event.text == ""

    def test_default_values(self):
        """StreamEvent defaults are correct."""
        event = StreamEvent(type="text")
        assert event.text == ""
        assert event.tool_call is None
        assert event.response is None


# ---------------------------------------------------------------------------
# Helper: create a mock streaming provider
# ---------------------------------------------------------------------------

def _make_streaming_provider(stream_events_sequence):
    """Create a mock provider that yields events from stream_message().

    Args:
        stream_events_sequence: Either a list of StreamEvents (single call)
            or a list of lists (multiple calls in sequence for tool loops).
    """
    provider = AsyncMock()
    provider.model_name = Mock(return_value="claude-sonnet-4-5-20250929")
    provider.count_tokens = AsyncMock(return_value=0)
    provider.send_message = AsyncMock(
        return_value=AIResponse(text="fallback", tool_calls=[], input_tokens=0, output_tokens=0)
    )

    # Determine if we have a sequence of calls or a single call
    if stream_events_sequence and isinstance(stream_events_sequence[0], list):
        call_idx = 0

        async def _stream_message(**kwargs):
            nonlocal call_idx
            events = stream_events_sequence[call_idx]
            call_idx += 1
            for event in events:
                yield event

        provider.stream_message = _stream_message
    else:
        async def _stream_message(**kwargs):
            for event in stream_events_sequence:
                yield event

        provider.stream_message = _stream_message

    return provider


# ---------------------------------------------------------------------------
# Orchestrator.chat_streaming() tests
# ---------------------------------------------------------------------------

class TestOrchestratorChatStreaming:
    """Tests for Orchestrator.chat_streaming() async generator."""

    @pytest.mark.asyncio
    async def test_simple_text_streaming(self):
        """chat_streaming yields text events and a done event for simple text."""
        events = [
            StreamEvent(type="text", text="Hello "),
            StreamEvent(type="text", text="world!"),
            StreamEvent(type="done", response=AIResponse(
                text="Hello world!", tool_calls=[], input_tokens=10, output_tokens=5
            )),
        ]
        provider = _make_streaming_provider(events)
        orch = Orchestrator(provider=provider)

        collected = []
        async for event in orch.chat_streaming("Hi"):
            collected.append(event)

        # Should have 2 text events + 1 done event
        text_events = [e for e in collected if e.type == "text"]
        done_events = [e for e in collected if e.type == "done"]
        assert len(text_events) == 2
        assert len(done_events) == 1
        assert text_events[0].text == "Hello "
        assert text_events[1].text == "world!"
        assert done_events[0].response.text == "Hello world!"

    @pytest.mark.asyncio
    async def test_streaming_tracks_usage(self):
        """chat_streaming tracks token usage and cost."""
        events = [
            StreamEvent(type="text", text="Hi"),
            StreamEvent(type="done", response=AIResponse(
                text="Hi", tool_calls=[], input_tokens=50, output_tokens=20
            )),
        ]
        provider = _make_streaming_provider(events)
        orch = Orchestrator(provider=provider)

        async for _ in orch.chat_streaming("Hello"):
            pass

        assert orch.total_input_tokens == 50
        assert orch.total_output_tokens == 20
        assert orch.total_cost > 0

    @pytest.mark.asyncio
    async def test_streaming_adds_to_history(self):
        """chat_streaming appends user and assistant messages to history."""
        events = [
            StreamEvent(type="text", text="Reply"),
            StreamEvent(type="done", response=AIResponse(
                text="Reply", tool_calls=[], input_tokens=10, output_tokens=5
            )),
        ]
        provider = _make_streaming_provider(events)
        orch = Orchestrator(provider=provider)

        async for _ in orch.chat_streaming("Question"):
            pass

        assert len(orch._history) == 2
        assert orch._history[0] == {"role": "user", "content": "Question"}
        assert orch._history[1] == {"role": "assistant", "content": "Reply"}

    @pytest.mark.asyncio
    async def test_streaming_humanizes_response(self):
        """chat_streaming applies humanize_response to the final text."""
        events = [
            StreamEvent(type="text", text="Certainly I shall help"),
            StreamEvent(type="done", response=AIResponse(
                text="Certainly I shall help", tool_calls=[], input_tokens=10, output_tokens=5
            )),
        ]
        provider = _make_streaming_provider(events)
        orch = Orchestrator(provider=provider)

        done_event = None
        async for event in orch.chat_streaming("Help me"):
            if event.type == "done":
                done_event = event

        # "Certainly" should be removed, "I shall" -> "I'll"
        assert done_event is not None
        assert "Certainly" not in done_event.response.text
        assert "I'll" in done_event.response.text

    @pytest.mark.asyncio
    async def test_streaming_with_tool_calls_no_executor(self):
        """chat_streaming yields tool call events and done when no executor."""
        tc = ToolCall(id="t1", name="inspect_variable", arguments={"name": "x"})
        events = [
            StreamEvent(type="text", text="Let me check"),
            StreamEvent(type="tool_call", tool_call=tc),
            StreamEvent(type="done", response=AIResponse(
                text="Let me check", tool_calls=[tc], input_tokens=10, output_tokens=5
            )),
        ]
        provider = _make_streaming_provider(events)
        orch = Orchestrator(provider=provider)

        collected = []
        async for event in orch.chat_streaming("What is x?"):
            collected.append(event)

        text_events = [e for e in collected if e.type == "text"]
        tool_events = [e for e in collected if e.type == "tool_call"]
        done_events = [e for e in collected if e.type == "done"]

        assert len(text_events) == 1
        assert len(tool_events) == 1
        assert tool_events[0].tool_call.name == "inspect_variable"
        assert len(done_events) == 1
        assert len(done_events[0].response.tool_calls) == 1

    @pytest.mark.asyncio
    async def test_streaming_with_tool_execution_loop(self):
        """chat_streaming executes tool calls and streams follow-up response."""
        tc = ToolCall(id="t1", name="inspect_variable", arguments={"name": "x"})

        # First call: tool call
        first_call_events = [
            StreamEvent(type="text", text="Checking "),
            StreamEvent(type="tool_call", tool_call=tc),
            StreamEvent(type="done", response=AIResponse(
                text="Checking", tool_calls=[tc], input_tokens=30, output_tokens=15
            )),
        ]
        # Second call: text-only follow-up after tool result
        second_call_events = [
            StreamEvent(type="text", text="x is 42."),
            StreamEvent(type="done", response=AIResponse(
                text="x is 42.", tool_calls=[], input_tokens=40, output_tokens=10
            )),
        ]

        provider = _make_streaming_provider([first_call_events, second_call_events])

        mock_executor = AsyncMock()
        mock_executor.execute = AsyncMock(return_value="x = 42 (int)")

        orch = Orchestrator(provider=provider, tool_executor=mock_executor)

        collected = []
        async for event in orch.chat_streaming("What is x?"):
            collected.append(event)

        # Should have text from both rounds, tool call from first, done from second
        text_events = [e for e in collected if e.type == "text"]
        tool_events = [e for e in collected if e.type == "tool_call"]
        done_events = [e for e in collected if e.type == "done"]

        assert len(text_events) == 2  # "Checking " + "x is 42."
        assert len(tool_events) == 1
        assert len(done_events) == 1
        assert done_events[0].response.text == "x is 42."

        # Tool executor should have been called
        mock_executor.execute.assert_called_once()

        # Usage should be accumulated from both rounds
        assert orch.total_input_tokens == 70  # 30 + 40
        assert orch.total_output_tokens == 25  # 15 + 10

    @pytest.mark.asyncio
    async def test_streaming_history_with_tool_loop(self):
        """chat_streaming correctly builds history through tool call loops."""
        tc = ToolCall(id="t1", name="step_over", arguments={})

        first_events = [
            StreamEvent(type="tool_call", tool_call=tc),
            StreamEvent(type="done", response=AIResponse(
                text="", tool_calls=[tc], input_tokens=10, output_tokens=5
            )),
        ]
        second_events = [
            StreamEvent(type="text", text="Done stepping."),
            StreamEvent(type="done", response=AIResponse(
                text="Done stepping.", tool_calls=[], input_tokens=10, output_tokens=5
            )),
        ]

        provider = _make_streaming_provider([first_events, second_events])

        mock_executor = AsyncMock()
        mock_executor.execute = AsyncMock(return_value="Stepped to line 43")

        orch = Orchestrator(provider=provider, tool_executor=mock_executor)

        async for _ in orch.chat_streaming("Step over"):
            pass

        # History: user, assistant(tool_use), user(tool_result), assistant(text)
        assert len(orch._history) == 4
        assert orch._history[0]["role"] == "user"
        assert orch._history[1]["role"] == "assistant"
        assert orch._history[2]["role"] == "user"  # tool results
        assert orch._history[3]["role"] == "assistant"
        assert orch._history[3]["content"] == "Done stepping."

    @pytest.mark.asyncio
    async def test_streaming_does_not_modify_chat(self):
        """chat_streaming does not affect the existing chat() method."""
        provider = AsyncMock()
        provider.model_name = Mock(return_value="claude-sonnet-4-5-20250929")
        provider.count_tokens = AsyncMock(return_value=0)
        provider.send_message = AsyncMock(return_value=AIResponse(
            text="Non-streaming response.",
            tool_calls=[],
            input_tokens=10,
            output_tokens=5,
        ))

        orch = Orchestrator(provider=provider)

        # Use the original chat() method
        resp = await orch.chat("Hello via chat()")
        assert resp.text == "Non-streaming response."
        provider.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_streaming_multiple_text_deltas(self):
        """chat_streaming yields many small text deltas."""
        words = ["The ", "bug ", "is ", "on ", "line ", "42."]
        events = [StreamEvent(type="text", text=w) for w in words]
        events.append(StreamEvent(type="done", response=AIResponse(
            text="The bug is on line 42.", tool_calls=[], input_tokens=10, output_tokens=5
        )))

        provider = _make_streaming_provider(events)
        orch = Orchestrator(provider=provider)

        text_chunks = []
        async for event in orch.chat_streaming("Where's the bug?"):
            if event.type == "text":
                text_chunks.append(event.text)

        assert text_chunks == words
        assert "".join(text_chunks) == "The bug is on line 42."

    @pytest.mark.asyncio
    async def test_streaming_empty_text_response(self):
        """chat_streaming handles response with no text (only tool calls)."""
        tc = ToolCall(id="t1", name="step_over", arguments={})
        events = [
            StreamEvent(type="tool_call", tool_call=tc),
            StreamEvent(type="done", response=AIResponse(
                text="", tool_calls=[tc], input_tokens=10, output_tokens=5
            )),
        ]
        provider = _make_streaming_provider(events)
        orch = Orchestrator(provider=provider)

        collected = []
        async for event in orch.chat_streaming("Step"):
            collected.append(event)

        text_events = [e for e in collected if e.type == "text"]
        assert len(text_events) == 0

    @pytest.mark.asyncio
    async def test_streaming_accumulates_cost_across_calls(self):
        """chat_streaming accumulates cost across multiple streaming calls."""
        events1 = [
            StreamEvent(type="text", text="First"),
            StreamEvent(type="done", response=AIResponse(
                text="First", tool_calls=[], input_tokens=20, output_tokens=10
            )),
        ]
        events2 = [
            StreamEvent(type="text", text="Second"),
            StreamEvent(type="done", response=AIResponse(
                text="Second", tool_calls=[], input_tokens=30, output_tokens=15
            )),
        ]

        provider = _make_streaming_provider([events1, events2])
        orch = Orchestrator(provider=provider)

        async for _ in orch.chat_streaming("First"):
            pass
        async for _ in orch.chat_streaming("Second"):
            pass

        assert orch.total_input_tokens == 50
        assert orch.total_output_tokens == 25


# ---------------------------------------------------------------------------
# ClaudeProvider.stream_message() tests (mocked)
# ---------------------------------------------------------------------------

class TestClaudeProviderStreaming:
    """Tests for ClaudeProvider.stream_message() with mocked Anthropic API."""

    @pytest.mark.asyncio
    async def test_stream_message_text_only(self):
        """stream_message yields text deltas and done event."""
        with patch("heyducky.ai.claude.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client

            # Build mock stream
            text_block = MagicMock(type="text", text="Hello world!")
            mock_message = MagicMock()
            mock_message.content = [text_block]
            mock_message.usage = MagicMock(input_tokens=10, output_tokens=5)

            # Mock the stream context manager
            mock_stream = AsyncMock()
            mock_stream.get_final_message = AsyncMock(return_value=mock_message)

            # Create the events that the stream yields
            delta_event = MagicMock()
            delta_event.type = "content_block_delta"
            delta_event.delta = MagicMock()
            delta_event.delta.type = "text_delta"
            delta_event.delta.text = "Hello world!"

            # Make the stream async iterable
            mock_stream.__aiter__ = lambda self: self
            _events = iter([delta_event])

            async def _anext(self):
                try:
                    return next(_events)
                except StopIteration:
                    raise StopAsyncIteration

            mock_stream.__anext__ = _anext

            # Set up the async context manager
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_stream)
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_client.messages.stream = MagicMock(return_value=mock_ctx)

            from heyducky.ai.claude import ClaudeProvider
            provider = ClaudeProvider(api_key="test-key")

            collected = []
            async for event in provider.stream_message(
                messages=[{"role": "user", "content": "Hi"}],
                system="test",
            ):
                collected.append(event)

            text_events = [e for e in collected if e.type == "text"]
            done_events = [e for e in collected if e.type == "done"]

            assert len(text_events) == 1
            assert text_events[0].text == "Hello world!"
            assert len(done_events) == 1
            assert done_events[0].response.text == "Hello world!"
            assert done_events[0].response.input_tokens == 10

    @pytest.mark.asyncio
    async def test_stream_message_with_tool_use(self):
        """stream_message yields tool_call events for tool_use blocks."""
        with patch("heyducky.ai.claude.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client

            # Build mock final message with text + tool_use
            text_block = MagicMock(type="text", text="Checking")
            tool_block = MagicMock(type="tool_use")
            tool_block.id = "t1"
            tool_block.name = "inspect_variable"
            tool_block.input = {"name": "x"}

            mock_message = MagicMock()
            mock_message.content = [text_block, tool_block]
            mock_message.usage = MagicMock(input_tokens=20, output_tokens=10)

            mock_stream = AsyncMock()
            mock_stream.get_final_message = AsyncMock(return_value=mock_message)

            # Stream yields a text delta
            delta_event = MagicMock()
            delta_event.type = "content_block_delta"
            delta_event.delta = MagicMock()
            delta_event.delta.type = "text_delta"
            delta_event.delta.text = "Checking"

            mock_stream.__aiter__ = lambda self: self
            _events = iter([delta_event])

            async def _anext(self):
                try:
                    return next(_events)
                except StopIteration:
                    raise StopAsyncIteration

            mock_stream.__anext__ = _anext

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_stream)
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_client.messages.stream = MagicMock(return_value=mock_ctx)

            from heyducky.ai.claude import ClaudeProvider
            provider = ClaudeProvider(api_key="test-key")

            collected = []
            async for event in provider.stream_message(
                messages=[{"role": "user", "content": "Check x"}],
            ):
                collected.append(event)

            tool_events = [e for e in collected if e.type == "tool_call"]
            assert len(tool_events) == 1
            assert tool_events[0].tool_call.name == "inspect_variable"
            assert tool_events[0].tool_call.id == "t1"

    @pytest.mark.asyncio
    async def test_stream_message_passes_kwargs(self):
        """stream_message passes system and tools to the API."""
        with patch("heyducky.ai.claude.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client

            text_block = MagicMock(type="text", text="Ok")
            mock_message = MagicMock()
            mock_message.content = [text_block]
            mock_message.usage = MagicMock(input_tokens=5, output_tokens=3)

            mock_stream = AsyncMock()
            mock_stream.get_final_message = AsyncMock(return_value=mock_message)
            mock_stream.__aiter__ = lambda self: self

            async def _anext(self):
                raise StopAsyncIteration

            mock_stream.__anext__ = _anext

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_stream)
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_client.messages.stream = MagicMock(return_value=mock_ctx)

            from heyducky.ai.claude import ClaudeProvider
            provider = ClaudeProvider(api_key="test-key")

            tools = [{"name": "test_tool", "description": "test", "input_schema": {}}]
            async for _ in provider.stream_message(
                messages=[{"role": "user", "content": "Hi"}],
                system="Be helpful",
                tools=tools,
            ):
                pass

            call_kwargs = mock_client.messages.stream.call_args[1]
            assert call_kwargs["system"] == "Be helpful"
            assert call_kwargs["tools"] == tools


# ---------------------------------------------------------------------------
# ConversationView streaming tests
# ---------------------------------------------------------------------------

class TestConversationViewStreaming:
    """Tests for ConversationView streaming methods."""

    @pytest.mark.asyncio
    async def test_start_ai_stream_initializes_state(self):
        """start_ai_stream initializes buffer and writes prefix."""
        from heyducky.app import HeyDuckyApp

        app = HeyDuckyApp()
        async with app.run_test():
            conv = app.query_one("#conversation-view", ConversationView)
            initial_lines = len(conv.lines)
            conv.start_ai_stream()

            assert conv._stream_buffer == ""
            assert conv._stream_line_buffer == ""
            # Should have written the "AI: " prefix line
            assert len(conv.lines) > initial_lines

    @pytest.mark.asyncio
    async def test_append_ai_chunk_adds_text(self):
        """append_ai_chunk buffers text and flushes on newlines."""
        from heyducky.app import HeyDuckyApp

        app = HeyDuckyApp()
        async with app.run_test():
            conv = app.query_one("#conversation-view", ConversationView)
            conv.start_ai_stream()
            lines_after_start = len(conv.lines)

            # Chunks without newlines are buffered, not written yet
            conv.append_ai_chunk("Hello ")
            assert conv._stream_buffer == "Hello "
            assert conv._stream_line_buffer == "Hello "
            assert len(conv.lines) == lines_after_start

            conv.append_ai_chunk("world!\n")
            assert conv._stream_buffer == "Hello world!\n"
            # Newline should flush the line to the log
            assert len(conv.lines) > lines_after_start

    @pytest.mark.asyncio
    async def test_finish_ai_stream_returns_buffer(self):
        """finish_ai_stream returns accumulated buffer and resets state."""
        from heyducky.app import HeyDuckyApp

        app = HeyDuckyApp()
        async with app.run_test():
            conv = app.query_one("#conversation-view", ConversationView)
            conv.start_ai_stream()
            conv.append_ai_chunk("Full ")
            conv.append_ai_chunk("response.")

            result = conv.finish_ai_stream()
            assert result == "Full response."
            assert conv._stream_buffer == ""

    @pytest.mark.asyncio
    async def test_append_empty_chunk_does_not_write(self):
        """append_ai_chunk with empty text does not add a line."""
        from heyducky.app import HeyDuckyApp

        app = HeyDuckyApp()
        async with app.run_test():
            conv = app.query_one("#conversation-view", ConversationView)
            conv.start_ai_stream()
            lines_after_start = len(conv.lines)

            conv.append_ai_chunk("")
            # Empty chunk should not add a line
            assert len(conv.lines) == lines_after_start
            assert conv._stream_buffer == ""

    @pytest.mark.asyncio
    async def test_existing_methods_still_work(self):
        """Existing add_ai_message and add_user_message still work."""
        from heyducky.app import HeyDuckyApp

        app = HeyDuckyApp()
        async with app.run_test():
            conv = app.query_one("#conversation-view", ConversationView)
            lines_before = len(conv.lines)

            conv.add_user_message("Test user msg")
            assert len(conv.lines) > lines_before

            lines_before = len(conv.lines)
            conv.add_ai_message("Test AI msg")
            assert len(conv.lines) > lines_before


# ---------------------------------------------------------------------------
# App integration tests
# ---------------------------------------------------------------------------

class TestAppStreamingIntegration:
    """Tests for app-level streaming integration."""

    @pytest.mark.asyncio
    async def test_app_has_stream_helper_methods(self):
        """App has _start_ai_stream, _append_ai_chunk, _finish_ai_stream."""
        from heyducky.app import HeyDuckyApp

        app = HeyDuckyApp()
        async with app.run_test():
            assert hasattr(app, "_start_ai_stream")
            assert hasattr(app, "_append_ai_chunk")
            assert hasattr(app, "_finish_ai_stream")
            assert callable(app._start_ai_stream)
            assert callable(app._append_ai_chunk)
            assert callable(app._finish_ai_stream)

    @pytest.mark.asyncio
    async def test_app_stream_methods_work(self):
        """App streaming helper methods correctly delegate to ConversationView."""
        from heyducky.app import HeyDuckyApp

        app = HeyDuckyApp()
        async with app.run_test():
            # Start stream
            app._start_ai_stream()
            conv = app.query_one("#conversation-view", ConversationView)
            assert conv._stream_buffer == ""

            # Append chunks
            app._append_ai_chunk("Hello ")
            assert conv._stream_buffer == "Hello "

            app._append_ai_chunk("world!")
            assert conv._stream_buffer == "Hello world!"

            # Finish
            app._finish_ai_stream("Hello world!")
            assert conv._stream_buffer == ""

    @pytest.mark.asyncio
    async def test_finish_stream_records_in_chat_history(self):
        """_finish_ai_stream records the full text in chat history."""
        from heyducky.app import HeyDuckyApp

        app = HeyDuckyApp()
        async with app.run_test():
            app._start_ai_stream()
            app._append_ai_chunk("Test response")
            app._finish_ai_stream("Test response")

            # Check chat history
            history = app._chat_history._messages
            assert any(
                msg.get("role") == "assistant" and msg.get("content") == "Test response"
                for msg in history
            )
