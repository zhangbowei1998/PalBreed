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
def isolated_user_store(tmp_path):
    """每个测试使用独立的数据目录，避免 users.json 残留。"""
    return FileUserStore(data_dir=tmp_path)


def _use_store(client, store):
    client.app.state.user_store = store


def test_register_login_me_flow(isolated_user_store):
    with TestClient(app) as client:
        _use_store(client, isolated_user_store)
        r = client.post(
            "/auth/register",
            json={"username": "pal_fan", "password": "secret123"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True  # noqa: E501
        token = body["data"]["token"]
        assert body["data"]["user"]["username"] == "pal_fan"

        me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["data"]["user"]["username"] == "pal_fan"

        login = client.post(
            "/auth/login",
            json={"username": "pal_fan", "password": "secret123"},
        )
        assert login.status_code == 200
        assert login.json()["data"]["token"]


def test_register_duplicate_username(isolated_user_store):
    with TestClient(app) as client:
        _use_store(client, isolated_user_store)
        client.post(
            "/auth/register",
            json={"username": "dup_user", "password": "secret123"},
        )
        r = client.post(
            "/auth/register",
            json={"username": "dup_user", "password": "secret123"},
        )
        assert r.status_code == 409


def test_login_wrong_password(isolated_user_store):
    with TestClient(app) as client:
        _use_store(client, isolated_user_store)
        client.post(
            "/auth/register",
            json={"username": "wrong_pw", "password": "secret123"},
        )
        r = client.post(
            "/auth/login",
            json={"username": "wrong_pw", "password": "bad-password"},
        )
        assert r.status_code == 401


def test_me_without_token(isolated_user_store):
    with TestClient(app) as client:
        _use_store(client, isolated_user_store)
        r = client.get("/auth/me")
        assert r.status_code == 401


def test_register_invalid_username(isolated_user_store):
    with TestClient(app) as client:
        _use_store(client, isolated_user_store)
        r = client.post(
            "/auth/register",
            json={"username": "x", "password": "secret123"},
        )
        assert r.status_code == 422
