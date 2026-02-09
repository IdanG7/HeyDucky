# tests/test_config.py
import os
import tempfile
from pathlib import Path
from voice_debugger.config import Config


def test_default_config():
    """Config has sensible defaults."""
    config = Config()
    assert config.ai_provider == "claude"
    assert config.whisper_model == "base.en"
    assert config.sample_rate == 16000


def test_config_from_dict():
    """Config can be created from a dictionary."""
    config = Config.from_dict({
        "ai": {"provider": "claude", "model": "claude-sonnet-4-5-20250929"},
        "voice": {"whisper_model": "tiny.en", "sample_rate": 16000},
    })
    assert config.ai_model == "claude-sonnet-4-5-20250929"
    assert config.whisper_model == "tiny.en"


def test_config_save_and_load(tmp_path):
    """Config round-trips through TOML file."""
    config_path = tmp_path / "config.toml"
    config = Config()
    config.api_key = "test-key-123"
    config.save(config_path)

    loaded = Config.load(config_path)
    assert loaded.api_key == "test-key-123"
    assert loaded.ai_provider == config.ai_provider


def test_config_load_missing_file():
    """Loading non-existent file returns defaults."""
    config = Config.load(Path("/nonexistent/config.toml"))
    assert config.ai_provider == "claude"
