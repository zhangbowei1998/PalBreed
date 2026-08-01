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

    state = await repository.get("u:default:s1")
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


@pytest.mark.asyncio
async def test_short_term_memory_is_per_user(tmp_path):
    """不同用户即使 session_id 相同，短期记忆也不串扰。"""
    settings = Settings()
    repository = InMemorySessionRepository()
    llm = WorkflowFakeLLM()

    workflow = AgentWorkflow(
        settings=settings,
        repository=repository,
        client=WorkflowFakeClient(),
        llm=llm,
        long_term_memory=LongTermMemory(data_dir=tmp_path),
    )

    # 用户 A 用 session "shared-1"
    await workflow.handle_chat(
        ChatInput(session_id="shared-1", message="A 的第一条", user_id="user-a")
    )
    # 用户 B 也用 session "shared-1"（不同用户）
    await workflow.handle_chat(
        ChatInput(session_id="shared-1", message="B 的第一条", user_id="user-b")
    )

    # 内部存储应存在两个隔离 key（u:user-a:shared-1 与 u:user-b:shared-1）
    state_a = await repository.get("u:user-a:shared-1")
    state_b = await repository.get("u:user-b:shared-1")
    assert state_a is not None and state_b is not None
    assert state_a.chat_history[0].content == "A 的第一条"
    assert state_b.chat_history[0].content == "B 的第一条"
    assert state_a is not state_b


@pytest.mark.asyncio
async def test_anonymous_session_isolated_from_user_session(tmp_path):
    """匿名用户与登录用户短期记忆隔离。"""
    settings = Settings()
    repository = InMemorySessionRepository()
    llm = WorkflowFakeLLM()

    workflow = AgentWorkflow(
        settings=settings,
        repository=repository,
        client=WorkflowFakeClient(),
        llm=llm,
        long_term_memory=LongTermMemory(data_dir=tmp_path),
    )

    await workflow.handle_chat(ChatInput(session_id="s1", message="匿名消息"))
    await workflow.handle_chat(
        ChatInput(session_id="s1", message="登录用户消息", user_id="user-x")
    )

    anon = await repository.get("u:default:s1")
    logged = await repository.get("u:user-x:s1")
    assert anon is not None and logged is not None
    assert anon.chat_history[0].content == "匿名消息"
    assert logged.chat_history[0].content == "登录用户消息"

