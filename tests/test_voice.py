"""Tests for voice handler."""

import numpy as np
import pytest
from unittest.mock import patch, MagicMock
from voice_debugger.voice import VoiceHandler, trim_silence


def test_trim_silence_removes_leading_trailing():
    """trim_silence removes quiet parts from start and end."""
    sr = 16000
    # 0.5s silence + 1s speech + 0.5s silence
    silence = np.zeros(sr // 2, dtype=np.float32)
    speech = np.random.randn(sr).astype(np.float32) * 0.5
    audio = np.concatenate([silence, speech, silence])

    trimmed = trim_silence(audio, threshold=0.02, sr=sr)
    # Trimmed should be shorter than original
    assert len(trimmed) < len(audio)
    # Trimmed should still contain speech
    assert len(trimmed) >= sr * 0.8  # at least most of the speech


def test_trim_silence_all_silent():
    """trim_silence returns empty for pure silence."""
    silence = np.zeros(16000, dtype=np.float32)
    trimmed = trim_silence(silence, threshold=0.02, sr=16000)
    assert len(trimmed) == 0


def test_voice_handler_init():
    """VoiceHandler initializes with config defaults."""
    with patch("voice_debugger.voice.WhisperModel") as mock_whisper:
        handler = VoiceHandler(whisper_model="tiny.en")
        assert handler.sample_rate == 16000
        assert handler._is_recording is False


def test_voice_handler_transcribe():
    """VoiceHandler transcribes audio buffer."""
    with patch("voice_debugger.voice.WhisperModel") as mock_whisper_cls:
        mock_model = MagicMock()
        mock_segment = MagicMock()
        mock_segment.text = " Hello world "
        mock_info = MagicMock()
        mock_model.transcribe.return_value = ([mock_segment], mock_info)
        mock_whisper_cls.return_value = mock_model

        handler = VoiceHandler(whisper_model="tiny.en")
        audio = np.random.randn(16000).astype(np.float32) * 0.5
        result = handler.transcribe(audio)
        assert result == "Hello world"
