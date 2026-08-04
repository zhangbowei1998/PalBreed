"""Auth API — register / login / me / admin invite.

注册登录后端先行，前端登录注册页面后续再补。
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from pl_agent.agent.auth.invites import (
    InviteError,
    InviteStore,
    normalize_code,
)
from pl_agent.agent.auth.models import (
    UserError,
    UserStore,
    UsernameTakenError,
    validate_username,
)
from pl_agent.agent.auth.security import (
    create_token,
    hash_password,
    parse_token,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=32)
    password: str = Field(min_length=6, max_length=128)
    invite_code: str = Field(min_length=4, max_length=32)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    token: str
    user: dict


class InviteCreateRequest(BaseModel):
    ttl_s: int | None = Field(default=None, ge=60, le=30 * 24 * 3600)


class InviteCreateResponse(BaseModel):
    code: str
    expires_at: str


def _get_user_store(request: Request) -> UserStore:
    return request.app.state.user_store


def _get_invite_store(request: Request) -> InviteStore:
    return request.app.state.invite_store


def _token_ttl(request: Request) -> int:
    return getattr(request.app.state.settings, "auth_token_ttl_s", 7 * 24 * 3600)


def _secret(request: Request) -> str:
    secret = getattr(request.app.state.settings, "auth_secret", "")
    if not secret:
        raise HTTPException(status_code=500, detail="auth secret not configured")
    return secret


def _current_user(request: Request) -> object | None:
    """从 Bearer token 解析当前用户；无效返回 None。"""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        return None
    token = auth_header.split(" ", 1)[1].strip()
    user_id = parse_token(token, _secret(request))
    if not user_id:
        return None
    return user_id


@router.post("/register")
async def register(body: RegisterRequest, request: Request) -> dict:
    username = body.username.strip()
    code = normalize_code(body.invite_code)
    try:
        validate_username(username)
    except UserError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    store = _get_user_store(request)
    invite_store = _get_invite_store(request)

    # 校验邀请码：存在 / 未过期 / 未使用
    invite = await invite_store.get_by_code(code)
    if invite is None:
        raise HTTPException(status_code=403, detail="邀请码无效")
    if invite.is_expired:
        raise HTTPException(status_code=403, detail="邀请码已过期")
    if invite.is_used:
        raise HTTPException(status_code=403, detail="邀请码已被使用")

    # 首个用户自动成为管理员（其后注册都需要有效邀请码）
    is_admin = (await store.count_users()) == 0

    try:
        user = await store.create_user(
            username, hash_password(body.password), is_admin=is_admin
        )
    except UsernameTakenError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except UserError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # 标记邀请码已使用（注册成功后才占用）
    try:
        await invite_store.mark_used(code, user.id)
    except InviteError as exc:
        # 理论上不会发生（前面已校验未使用）；若并发竞争，回滚用户
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    token = create_token(user.id, _secret(request), _token_ttl(request))
    return {
        "success": True,
        "data": TokenResponse(token=token, user=user.to_public_dict()).model_dump(),
    }


@router.post("/admin/invite")
async def create_invite(
    body: InviteCreateRequest | None, request: Request
) -> dict:
    """管理员生成邀请码（仅管理员可调用）。"""
    user_id = _current_user(request)
    if user_id is None:
        raise HTTPException(status_code=401, detail="请先登录")
    store = _get_user_store(request)
    user = await store.get_user_by_id(user_id)
    if user is None or not _is_admin_user(request, user):
        raise HTTPException(status_code=403, detail="仅管理员可生成邀请码")

    invite_store = _get_invite_store(request)
    ttl_s = body.ttl_s if body is not None and body.ttl_s else _invite_ttl(request)
    from datetime import timedelta

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_s)

    invite = await invite_store.create(user_id, expires_at)
    return {
        "success": True,
        "data": InviteCreateResponse(
            code=invite.code, expires_at=invite.expires_at
        ).model_dump(),
    }


@router.get("/admin/invites")
async def list_invites(request: Request) -> dict:
    """管理员查看自己生成的邀请码列表。"""
    user_id = _current_user(request)
    if user_id is None:
        raise HTTPException(status_code=401, detail="请先登录")
    store = _get_user_store(request)
    user = await store.get_user_by_id(user_id)
    if user is None or not _is_admin_user(request, user):
        raise HTTPException(status_code=403, detail="仅管理员可查看邀请码")

    invite_store = _get_invite_store(request)
    invites = await invite_store.list_by_creator(user_id)
    return {
        "success": True,
        "data": {
            "invites": [i.to_public_dict() for i in invites],
            "total": len(invites),
        },
    }


def _invite_ttl(request: Request) -> int:
    return getattr(
        request.app.state.settings, "invite_ttl_s", 7 * 24 * 3600
    )


def _is_admin_user(request: Request, user) -> bool:
    """判断用户是否为管理员。

    两种途径：
    1. 用户 DB 的 is_admin=true（首个注册用户自动获得，或已手动提升）
    2. 用户名命中 ADMIN_USERNAME 配置（线上已有用户的引导方式）
    """
    if user is None:
        return False
    if user.is_admin:
        return True
    admin_name = getattr(request.app.state.settings, "admin_username", "") or ""
    return admin_name and user.username == admin_name


@router.post("/login")
async def login(body: LoginRequest, request: Request) -> dict:
    store = _get_user_store(request)
    user = await store.get_user_by_username(body.username.strip())
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    # 登录响应中按 ADMIN_USERNAME 配置动态标记管理员（不落库，仅本次会话判断）
    public = user.to_public_dict()
    if _is_admin_user(request, user):
        public["is_admin"] = True
    token = create_token(user.id, _secret(request), _token_ttl(request))
    return {
        "success": True,
        "data": TokenResponse(token=token, user=public).model_dump(),
    }


@router.get("/me")
async def me(request: Request) -> dict:
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="缺少 token")
    token = auth_header.split(" ", 1)[1].strip()
    user_id = parse_token(token, _secret(request))
    if not user_id:
        raise HTTPException(status_code=401, detail="token 无效或已过期")
    user = await _get_user_store(request).get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    public = user.to_public_dict()
    if _is_admin_user(request, user):
        public["is_admin"] = True
    return {"success": True, "data": {"user": public}}


def resolve_user_id_from_request(request: Request) -> str | None:
    """从请求头解析当前用户 id；无有效 token 时返回 None（视为匿名用户）。"""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        return None
    token = auth_header.split(" ", 1)[1].strip()
    user_id = parse_token(token, _secret(request))
    if not user_id:
        return None
    return user_id
