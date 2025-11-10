"""WeChat authentication helpers."""

from __future__ import annotations

import httpx
from fastapi import HTTPException, status

from src.core.config import settings

_WECHAT_AUTH_PATH = "/sns/jscode2session"


async def exchange_code_for_openid(code: str, client: httpx.AsyncClient | None = None) -> str:
    """Return a stable openid for the provided login code."""
    params = {
        "appid": settings.wechat_appid,
        "secret": settings.wechat_secret,
        "js_code": code,
        "grant_type": "authorization_code",
    }
    created_client = False
    if client is None:
        client = httpx.AsyncClient(
            base_url=settings.wechat_api_base,
            timeout=settings.wechat_timeout_seconds,
        )
        created_client = True
    try:
        response = await client.get(_WECHAT_AUTH_PATH, params=params)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="WeChat login service is unavailable",
        ) from exc
    finally:
        if created_client:
            await client.aclose()

    if response.status_code != status.HTTP_200_OK:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="WeChat login service returned an unexpected status",
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to parse WeChat login response",
        ) from exc

    errcode = payload.get("errcode", 0)
    if errcode not in (0, None):
        if errcode in (40029, 40163):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="WeChat code is invalid or expired",
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"WeChat login error {errcode}",
        )

    openid = payload.get("openid")
    if not openid:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="WeChat login response did not include openid",
        )

    return openid
