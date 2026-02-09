"""AI orchestration - manages conversation, context, and cost."""

from __future__ import annotations

from voice_debugger.ai.provider import AIProvider, AIResponse
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
        if response.tool_calls:
            # Store full content blocks for tool-use round-trips
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
        else:
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
