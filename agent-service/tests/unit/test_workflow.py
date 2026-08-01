from __future__ import annotations

import pytest

from pl_agent_agent.clients.schemas import SuitabilityCandidate, UpstreamPal
from pl_agent_agent.config import Settings
from pl_agent_agent.graph.workflow import ActionInput, AgentWorkflow, ChatInput
from pl_agent_agent.state.memory_store import InMemorySessionRepository


class FakeClient:
    async def query_top_suitability(self, work_type: str, level: int, top_n: int):
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
async def test_confirm_then_summarize_returns_graph_json():
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
            action="summarize_route",
            mode="explored_only",
        )
    )

    assert "graph_json" in result
    assert result["graph_json"]["roots"] == ["anubis"]
