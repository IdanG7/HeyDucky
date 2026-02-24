"""Anthropic Claude AI provider."""

from __future__ import annotations

from typing import AsyncIterator

from anthropic import AsyncAnthropic

from heyducky.ai.provider import AIProvider, AIResponse, StreamEvent, ToolCall


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
            "max_tokens": 4096,
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

    async def stream_message(
        self,
        messages: list[dict],
        system: str = "",
        tools: list[dict] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Stream a response from Claude, yielding events as they arrive."""
        kwargs: dict = {
            "model": self._model,
            "max_tokens": 4096,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        async with self._client.messages.stream(**kwargs) as stream:
            async for event in stream:
                if event.type == "content_block_delta":
                    if event.delta.type == "text_delta":
                        yield StreamEvent(type="text", text=event.delta.text)

            # After stream completes, get the full message
            message = await stream.get_final_message()

        # Extract tool calls from the final message
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for block in message.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tc = ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input,
                )
                tool_calls.append(tc)
                yield StreamEvent(type="tool_call", tool_call=tc)

        response = AIResponse(
            text=" ".join(text_parts),
            tool_calls=tool_calls,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
        )
        yield StreamEvent(type="done", response=response)

    async def count_tokens(
        self,
        messages: list[dict],
        system: str = "",
        tools: list[dict] | None = None,
    ) -> int:
        """Count input tokens using the Anthropic API."""
        kwargs: dict = {
            "model": self._model,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        result = await self._client.messages.count_tokens(**kwargs)
        return result.input_tokens

    def model_name(self) -> str:
        return self._model
