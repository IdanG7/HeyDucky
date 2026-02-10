"""Configuration management for voice-debugger."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import toml


DEFAULT_CONFIG_DIR = Path.home() / ".config" / "voice-debugger"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.toml"


@dataclass
class Config:
    """Application configuration."""

    # AI settings
    ai_provider: str = "claude"
    ai_model: str = "claude-sonnet-4-5-20250929"
    api_key: str = ""
    compaction_enabled: bool = True

    # Appearance
    theme: str = "textual-dark"

    # Voice settings
    whisper_model: str = "base.en"
    sample_rate: int = 16000
    silence_threshold: float = 0.02
    silence_duration: float = 1.5

    # TTS settings
    tts_enabled: bool = False
    tts_api_key: str = ""
    tts_voice_id: str = "JBFqnCBsd6RMkjVDRZzb"

    @classmethod
    def from_dict(cls, data: dict) -> Config:
        """Create Config from nested dictionary (TOML structure)."""
        ai = data.get("ai", {})
        voice = data.get("voice", {})
        appearance = data.get("appearance", {})
        tts = data.get("tts", {})
        return cls(
            ai_provider=ai.get("provider", "claude"),
            ai_model=ai.get("model", "claude-sonnet-4-5-20250929"),
            api_key=ai.get("api_key", ""),
            compaction_enabled=ai.get("compaction_enabled", True),
            theme=appearance.get("theme", "textual-dark"),
            whisper_model=voice.get("whisper_model", "base.en"),
            sample_rate=voice.get("sample_rate", 16000),
            silence_threshold=voice.get("silence_threshold", 0.02),
            silence_duration=voice.get("silence_duration", 1.5),
            tts_enabled=tts.get("enabled", False),
            tts_api_key=tts.get("api_key", ""),
            tts_voice_id=tts.get("voice_id", "JBFqnCBsd6RMkjVDRZzb"),
        )

    def to_dict(self) -> dict:
        """Convert to nested dictionary for TOML serialization."""
        return {
            "ai": {
                "provider": self.ai_provider,
                "model": self.ai_model,
                "api_key": self.api_key,
                "compaction_enabled": self.compaction_enabled,
            },
            "appearance": {
                "theme": self.theme,
            },
            "voice": {
                "whisper_model": self.whisper_model,
                "sample_rate": self.sample_rate,
                "silence_threshold": self.silence_threshold,
                "silence_duration": self.silence_duration,
            },
            "tts": {
                "enabled": self.tts_enabled,
                "api_key": self.tts_api_key,
                "voice_id": self.tts_voice_id,
            },
        }

    def save(self, path: Path | None = None) -> None:
        """Save config to TOML file."""
        path = path or DEFAULT_CONFIG_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            toml.dump(self.to_dict(), f)

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        """Load config from TOML file. Returns defaults if file missing."""
        path = path or DEFAULT_CONFIG_PATH
        if not path.exists():
            return cls()
        with open(path) as f:
            data = toml.load(f)
        return cls.from_dict(data)
