from __future__ import annotations

import pytest

from pl_agent.agent.config import Settings
from pl_agent.agent.graph.agent_loop import AgentLoop
from pl_agent.agent.graph.workflow import AgentWorkflow, ChatInput
from pl_agent.agent.llm import LLMResponse
from pl_agent.agent.memory.long_term import LongTermMemory
from pl_agent.agent.state.memory_store import InMemorySessionRepository
from pl_agent.agent.tools import ToolRegistry, build_breeding_tools


class WorkflowFakeClient:
    async def query_top_suitability(self, work_type: str, level: int, top_n: int):
        return []

    async def get_parent_pairs(self, pal_id: str):
        return []

    async def resolve_pal(self, token: str):
        return {"id": token, "cn_name": token}

    async def resolve_pal_name(self, name: str):
        return {"id": name, "cn_name": name}

    async def query_stats(self):
        return {"total_pals": 288}


class WorkflowFakeLLM:
    """模拟 LLM：每次返回固定回答，并记录是否看到了压缩摘要。"""

    def __init__(self) -> None:
        self.saw_summary = False
        self.turn_count = 0

    async def chat(self, messages, *, tools=None):
        self.turn_count += 1
        for entry in messages:
            if entry.get("role") == "system" and "上下文记忆" in entry.get(
                "content", ""
            ):
                self.saw_summary = True
                break
        return LLMResponse(content=f"回答 {self.turn_count}", model="fake")


@pytest.mark.asyncio
async def test_llm_chat_triggers_compression_when_history_exceeds_limit(tmp_path):
    settings = Settings(short_term_max_turns=2)
    repository = InMemorySessionRepository()
    long_term = LongTermMemory(data_dir=tmp_path)
    llm = WorkflowFakeLLM()

    workflow = AgentWorkflow(
        settings=settings,
        repository=repository,
        client=WorkflowFakeClient(),
        llm=llm,
        long_term_memory=long_term,
    )
    # 让 workflow 走 LLM 模式：手工构造 agent_loop（因为 llm 非 None 会自动构造）

    # 连续 6 次对话，每轮 2 条（user+assistant），阈值 2 轮 = 4 条
    for i in range(6):
        await workflow.handle_chat(ChatInput(session_id="s1", message=f"消息 {i}"))

    state = await repository.get("s1")
    assert state is not None
    # 短期记忆被截断到 max_turns*2 = 4 条
    assert len(state.chat_history) <= 4
    # 早期对话被压缩成摘要
    assert state.history_summary


@pytest.mark.asyncio
async def test_llm_chat_long_term_memory_is_per_user(tmp_path):
    settings = Settings()
    repository = InMemorySessionRepository()
    long_term = LongTermMemory(data_dir=tmp_path)
    llm = WorkflowFakeLLM()

    workflow = AgentWorkflow(
        settings=settings,
        repository=repository,
        client=WorkflowFakeClient(),
        llm=llm,
        long_term_memory=long_term,
    )

    # 用户 A 声明拥有阿努比斯
    await workflow.handle_chat(
        ChatInput(session_id="a-1", message="我已经有阿努比斯了", user_id="user-a")
    )
    # 用户 B 声明拥有墨罗娜
    await workflow.handle_chat(
        ChatInput(session_id="b-1", message="我已经有墨罗娜了", user_id="user-b")
    )

    facts_a = await long_term.load("user-a")
    facts_b = await long_term.load("user-b")
    assert {f.content for f in facts_a} == {"阿努比斯"}
    assert {f.content for f in facts_b} == {"墨罗娜"}
    # 匿名用户（无 token）长期记忆为空
    assert await long_term.load(settings.default_user_key) == []
