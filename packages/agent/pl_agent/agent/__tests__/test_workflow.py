from __future__ import annotations

import pytest

from pl_agent.agent.clients.schemas import SuitabilityCandidate, UpstreamPal
from pl_agent.agent.config import Settings
from pl_agent.agent.graph.workflow import ActionInput, AgentWorkflow, ChatInput
from pl_agent.agent.state.memory_store import InMemorySessionRepository


class FakeClient:
    def __init__(self) -> None:
        self.last_work_type: str | None = None

    async def query_top_suitability(self, work_type: str, level: int, top_n: int):
        self.last_work_type = work_type
        return [
            SuitabilityCandidate(
                pal=UpstreamPal(id="anubis", cn_name="阿努比斯"),
                matched_level=4,
            ),
            SuitabilityCandidate(
                pal=UpstreamPal(id="penking", cn_name="企丸丸"),
                matched_level=4,
            ),
        ][:top_n]

    async def get_parent_pairs(self, pal_id: str):
        if pal_id == "anubis":
            return [{"parent_a": "棉悠悠", "parent_b": "捣蛋猫", "method": "breed"}]
        return []

    async def resolve_pal(self, token: str):
        mapper = {
            "棉悠悠": {"id": "lamball", "cn_name": "棉悠悠"},
            "捣蛋猫": {"id": "cattiva", "cn_name": "捣蛋猫"},
            "anubis": {"id": "anubis", "cn_name": "阿努比斯"},
        }
        return mapper.get(token, {"id": token, "cn_name": token})

    async def resolve_pal_name(self, name: str):
        if name in {"anubis", "阿努比斯"}:
            return {"id": "anubis", "cn_name": "阿努比斯"}
        return None

    async def query_stats(self):
        return {"total_pals": 288}


@pytest.mark.asyncio
async def test_top_query_returns_confirm_actions():
    workflow = AgentWorkflow(
        settings=Settings(top_candidates=3),
        repository=InMemorySessionRepository(),
        client=FakeClient(),
    )

    result = await workflow.handle_chat(
        ChatInput(session_id="s1", message="手工等级最高的帕鲁怎么配种")
    )

    assert result["messages"]
    assert any(a["action"] == "confirm_target" for a in result["actions"])


@pytest.mark.asyncio
async def test_kindling_top_query_uses_kindling_work_type():
    client = FakeClient()
    workflow = AgentWorkflow(
        settings=Settings(top_candidates=3),
        repository=InMemorySessionRepository(),
        client=client,
    )

    result = await workflow.handle_chat(
        ChatInput(session_id="s3", message="烧火最高的是哪只帕鲁")
    )

    assert client.last_work_type == "kindling"
    assert result["messages"]
    assert any(a["action"] == "confirm_target" for a in result["actions"])


@pytest.mark.asyncio
async def test_stats_query_returns_total():
    workflow = AgentWorkflow(
        settings=Settings(top_candidates=3),
        repository=InMemorySessionRepository(),
        client=FakeClient(),
    )

    result = await workflow.handle_chat(
        ChatInput(session_id="s4", message="一共有多少帕鲁")
    )

    assert result["messages"]
    assert "288" in result["messages"][0]["content"]


@pytest.mark.asyncio
async def test_pal_name_query_starts_expand_flow():
    workflow = AgentWorkflow(
        settings=Settings(top_candidates=3),
        repository=InMemorySessionRepository(),
        client=FakeClient(),
    )

    result = await workflow.handle_chat(ChatInput(session_id="s5", message="阿努比斯"))

    assert result["messages"]
    assert any(a["action"] == "select_parent_pair" for a in result["actions"])
    assert "阿努比斯" in result["messages"][0]["content"]


@pytest.mark.asyncio
async def test_confirm_then_select_returns_continue_actions():
    workflow = AgentWorkflow(
        settings=Settings(top_candidates=3),
        repository=InMemorySessionRepository(),
        client=FakeClient(),
    )

    await workflow.handle_chat(
        ChatInput(session_id="s2", message="手工等级最高的帕鲁怎么配种")
    )
    await workflow.handle_action(
        ActionInput(session_id="s2", action="confirm_target", pal_id="anubis")
    )
    result = await workflow.handle_action(
        ActionInput(
            session_id="s2",
            action="select_parent_pair",
            child_pal_id="anubis",
            pair_index=0,
        )
    )

    assert "graph_json" not in result
    continue_actions = [
        a for a in result["actions"] if a["action"] == "continue_from_parent"
    ]
    assert len(continue_actions) == 2
