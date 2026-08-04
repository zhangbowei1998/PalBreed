"""PostgreSQL-backed user store.

表结构：agent_users(id BIGSERIAL PRIMARY KEY, user_id text UNIQUE, username text UNIQUE,
                   password_hash text, is_admin boolean default false,
                   created_at timestamptz)
"""

from __future__ import annotations

import asyncpg

from .models import FileUserStore, User, UsernameTakenError, new_user_id

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS agent_users (
    id            BIGSERIAL PRIMARY KEY,
    user_id       TEXT NOT NULL UNIQUE,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    is_admin      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


class PostgresUserStore:
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
            # 兼容旧表：无 is_admin 列时补列
            await conn.execute(
                "ALTER TABLE agent_users ADD COLUMN IF NOT EXISTS is_admin "
                "BOOLEAN NOT NULL DEFAULT FALSE"
            )

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def create_user(
        self, username: str, password_hash: str, is_admin: bool = False
    ) -> User:
        assert self._pool is not None
        user_id = new_user_id()
        sql = """
            INSERT INTO agent_users (user_id, username, password_hash, is_admin)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (username) DO NOTHING
            RETURNING user_id, username, password_hash, is_admin, created_at
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                sql, user_id, username, password_hash, is_admin
            )
        if row is None:
            raise UsernameTakenError(f"用户名 {username} 已被占用")
        return User(
            id=row["user_id"],
            username=row["username"],
            password_hash=row["password_hash"],
            is_admin=bool(row["is_admin"]),
            created_at=str(row["created_at"]),
        )

    async def count_users(self) -> int:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT count(*) AS n FROM agent_users")
        return int(row["n"]) if row else 0

    async def get_user_by_username(self, username: str) -> User | None:
        assert self._pool is not None
        sql = """
            SELECT user_id, username, password_hash, is_admin, created_at
            FROM agent_users WHERE username = $1
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(sql, username)
        if row is None:
            return None
        return User(
            id=row["user_id"],
            username=row["username"],
            password_hash=row["password_hash"],
            is_admin=bool(row["is_admin"]),
            created_at=str(row["created_at"]),
        )

    async def get_user_by_id(self, user_id: str) -> User | None:
        assert self._pool is not None
        sql = """
            SELECT user_id, username, password_hash, is_admin, created_at
            FROM agent_users WHERE user_id = $1
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(sql, user_id)
        if row is None:
            return None
        return User(
            id=row["user_id"],
            username=row["username"],
            password_hash=row["password_hash"],
            is_admin=bool(row["is_admin"]),
            created_at=str(row["created_at"]),
        )


def make_user_store(store: str, dsn: str) -> FileUserStore | PostgresUserStore:
    """按配置创建用户存储；返回类型便于 lifespan 调用 connect/close."""
    if store == "postgres":
        return PostgresUserStore(dsn)
    return FileUserStore()
