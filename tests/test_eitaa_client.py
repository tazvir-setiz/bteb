import pytest
import httpx
from eitaa_client import EitaaClient, EitaaAPIError, EitaaAuthError

@pytest.mark.asyncio
async def test_eitaa_get_me_success():
    mock_token = "valid_token_123"
    
    def handler(request: httpx.Request):
        assert f"/api/{mock_token}/getMe" in str(request.url)
        return httpx.Response(200, json={
            "ok": True,
            "result": {
                "id": 112233,
                "is_bot": True,
                "first_name": "ایتایار",
                "username": "testAdmin"
            }
        })

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = EitaaClient(token=mock_token, http_client=http_client)
        result = await client.get_me()
        assert result["ok"] is True
        assert result["result"]["username"] == "testAdmin"

@pytest.mark.asyncio
async def test_eitaa_get_me_invalid_token():
    mock_token = "invalid_token"

    def handler(request: httpx.Request):
        return httpx.Response(401, json={
            "ok": False,
            "description": "Unauthorized or invalid token"
        })

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = EitaaClient(token=mock_token, http_client=http_client)
        with pytest.raises(EitaaAuthError) as exc_info:
            await client.get_me()
        assert "Unauthorized" in str(exc_info.value)

@pytest.mark.asyncio
async def test_eitaa_send_message_success():
    mock_token = "test_token"

    def handler(request: httpx.Request):
        assert f"/api/{mock_token}/sendMessage" in str(request.url)
        # Form or json parameters check
        assert request.method == "POST"
        return httpx.Response(200, json={
            "ok": True,
            "result": {
                "message_id": 85917,
                "text": "سلام ایتا"
            }
        })

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = EitaaClient(token=mock_token, http_client=http_client)
        res = await client.send_message(chat_id="my_channel", text="سلام ایتا")
        assert res["ok"] is True
        assert res["result"]["message_id"] == 85917

@pytest.mark.asyncio
async def test_eitaa_send_file_success():
    mock_token = "test_token"

    def handler(request: httpx.Request):
        assert f"/api/{mock_token}/sendFile" in str(request.url)
        assert request.method == "POST"
        assert "multipart/form-data" in request.headers.get("content-type", "")
        return httpx.Response(200, json={
            "ok": True,
            "result": {
                "message_id": 85918,
                "caption": "عکس ارسالی"
            }
        })

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = EitaaClient(token=mock_token, http_client=http_client)
        dummy_file = b"fake-image-bytes"
        res = await client.send_file(
            chat_id="my_channel",
            file_bytes=dummy_file,
            filename="image.jpg",
            caption="عکس ارسالی"
        )
        assert res["ok"] is True
        assert res["result"]["message_id"] == 85918

@pytest.mark.asyncio
async def test_eitaa_api_error_response():
    mock_token = "test_token"

    def handler(request: httpx.Request):
        return httpx.Response(200, json={
            "ok": False,
            "description": "chat_id not found"
        })

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = EitaaClient(token=mock_token, http_client=http_client)
        with pytest.raises(EitaaAPIError) as exc_info:
            await client.send_message(chat_id="unknown_chan", text="test")
        assert "chat_id not found" in str(exc_info.value)
