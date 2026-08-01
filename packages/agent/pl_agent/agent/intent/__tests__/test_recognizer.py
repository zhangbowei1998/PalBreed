"""Intent recognizer tests — LLM + rule fallback."""

from __future__ import annotations

import pytest

from pl_agent.agent.intent import Intent, IntentRecognizer


class FakeLLM:
    def __init__(self, content: str) -> None:
        self._content = content
        self.calls = 0

    async def chat(self, messages):
        self.calls += 1
        return type(
            "Resp", (), {"content": self._content, "model": "fake", "raw": {}}
        )()


class FakeApi:
    def __init__(self, known: set[str] | None = None) -> None:
        self._known = known or set()

    async def resolve_pal_name(self, name: str):
        if name in self._known:
            return {"id": name, "cn_name": name}
        return None


@pytest.mark.asyncio
async def test_llm_top_suitability():
    llm = FakeLLM(
        '{"intent":"top_suitability","work_type":"烧火","pal_name":null,"reason":"x"}'
    )
    recognizer = IntentRecognizer(llm=llm)
    result = await recognizer.recognize("烧火最高的是哪只")
    assert result.intent == Intent.TOP_SUITABILITY
    assert result.work_type == "kindling"


@pytest.mark.asyncio
async def test_llm_expand_pal():
    llm = FakeLLM(
        '{"intent":"expand_pal","work_type":null,"pal_name":"墨罗娜","reason":"x"}'
    )
    recognizer = IntentRecognizer(llm=llm)
    result = await recognizer.recognize("墨罗娜怎么配种")
    assert result.intent == Intent.EXPAND_PAL
    assert result.pal_name == "墨罗娜"


@pytest.mark.asyncio
async def test_llm_failure_falls_back_to_rules():
    recognizer = IntentRecognizer(llm=None)
    result = await recognizer.recognize("采矿最高的是哪只")
    assert result.intent == Intent.TOP_SUITABILITY
    assert result.work_type == "mining"


@pytest.mark.asyncio
async def test_rule_expand_pal_via_api():
    recognizer = IntentRecognizer(llm=None, breeding_api=FakeApi(known={"墨罗娜"}))
    result = await recognizer.recognize("墨罗娜")
    assert result.intent == Intent.EXPAND_PAL
    assert result.pal_name == "墨罗娜"


@pytest.mark.asyncio
async def test_rule_stats():
    recognizer = IntentRecognizer(llm=None)
    result = await recognizer.recognize("一共有多少帕鲁")
    assert result.intent == Intent.PAL_STATS


@pytest.mark.asyncio
async def test_rule_general_chat():
    recognizer = IntentRecognizer(llm=None)
    result = await recognizer.recognize("你好呀")
    assert result.intent == Intent.GENERAL_CHAT
