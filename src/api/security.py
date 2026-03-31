import base64
import binascii
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.database import get_db
from src.db.models import User

AUTH_TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7
AUTH_SECRET_KEY = os.getenv("AUTH_SECRET_KEY", "deep-research-dev-secret")


def serialize_user(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
    }


def normalize_identifier(value: str) -> str:
    return value.strip().lower()


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt_bytes = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt_bytes,
        200_000,
    )
    return f"{salt_bytes.hex()}:{digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        salt_hex, digest_hex = password_hash.split(":", 1)
        calculated = hash_password(password, bytes.fromhex(salt_hex))
        return hmac.compare_digest(calculated, f"{salt_hex}:{digest_hex}")
    except (ValueError, binascii.Error):
        return False


def encode_token(payload: dict[str, Any]) -> str:
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    token_body = base64.urlsafe_b64encode(payload_bytes).decode("utf-8").rstrip("=")
    signature = hmac.new(
        AUTH_SECRET_KEY.encode("utf-8"),
        token_body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{token_body}.{signature}"


def decode_token(token: str) -> dict[str, Any]:
    try:
        token_body, signature = token.split(".", 1)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid authentication token") from exc

    expected_signature = hmac.new(
        AUTH_SECRET_KEY.encode("utf-8"),
        token_body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_signature):
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    padding = "=" * (-len(token_body) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(token_body + padding))
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=401, detail="Invalid authentication token") from exc

    if payload.get("exp", 0) < int(time.time()):
        raise HTTPException(status_code=401, detail="Authentication token has expired")

    return payload


def create_auth_response(user: User) -> dict[str, Any]:
    token = encode_token(
        {
            "sub": user.id,
            "username": user.username,
            "exp": int(time.time()) + AUTH_TOKEN_TTL_SECONDS,
        }
    )
    return {
        "token": token,
        "user": serialize_user(user),
    }


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")

    payload = decode_token(authorization.removeprefix("Bearer ").strip())
    user_id = payload.get("sub")
    if not isinstance(user_id, int):
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    return user
