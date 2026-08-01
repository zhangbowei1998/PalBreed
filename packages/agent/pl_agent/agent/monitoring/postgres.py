"""PostgreSQL-backed agent trace store.

表结构 agent_trace:
    id BIGSERIAL PRIMARY KEY,
    trace_uid text UNIQUE,            -- 唯一标识（用于按 id 查询）
    session_id text, user_key text,
    user_message text, reply text,
    model text, llm_rounds jsonb,     -- 工具调用/LLM 轮次记录
    error text, latency_ms int,
    used_tools bool, had_error bool, tool_success_rate float,
    reply_length int, ts timestamptz
"""

from __future__ import annotations

import json
import uuid

import asyncpg

from .models import AgentTrace, LlmRoundRecord, ToolCallRecord

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS agent_trace (
    id                 BIGSERIAL PRIMARY KEY,
    trace_uid          TEXT NOT NULL UNIQUE,
    session_id         TEXT NOT NULL,
    user_key           TEXT NOT NULL DEFAULT 'default',
    user_message       TEXT NOT NULL,
    reply              TEXT NOT NULL,
    model              TEXT NOT NULL DEFAULT '',
    llm_rounds         JSONB NOT NULL DEFAULT '[]'::jsonb,
    error              TEXT NOT NULL DEFAULT '',
    latency_ms         INT NOT NULL DEFAULT 0,
    used_tools         BOOLEAN NOT NULL DEFAULT FALSE,
    had_error          BOOLEAN NOT NULL DEFAULT FALSE,
    tool_success_rate  FLOAT NOT NULL DEFAULT 1.0,
    reply_length       INT NOT NULL DEFAULT 0,
    ts                 TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_agent_trace_ts ON agent_trace (ts DESC);
CREATE INDEX IF NOT EXISTS idx_agent_trace_session ON agent_trace (session_id);
"""

_INSERT_SQL = """
INSERT INTO agent_trace (
    trace_uid, session_id, user_key, user_message, reply, model,
    llm_rounds, error, latency_ms, used_tools, had_error,
    tool_success_rate, reply_length, ts
) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13, now())
ON CONFLICT (trace_uid) DO NOTHING
"""

_SELECT_LIST = """
SELECT trace_uid, session_id, user_key, user_message, reply, model,
       llm_rounds, error, latency_ms, used_tools, had_error,
       tool_success_rate, reply_length, ts
FROM agent_trace ORDER BY ts DESC LIMIT $1
"""

_SELECT_ONE = _SELECT_LIST.replace(" ORDER BY ts DESC LIMIT $1", " WHERE trace_uid = $1 LIMIT 1")


def _trace_to_row(trace: AgentTrace) -> tuple:
    rounds = [
        {
            "round": r.round,
            "requested_tools": r.requested_tools,
            "tool_calls": [
                {
                    "name": tc.name,
                    "arguments": tc.arguments,
                    "result": tc.result,
                    "success": tc.success,
                    "error": tc.error,
                }
                for tc in r.tool_calls
            ],
        }
        for r in trace.llm_rounds
    ]
    return (
        trace.trace_uid,
        trace.session_id,
        trace.user_key,
        trace.user_message,
        trace.reply,
        trace.model,
        json.dumps(rounds, ensure_ascii=False),
        trace.error,
        trace.latency_ms,
        trace.used_tools,
        trace.had_error,
        trace.tool_success_rate,
        trace.reply_length,
    )


def _row_to_trace(row: asyncpg.Record) -> AgentTrace:
    rounds_raw = row["llm_rounds"]
    # asyncpg 对 jsonb 默认返回 str；统一转 dict
    if isinstance(rounds_raw, str):
        rounds_raw = json.loads(rounds_raw) if rounds_raw else []
    rounds_raw = rounds_raw or []
    rounds: list[LlmRoundRecord] = []
    for r in rounds_raw:
        round_rec = LlmRoundRecord(
            round=int(r.get("round", 0)),
            requested_tools=bool(r.get("requested_tools", False)),
        )
        for tc in r.get("tool_calls", []):
            round_rec.tool_calls.append(
                ToolCallRecord(
                    name=tc.get("name", ""),
                    arguments=tc.get("arguments", {}),
                    result=tc.get("result", {}),
                    success=bool(tc.get("success", True)),
                    error=tc.get("error", ""),
                )
            )
        rounds.append(round_rec)
    trace = AgentTrace(
        session_id=row["session_id"],
        user_key=row["user_key"],
        user_message=row["user_message"],
        reply=row["reply"],
        model=row["model"],
        llm_rounds=rounds,
        error=row["error"],
        latency_ms=row["latency_ms"],
        used_tools=row["used_tools"],
        had_error=row["had_error"],
        tool_success_rate=float(row["tool_success_rate"]),
        reply_length=row["reply_length"],
        ts=str(row["ts"]),
    )
    trace.trace_uid = row["trace_uid"]
    return trace


class PostgresTraceStore:
    def __init__(self, dsn: str, *, pool_size: int = 5) -> None:
        self._dsn = dsn
        self._pool_size = pool_size
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(
            dsn=self._dsn, min_size=1, max_size=self._pool_size
        )
        async with self._pool.acquire() as conn:
            await conn.execute(_CREATE_TABLE_SQL)

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def record(self, trace: AgentTrace) -> None:
        assert self._pool is not None
        if not getattr(trace, "trace_uid", None):
            trace.trace_uid = uuid.uuid4().hex[:16]
        async with self._pool.acquire() as conn:
            await conn.execute(_INSERT_SQL, *_trace_to_row(trace))

    async def list_recent(self, limit: int = 50) -> list[AgentTrace]:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(_SELECT_LIST, limit)
        return [_row_to_trace(r) for r in rows]

    async def get(self, trace_id: str) -> AgentTrace | None:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(_SELECT_ONE, trace_id)
        return _row_to_trace(row) if row else None
