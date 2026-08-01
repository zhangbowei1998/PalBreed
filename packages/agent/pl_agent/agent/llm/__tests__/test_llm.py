"""LLM adapter tests — factory and DeepSeek request shaping."""

from __future__ import annotations

import json

import pytest

from pl_agent.agent.llm import (
    ChatMessage,
    LLMConfig,
    LLMError,
    Role,
    create_llm_client,
)
from pl_agent.agent.llm.deepseek import DeepSeekClient


def test_factory_creates_deepseek():
    config = LLMConfig(provider="deepseek", api_key="k", model="deepseek-chat")
    client = create_llm_client(config)
    assert isinstance(client, DeepSeekClient)
    assert client.model == "deepseek-chat"


def test_factory_rejects_unknown_provider():
    with pytest.raises(LLMError):
        create_llm_client(LLMConfig(provider="nope"))


@pytest.mark.asyncio
async def test_deepseek_request_and_response(monkeypatch):
    client = DeepSeekClient(
        LLMConfig(
            base_url="https://api.deepseek.com", api_key="secret", model="deepseek-chat"
        )
    )

    captured: dict = {}

    async def fake_post(self, url, headers, content):
        captured["url"] = url
        captured["headers"] = headers
        captured["body"] = json.loads(content)
        return _FakeResponse(
            200,
            {
                "choices": [{"message": {"content": '{"ok":1}'}}],
                "model": "deepseek-chat",
            },
        )

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)
    response = await client.chat(
        [ChatMessage(role=Role.USER, content="烧火最高的是哪只")]
    )

    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer secret"
    assert captured["body"]["messages"][0] == {
        "role": "user",
        "content": "烧火最高的是哪只",
    }
    assert response.content == '{"ok":1}'
    assert response.model == "deepseek-chat"


class _FakeResponse:
    def __init__(self, status_code: int, json_payload: dict) -> None:
        self.status_code = status_code
        self._json = json_payload
        self.text = json.dumps(json_payload)

    def json(self):
        return self._json
