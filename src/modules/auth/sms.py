"""Simple SMS code helper for phone authentication."""

from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Dict, Tuple

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

CODE_TTL = timedelta(minutes=5)
CODE_LENGTH = 6

_codes: Dict[str, Tuple[str, datetime]] = {}


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _cleanup_expired(phone: str) -> None:
    entry = _codes.get(phone)
    if entry is None:
        return
    _, expires_at = entry
    if _now() > expires_at:
        _codes.pop(phone, None)


def request_sms_code(phone: str) -> str:
    """Generate and store a verification code that expires after CODE_TTL."""
    code = ''.join(str(random.randint(0, 9)) for _ in range(CODE_LENGTH))
    expires_at = _now() + CODE_TTL
    _codes[phone] = (code, expires_at)
    logger.info("Generated sms code for %s (expires %s)", phone, expires_at.isoformat())
    return code


def validate_sms_code(phone: str, submitted: str) -> None:
    """Raise HTTPException if the submitted code is invalid."""
    _cleanup_expired(phone)
    entry = _codes.get(phone)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码无效或已过期"
        )
    stored_code, _ = entry
    if stored_code != submitted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码不匹配"
        )
    _codes.pop(phone, None)
