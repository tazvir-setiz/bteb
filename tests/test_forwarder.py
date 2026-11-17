import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock
from config import ConfigManager
from forwarder import MessageForwarder
from bale_client import BaleClient
from eitaa_client import EitaaClient

@pytest.fixture
def mock_clients():
    bale = AsyncMock(spec=BaleClient)
    eitaa = AsyncMock(spec=EitaaClient)
    config = MagicMock(spec=ConfigManager)
    
    config.is_forwarding_enabled.return_value = True
    config.get_eitaa_token.return_value = "valid_eitaa_token"
    config.get_eitaa_channel.return_value = "target_eitaa"
    config.get_bale_channel.return_value = "-100123456"
    
    return bale, eitaa, config

@pytest.mark.asyncio
async def test_forward_text_message(mock_clients):
    bale, eitaa, config = mock_clients
    forwarder = MessageForwarder(bale_client=bale, eitaa_client=eitaa, config=config)

    channel_post = {
        "message_id": 55,
        "chat": {"id": -100123456, "title": "کانال بله"},
        "text": "سلام این یک پیام تست است"
    }

    eitaa.send_message.return_value = {"ok": True, "result": {"message_id": 999}}

    success = await forwarder.forward_channel_post(channel_post)
    assert success is True
    eitaa.send_message.assert_called_once_with(
        chat_id="target_eitaa",
        text="سلام این یک پیام تست است"
    )
    config.record_forward_success.assert_called_once()

@pytest.mark.asyncio
async def test_forward_photo_message(mock_clients):
    bale, eitaa, config = mock_clients
    forwarder = MessageForwarder(bale_client=bale, eitaa_client=eitaa, config=config)

    channel_post = {
        "message_id": 56,
        "chat": {"id": -100123456},
        "caption": "عکس جدید کانال",
        "photo": [
            {"file_id": "thumb_1", "file_size": 100},
            {"file_id": "large_1", "file_size": 5000}
        ]
    }

    bale.get_file.return_value = {"ok": True, "result": {"file_path": "photos/large_1.jpg"}}
    bale.download_file.return_value = b"photo-bytes"
    eitaa.send_file.return_value = {"ok": True, "result": {"message_id": 1000}}

    success = await forwarder.forward_channel_post(channel_post)
    assert success is True
    bale.get_file.assert_called_once_with("large_1")
    bale.download_file.assert_called_once_with("photos/large_1.jpg")
    eitaa.send_file.assert_called_once_with(
        chat_id="target_eitaa",
        file_bytes=b"photo-bytes",
        filename="photo.jpg",
        caption="عکس جدید کانال"
    )
    config.record_forward_success.assert_called_once()

@pytest.mark.asyncio
async def test_forward_disabled_or_channel_mismatch(mock_clients):
    bale, eitaa, config = mock_clients
    forwarder = MessageForwarder(bale_client=bale, eitaa_client=eitaa, config=config)

    # 1. Forwarding disabled
    config.is_forwarding_enabled.return_value = False
    channel_post = {
        "message_id": 57,
        "chat": {"id": -100123456},
        "text": "تست"
    }
    success = await forwarder.forward_channel_post(channel_post)
    assert success is False
    eitaa.send_message.assert_not_called()

    # 2. Channel mismatch
    config.is_forwarding_enabled.return_value = True
    wrong_channel_post = {
        "message_id": 58,
        "chat": {"id": -999999999},
        "text": "کانال متفرقه"
    }
    success = await forwarder.forward_channel_post(wrong_channel_post)
    assert success is False
    eitaa.send_message.assert_not_called()

@pytest.mark.asyncio
async def test_forward_error_records_failure(mock_clients):
    bale, eitaa, config = mock_clients
    forwarder = MessageForwarder(bale_client=bale, eitaa_client=eitaa, config=config)

    channel_post = {
        "message_id": 59,
        "chat": {"id": -100123456},
        "text": "تست خطا"
    }

    eitaa.send_message.side_effect = Exception("Network timeout")

    success = await forwarder.forward_channel_post(channel_post)
    assert success is False
    config.record_forward_failure.assert_called_once()
