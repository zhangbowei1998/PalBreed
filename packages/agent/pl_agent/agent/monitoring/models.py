"""Agent monitoring — trace every agent conversation.

记录每次用户对话的完整轨迹：
- 用户消息 / 最终回复
- 每次 LLM 调用（是否请求工具）
- 每个工具调用（name / arguments / result / 成功失败）
- 错误、耗时、质量信号
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol


@dataclass
class ToolCallRecord:
    name: str
    arguments: dict
    result: dict = field(default_factory=dict)
    success: bool = True
    error: str = ""


@dataclass
class LlmRoundRecord:
    round: int
    requested_tools: bool = False
    tool_calls: list[ToolCallRecord] = field(default_factory=list)


@dataclass
class AgentTrace:
    session_id: str
    user_key: str
    user_message: str
    reply: str
    model: str = ""
    llm_rounds: list[LlmRoundRecord] = field(default_factory=list)
    error: str = ""
    latency_ms: int = 0
    trace_uid: str = ""
    # 质量信号
    used_tools: bool = False
    had_error: bool = False
    tool_success_rate: float = 1.0
    reply_length: int = 0
    ts: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def tool_calls(self) -> list[ToolCallRecord]:
        return [
            tc
            for round_ in self.llm_rounds
            for tc in round_.tool_calls
        ]

    @property
    def quality_tags(self) -> list[str]:
        tags: list[str] = []
        if self.had_error:
            tags.append("有错误")
        if self.error:
            tags.append(f"异常: {self.error[:30]}")
        if self.used_tools and self.tool_success_rate < 1.0:
            tags.append("工具部分失败")
        if self.reply and self.reply_length < 10:
            tags.append("回复过短")
        return tags


class TraceStore(Protocol):
    async def record(self, trace: AgentTrace) -> None: ...

    async def list_recent(self, limit: int = 50) -> list[AgentTrace]: ...

    async def get(self, trace_id: str) -> AgentTrace | None: ...
