"""Password, signed token, and one-time token helpers."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def _create_jwt(user_id: str, token_type: str, expires: timedelta, token_version: int = 0) -> str:
    payload = {"sub": user_id, "type": token_type, "ver": token_version, "exp": datetime.now(timezone.utc) + expires}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def create_access_token(user_id: str, remember_me: bool = False, token_version: int = 0) -> str:
    minutes = settings.access_token_minutes
    if remember_me:
        minutes = settings.refresh_token_days * 24 * 60
    return _create_jwt(user_id, "access", timedelta(minutes=minutes), token_version)


def create_refresh_token(user_id: str, token_version: int = 0) -> str:
    return _create_jwt(user_id, "refresh", timedelta(days=settings.refresh_token_days), token_version)


def decode_token(token: str, expected_type: str = "access") -> dict[str, Any] | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        if payload.get("type") != expected_type or not payload.get("sub"):
            return None
        return payload
    except JWTError:
        return None


def verify_token(token: str, expected_type: str = "access") -> str | None:
    payload = decode_token(token, expected_type)
    return str(payload["sub"]) if payload else None


def create_one_time_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(32)
    return raw, hash_one_time_token(raw)


def hash_one_time_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
