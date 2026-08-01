"""DeepSeek LLM client — OpenAI-compatible chat completions API.

DeepSeek 官方 API 使用 OpenAI 兼容协议（base_url=https://api.deepseek.com）。
该类通过 httpx 直接调用 /chat/completions，不依赖第三方 SDK，方便移植到
其他 OpenAI 兼容服务（通义、智谱、Ollama 等）。
"""

from __future__ import annotations

import json

import httpx

from .base import (
    ChatMessage,
    LLMClient,
    LLMConfig,
    LLMError,
    LLMInvalidResponseError,
    LLMResponse,
    LLMTimeoutError,
    LLMUnavailableError,
    ToolCall,
)


class DeepSeekClient(LLMClient):
    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"
        return headers

    def _serialize_message(self, message: ChatMessage | dict) -> dict:
        if isinstance(message, dict):
            return message
        return {"role": message.role.value, "content": message.content}

    def _payload(
        self, messages: list[ChatMessage | dict], tools: list[dict] | None
    ) -> dict:
        payload: dict = {
            "model": self._config.model,
            "messages": [self._serialize_message(m) for m in messages],
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        return payload

    def _stream_payload(
        self, messages: list[ChatMessage | dict], tools: list[dict] | None
    ) -> dict:
        payload: dict = {
            "model": self._config.model,
            "messages": [self._serialize_message(m) for m in messages],
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        return payload

    async def chat_stream(
        self,
        messages: list[ChatMessage | dict],
        *,
        tools: list[dict] | None = None,
    ):
        """Stream chat completion (OpenAI SSE). Yields text deltas."""
        url = f"{self._config.base_url.rstrip('/')}/chat/completions"
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST",
                    url,
                    headers=self._headers(),
                    content=json.dumps(self._stream_payload(messages, tools)),
                ) as response:
                    if response.status_code >= 400:
                        body = await response.aread()
                        raise LLMUnavailableError(
                            f"LLM HTTP {response.status_code}: {body[:300].decode(errors='ignore')}"
                        )
                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[len("data:"):].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        try:
                            delta = chunk["choices"][0]["delta"]
                        except (KeyError, IndexError, TypeError):
                            continue
                        content = delta.get("content")
                        if content:
                            yield content
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError("LLM stream timed out") from exc
        except httpx.HTTPError as exc:
            raise LLMUnavailableError(f"LLM stream network error: {exc}") from exc

    async def chat(
        self,
        messages: list[ChatMessage | dict],
        *,
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        url = f"{self._config.base_url.rstrip('/')}/chat/completions"
        try:
            async with httpx.AsyncClient(timeout=self._config.timeout_s) as client:
                response = await client.post(
                    url,
                    headers=self._headers(),
                    content=json.dumps(self._payload(messages, tools)),
                )
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError("LLM request timed out") from exc
        except httpx.HTTPError as exc:
            raise LLMUnavailableError(f"LLM network error: {exc}") from exc

        if response.status_code >= 400:
            raise LLMUnavailableError(
                f"LLM HTTP {response.status_code}: {response.text[:300]}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise LLMInvalidResponseError("LLM returned non-JSON payload") from exc

        try:
            message = payload["choices"][0]["message"]
            model = payload.get("model", self._config.model)
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMInvalidResponseError(
                "LLM payload missing choices[0].message"
            ) from exc

        content = message.get("content") or ""
        tool_calls: list[ToolCall] = []
        for raw_call in message.get("tool_calls") or []:
            function = raw_call.get("function") or {}
            name = function.get("name", "")
            arguments_raw = function.get("arguments", "{}")
            try:
                arguments = json.loads(arguments_raw) if arguments_raw else {}
            except json.JSONDecodeError:
                arguments = {}
            tool_calls.append(
                ToolCall(
                    id=raw_call.get("id", ""),
                    name=name,
                    arguments=arguments if isinstance(arguments, dict) else {},
                )
            )

        return LLMResponse(
            content=content,
            model=model,
            raw=payload,
            tool_calls=tool_calls,
        )
