"""Tests for TTS handler and related integration."""

from __future__ import annotations

import sys
import time
from unittest.mock import MagicMock, patch

import pytest

from voice_debugger.config import Config
from voice_debugger.tts import TTSHandler, split_sentences


# --- split_sentences tests ---


class TestSplitSentences:
    """Tests for the sentence boundary detection helper."""

    def test_no_boundary(self):
        """Text without sentence boundaries is all remainder."""
        sentences, remainder = split_sentences("Hello world")
        assert sentences == []
        assert remainder == "Hello world"

    def test_single_period(self):
        """Period followed by space splits into sentence + remainder."""
        sentences, remainder = split_sentences("Hello. World")
        assert sentences == ["Hello."]
        assert remainder == "World"

    def test_exclamation_boundary(self):
        """Exclamation mark followed by space is a boundary."""
        sentences, remainder = split_sentences("Wow! That's great")
        assert sentences == ["Wow!"]
        assert remainder == "That's great"

    def test_question_boundary(self):
        """Question mark followed by space is a boundary."""
        sentences, remainder = split_sentences("Really? Yes")
        assert sentences == ["Really?"]
        assert remainder == "Yes"

    def test_multiple_sentences(self):
        """Multiple sentence boundaries split correctly."""
        sentences, remainder = split_sentences("One. Two. Three")
        assert sentences == ["One.", "Two."]
        assert remainder == "Three"

    def test_newline_boundary(self):
        """Newline acts as a sentence boundary."""
        sentences, remainder = split_sentences("First line\nSecond line")
        assert sentences == ["First line"]
        assert remainder == "Second line"

    def test_empty_string(self):
        """Empty string returns no sentences and empty remainder."""
        sentences, remainder = split_sentences("")
        assert sentences == []
        assert remainder == ""

    def test_trailing_period_no_space(self):
        """Period at end without trailing space stays in remainder."""
        sentences, remainder = split_sentences("Hello world.")
        assert sentences == []
        assert remainder == "Hello world."

    def test_sentence_then_trailing(self):
        """Complete sentence plus incomplete text."""
        sentences, remainder = split_sentences("Done. Now working on")
        assert sentences == ["Done."]
        assert remainder == "Now working on"

    def test_whitespace_only_parts_filtered(self):
        """Whitespace-only parts are filtered out of sentences list."""
        sentences, remainder = split_sentences("A. B. C")
        assert all(s.strip() for s in sentences)


# --- TTSHandler tests ---


@pytest.fixture
def mock_elevenlabs():
    """Fixture that mocks the elevenlabs package for TTSHandler tests."""
    mock_client_cls = MagicMock()
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    mock_stream = MagicMock()

    with patch.dict(sys.modules, {
        "elevenlabs": MagicMock(stream=mock_stream),
        "elevenlabs.client": MagicMock(ElevenLabs=mock_client_cls),
    }):
        yield {
            "client_cls": mock_client_cls,
            "client": mock_client,
            "stream": mock_stream,
        }


class TestTTSHandler:
    """Tests for the TTSHandler class."""

    def test_constructor_creates_client(self, mock_elevenlabs):
        """TTSHandler creates an ElevenLabs client with the given key."""
        handler = TTSHandler(api_key="test-key")
        mock_elevenlabs["client_cls"].assert_called_once_with(api_key="test-key")
        handler.shutdown()

    def test_constructor_custom_voice_model(self, mock_elevenlabs):
        """TTSHandler stores custom voice and model IDs."""
        handler = TTSHandler(
            api_key="key",
            voice_id="custom-voice",
            model_id="custom-model",
        )
        assert handler._voice_id == "custom-voice"
        assert handler._model_id == "custom-model"
        handler.shutdown()

    def test_constructor_missing_package(self):
        """TTSHandler raises RuntimeError when elevenlabs is not installed."""
        with patch.dict(sys.modules, {"elevenlabs.client": None}):
            # Force the import to fail
            with patch("builtins.__import__", side_effect=ImportError("No module")):
                with pytest.raises(RuntimeError, match="ElevenLabs SDK is not installed"):
                    TTSHandler(api_key="test-key")

    def test_speak_enqueues_text(self, mock_elevenlabs):
        """speak() puts text on the queue and playback loop processes it."""
        mock_client = mock_elevenlabs["client"]
        handler = TTSHandler(api_key="key")
        handler.speak("Hello")
        # Give the playback thread time to process
        time.sleep(0.2)
        handler.shutdown()
        handler._thread.join(timeout=2)
        # Verify the text was actually processed by the playback loop
        mock_client.text_to_speech.stream.assert_called_with(
            text="Hello",
            voice_id="JBFqnCBsd6RMkjVDRZzb",
            model_id="eleven_flash_v2_5",
        )

    def test_speak_skips_empty(self, mock_elevenlabs):
        """speak() ignores empty/whitespace text."""
        handler = TTSHandler(api_key="key")
        handler.speak("")
        handler.speak("   ")
        # Queue should be empty (nothing enqueued)
        assert handler._queue.empty()
        handler.shutdown()

    def test_speak_disabled_no_enqueue(self, mock_elevenlabs):
        """speak() does nothing when handler is disabled (muted)."""
        handler = TTSHandler(api_key="key")
        handler._enabled = False
        handler.speak("This should not enqueue")
        assert handler._queue.empty()
        handler.shutdown()

    def test_toggle_returns_new_state(self, mock_elevenlabs):
        """toggle() flips enabled and returns the new state."""
        handler = TTSHandler(api_key="key")
        assert handler._enabled is True

        result = handler.toggle()
        assert result is False
        assert handler._enabled is False

        result = handler.toggle()
        assert result is True
        assert handler._enabled is True
        handler.shutdown()

    def test_toggle_drains_queue_when_muting(self, mock_elevenlabs):
        """toggle() to muted drains pending items from the queue."""
        handler = TTSHandler(api_key="key")
        # Pause the playback thread by not letting it process
        handler._enabled = False  # disable to prevent auto-processing
        handler._enabled = True
        handler._queue.put("item1")
        handler._queue.put("item2")

        handler.toggle()  # Mute -> should drain
        assert handler._queue.empty()
        handler.shutdown()

    def test_stop_drains_queue(self, mock_elevenlabs):
        """stop() empties the queue."""
        handler = TTSHandler(api_key="key")
        handler._queue.put("a")
        handler._queue.put("b")
        handler._queue.put("c")

        handler.stop()
        assert handler._queue.empty()
        handler.shutdown()

    def test_shutdown_sends_sentinel(self, mock_elevenlabs):
        """shutdown() puts None on the queue to stop the thread."""
        handler = TTSHandler(api_key="key")
        handler.shutdown()
        # Thread should exit
        handler._thread.join(timeout=2)
        assert not handler._thread.is_alive()

    def test_playback_loop_calls_stream(self, mock_elevenlabs):
        """The playback loop calls client.stream() and plays audio."""
        mock_client = mock_elevenlabs["client"]
        mock_audio = MagicMock()
        mock_client.text_to_speech.stream.return_value = mock_audio

        handler = TTSHandler(api_key="key")
        handler.speak("Test speech")
        # Give the background thread time to process
        time.sleep(0.2)
        handler.shutdown()
        handler._thread.join(timeout=2)

        mock_client.text_to_speech.stream.assert_called_with(
            text="Test speech",
            voice_id="JBFqnCBsd6RMkjVDRZzb",
            model_id="eleven_flash_v2_5",
        )
        mock_elevenlabs["stream"].assert_called_with(mock_audio)

    def test_playback_loop_handles_exception(self, mock_elevenlabs):
        """Playback loop doesn't crash on TTS API errors."""
        mock_client = mock_elevenlabs["client"]
        mock_client.text_to_speech.stream.side_effect = RuntimeError("API error")

        handler = TTSHandler(api_key="key")
        handler.speak("This will fail")
        time.sleep(0.2)

        # Thread should still be alive (not crashed)
        assert handler._thread.is_alive()
        handler.shutdown()
        handler._thread.join(timeout=2)

    def test_thread_is_daemon(self, mock_elevenlabs):
        """The playback thread is a daemon so it won't block exit."""
        handler = TTSHandler(api_key="key")
        assert handler._thread.daemon is True
        handler.shutdown()


# --- Config TTS round-trip tests ---


class TestConfigTTS:
    """Tests for TTS fields in Config."""

    def test_default_tts_fields(self):
        """Config has TTS defaults."""
        config = Config()
        assert config.tts_enabled is False
        assert config.tts_api_key == ""
        assert config.tts_voice_id == "JBFqnCBsd6RMkjVDRZzb"

    def test_tts_from_dict(self):
        """Config reads TTS settings from dict."""
        config = Config.from_dict({
            "tts": {
                "enabled": True,
                "api_key": "sk-test-123",
                "voice_id": "custom-voice",
            },
        })
        assert config.tts_enabled is True
        assert config.tts_api_key == "sk-test-123"
        assert config.tts_voice_id == "custom-voice"

    def test_tts_from_dict_defaults(self):
        """Config uses TTS defaults when tts section missing."""
        config = Config.from_dict({})
        assert config.tts_enabled is False
        assert config.tts_api_key == ""
        assert config.tts_voice_id == "JBFqnCBsd6RMkjVDRZzb"

    def test_tts_to_dict(self):
        """Config serializes TTS fields to dict."""
        config = Config(
            tts_enabled=True,
            tts_api_key="my-key",
            tts_voice_id="my-voice",
        )
        d = config.to_dict()
        assert d["tts"]["enabled"] is True
        assert d["tts"]["api_key"] == "my-key"
        assert d["tts"]["voice_id"] == "my-voice"

    def test_tts_round_trip(self, tmp_path):
        """TTS settings survive save/load cycle."""
        config_path = tmp_path / "config.toml"
        config = Config(
            tts_enabled=True,
            tts_api_key="test-eleven-key",
            tts_voice_id="voice-abc",
        )
        config.save(config_path)

        loaded = Config.load(config_path)
        assert loaded.tts_enabled is True
        assert loaded.tts_api_key == "test-eleven-key"
        assert loaded.tts_voice_id == "voice-abc"


# --- Lazy import safety test ---


class TestLazyImport:
    """Test that missing elevenlabs doesn't crash the app."""

    def test_tts_module_importable_without_elevenlabs(self):
        """The tts module itself can be imported without elevenlabs installed."""
        # split_sentences and the module-level code should work fine
        # Only the TTSHandler constructor actually needs elevenlabs
        from voice_debugger.tts import split_sentences as ss
        assert callable(ss)

    def test_handler_import_error_message(self):
        """TTSHandler gives clear error when elevenlabs missing."""
        # Remove elevenlabs from sys.modules if present and mock ImportError
        saved_modules = {}
        for key in list(sys.modules.keys()):
            if key.startswith("elevenlabs"):
                saved_modules[key] = sys.modules.pop(key)

        try:
            with patch.dict(sys.modules, {"elevenlabs.client": None}):
                with patch(
                    "builtins.__import__",
                    side_effect=ImportError("No module named 'elevenlabs'"),
                ):
                    with pytest.raises(RuntimeError) as exc_info:
                        TTSHandler(api_key="test")
                    assert "pip install" in str(exc_info.value)
        finally:
            sys.modules.update(saved_modules)
