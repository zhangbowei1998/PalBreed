"""User models and store protocol for the agent service.

用户体系最小实现：username + password 注册/登录，签发 HMAC 签名 token。
存储支持文件（开发/测试）与 PostgreSQL（生产），通过配置切换。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_\u4e00-\u9fff-]{2,32}$")


class UserError(Exception):
    """Base user error."""


class UsernameTakenError(UserError):
    pass


class InvalidCredentialsError(UserError):
    pass


@dataclass
class User:
    id: str
    username: str
    password_hash: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_public_dict(self) -> dict:
        return {"id": self.id, "username": self.username, "created_at": self.created_at}


def validate_username(username: str) -> None:
    if not _USERNAME_RE.match(username):
        raise UserError("用户名需为 2-32 位字母、数字、下划线或中文（可含中划线）")


def new_user_id() -> str:
    import uuid

    return uuid.uuid4().hex[:16]


class UserStore(Protocol):
    async def create_user(self, username: str, password_hash: str) -> User: ...

    async def get_user_by_username(self, username: str) -> User | None: ...

    async def get_user_by_id(self, user_id: str) -> User | None: ...


class FileUserStore:
    """JSON-file backed user store (dev / tests)."""

    def __init__(self, data_dir: Path | str | None = None) -> None:
        if data_dir is None:
            # 包根 data 目录（packages/agent/data）
            data_dir = Path(__file__).resolve().parents[3] / "data"
        self._path = Path(data_dir) / "users.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, dict] = self._load_file()
        self._by_username: dict[str, str] = {
            u["username"]: uid for uid, u in self._data.items()
        }

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

    async def create_user(self, username: str, password_hash: str) -> User:
        if username in self._by_username:
            raise UsernameTakenError(f"用户名 {username} 已被占用")
        user = User(id=new_user_id(), username=username, password_hash=password_hash)
        self._data[user.id] = {
            "id": user.id,
            "username": user.username,
            "password_hash": user.password_hash,
            "created_at": user.created_at,
        }
        self._by_username[user.username] = user.id
        self._save_file()
        return user

    async def get_user_by_username(self, username: str) -> User | None:
        user_id = self._by_username.get(username)
        if not user_id:
            return None
        return await self.get_user_by_id(user_id)

    async def get_user_by_id(self, user_id: str) -> User | None:
        raw = self._data.get(user_id)
        if not raw:
            return None
        return User(
            id=raw["id"],
            username=raw["username"],
            password_hash=raw.get("password_hash", ""),
            created_at=raw.get("created_at", ""),
        )
