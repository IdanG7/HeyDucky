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
