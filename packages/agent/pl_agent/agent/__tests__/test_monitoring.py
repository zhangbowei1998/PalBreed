from __future__ import annotations

import pytest

from pl_agent.agent.config import Settings
from pl_agent.agent.graph.workflow import AgentWorkflow, ChatInput
from pl_agent.agent.llm import LLMResponse, ToolCall
from pl_agent.agent.memory.long_term import LongTermMemory
from pl_agent.agent.monitoring.models import AgentTrace, TraceStore
from pl_agent.agent.state.memory_store import InMemorySessionRepository


class InMemoryTraceStore(TraceStore):
    def __init__(self) -> None:
        self.records: list[AgentTrace] = []

    async def record(self, trace: AgentTrace) -> None:
        self.records.append(trace)

    async def list_recent(self, limit: int = 50) -> list[AgentTrace]:
        return self.records[-limit:]

    async def get(self, trace_id: str) -> AgentTrace | None:
        for t in self.records:
            if t.trace_uid == trace_id:
                return t
        return None


class Client:
    async def query_top_suitability(self, work_type, level, top_n):
        return []

    async def get_parent_pairs(self, pal_id):
        return []

    async def resolve_pal(self, token):
        return {"id": token, "cn_name": token}

    async def resolve_pal_name(self, name):
        return {"id": name, "cn_name": name}

    async def query_stats(self):
        return {"total_pals": 288}


class TracingLLM:
    """第一轮请求工具，第二轮返回最终回答。"""

    def __init__(self) -> None:
        self.calls = 0

    async def chat(self, messages, *, tools=None):
        self.calls += 1
        if self.calls == 1:
            return LLMResponse(
                content="",
                model="fake-model",
                tool_calls=[
                    ToolCall(
                        id="c1",
                        name="query_top_suitability",
                        arguments={"work_type": "采矿", "top_n": 3},
                    )
                ],
            )
        return LLMResponse(content="磐甲龙采矿最高。", model="fake-model")


class FailingToolLLM:
    """请求一个不存在的工具，触发 ToolError。"""

    async def chat(self, messages, *, tools=None):
        return LLMResponse(
            content="",
            model="fake-model",
            tool_calls=[
                ToolCall(id="c1", name="nonexistent_tool", arguments={})
            ],
        )


@pytest.mark.asyncio
async def test_workflow_records_trace_with_tool_call(tmp_path):
    store = InMemoryTraceStore()
    workflow = AgentWorkflow(
        settings=Settings(short_term_max_turns=2),
        repository=InMemorySessionRepository(),
        client=Client(),
        llm=TracingLLM(),
        long_term_memory=LongTermMemory(data_dir=tmp_path),
        trace_store=store,
    )

    await workflow.handle_chat(
        ChatInput(session_id="s1", message="采矿最高的是哪只帕鲁", user_id="u1")
    )

    assert len(store.records) == 1
    trace = store.records[0]
    assert trace.user_message == "采矿最高的是哪只帕鲁"
    assert trace.user_key == "u1"
    assert trace.used_tools is True
    assert trace.had_error is False
    assert trace.reply == "磐甲龙采矿最高。"
    assert len(trace.tool_calls) == 1
    assert trace.tool_calls[0].name == "query_top_suitability"
    assert trace.tool_calls[0].success is True
    assert trace.model == "fake-model"


@pytest.mark.asyncio
async def test_workflow_records_trace_with_tool_error(tmp_path):
    store = InMemoryTraceStore()
    workflow = AgentWorkflow(
        settings=Settings(),
        repository=InMemorySessionRepository(),
        client=Client(),
        llm=FailingToolLLM(),
        long_term_memory=LongTermMemory(data_dir=tmp_path),
        trace_store=store,
    )

    await workflow.handle_chat(ChatInput(session_id="s2", message="配种一下"))

    assert len(store.records) == 1
    trace = store.records[0]
    assert trace.used_tools is True
    assert trace.tool_success_rate < 1.0
    assert trace.tool_calls[0].success is False
    assert trace.tool_calls[0].error


@pytest.mark.asyncio
async def test_workflow_skips_trace_when_no_store(tmp_path):
    workflow = AgentWorkflow(
        settings=Settings(),
        repository=InMemorySessionRepository(),
        client=Client(),
        llm=TracingLLM(),
        long_term_memory=LongTermMemory(data_dir=tmp_path),
        trace_store=None,
    )

    await workflow.handle_chat(ChatInput(session_id="s3", message="阿努比斯"))
    # 无 store 不应报错
