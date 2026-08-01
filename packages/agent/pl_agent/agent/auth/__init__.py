"""Auth core — user models, storage backends, password hash, token utils.

FastAPI 路由（register/login/me）在 `pl_agent.agent_web.auth.routes`。
本包只包含无 web 依赖的认证核心。
"""

from __future__ import annotations

from .models import (
    FileUserStore,
    InvalidCredentialsError,
    User,
    UserError,
    UserStore,
    UsernameTakenError,
    validate_username,
)
from .postgres import PostgresUserStore, make_user_store
from .security import create_token, hash_password, parse_token, verify_password

__all__ = [
    "FileUserStore",
    "InvalidCredentialsError",
    "PostgresUserStore",
    "User",
    "UserError",
    "UserStore",
    "UsernameTakenError",
    "create_token",
    "hash_password",
    "make_user_store",
    "parse_token",
    "validate_username",
    "verify_password",
]
