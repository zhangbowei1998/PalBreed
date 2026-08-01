"""Tool abstraction — deterministic APIs exposed to the LLM as function-calling tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ToolError(Exception):
    """Tool execution error."""


class Tool(ABC):
    """A deterministic tool the LLM can call via function calling.

    Implementations must return a plain-JSON-serializable value that the LLM
    will receive as the tool result. Errors should be raised as ToolError so
    the agent loop can surface them gracefully.
    """

    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {}

    def to_openai_function(self) -> dict[str, Any]:
        """Convert this tool to an OpenAI-compatible function schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    @abstractmethod
    async def run(self, **kwargs: Any) -> Any:
        """Execute the tool with validated arguments."""
