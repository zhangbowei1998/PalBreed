"""Auth API — register / login / me.

注册登录后端先行，前端登录注册页面后续再补。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

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


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    token: str
    user: dict


def _get_user_store(request: Request) -> UserStore:
    return request.app.state.user_store


def _token_ttl(request: Request) -> int:
    return getattr(request.app.state.settings, "auth_token_ttl_s", 7 * 24 * 3600)


def _secret(request: Request) -> str:
    secret = getattr(request.app.state.settings, "auth_secret", "")
    if not secret:
        raise HTTPException(status_code=500, detail="auth secret not configured")
    return secret


@router.post("/register")
async def register(body: RegisterRequest, request: Request) -> dict:
    username = body.username.strip()
    try:
        validate_username(username)
    except UserError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    store = _get_user_store(request)
    try:
        user = await store.create_user(username, hash_password(body.password))
    except UsernameTakenError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except UserError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    token = create_token(user.id, _secret(request), _token_ttl(request))
    return {
        "success": True,
        "data": TokenResponse(token=token, user=user.to_public_dict()).model_dump(),
    }


@router.post("/login")
async def login(body: LoginRequest, request: Request) -> dict:
    store = _get_user_store(request)
    user = await store.get_user_by_username(body.username.strip())
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_token(user.id, _secret(request), _token_ttl(request))
    return {
        "success": True,
        "data": TokenResponse(token=token, user=user.to_public_dict()).model_dump(),
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
    return {"success": True, "data": {"user": user.to_public_dict()}}


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
