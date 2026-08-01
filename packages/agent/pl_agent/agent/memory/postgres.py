"""PostgreSQL-backed long-term memory.

复用项目现有的 PostgreSQL（asyncpg）。存储用户持久事实（已拥有帕鲁/偏好），
支持按用户查询、去重、重置。表结构：
    agent_long_term_memory(user_key text, category text, content text, ts timestamptz)
"""

from __future__ import annotations

import asyncpg

from .long_term import LongTermMemoryStore, MemoryFact

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS agent_long_term_memory (
    id       BIGSERIAL PRIMARY KEY,
    user_key TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'general',
    content  TEXT NOT NULL,
    ts       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_agent_ltm_user ON agent_long_term_memory(user_key);
"""

_SELECT_SQL = """
SELECT category, content, ts
FROM agent_long_term_memory
WHERE user_key = $1
ORDER BY id ASC
"""

_INSERT_SQL = """
INSERT INTO agent_long_term_memory (user_key, category, content)
SELECT $1, $2, $3
WHERE NOT EXISTS (
    SELECT 1 FROM agent_long_term_memory
    WHERE user_key = $1 AND category = $2 AND content = $3
)
"""

_DELETE_SQL = "DELETE FROM agent_long_term_memory WHERE user_key = $1"


class PostgresLongTermMemory(LongTermMemoryStore):
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

    async def load(self, user_key: str) -> list[MemoryFact]:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(_SELECT_SQL, user_key)
        return [
            MemoryFact(
                category=row["category"], content=row["content"], ts=str(row["ts"])
            )
            for row in rows
        ]

    async def add(self, user_key: str, fact: MemoryFact) -> None:
        if not fact.content.strip():
            return
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            await conn.execute(_INSERT_SQL, user_key, fact.category, fact.content)

    async def reset(self, user_key: str) -> None:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            await conn.execute(_DELETE_SQL, user_key)
