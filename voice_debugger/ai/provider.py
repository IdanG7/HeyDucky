"""Abstract AI provider and response types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


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
    def model_name(self) -> str:
        """Return the model identifier."""
        ...
