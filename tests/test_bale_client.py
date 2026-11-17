import pytest
import httpx
from bale_client import BaleClient, BaleAPIError

@pytest.mark.asyncio
async def test_bale_get_me_success():
    mock_token = "bale_token_123"

    def handler(request: httpx.Request):
        assert f"/bot{mock_token}/getMe" in str(request.url)
        return httpx.Response(200, json={
            "ok": True,
            "result": {
                "id": 987654321,
                "is_bot": True,
                "first_name": "Forwarder Bot",
                "username": "ForwarderBot"
            }
        })

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = BaleClient(token=mock_token, http_client=http_client)
        me = await client.get_me()
        assert me["ok"] is True
        assert me["result"]["username"] == "ForwarderBot"

@pytest.mark.asyncio
async def test_bale_get_updates():
    mock_token = "bale_token_123"

    def handler(request: httpx.Request):
        assert f"/bot{mock_token}/getUpdates" in str(request.url)
        return httpx.Response(200, json={
            "ok": True,
            "result": [
                {
                    "update_id": 1001,
                    "message": {
                        "message_id": 1,
                        "chat": {"id": 12345, "type": "private"},
                        "from": {"id": 12345, "username": "admin"},
                        "text": "/start"
                    }
                }
            ]
        })

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = BaleClient(token=mock_token, http_client=http_client)
        updates = await client.get_updates(offset=1000)
        assert len(updates) == 1
        assert updates[0]["update_id"] == 1001

@pytest.mark.asyncio
async def test_bale_send_message_with_keyboard():
    mock_token = "bale_token_123"

    def handler(request: httpx.Request):
        assert f"/bot{mock_token}/sendMessage" in str(request.url)
        payload = httpx.QueryParams(request.url.query) if request.method == "GET" else request.read()
        return httpx.Response(200, json={
            "ok": True,
            "result": {
                "message_id": 42,
                "chat": {"id": 12345},
                "text": "سلام ادمین"
            }
        })

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = BaleClient(token=mock_token, http_client=http_client)
        keyboard = {
            "inline_keyboard": [
                [{"text": "تنظیمات", "callback_data": "menu_settings"}]
            ]
        }
        res = await client.send_message(chat_id=12345, text="سلام ادمین", reply_markup=keyboard)
        assert res["ok"] is True
        assert res["result"]["message_id"] == 42

@pytest.mark.asyncio
async def test_bale_download_file():
    mock_token = "bale_token_123"

    def handler(request: httpx.Request):
        url_str = str(request.url)
        if "/getFile" in url_str:
            return httpx.Response(200, json={
                "ok": True,
                "result": {
                    "file_id": "photo_file_123",
                    "file_path": "photos/photo_123.jpg",
                    "file_size": 1024
                }
            })
        elif "/file/bot" in url_str and "photos/photo_123.jpg" in url_str:
            return httpx.Response(200, content=b"fake-image-bytes-from-bale")
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = BaleClient(token=mock_token, http_client=http_client)
        file_info = await client.get_file("photo_file_123")
        assert file_info["ok"] is True
        assert file_info["result"]["file_path"] == "photos/photo_123.jpg"

        file_bytes = await client.download_file("photos/photo_123.jpg")
        assert file_bytes == b"fake-image-bytes-from-bale"
