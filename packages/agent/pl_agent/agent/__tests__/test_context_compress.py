from __future__ import annotations

import pytest

from pl_agent.agent.graph.agent_loop import AgentLoop
from pl_agent.agent.llm import LLMResponse
from pl_agent.agent.memory.compress import summarize_history
from pl_agent.agent.state.models import ChatTurn
from pl_agent.agent.tools import ToolRegistry, build_breeding_tools


class FakeToolClient:
    async def resolve_pal_name(self, name: str):
        return {"id": "MonochromeQueen", "cn_name": "墨罗娜"}

    async def get_parent_pairs(self, pal_id: str):
        return [{"parent_a": "奥沧鲸", "parent_b": "凌角马", "method": "breed"}]

    async def get_pal_detail(self, pal_id: str):
        return {"id": pal_id, "cn_name": "墨罗娜"}

    async def query_top_suitability(self, work_type: str, level: int, top_n: int):
        return []

    async def query_stats(self):
        return {"total_pals": 288}


class FakeLLM:
    def __init__(self) -> None:
        self.last_messages = []

    async def chat(self, messages, *, tools=None):
        self.last_messages = messages
        return LLMResponse(content="摘要：用户想要墨罗娜，已有阿努比斯。", model="fake")


@pytest.mark.asyncio
async def test_summarize_history_calls_llm_and_returns_summary():
    llm = FakeLLM()
    turns = [
        ChatTurn(role="user", content="我想要墨罗娜"),
        ChatTurn(role="assistant", content="墨罗娜需要 奥沧鲸 + 凌角马"),
        ChatTurn(role="user", content="我已经有阿努比斯了"),
    ]
    summary = await summarize_history(llm, turns)
    assert summary == "摘要：用户想要墨罗娜，已有阿努比斯。"


@pytest.mark.asyncio
async def test_summarize_history_empty_turns_returns_empty():
    llm = FakeLLM()
    assert await summarize_history(llm, []) == ""


class SummaryAwareLLM:
    def __init__(self) -> None:
        self.saw_summary = False

    async def chat(self, messages, *, tools=None):
        for entry in messages:
            if entry.get("role") == "system" and "上下文记忆" in entry.get(
                "content", ""
            ):
                self.saw_summary = True
                break
        return LLMResponse(content="好的。", model="fake")


@pytest.mark.asyncio
async def test_agent_loop_injects_history_summary():
    registry = ToolRegistry(build_breeding_tools(FakeToolClient(), top_n_default=3))
    llm = SummaryAwareLLM()
    loop = AgentLoop(llm=llm, registry=registry, system_prompt="你是测试助手")

    await loop.run(
        "怎么配种",
        history=[{"role": "user", "content": "手工最高的是哪只帕鲁"}],
        long_term_facts=["用户拥有帕鲁：阿努比斯"],
        history_summary="摘要：用户之前问过手工最高帕鲁。",
    )

    assert llm.saw_summary
