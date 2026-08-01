from __future__ import annotations

import pytest

from pl_agent.agent.config import Settings
from pl_agent.agent.graph.agent_loop import AgentLoop
from pl_agent.agent.graph.workflow import AgentWorkflow, ChatInput
from pl_agent.agent.llm import LLMResponse, ToolCall
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


class ToolCallingLLM:
    """第一轮调用 query_parent_pairs，第二轮返回最终文本。"""

    def __init__(self) -> None:
        self.round = 0

    async def chat(self, messages, *, tools=None):
        self.round += 1
        if self.round == 1:
            return LLMResponse(
                content="",
                model="fake",
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="query_parent_pairs",
                        arguments={"pal_name": "阿努比斯"},
                    )
                ],
            )
        return LLMResponse(content="阿努比斯可以这样配。", model="fake")


class PairFakeClient(WorkflowFakeClient):
    """提供一组真实配种对的客户端。"""

    async def get_parent_pairs(self, pal_id: str):
        if pal_id == "阿努比斯":
            return [
                {"parent_a": "空涡龙", "parent_b": "妖焰灯", "method": "breed"},
                {"parent_a": "默世鹿", "parent_b": "塞赫麦特", "method": "breed"},
            ]
        return []


@pytest.mark.asyncio
async def test_llm_chat_returns_select_parent_pair_actions(tmp_path):
    """LLM 调用 query_parent_pairs 成功后，应返回可点击的配种方案操作，
    前端据此触发配种二叉树。"""
    settings = Settings()
    repository = InMemorySessionRepository()
    llm = ToolCallingLLM()

    workflow = AgentWorkflow(
        settings=settings,
        repository=repository,
        client=PairFakeClient(),
        llm=llm,
        long_term_memory=LongTermMemory(data_dir=tmp_path),
    )

    result = await workflow.handle_chat(
        ChatInput(session_id="tree1", message="阿努比斯怎么配种")
    )

    # LLM 文本回复 + 确定性的父母候选消息
    assert len(result["messages"]) >= 2
    assert "父母候选" in result["messages"][1]["content"]

    # 返回 select_parent_pair 操作，前端可点击
    pair_actions = [
        a for a in result["actions"] if a["action"] == "select_parent_pair"
    ]
    assert pair_actions, "LLM 配种后应返回 select_parent_pair actions"
    assert pair_actions[0]["payload"]["child_pal_id"] == "阿努比斯"
    assert len(pair_actions) == 2

    # state 已记录候选，配种树可渲染
    snapshot = result["state_snapshot"]
    assert snapshot["candidate_pairs"], "候选配种组合应已记录"
    assert snapshot["edges"], "配种边应已写入"
    # LLM 查询配种方案后，自动设为当前目标，后续追溯可正常进行
    assert snapshot["target_pal"] == "阿努比斯"
    assert snapshot["confirmed_target_pal"] == "阿努比斯"

