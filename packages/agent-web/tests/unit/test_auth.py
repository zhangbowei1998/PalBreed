from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from pl_agent.agent_web.app import app
from pl_agent.agent.auth.models import FileUserStore, User, UsernameTakenError
from pl_agent.agent.auth.security import (
    create_token,
    hash_password,
    parse_token,
    verify_password,
)

# ── security 单元测试 ──


def test_password_hash_roundtrip():
    hashed = hash_password("secret123")
    assert hashed.startswith("pbkdf2_sha256$")
    assert verify_password("secret123", hashed)
    assert not verify_password("wrong", hashed)


def test_token_roundtrip_and_expiry():
    secret = "test-secret"
    token = create_token("user-1", secret, ttl_s=100)
    assert parse_token(token, secret) == "user-1"
    assert parse_token(token, "other-secret") is None


def test_token_tampered_is_rejected():
    secret = "test-secret"
    token = create_token("user-1", secret, ttl_s=100)
    tampered = token[:-2] + ("aa" if not token.endswith("aa") else "bb")
    assert parse_token(tampered, secret) is None


# ── FileUserStore 单元测试 ──


@pytest.mark.asyncio
async def test_file_user_store_create_and_get(tmp_path):
    store = FileUserStore(data_dir=tmp_path)
    user = await store.create_user("alice", hash_password("secret123"))
    assert user.id

    fetched = await store.get_user_by_username("alice")
    assert fetched is not None
    assert fetched.id == user.id

    by_id = await store.get_user_by_id(user.id)
    assert by_id is not None
    assert by_id.username == "alice"


@pytest.mark.asyncio
async def test_file_user_store_duplicate_username(tmp_path):
    store = FileUserStore(data_dir=tmp_path)
    await store.create_user("alice", hash_password("secret123"))
    with pytest.raises(UsernameTakenError):
        await store.create_user("alice", hash_password("other"))


@pytest.mark.asyncio
async def test_file_user_store_persists_across_instances(tmp_path):
    first = FileUserStore(data_dir=tmp_path)
    user = await first.create_user("bob", hash_password("secret123"))

    second = FileUserStore(data_dir=tmp_path)
    fetched = await second.get_user_by_username("bob")
    assert fetched is not None
    assert fetched.id == user.id


# ── auth API 集成测试 ──


@pytest.fixture()
def isolated_auth(tmp_path):
    """每个测试使用独立的数据目录 + 预置邀请码，避免残留。"""
    from pl_agent.agent.auth.invites import FileInviteStore

    user_store = FileUserStore(data_dir=tmp_path)
    invite_store = FileInviteStore(data_dir=tmp_path / "invites")
    import asyncio

    asyncio.run(
        invite_store.create(
            "test-admin", "2099-12-31T00:00:00+00:00", code="ITCODE123"
        )
    )
    return user_store, invite_store


def _use_stores(client, user_store, invite_store):
    client.app.state.user_store = user_store
    client.app.state.invite_store = invite_store


def test_register_login_me_flow(isolated_auth):
    user_store, invite_store = isolated_auth
    with TestClient(app) as client:
        _use_stores(client, user_store, invite_store)
        r = client.post(
            "/auth/register",
            json={
                "username": "pal_fan",
                "password": "secret123",
                "invite_code": "ITCODE123",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True  # noqa: E501
        token = body["data"]["token"]
        assert body["data"]["user"]["username"] == "pal_fan"
        # 首个用户自动成为管理员
        assert body["data"]["user"]["is_admin"] is True

        me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["data"]["user"]["username"] == "pal_fan"

        login = client.post(
            "/auth/login",
            json={"username": "pal_fan", "password": "secret123"},
        )
        assert login.status_code == 200
        assert login.json()["data"]["token"]


def test_register_duplicate_username(isolated_auth):
    user_store, invite_store = isolated_auth
    with TestClient(app) as client:
        _use_stores(client, user_store, invite_store)
        # 首次注册（首个用户=管理员）占用邀请码；再次注册需新码
        client.post(
            "/auth/register",
            json={
                "username": "dup_user",
                "password": "secret123",
                "invite_code": "ITCODE123",
            },
        )
        # 注册第二个用户需要新邀请码，这里只测用户名重复
        import asyncio

        asyncio.run(
            invite_store.create(
                "test-admin", "2099-12-31T00:00:00+00:00", code="ITCODE124"
            )
        )
        r = client.post(
            "/auth/register",
            json={
                "username": "dup_user",
                "password": "secret123",
                "invite_code": "ITCODE124",
            },
        )
        assert r.status_code == 409


def test_register_invalid_invite_code(isolated_auth):
    user_store, invite_store = isolated_auth
    with TestClient(app) as client:
        _use_stores(client, user_store, invite_store)
        r = client.post(
            "/auth/register",
            json={
                "username": "no_invite",
                "password": "secret123",
                "invite_code": "WRONGCODE",
            },
        )
        assert r.status_code == 403


def test_register_reused_invite_code(isolated_auth):
    user_store, invite_store = isolated_auth
    with TestClient(app) as client:
        _use_stores(client, user_store, invite_store)
        r1 = client.post(
            "/auth/register",
            json={
                "username": "first_user",
                "password": "secret123",
                "invite_code": "ITCODE123",
            },
        )
        assert r1.status_code == 200
        # 同一邀请码不能二次使用
        r2 = client.post(
            "/auth/register",
            json={
                "username": "second_user",
                "password": "secret123",
                "invite_code": "ITCODE123",
            },
        )
        assert r2.status_code == 403


def test_login_wrong_password(isolated_auth):
    user_store, invite_store = isolated_auth
    with TestClient(app) as client:
        _use_stores(client, user_store, invite_store)
        client.post(
            "/auth/register",
            json={
                "username": "wrong_pw",
                "password": "secret123",
                "invite_code": "ITCODE123",
            },
        )
        r = client.post(
            "/auth/login",
            json={"username": "wrong_pw", "password": "bad-password"},
        )
        assert r.status_code == 401


def test_me_without_token(isolated_auth):
    user_store, invite_store = isolated_auth
    with TestClient(app) as client:
        _use_stores(client, user_store, invite_store)
        r = client.get("/auth/me")
        assert r.status_code == 401


def test_register_invalid_username(isolated_auth):
    user_store, invite_store = isolated_auth
    with TestClient(app) as client:
        _use_stores(client, user_store, invite_store)
        r = client.post(
            "/auth/register",
            json={
                "username": "x",
                "password": "secret123",
                "invite_code": "ITCODE123",
            },
        )
        assert r.status_code == 422


def test_admin_invite_flow(isolated_auth):
    """管理员生成邀请码 → 新用户用它注册。"""
    user_store, invite_store = isolated_auth
    with TestClient(app) as client:
        _use_stores(client, user_store, invite_store)
        # 首个用户注册 → 自动成为管理员
        r1 = client.post(
            "/auth/register",
            json={
                "username": "admin_user",
                "password": "secret123",
                "invite_code": "ITCODE123",
            },
        )
        assert r1.status_code == 200
        admin_token = r1.json()["data"]["token"]

        # 管理员生成新邀请码
        r2 = client.post(
            "/auth/admin/invite",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"ttl_s": 3600},
        )
        assert r2.status_code == 200
        new_code = r2.json()["data"]["code"]

        # 新用户用管理员生成的邀请码注册
        r3 = client.post(
            "/auth/register",
            json={
                "username": "new_member",
                "password": "secret123",
                "invite_code": new_code,
            },
        )
        assert r3.status_code == 200
        # 第二个用户不是管理员
        assert r3.json()["data"]["user"]["is_admin"] is False


def test_admin_invite_requires_admin(isolated_auth):
    """非管理员不能生成邀请码。"""
    user_store, invite_store = isolated_auth
    with TestClient(app) as client:
        _use_stores(client, user_store, invite_store)
        # 首个用户=管理员，再注册一个非管理员
        client.post(
            "/auth/register",
            json={
                "username": "admin1",
                "password": "secret123",
                "invite_code": "ITCODE123",
            },
        )
        import asyncio

        asyncio.run(
            invite_store.create(
                "test-admin", "2099-12-31T00:00:00+00:00", code="ITCODE125"
            )
        )
        r1 = client.post(
            "/auth/register",
            json={
                "username": "member1",
                "password": "secret123",
                "invite_code": "ITCODE125",
            },
        )
        assert r1.status_code == 200
        member_token = r1.json()["data"]["token"]

        r2 = client.post(
            "/auth/admin/invite",
            headers={"Authorization": f"Bearer {member_token}"},
            json={},
        )
        assert r2.status_code == 403


def test_admin_username_config_grants_admin(isolated_auth):
    """ADMIN_USERNAME 配置可引导已有用户为管理员（不落库）。"""
    user_store, invite_store = isolated_auth
    with TestClient(app) as client:
        _use_stores(client, user_store, invite_store)
        # 首个用户注册成管理员，用于生成新邀请码给"boss"
        client.post(
            "/auth/register",
            json={
                "username": "admin1",
                "password": "secret123",
                "invite_code": "ITCODE123",
            },
        )
        import asyncio

        asyncio.run(
            invite_store.create(
                "test-admin", "2099-12-31T00:00:00+00:00", code="ITCODE126"
            )
        )
        # 注册第二个用户 boss（非管理员）
        r = client.post(
            "/auth/register",
            json={
                "username": "boss",
                "password": "secret123",
                "invite_code": "ITCODE126",
            },
        )
        assert r.status_code == 200
        # 模拟 ADMIN_USERNAME=boss 配置（Settings 为 frozen dataclass）
        object.__setattr__(client.app.state.settings, "admin_username", "boss")
        r2 = client.post(
            "/auth/login",
            json={"username": "boss", "password": "secret123"},
        )
        assert r2.status_code == 200
        assert r2.json()["data"]["user"]["is_admin"] is True
        # boss 现在可生成邀请码
        r3 = client.post(
            "/auth/admin/invite",
            headers={"Authorization": f"Bearer {r2.json()['data']['token']}"},
            json={},
        )
        assert r3.status_code == 200
