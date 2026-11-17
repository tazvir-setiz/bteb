import pytest
from unittest.mock import AsyncMock, MagicMock
from config import ConfigManager
from bale_client import BaleClient
from eitaa_client import EitaaClient, EitaaAPIError
from dashboard import AdminDashboard

@pytest.fixture
def dashboard_fixture():
    bale = AsyncMock(spec=BaleClient)
    eitaa = AsyncMock(spec=EitaaClient)
    config = MagicMock(spec=ConfigManager)

    # Defaults
    config.has_admins.return_value = True
    config.is_admin.side_effect = lambda uid: uid == 12345
    config.get_eitaa_token.return_value = "token_abc123"
    config.get_eitaa_channel.return_value = "target_chan"
    config.get_bale_channel.return_value = "-100123"
    config.is_forwarding_enabled.return_value = True
    config.get_stats.return_value = {
        "total_forwarded": 10,
        "total_failed": 1,
        "last_forwarded_at": "2026-11-17 18:00:00",
        "forwarding_enabled": True
    }

    dash = AdminDashboard(bale_client=bale, eitaa_client=eitaa, config=config)
    return dash, bale, eitaa, config

@pytest.mark.asyncio
async def test_start_command_first_user_admin(dashboard_fixture):
    dash, bale, eitaa, config = dashboard_fixture
    config.has_admins.return_value = False

    msg = {
        "message_id": 1,
        "chat": {"id": 111, "type": "private"},
        "from": {"id": 111, "first_name": "Boss"},
        "text": "/start"
    }

    await dash.handle_message(msg)
    config.add_admin.assert_called_once_with(111)
    assert bale.send_message.call_count == 2

@pytest.mark.asyncio
async def test_non_admin_blocked(dashboard_fixture):
    dash, bale, eitaa, config = dashboard_fixture

    msg = {
        "message_id": 2,
        "chat": {"id": 999, "type": "private"},
        "from": {"id": 999},
        "text": "/start"
    }

    await dash.handle_message(msg)
    bale.send_message.assert_called_once()
    assert "دسترسی غیرمجاز" in bale.send_message.call_args[1]["text"]

@pytest.mark.asyncio
async def test_toggle_forwarding_callback(dashboard_fixture):
    dash, bale, eitaa, config = dashboard_fixture

    cb = {
        "id": "cb_1",
        "from": {"id": 12345},
        "message": {"message_id": 10, "chat": {"id": 12345}},
        "data": "toggle_forward"
    }

    await dash.handle_callback_query(cb)
    config.set_forwarding_enabled.assert_called_once_with(False)
    bale.answer_callback_query.assert_called_once()
    bale.edit_message_text.assert_called_once()

@pytest.mark.asyncio
async def test_wizard_set_eitaa_token(dashboard_fixture):
    dash, bale, eitaa, config = dashboard_fixture

    # 1. Admin clicks button to set token
    cb = {
        "id": "cb_2",
        "from": {"id": 12345},
        "message": {"message_id": 10, "chat": {"id": 12345}},
        "data": "set_eitaa_token"
    }
    await dash.handle_callback_query(cb)
    assert dash.user_states.get(12345) == "awaiting_eitaa_token"
    bale.edit_message_text.assert_called_once()

    # 2. Admin sends new token
    input_msg = {
        "message_id": 3,
        "chat": {"id": 12345, "type": "private"},
        "from": {"id": 12345},
        "text": "new_secret_eitaa_token"
    }
    await dash.handle_message(input_msg)
    config.set_eitaa_token.assert_called_once_with("new_secret_eitaa_token")
    assert 12345 not in dash.user_states
    # Confirm message and dashboard sent
    assert bale.send_message.call_count >= 1

@pytest.mark.asyncio
async def test_test_eitaa_connection_success(dashboard_fixture):
    dash, bale, eitaa, config = dashboard_fixture
    eitaa.get_me.return_value = {
        "ok": True,
        "result": {
            "id": 123456,
            "first_name": "تست ایتا",
            "username": "eitaa_bot_test"
        }
    }

    cb = {
        "id": "cb_3",
        "from": {"id": 12345},
        "message": {"message_id": 10, "chat": {"id": 12345}},
        "data": "test_eitaa"
    }

    await dash.handle_callback_query(cb)
    eitaa.get_me.assert_called_once()
    bale.edit_message_text.assert_called_once()
    args, kwargs = bale.edit_message_text.call_args
    assert "موفقیت‌آمیز" in kwargs["text"]
