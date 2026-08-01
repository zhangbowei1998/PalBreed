from __future__ import annotations

import pytest

from pl_agent.agent.graph.agent_loop import AgentLoop
from pl_agent.agent.llm import LLMResponse, ToolCall
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
        self.calls = 0

    async def chat(self, messages, *, tools=None):
        self.calls += 1
        if self.calls == 1:
            return LLMResponse(
                content="",
                model="fake",
                tool_calls=[
                    ToolCall(
                        id="call-1",
                        name="query_parent_pairs",
                        arguments={"pal_name": "墨罗娜"},
                    )
                ],
            )
        return LLMResponse(
            content="墨罗娜可以由 奥沧鲸 + 凌角马 配种得到。",
            model="fake",
        )


@pytest.mark.asyncio
async def test_agent_loop_runs_tool_then_returns_answer():
    registry = ToolRegistry(build_breeding_tools(FakeToolClient(), top_n_default=3))
    loop = AgentLoop(
        llm=FakeLLM(),
        registry=registry,
        system_prompt="你是测试助手",
    )

    answer = await loop.run("墨罗娜怎么配种")

    assert "奥沧鲸" in answer
    assert "凌角马" in answer


class MemoryCheckingLLM:
    def __init__(self) -> None:
        self.seen_history = False

    async def chat(self, messages, *, tools=None):
        for entry in messages:
            if (
                entry.get("role") == "user"
                and entry.get("content") == "手工最高的是哪只帕鲁"
            ):
                self.seen_history = True
                break
        return LLMResponse(content="应该是指墨罗娜。", model="fake")


@pytest.mark.asyncio
async def test_agent_loop_carries_history():
    registry = ToolRegistry(build_breeding_tools(FakeToolClient(), top_n_default=3))
    llm = MemoryCheckingLLM()
    loop = AgentLoop(llm=llm, registry=registry, system_prompt="你是测试助手")

    history = [{"role": "user", "content": "手工最高的是哪只帕鲁"}]
    answer = await loop.run("怎么配种", history=history)

    assert llm.seen_history
    assert answer == "应该是指墨罗娜。"
