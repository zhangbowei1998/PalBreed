"""LLM client abstraction — providers implement this interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class ChatMessage:
    role: Role | Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass(frozen=True)
class LLMResponse:
    content: str
    model: str = ""
    raw: dict = field(default_factory=dict)
    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass(frozen=True)
class LLMConfig:
    provider: str = "deepseek"
    base_url: str = "https://api.deepseek.com"
    api_key: str = ""
    model: str = "deepseek-chat"
    temperature: float = 0.1
    max_tokens: int = 1024
    timeout_s: float = 15.0


class LLMError(Exception):
    """Base LLM provider error."""


class LLMUnavailableError(LLMError):
    """Provider unreachable or returned a server error."""


class LLMTimeoutError(LLMError):
    """Provider call timed out."""


class LLMInvalidResponseError(LLMError):
    """Provider returned unparseable / unexpected payload."""


class LLMClient(ABC):
    """Uniform interface every provider adapter must implement."""

    def __init__(self, config: LLMConfig) -> None:
        self._config = config

    @property
    def config(self) -> LLMConfig:
        return self._config

    @property
    def provider(self) -> str:
        return self._config.provider

    @property
    def model(self) -> str:
        return self._config.model

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage | dict],
        *,
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """Send a chat completion request; optionally pass OpenAI-style tool schemas.

        ``messages`` may contain ``ChatMessage`` objects or raw OpenAI wire-format
        dicts (e.g. assistant ``tool_calls`` frames and ``tool`` result frames).
        Providers that support function calling should populate
        ``LLMResponse.tool_calls`` when the model asks to call a tool.
        """

    async def chat_stream(
        self,
        messages: list[ChatMessage | dict],
        *,
        tools: list[dict] | None = None,
    ):
        """Stream a chat completion, yielding text deltas.

        Default implementation falls back to a single ``chat`` call.
        Providers that support OpenAI-style SSE streaming override this.
        """
        response = await self.chat(messages, tools=tools)
        if response.content:
            yield response.content

    async def complete(self, prompt: str) -> str:
        """Convenience helper for single-prompt completion."""
        response = await self.chat([ChatMessage(role=Role.USER, content=prompt)])
        return response.content
