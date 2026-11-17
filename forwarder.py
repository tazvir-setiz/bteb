import os
import logging
from typing import Dict, Any, Optional
from bale_client import BaleClient
from eitaa_client import EitaaClient
from config import ConfigManager

logger = logging.getLogger(__name__)

class MessageForwarder:
    """
    Coordinates message forwarding from Bale channel to Eitaa channel.
    """
    def __init__(self, bale_client: BaleClient, eitaa_client: EitaaClient, config: ConfigManager):
        self.bale_client = bale_client
        self.eitaa_client = eitaa_client
        self.config = config

    def _is_channel_match(self, chat: Dict[str, Any]) -> bool:
        configured_channel = self.config.get_bale_channel().strip()
        if not configured_channel:
            return False

        chat_id = str(chat.get("id", ""))
        chat_username = str(chat.get("username", "")).lstrip("@").lower()
        clean_conf = configured_channel.lstrip("@").lower()

        # Match by ID or by username
        if chat_id == configured_channel or (clean_conf and chat_username == clean_conf):
            return True
        return False

    async def forward_channel_post(self, post: Dict[str, Any]) -> bool:
        """
        Process and forward a post received from a channel.
        """
        if not self.config.is_forwarding_enabled():
            logger.info("Forwarding is currently disabled.")
            return False

        chat = post.get("chat", {})
        if not self._is_channel_match(chat):
            logger.debug(f"Ignored post from unconfigured channel: id={chat.get('id')}, username={chat.get('username')}")
            return False

        target_channel = self.config.get_eitaa_channel()
        if not target_channel:
            logger.warning("Target Eitaa channel is not configured.")
            return False

        # Ensure Eitaa token matches current config
        self.eitaa_client.token = self.config.get_eitaa_token()
        if not self.eitaa_client.token:
            logger.warning("Eitaa API token is not configured.")
            return False

        try:
            # 1. Photo Message
            if "photo" in post and post["photo"]:
                # Select the photo with largest size (usually the last element)
                photos = post["photo"]
                best_photo = photos[-1]
                file_id = best_photo["file_id"]
                caption = post.get("caption")

                file_info = await self.bale_client.get_file(file_id)
                file_path = file_info["result"]["file_path"]
                file_bytes = await self.bale_client.download_file(file_path)

                await self.eitaa_client.send_file(
                    chat_id=target_channel,
                    file_bytes=file_bytes,
                    filename="photo.jpg",
                    caption=caption
                )

            # 2. Document / File Message
            elif "document" in post:
                doc = post["document"]
                file_id = doc["file_id"]
                filename = doc.get("file_name", "document.bin")
                caption = post.get("caption")

                file_info = await self.bale_client.get_file(file_id)
                file_path = file_info["result"]["file_path"]
                file_bytes = await self.bale_client.download_file(file_path)

                await self.eitaa_client.send_file(
                    chat_id=target_channel,
                    file_bytes=file_bytes,
                    filename=filename,
                    caption=caption
                )

            # 3. Video Message
            elif "video" in post:
                video = post["video"]
                file_id = video["file_id"]
                filename = video.get("file_name", "video.mp4")
                caption = post.get("caption")

                file_info = await self.bale_client.get_file(file_id)
                file_path = file_info["result"]["file_path"]
                file_bytes = await self.bale_client.download_file(file_path)

                await self.eitaa_client.send_file(
                    chat_id=target_channel,
                    file_bytes=file_bytes,
                    filename=filename,
                    caption=caption
                )

            # 4. Audio or Voice Message
            elif "audio" in post or "voice" in post:
                audio = post.get("audio") or post.get("voice")
                file_id = audio["file_id"]
                filename = audio.get("file_name", "audio.ogg" if "voice" in post else "audio.mp3")
                caption = post.get("caption")

                file_info = await self.bale_client.get_file(file_id)
                file_path = file_info["result"]["file_path"]
                file_bytes = await self.bale_client.download_file(file_path)

                await self.eitaa_client.send_file(
                    chat_id=target_channel,
                    file_bytes=file_bytes,
                    filename=filename,
                    caption=caption
                )

            # 5. Animation / GIF Message
            elif "animation" in post:
                anim = post["animation"]
                file_id = anim["file_id"]
                filename = "animation.gif"
                caption = post.get("caption")

                file_info = await self.bale_client.get_file(file_id)
                file_path = file_info["result"]["file_path"]
                file_bytes = await self.bale_client.download_file(file_path)

                await self.eitaa_client.send_file(
                    chat_id=target_channel,
                    file_bytes=file_bytes,
                    filename=filename,
                    caption=caption
                )

            # 6. Plain Text Message
            elif "text" in post:
                text = post["text"]
                await self.eitaa_client.send_message(
                    chat_id=target_channel,
                    text=text
                )
            else:
                logger.info("Unsupported post type encountered, skipped.")
                return False

            self.config.record_forward_success()
            logger.info(f"Successfully forwarded post {post.get('message_id')} to Eitaa channel {target_channel}.")
            return True

        except Exception as e:
            logger.error(f"Failed to forward channel post {post.get('message_id')}: {e}")
            self.config.record_forward_failure()
            return False
