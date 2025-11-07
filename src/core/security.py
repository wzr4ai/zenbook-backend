"""Security helpers for JWT handling."""

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from .config import settings


class TokenDecodeError(Exception):
    """Raised when a JWT cannot be decoded or is invalid."""


def create_access_token(subject: str, role: str, expires_minutes: int | None = None) -> str:
    """Create a signed JWT."""
    expire_in = expires_minutes or settings.jwt_expires_in_minutes
    to_encode: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "exp": datetime.now(tz=timezone.utc) + timedelta(minutes=expire_in),
    }
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT, raising TokenDecodeError on failure."""
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:  # pragma: no cover - jose already well tested
        raise TokenDecodeError("Invalid token") from exc
