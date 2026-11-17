import os
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class ConfigManager:
    """
    Manages bot configuration and persistent state.
    Allows dynamic runtime updates from the Bale dashboard, saved immediately to disk.
    """
    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path or os.getenv("DATA_STORAGE_PATH", "bot_data.json")
        self.bale_bot_token = os.getenv("BALE_BOT_TOKEN", "").strip()
        
        self.state: Dict[str, Any] = {
            "eitaa_api_token": os.getenv("EITAA_API_TOKEN", "").strip(),
            "eitaa_channel_id": self._clean_channel(os.getenv("EITAA_CHANNEL_ID", "").strip(), is_eitaa=True),
            "bale_channel_id": os.getenv("BALE_CHANNEL_ID", "").strip(),
            "admin_user_ids": [],
            "forwarding_enabled": True,
            "total_forwarded": 0,
            "total_failed": 0,
            "last_forwarded_at": None,
            "custom_footer": "",
        }

        # Initialize admin from ENV if provided
        env_admin = os.getenv("ADMIN_USER_ID", "").strip()
        if env_admin:
            try:
                self.state["admin_user_ids"].append(int(env_admin))
            except ValueError:
                logger.warning(f"Invalid ADMIN_USER_ID in env: {env_admin}")

        self._load_from_disk()

    def _clean_channel(self, channel: str, is_eitaa: bool = False) -> str:
        channel = channel.strip()
        if is_eitaa and channel.startswith("@"):
            channel = channel[1:]
        return channel

    def _load_from_disk(self) -> None:
        if not os.path.exists(self.storage_path):
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                saved_data = json.load(f)
                if isinstance(saved_data, dict):
                    # Update state while keeping env defaults if saved value is empty
                    for key, val in saved_data.items():
                        if key in self.state:
                            # If admins in saved data, union with existing
                            if key == "admin_user_ids" and isinstance(val, list):
                                combined = set(self.state["admin_user_ids"]) | set(val)
                                self.state["admin_user_ids"] = list(combined)
                            elif val is not None and val != "":
                                self.state[key] = val
        except Exception as e:
            logger.error(f"Error loading persistent config from {self.storage_path}: {e}")

    def save_to_disk(self) -> None:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.storage_path)), exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving config to {self.storage_path}: {e}")

    # Eitaa Token
    def get_eitaa_token(self) -> str:
        return self.state.get("eitaa_api_token", "")

    def set_eitaa_token(self, token: str) -> None:
        self.state["eitaa_api_token"] = token.strip()
        self.save_to_disk()

    # Eitaa Channel
    def get_eitaa_channel(self) -> str:
        return self.state.get("eitaa_channel_id", "")

    def set_eitaa_channel(self, channel: str) -> None:
        self.state["eitaa_channel_id"] = self._clean_channel(channel, is_eitaa=True)
        self.save_to_disk()

    # Bale Channel
    def get_bale_channel(self) -> str:
        return self.state.get("bale_channel_id", "")

    def set_bale_channel(self, channel: str) -> None:
        self.state["bale_channel_id"] = channel.strip()
        self.save_to_disk()

    # Forwarding toggle
    def is_forwarding_enabled(self) -> bool:
        return bool(self.state.get("forwarding_enabled", True))

    def set_forwarding_enabled(self, enabled: bool) -> None:
        self.state["forwarding_enabled"] = enabled
        self.save_to_disk()

    # Admin Management
    def is_admin(self, user_id: int) -> bool:
        return user_id in self.state.get("admin_user_ids", [])

    def has_admins(self) -> bool:
        return len(self.state.get("admin_user_ids", [])) > 0

    def add_admin(self, user_id: int) -> None:
        if user_id not in self.state["admin_user_ids"]:
            self.state["admin_user_ids"].append(user_id)
            self.save_to_disk()

    # Stats
    def record_forward_success(self) -> None:
        self.state["total_forwarded"] = self.state.get("total_forwarded", 0) + 1
        self.state["last_forwarded_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.save_to_disk()

    def record_forward_failure(self) -> None:
        self.state["total_failed"] = self.state.get("total_failed", 0) + 1
        self.save_to_disk()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_forwarded": self.state.get("total_forwarded", 0),
            "total_failed": self.state.get("total_failed", 0),
            "last_forwarded_at": self.state.get("last_forwarded_at"),
            "forwarding_enabled": self.is_forwarding_enabled(),
        }

    def reset_stats(self) -> None:
        self.state["total_forwarded"] = 0
        self.state["total_failed"] = 0
        self.state["last_forwarded_at"] = None
        self.save_to_disk()
