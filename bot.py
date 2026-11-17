import sys
import asyncio
import logging
import signal
from typing import Optional, Dict, Any
from config import ConfigManager
from bale_client import BaleClient
from eitaa_client import EitaaClient
from forwarder import MessageForwarder
from dashboard import AdminDashboard

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("BotRunner")

class BotRunner:
    """
    Main orchestrator for long polling, dispatching updates to Dashboard
    and Message Forwarder, and managing lifecycle.
    """
    def __init__(
        self,
        config: ConfigManager,
        bale_client: BaleClient,
        eitaa_client: EitaaClient,
        forwarder: MessageForwarder,
        dashboard: AdminDashboard
    ):
        self.config = config
        self.bale_client = bale_client
        self.eitaa_client = eitaa_client
        self.forwarder = forwarder
        self.dashboard = dashboard
        self.running = False
        self.offset: Optional[int] = None

    async def process_update(self, update: Dict[str, Any]) -> None:
        """Route update according to its payload."""
        update_id = update.get("update_id")
        if update_id is not None:
            self.offset = update_id + 1

        # 1. Channel post from Bale Channel -> Forwarder
        if "channel_post" in update:
            await self.forwarder.forward_channel_post(update["channel_post"])

        # 2. Callback query from Inline Keyboard -> Dashboard
        elif "callback_query" in update:
            await self.dashboard.handle_callback_query(update["callback_query"])

        # 3. Message (e.g. private chat with bot) -> Dashboard
        elif "message" in update:
            msg = update["message"]
            chat_type = msg.get("chat", {}).get("type", "")
            # In Telegram/Bale bot API, private chats with the bot are for admin dashboard
            if chat_type in ["private", ""]:
                await self.dashboard.handle_message(msg)
            else:
                # In case group or channel messages come through message field
                logger.debug(f"Unhandled non-private message: {msg.get('message_id')}")

    async def run(self) -> None:
        """Main polling loop."""
        self.running = True
        logger.info("Starting Bale-to-Eitaa Forwarder Bot...")

        # Verify Bale Bot Token
        try:
            bot_me = await self.bale_client.get_me()
            bale_name = bot_me.get("result", {}).get("username", "Unknown")
            logger.info(f"Connected to Bale as @{bale_name}")
        except Exception as e:
            logger.error(f"Failed to connect to Bale Bot API: {e}")
            logger.error("Please verify BALE_BOT_TOKEN in .env or your environment variables.")
            return

        # Check Eitaa Token
        eitaa_token = self.config.get_eitaa_token()
        if eitaa_token:
            try:
                eitaa_me = await self.eitaa_client.get_me()
                eitaa_name = eitaa_me.get("result", {}).get("username", "Unknown")
                logger.info(f"Connected to Eitaa as @{eitaa_name}")
            except Exception as e:
                logger.warning(f"Could not verify Eitaa token initially ({e}). You can update it in the Bale dashboard.")
        else:
            logger.warning("Eitaa API Token is not set yet. Configure it via Bale Bot Dashboard (/start).")

        logger.info("Bot is active and polling updates...")

        while self.running:
            try:
                updates = await self.bale_client.get_updates(offset=self.offset, timeout=20)
                for update in updates:
                    try:
                        await self.process_update(update)
                    except Exception as e:
                        logger.error(f"Error handling update: {e}", exc_info=True)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error during polling getUpdates: {e}")
                await asyncio.sleep(3)

    async def stop(self) -> None:
        logger.info("Stopping BotRunner...")
        self.running = False
        await self.bale_client.close()
        await self.eitaa_client.close()


def create_bot() -> BotRunner:
    config = ConfigManager()
    if not config.bale_bot_token:
        print("\n[ERROR] BALE_BOT_TOKEN is missing!")
        print("Please create a .env file based on .env.example and set your BALE_BOT_TOKEN.\n")
        sys.exit(1)

    bale_client = BaleClient(token=config.bale_bot_token)
    eitaa_client = EitaaClient(token=config.get_eitaa_token())
    forwarder = MessageForwarder(bale_client=bale_client, eitaa_client=eitaa_client, config=config)
    dashboard = AdminDashboard(bale_client=bale_client, eitaa_client=eitaa_client, config=config)

    return BotRunner(
        config=config,
        bale_client=bale_client,
        eitaa_client=eitaa_client,
        forwarder=forwarder,
        dashboard=dashboard
    )


async def main() -> None:
    runner = create_bot()

    # Graceful shutdown handling
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def signal_handler():
        logger.info("Received shutdown signal.")
        stop_event.set()

    # On Windows, add_signal_handler is only partially supported for SIGINT
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except (NotImplementedError, RuntimeError):
            pass

    bot_task = asyncio.create_task(runner.run())

    try:
        await bot_task
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Shutting down...")
    finally:
        await runner.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
