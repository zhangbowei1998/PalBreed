"""Async ORM session factory."""

from __future__ import annotations

import os

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def _build_database_url() -> str:
    """Build DB URL from DATABASE_URL or PG* env vars."""
    url = os.getenv("DATABASE_URL")
    if url:
        if url.startswith("postgresql+asyncpg://"):
            return url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url

    host = os.getenv("PGHOST", "localhost")
    port = os.getenv("PGPORT", "5432")
    database = os.getenv("PGDATABASE", "pl_agent")
    user = os.getenv("PGUSER", "postgres")
    password = os.getenv("PGPASSWORD", "")
    auth = f"{user}:{password}" if password else user
    return f"postgresql+asyncpg://{auth}@{host}:{port}/{database}"


def create_engine_and_sessionmaker() -> (
    tuple[AsyncEngine, async_sessionmaker[AsyncSession]]
):
    """Create async engine and sessionmaker for API runtime."""
    engine = create_async_engine(_build_database_url(), pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, session_factory
