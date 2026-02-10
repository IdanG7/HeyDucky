"""Abstract AI provider and response types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator


# Approximate per-token costs (USD)
COST_PER_TOKEN = {
    "claude": {"input": 3.0 / 1_000_000, "output": 15.0 / 1_000_000},
}


@dataclass
class ToolCall:
    """A function/tool call from the AI."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class AIResponse:
    """Response from an AI provider."""

    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0

    def cost(self, provider: str) -> float:
        """Calculate cost in USD for this response."""
        rates = COST_PER_TOKEN.get(provider, COST_PER_TOKEN["claude"])
        return (
            self.input_tokens * rates["input"]
            + self.output_tokens * rates["output"]
        )


@dataclass
class StreamEvent:
    """A single event from a streaming AI response.

    Attributes:
        type: Event type - "text" for text deltas, "tool_call" for completed
              tool calls, "done" for the final event with full response.
        text: Text delta for "text" events, empty otherwise.
        tool_call: Completed ToolCall for "tool_call" events, None otherwise.
        response: Full AIResponse for "done" events, None otherwise.
    """

    type: str  # "text", "tool_call", "done"
    text: str = ""
    tool_call: ToolCall | None = None
    response: AIResponse | None = None


class AIProvider(ABC):
    """Abstract base for AI providers."""

    @abstractmethod
    async def send_message(
        self,
        messages: list[dict],
        system: str = "",
        tools: list[dict] | None = None,
    ) -> AIResponse:
        """Send messages and get a response."""
        ...

    @abstractmethod
    async def stream_message(
        self,
        messages: list[dict],
        system: str = "",
        tools: list[dict] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Stream a response, yielding events as they arrive.

        Yields StreamEvent with type="text" for text deltas,
        type="tool_call" for each completed tool call, and
        type="done" with the full AIResponse at the end.
        """
        ...
        # Make this an async generator for type-checking purposes
        yield  # type: ignore[misc]  # pragma: no cover

    @abstractmethod
    async def count_tokens(
        self,
        messages: list[dict],
        system: str = "",
        tools: list[dict] | None = None,
    ) -> int:
        """Count input tokens for the given messages."""
        ...

    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier."""
        ...
