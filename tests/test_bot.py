import pytest
from unittest.mock import AsyncMock, MagicMock
from bot import BotRunner
from config import ConfigManager
from bale_client import BaleClient
from eitaa_client import EitaaClient
from forwarder import MessageForwarder
from dashboard import AdminDashboard

@pytest.fixture
def runner_fixture():
    config = MagicMock(spec=ConfigManager)
    bale = AsyncMock(spec=BaleClient)
    eitaa = AsyncMock(spec=EitaaClient)
    forwarder = AsyncMock(spec=MessageForwarder)
    dashboard = AsyncMock(spec=AdminDashboard)

    runner = BotRunner(
        config=config,
        bale_client=bale,
        eitaa_client=eitaa,
        forwarder=forwarder,
        dashboard=dashboard
    )
    return runner, config, bale, eitaa, forwarder, dashboard

@pytest.mark.asyncio
async def test_dispatch_channel_post(runner_fixture):
    runner, config, bale, eitaa, forwarder, dashboard = runner_fixture

    update = {
        "update_id": 200,
        "channel_post": {
            "message_id": 10,
            "chat": {"id": -100123},
            "text": "سلام کانال"
        }
    }

    await runner.process_update(update)
    forwarder.forward_channel_post.assert_called_once_with(update["channel_post"])
    dashboard.handle_message.assert_not_called()
    dashboard.handle_callback_query.assert_not_called()

@pytest.mark.asyncio
async def test_dispatch_private_message(runner_fixture):
    runner, config, bale, eitaa, forwarder, dashboard = runner_fixture

    update = {
        "update_id": 201,
        "message": {
            "message_id": 11,
            "chat": {"id": 12345, "type": "private"},
            "text": "/start"
        }
    }

    await runner.process_update(update)
    dashboard.handle_message.assert_called_once_with(update["message"])
    forwarder.forward_channel_post.assert_not_called()

@pytest.mark.asyncio
async def test_dispatch_callback_query(runner_fixture):
    runner, config, bale, eitaa, forwarder, dashboard = runner_fixture

    update = {
        "update_id": 202,
        "callback_query": {
            "id": "cb_99",
            "data": "main_menu"
        }
    }

    await runner.process_update(update)
    dashboard.handle_callback_query.assert_called_once_with(update["callback_query"])
    forwarder.forward_channel_post.assert_not_called()
    dashboard.handle_message.assert_not_called()
