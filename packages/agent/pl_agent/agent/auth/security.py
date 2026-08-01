"""Password hashing and signed token utilities.

- 密码：PBKDF2-HMAC-SHA256（标准库，无第三方依赖），存储为
  ``pbkdf2_sha256$iterations$salt$hash``。
- token：HMAC-SHA256 签名的 ``user_id:expiry``，避免引入 JWT 依赖。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time

_ITERATIONS = 120_000
_SALT_BYTES = 16
_ALGO = "pbkdf2_sha256"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return "{0}${1}${2}${3}".format(
        _ALGO,
        _ITERATIONS,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations_str, salt_b64, hash_b64 = stored.split("$")
        if algo != _ALGO:
            return False
        iterations = int(iterations_str)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
    except (ValueError, TypeError):
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(digest, expected)


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_token(user_id: str, secret: str, ttl_s: int = 7 * 24 * 3600) -> str:
    """签发 HMAC 签名 token：payload = base64(user_id:expiry)。"""
    expires = int(time.time()) + ttl_s
    payload_raw = f"{user_id}:{expires}".encode("utf-8")
    payload = _b64encode(payload_raw)
    signature = hmac.new(
        secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256
    ).hexdigest()
    return f"{payload}.{signature}"


def parse_token(token: str, secret: str) -> str | None:
    """校验并解析 token，返回 user_id；无效或过期返回 None。"""
    try:
        payload, signature = token.split(".", 1)
    except ValueError:
        return None
    expected = hmac.new(
        secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        payload_raw = _b64decode(payload).decode("utf-8")
        user_id, expires_str = payload_raw.rsplit(":", 1)
        expires = int(expires_str)
    except (ValueError, UnicodeDecodeError):
        return None
    if time.time() > expires:
        return None
    return user_id
