"""AI orchestration - manages conversation, context, and cost."""

from __future__ import annotations

from typing import TYPE_CHECKING

from voice_debugger.ai.provider import AIProvider, AIResponse
from voice_debugger.ai.prompts import DEBUGGER_SYSTEM_PROMPT, humanize_response
from voice_debugger.ai.functions import DEBUGGER_TOOLS

if TYPE_CHECKING:
    from voice_debugger.debugger.tool_executor import ToolExecutor


class Orchestrator:
    """Manages conversation with AI provider."""

    def __init__(self, provider: AIProvider, tool_executor: ToolExecutor | None = None):
        self._provider = provider
        self._tool_executor = tool_executor
        self._history: list[dict] = []
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.total_cost: float = 0.0

    async def chat(self, user_message: str) -> AIResponse:
        """Send a user message and get AI response, executing tool calls if needed."""
        self._history.append({"role": "user", "content": user_message})

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
