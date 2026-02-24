"""AI orchestration - manages conversation, context, and cost."""

from __future__ import annotations

from typing import TYPE_CHECKING, AsyncIterator

from heyducky.ai.provider import AIProvider, AIResponse, StreamEvent
from heyducky.ai.prompts import DEBUGGER_SYSTEM_PROMPT, humanize_response
from heyducky.ai.functions import DEBUGGER_TOOLS

if TYPE_CHECKING:
    from heyducky.debugger.tool_executor import ToolExecutor

# Known model context windows (tokens)
MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    "claude-sonnet-4-5-20250929": 200_000,
    "claude-haiku-3-5-20241022": 200_000,
}
DEFAULT_CONTEXT_WINDOW = 200_000

# Compaction triggers at 80% of context window; max 3 compactions before
# quality degrades too much (each summary loses nuance).
COMPACTION_RATIO = 0.80
MAX_COMPACTIONS = 3

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


def _smart_threshold(model: str) -> int:
    """Return compaction threshold (tokens) based on model context window."""
    window = MODEL_CONTEXT_WINDOWS.get(model, DEFAULT_CONTEXT_WINDOW)
    return int(window * COMPACTION_RATIO)


class Orchestrator:
    """Manages conversation with AI provider."""

    def __init__(
        self,
        provider: AIProvider,
        tool_executor: ToolExecutor | None = None,
        compaction_enabled: bool = True,
    ):
        self._provider = provider
        self._tool_executor = tool_executor
        self._history: list[dict] = []
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.total_cost: float = 0.0
        self._compaction_enabled = compaction_enabled
        self._compaction_threshold = _smart_threshold(provider.model_name())
        self._max_compactions = MAX_COMPACTIONS
        self.compaction_count: int = 0
        self._on_compaction: callable | None = None

    async def chat(self, user_message: str) -> AIResponse:
        """Send a user message and get AI response, executing tool calls if needed."""
        self._history.append({"role": "user", "content": user_message})

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

    async def chat_streaming(
        self, user_message: str
    ) -> AsyncIterator[StreamEvent]:
        """Stream an AI response, yielding events as they arrive.

        Like chat(), manages history, compaction, and tool call loops.
        Yields StreamEvent objects:
          - type="text": incremental text deltas
          - type="tool_call": a completed tool call (already executed if executor set)
          - type="done": final AIResponse with full text and usage stats

        The tool call loop works: if Claude makes tool calls during streaming,
        they are executed and the follow-up response is also streamed.
        """
        self._history.append({"role": "user", "content": user_message})

        await self._compact_if_needed()

        max_rounds = 5
        for _ in range(max_rounds):
            response = None

            async for event in self._provider.stream_message(
                messages=list(self._history),
                system=DEBUGGER_SYSTEM_PROMPT,
                tools=DEBUGGER_TOOLS,
            ):
                if event.type == "text":
                    yield event
                elif event.type == "tool_call":
                    yield event
                elif event.type == "done":
                    response = event.response

            if response is None:
                return  # pragma: no cover

            from heyducky.ai.prompts import humanize_response

            response.text = humanize_response(response.text)
            self._track_usage(response)

            if response.tool_calls:
                content: list[dict] = []
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

                if self._tool_executor:
                    tool_results = []
                    for tc in response.tool_calls:
                        result = await self._tool_executor.execute(tc)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tc.id,
                            "content": result,
                        })
                    self._history.append(
                        {"role": "user", "content": tool_results}
                    )
                    continue  # Stream the follow-up response
                else:
                    yield StreamEvent(type="done", response=response)
                    return
            else:
                self._history.append(
                    {"role": "assistant", "content": response.text}
                )
                yield StreamEvent(type="done", response=response)
                return

        # Safety: yield last response if max rounds hit
        if response is not None:
            yield StreamEvent(type="done", response=response)

    async def _compact_if_needed(self) -> None:
        """Compact conversation history if token count exceeds threshold."""
        if not self._compaction_enabled:
            return
        if len(self._history) < 4:
            return
        if self.compaction_count >= self._max_compactions:
            return

        try:
            token_count = await self._provider.count_tokens(
                messages=self._history,
                system=DEBUGGER_SYSTEM_PROMPT,
                tools=DEBUGGER_TOOLS,
            )
        except Exception:
            return

        if token_count < self._compaction_threshold:
            return

        # Preserve last 3 messages (prev user, prev assistant, new user)
        preserved = (
            self._history[-3:]
            if len(self._history) >= 3
            else self._history[:]
        )
        to_compact = (
            self._history[:-3]
            if len(self._history) > 3
            else self._history[:]
        )

        if not to_compact:
            return

        summary_response = await self._provider.send_message(
            messages=to_compact
            + [{"role": "user", "content": COMPACTION_PROMPT}],
            system="You are a conversation summarizer. Be concise and thorough.",
        )
        self._track_usage(summary_response)

        summary_text = summary_response.text

        self._history = [
            {
                "role": "user",
                "content": f"[Previous conversation summary]: {summary_text}",
            },
            {
                "role": "assistant",
                "content": "Got it, I have the context. Let's continue.",
            },
        ] + preserved

        self.compaction_count += 1

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

    def get_state(self) -> dict:
        """Serialize orchestrator state for auto-save."""
        return {
            "history": self._history,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cost": self.total_cost,
            "compaction_count": self.compaction_count,
        }

    def restore_state(self, state: dict) -> None:
        """Restore orchestrator state from auto-save."""
        self._history = state.get("history", [])
        self.total_input_tokens = state.get("total_input_tokens", 0)
        self.total_output_tokens = state.get("total_output_tokens", 0)
        self.total_cost = state.get("total_cost", 0.0)
        self.compaction_count = state.get("compaction_count", 0)

    def reset(self) -> None:
        """Clear conversation history and cost tracking."""
        self._history = []
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        self.compaction_count = 0
