import httpx
import pytest
from fastapi import HTTPException, status

from src.modules.auth.wechat import exchange_code_for_openid


@pytest.mark.asyncio
async def test_exchange_code_returns_openid():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/sns/jscode2session"
        return httpx.Response(200, json={"errcode": 0, "openid": "mock-openid", "session_key": "abc"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://api.weixin.qq.com") as client:
        openid = await exchange_code_for_openid("valid-code", client=client)

    assert openid == "mock-openid"


@pytest.mark.asyncio
async def test_exchange_code_handles_invalid_code():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"errcode": 40029, "errmsg": "invalid code"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://api.weixin.qq.com") as client:
        with pytest.raises(HTTPException) as excinfo:
            await exchange_code_for_openid("bad-code", client=client)

    assert excinfo.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "invalid" in excinfo.value.detail.lower()


@pytest.mark.asyncio
async def test_exchange_code_handles_network_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://api.weixin.qq.com") as client:
        with pytest.raises(HTTPException) as excinfo:
            await exchange_code_for_openid("any", client=client)

    assert excinfo.value.status_code == status.HTTP_502_BAD_GATEWAY
