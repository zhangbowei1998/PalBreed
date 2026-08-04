"""Auth core — user models, storage backends, password hash, token utils.

FastAPI 路由（register/login/me/admin）在 `pl_agent.agent_web.auth.routes`。
本包只包含无 web 依赖的认证核心。
"""

from __future__ import annotations

from .invites import (
    FileInviteStore,
    InviteAlreadyUsedError,
    InviteCode,
    InviteError,
    InviteExpiredError,
    InviteInvalidError,
    InviteNotFoundError,
    InviteStore,
    PostgresInviteStore,
    generate_invite_code,
    make_invite_store,
    normalize_code,
)
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
    "FileInviteStore",
    "FileUserStore",
    "InvalidCredentialsError",
    "InviteAlreadyUsedError",
    "InviteCode",
    "InviteError",
    "InviteExpiredError",
    "InviteInvalidError",
    "InviteNotFoundError",
    "InviteStore",
    "PostgresInviteStore",
    "PostgresUserStore",
    "User",
    "UserError",
    "UserStore",
    "UsernameTakenError",
    "create_token",
    "generate_invite_code",
    "hash_password",
    "make_invite_store",
    "make_user_store",
    "normalize_code",
    "parse_token",
    "validate_username",
    "verify_password",
]
