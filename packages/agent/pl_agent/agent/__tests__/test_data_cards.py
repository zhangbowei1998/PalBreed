"""端到端: AgentWorkflow.handle_chat 工具调用 → data_cards 集成测试。"""

import pytest

from pl_agent.agent.config import Settings
from pl_agent.agent.graph.agent_loop import AgentLoopResult
from pl_agent.agent.graph.workflow import AgentWorkflow, ChatInput
from pl_agent.agent.monitoring.models import LlmRoundRecord, ToolCallRecord
from pl_agent.agent.state.memory_store import InMemorySessionRepository


class _MinClient:
    """handle_chat 所需的 client 最小实现。"""

    async def resolve_pal_name(self, name: str):
        return {"id": name, "cn_name": name} if name in {"anubis", "阿努比斯"} else None

    async def get_parent_pairs(self, pal_id: str):
        return []

    async def query_top_suitability(self, work_type, level, top_n):
        return []


class FakeAgentLoop:
    """返回固定 AgentLoopResult（含工具调用记录）的假 AgentLoop。"""

    def __init__(self, content: str = "", tool_calls: list | None = None) -> None:
        self._content = content
        self._tool_calls = tool_calls or []

    async def run(self, message, *, history, long_term_facts, history_summary, text_callback=None):
        if text_callback:
            await text_callback(self._content)
        rounds = (
            [LlmRoundRecord(round=1, tool_calls=self._tool_calls)]
            if self._tool_calls
            else []
        )
        return AgentLoopResult(content=self._content, model="fake", llm_rounds=rounds)


def _workflow(loop: FakeAgentLoop) -> AgentWorkflow:
    wf = AgentWorkflow(
        settings=Settings(top_candidates=3),
        repository=InMemorySessionRepository(),
        client=_MinClient(),
        llm=None,
    )
    wf._agent_loop = loop  # 注入假 AgentLoop
    return wf


@pytest.mark.asyncio
async def test_item_drops_produces_drop_card():
    tool = ToolCallRecord(
        name="query_item_drops",
        arguments={"item_name": "骨头"},
        result={"item": "骨头", "pals": [{"pal_id": "garm", "pal_cn": "加姆", "rate": 3}], "total": 1},
        success=True,
    )
    wf = _workflow(FakeAgentLoop("骨头由以下帕鲁掉落。", [tool]))
    result = await wf.handle_chat(
        ChatInput(session_id="s1", message="骨头怎么获取", user_id="u1")
    )
    assert "data_cards" in result
    cards = result["data_cards"]
    assert cards[0]["type"] == "drop"
    assert cards[0]["item"] == "骨头"
    assert cards[0]["pals"][0]["pal_cn"] == "加姆"


@pytest.mark.asyncio
async def test_pals_by_passive_produces_passive_card():
    tool = ToolCallRecord(
        name="query_pals_by_passive",
        arguments={"passive_name": "重量级"},
        result={"passive": "重量级", "pals": [{"id": "KingAlpaca", "cn_name": "君王美露帕"}], "total": 1},
        success=True,
    )
    wf = _workflow(FakeAgentLoop("拥有重量级被动的帕鲁有：", [tool]))
    result = await wf.handle_chat(
        ChatInput(session_id="s2", message="哪只帕鲁有重量级", user_id="u1")
    )
    assert result["data_cards"][0]["type"] == "passive"
    assert result["data_cards"][0]["passive"] == "重量级"


@pytest.mark.asyncio
async def test_no_tool_calls_no_data_cards():
    wf = _workflow(FakeAgentLoop("你好", []))
    result = await wf.handle_chat(
        ChatInput(session_id="s3", message="你好", user_id="u1")
    )
    assert "data_cards" not in result


@pytest.mark.asyncio
async def test_failed_tool_no_card():
    tool = ToolCallRecord(
        name="query_item_drops",
        arguments={"item_name": "骨头"},
        result={},
        success=False,
    )
    wf = _workflow(FakeAgentLoop("没找到。", [tool]))
    result = await wf.handle_chat(
        ChatInput(session_id="s4", message="骨头怎么获取", user_id="u1")
    )
    assert "data_cards" not in result
