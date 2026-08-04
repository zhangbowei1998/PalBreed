"""Invite code models and store protocol for the agent service.

邀请码体系：注册需提供邀请码（有时效、一次性使用）。
- 只有管理员（is_admin=true 的用户）能生成邀请码。
- 每个邀请码在有效期内只能注册一个用户。

存储支持文件（开发/测试）与 PostgreSQL（生产），通过配置切换。
"""

from __future__ import annotations

import json
import secrets
import string
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

_ALPHABET = string.ascii_uppercase + string.digits  # 不含易混淆字符(0/O,1/I)


class InviteError(Exception):
    """Base invite error."""


class InviteNotFoundError(InviteError):
    pass


class InviteExpiredError(InviteError):
    pass


class InviteAlreadyUsedError(InviteError):
    pass


class InviteInvalidError(InviteError):
    pass


@dataclass
class InviteCode:
    code: str
    created_by: str  # 生成者 user_id
    expires_at: str  # ISO 时间
    used_by: str | None = None  # 使用者 user_id
    used_at: str | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def is_used(self) -> bool:
        return self.used_by is not None

    @property
    def is_expired(self) -> bool:
        try:
            expires = datetime.fromisoformat(self.expires_at)
            now = datetime.now(timezone.utc)
            # 兼容无时区标记的存储值
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            return now >= expires
        except ValueError:
            return True

    def to_public_dict(self) -> dict:
        return {
            "code": self.code,
            "created_by": self.created_by,
            "expires_at": self.expires_at,
            "used": self.is_used,
            "used_by": self.used_by,
            "used_at": self.used_at,
            "created_at": self.created_at,
        }


def generate_invite_code(length: int = 12) -> str:
    """生成随机邀请码（默认 12 位大写字母+数字）。"""
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


def normalize_code(code: str) -> str:
    """规范化：去空白 + 转大写 + 去连接符。"""
    return code.strip().replace("-", "").upper()


def _to_iso(value) -> str:
    """datetime → ISO 字符串；已是字符串则原样返回。"""
    if isinstance(value, str):
        return value
    return value.isoformat()


def _parse_dt(value: str):
    """ISO 字符串 → aware datetime（缺失时区按 UTC）。"""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class InviteStore(Protocol):
    async def create(
        self, created_by: str, expires_at, code: str | None = None
    ) -> InviteCode: ...

    async def get_by_code(self, code: str) -> InviteCode | None: ...

    async def mark_used(
        self, code: str, used_by: str
    ) -> InviteCode: ...

    async def list_by_creator(self, created_by: str) -> list[InviteCode]: ...


class FileInviteStore:
    """JSON-file backed invite store (dev / tests)."""

    def __init__(self, data_dir: Path | str | None = None) -> None:
        if data_dir is None:
            # 包根 data 目录（packages/agent/data）
            data_dir = Path(__file__).resolve().parents[3] / "data"
        self._path = Path(data_dir) / "invites.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, dict] = self._load_file()

    def _load_file(self) -> dict[str, dict]:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_file(self) -> None:
        self._path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _from_dict(self, code: str, raw: dict) -> InviteCode:
        return InviteCode(
            code=code,
            created_by=raw.get("created_by", ""),
            expires_at=raw.get("expires_at", ""),
            used_by=raw.get("used_by"),
            used_at=raw.get("used_at"),
            created_at=raw.get("created_at", ""),
        )

    async def create(
        self, created_by: str, expires_at, code: str | None = None
    ) -> InviteCode:
        final_code = code or generate_invite_code()
        # 避免碰撞：若已存在同码，重新生成
        while final_code in self._data:
            final_code = generate_invite_code()
        # 兼容 datetime 与 ISO 字符串
        exp = _to_iso(expires_at)
        invite = InviteCode(
            code=final_code, created_by=created_by, expires_at=exp
        )
        self._data[final_code] = {
            "created_by": invite.created_by,
            "expires_at": invite.expires_at,
            "used_by": invite.used_by,
            "used_at": invite.used_at,
            "created_at": invite.created_at,
        }
        self._save_file()
        return invite

    async def get_by_code(self, code: str) -> InviteCode | None:
        raw = self._data.get(code)
        if raw is None:
            return None
        return self._from_dict(code, raw)

    async def mark_used(self, code: str, used_by: str) -> InviteCode:
        raw = self._data.get(code)
        if raw is None:
            raise InviteNotFoundError(f"邀请码不存在: {code}")
        raw["used_by"] = used_by
        raw["used_at"] = datetime.now(timezone.utc).isoformat()
        self._data[code] = raw
        self._save_file()
        return self._from_dict(code, raw)

    async def list_by_creator(self, created_by: str) -> list[InviteCode]:
        return [
            self._from_dict(code, raw)
            for code, raw in self._data.items()
            if raw.get("created_by") == created_by
        ]


class PostgresInviteStore:
    """PostgreSQL-backed invite store."""

    def __init__(self, dsn: str, *, pool_size: int = 5) -> None:
        self._dsn = dsn
        self._pool_size = pool_size
        self._pool = None

    async def connect(self) -> None:
        import asyncpg

        self._pool = await asyncpg.create_pool(
            dsn=self._dsn, min_size=1, max_size=self._pool_size
        )
        async with self._pool.acquire() as conn:
            await conn.execute(_CREATE_TABLE_SQL)

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    def _from_row(self, row) -> InviteCode:
        return InviteCode(
            code=row["code"],
            created_by=row["created_by"],
            expires_at=str(row["expires_at"]),
            used_by=row.get("used_by"),
            used_at=str(row["used_at"]) if row.get("used_at") else None,
            created_at=str(row["created_at"]),
        )

    async def create(
        self, created_by: str, expires_at, code: str | None = None
    ) -> InviteCode:
        import asyncpg

        assert self._pool is not None
        # 统一为 datetime 对象（asyncpg 参数化 timestamptz 需要 datetime）
        if isinstance(expires_at, str):
            expires_at = _parse_dt(expires_at)
        async with self._pool.acquire() as conn:
            for _ in range(5):  # 碰撞重试
                final_code = code or generate_invite_code()
                try:
                    row = await conn.fetchrow(
                        """
                        INSERT INTO agent_invite_codes
                            (code, created_by, expires_at)
                        VALUES ($1, $2, $3)
                        RETURNING code, created_by, expires_at, used_by, used_at,
                                  created_at
                        """,
                        final_code,
                        created_by,
                        expires_at,
                    )
                    return self._from_row(row)
                except asyncpg.UniqueViolationError:
                    if code is not None:
                        raise InviteInvalidError(f"邀请码已存在: {code}")
                    continue  # 自动生成碰撞 → 重试
        raise InviteError("生成邀请码失败")

    async def get_by_code(self, code: str) -> InviteCode | None:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT code, created_by, expires_at, used_by, used_at, created_at
                FROM agent_invite_codes WHERE code = $1
                """,
                code,
            )
        if row is None:
            return None
        return self._from_row(row)

    async def mark_used(self, code: str, used_by: str) -> InviteCode:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE agent_invite_codes
                SET used_by = $2, used_at = now()
                WHERE code = $1 AND used_by IS NULL
                RETURNING code, created_by, expires_at, used_by, used_at, created_at
                """,
                code,
                used_by,
            )
        if row is None:
            # 可能不存在或已被使用
            existing = await self.get_by_code(code)
            if existing is None:
                raise InviteNotFoundError(f"邀请码不存在: {code}")
            raise InviteAlreadyUsedError(f"邀请码已被使用: {code}")
        return self._from_row(row)

    async def list_by_creator(self, created_by: str) -> list[InviteCode]:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT code, created_by, expires_at, used_by, used_at, created_at
                FROM agent_invite_codes WHERE created_by = $1
                ORDER BY created_at DESC
                """,
                created_by,
            )
        return [self._from_row(r) for r in rows]


_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS agent_invite_codes (
    id         BIGSERIAL PRIMARY KEY,
    code       TEXT NOT NULL UNIQUE,
    created_by TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used_by    TEXT,
    used_at    TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_invite_created_by ON agent_invite_codes(created_by);
"""


def make_invite_store(store: str, dsn: str) -> FileInviteStore | PostgresInviteStore:
    """按配置创建邀请码存储。"""
    if store == "postgres":
        return PostgresInviteStore(dsn)
    return FileInviteStore()
