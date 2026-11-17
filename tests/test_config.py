import os
import json
import tempfile
import pytest
from config import ConfigManager

def test_config_defaults_and_env():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_file = os.path.join(tmpdir, "test_config.json")
        os.environ["BALE_BOT_TOKEN"] = "test_bale_token"
        os.environ["ADMIN_USER_ID"] = "123456"
        os.environ["EITAA_API_TOKEN"] = "env_eitaa_token"
        os.environ["EITAA_CHANNEL_ID"] = "env_eitaa_chan"
        os.environ["BALE_CHANNEL_ID"] = "-100123"

        cfg = ConfigManager(storage_path=storage_file)
        
        assert cfg.bale_bot_token == "test_bale_token"
        assert cfg.is_admin(123456) is True
        assert cfg.is_admin(999999) is False
        assert cfg.get_eitaa_token() == "env_eitaa_token"
        assert cfg.get_eitaa_channel() == "env_eitaa_chan"
        assert cfg.get_bale_channel() == "-100123"
        assert cfg.is_forwarding_enabled() is True

def test_config_persistence_and_normalization():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_file = os.path.join(tmpdir, "test_config.json")
        cfg = ConfigManager(storage_path=storage_file)

        # Test normalization: strip @ from eitaa channel
        cfg.set_eitaa_channel("@my_eitaa_channel")
        assert cfg.get_eitaa_channel() == "my_eitaa_channel"

        cfg.set_eitaa_token("new_token_123")
        assert cfg.get_eitaa_token() == "new_token_123"

        cfg.set_bale_channel("  @bale_news  ")
        assert cfg.get_bale_channel() == "@bale_news"

        cfg.set_forwarding_enabled(False)
        assert cfg.is_forwarding_enabled() is False

        # Verify disk persistence
        assert os.path.exists(storage_file)
        with open(storage_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["eitaa_channel_id"] == "my_eitaa_channel"
            assert data["eitaa_api_token"] == "new_token_123"
            assert data["forwarding_enabled"] is False

        # Load fresh instance from disk
        cfg2 = ConfigManager(storage_path=storage_file)
        assert cfg2.get_eitaa_channel() == "my_eitaa_channel"
        assert cfg2.get_eitaa_token() == "new_token_123"
        assert cfg2.is_forwarding_enabled() is False

def test_config_stats():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_file = os.path.join(tmpdir, "test_config.json")
        cfg = ConfigManager(storage_path=storage_file)

        stats = cfg.get_stats()
        assert stats["total_forwarded"] == 0
        assert stats["total_failed"] == 0

        cfg.record_forward_success()
        cfg.record_forward_success()
        cfg.record_forward_failure()

        stats = cfg.get_stats()
        assert stats["total_forwarded"] == 2
        assert stats["total_failed"] == 1
        assert stats["last_forwarded_at"] is not None

def test_first_user_admin_claim_if_empty():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_file = os.path.join(tmpdir, "test_config.json")
        # Clear env admin
        if "ADMIN_USER_ID" in os.environ:
            del os.environ["ADMIN_USER_ID"]
            
        cfg = ConfigManager(storage_path=storage_file)
        assert cfg.has_admins() is False
        assert cfg.is_admin(111) is False
        
        # Claim first admin
        cfg.add_admin(111)
        assert cfg.has_admins() is True
        assert cfg.is_admin(111) is True
        assert cfg.is_admin(222) is False
