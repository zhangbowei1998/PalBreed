"""In-memory agent trace store (for tests / no-Postgres environments)."""

from __future__ import annotations

from .models import AgentTrace, TraceStore


class InMemoryTraceStore(TraceStore):
    """进程内存储的 trace store，不需要外部数据库。

    用于单元测试与未配置 PostgreSQL 的环境；生产环境请用 PostgresTraceStore。
    """

    def __init__(self) -> None:
        self._traces: dict[str, AgentTrace] = {}
        self._order: list[str] = []

    async def connect(self) -> None:
        # 内存实现无需连接
        return None

    async def close(self) -> None:
        self._traces.clear()
        self._order.clear()

    async def record(self, trace: AgentTrace) -> None:
        if not trace.trace_uid:
            # 由调用方生成；这里兜底避免缺 key
            from uuid import uuid4

            trace.trace_uid = str(uuid4())
        self._traces[trace.trace_uid] = trace
        self._order.append(trace.trace_uid)

    async def list_recent(self, limit: int = 50) -> list[AgentTrace]:
        return [
            self._traces[uid]
            for uid in reversed(self._order[-limit:])
            if uid in self._traces
        ]

    async def get(self, trace_id: str) -> AgentTrace | None:
        return self._traces.get(trace_id)
