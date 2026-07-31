"""PostgreSQL adapter — configuration and connection management."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class PostgresConfig:
    """PostgreSQL 连接配置.

    通过环境变量 DATABASE_URL 或独立字段配置.
    默认连接本地 pl_agent 数据库.
    """

    host: str = "localhost"
    port: int = 5432
    database: str = "pl_agent"
    user: str = "postgres"
    password: str = ""

    @classmethod
    def from_env(cls) -> "PostgresConfig":
        """从环境变量加载配置."""
        url = os.getenv("DATABASE_URL", "")
        if url:
            return cls.from_url(url)

        return cls(
            host=os.getenv("PGHOST", "localhost"),
            port=int(os.getenv("PGPORT", "5432")),
            database=os.getenv("PGDATABASE", "pl_agent"),
            user=os.getenv("PGUSER", "postgres"),
            password=os.getenv("PGPASSWORD", ""),
        )

    @classmethod
    def from_url(cls, url: str) -> "PostgresConfig":
        """从 postgres://user:pass@host:port/db 解析."""
        # postgresql://user:pass@host:port/db
        rest = url.replace("postgresql://", "").replace("postgres://", "")
        auth, _, rest = rest.partition("@")
        host_port, _, db = rest.partition("/")

        user, _, password = auth.partition(":")
        host, _, port_str = host_port.partition(":")
        port = int(port_str) if port_str else 5432

        return cls(host=host, port=port, database=db, user=user, password=password)

    @property
    def dsn(self) -> str:
        """生成 asyncpg 兼容的 DSN."""
        return (
            f"postgresql://{self.user}"
            + (f":{self.password}" if self.password else "")
            + f"@{self.host}:{self.port}/{self.database}"
        )
