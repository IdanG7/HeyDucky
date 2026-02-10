"""Tests for voice handler."""

import numpy as np
import sounddevice as sd
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
    with patch("voice_debugger.voice.WhisperModel"):
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


# --- Error handling tests ---


def test_last_error_set_get_clear():
    """last_error returns the error and clears it on read."""
    with patch("voice_debugger.voice.WhisperModel"):
        handler = VoiceHandler(whisper_model="tiny.en")

        # Initially no error
        assert handler.last_error is None

        # Set an error internally
        handler._error = "something went wrong"
        assert handler.last_error == "something went wrong"

        # Reading again should return None (cleared)
        assert handler.last_error is None


def test_start_recording_port_audio_error():
    """start_recording sets last_error on sd.PortAudioError."""
    with patch("voice_debugger.voice.WhisperModel"):
        handler = VoiceHandler(whisper_model="tiny.en")

    with patch("voice_debugger.voice.sd.InputStream", side_effect=sd.PortAudioError("No device")):
        handler.start_recording()

    assert handler._is_recording is False
    assert handler._stream is None
    error = handler.last_error
    assert error is not None
    assert "Microphone error" in error
    assert "No device" in error


def test_start_recording_general_exception():
    """start_recording sets last_error on generic Exception."""
    with patch("voice_debugger.voice.WhisperModel"):
        handler = VoiceHandler(whisper_model="tiny.en")

    with patch("voice_debugger.voice.sd.InputStream", side_effect=RuntimeError("unknown")):
        handler.start_recording()

    assert handler._is_recording is False
    error = handler.last_error
    assert error is not None
    assert "Could not start recording" in error


def test_transcribe_exception_sets_error():
    """transcribe returns '' and sets last_error on model failure."""
    with patch("voice_debugger.voice.WhisperModel") as mock_whisper_cls:
        mock_model = MagicMock()
        mock_model.transcribe.side_effect = RuntimeError("model crashed")
        mock_whisper_cls.return_value = mock_model

        handler = VoiceHandler(whisper_model="tiny.en")
        audio = np.random.randn(16000).astype(np.float32) * 0.5
        result = handler.transcribe(audio)

        assert result == ""
        error = handler.last_error
        assert error is not None
        assert "Transcription failed" in error
        assert "model crashed" in error


def test_audio_callback_overflow_tracking():
    """_audio_callback sets error after 10+ overflow events."""
    with patch("voice_debugger.voice.WhisperModel"):
        handler = VoiceHandler(whisper_model="tiny.en")

    handler._is_recording = True
    indata = np.zeros((1024, 1), dtype=np.float32)

    # Create a mock status with input_overflow
    overflow_status = MagicMock(spec=sd.CallbackFlags)
    overflow_status.input_overflow = True
    # Make it truthy
    overflow_status.__bool__ = lambda self: True

    # Fire 9 overflows - should not set error yet
    for _ in range(9):
        handler._audio_callback(indata, 1024, {}, overflow_status)

    assert handler._overflow_count == 9
    assert handler._error is None

    # 10th overflow should trigger the error
    handler._audio_callback(indata, 1024, {}, overflow_status)
    assert handler._overflow_count == 10
    assert handler._error == "Microphone may have disconnected"


def test_audio_callback_no_overflow_no_error():
    """_audio_callback does not increment overflow for normal status."""
    with patch("voice_debugger.voice.WhisperModel"):
        handler = VoiceHandler(whisper_model="tiny.en")

    handler._is_recording = True
    indata = np.zeros((1024, 1), dtype=np.float32)

    # Normal status (no overflow) - use a falsy status
    no_status = MagicMock(spec=sd.CallbackFlags)
    no_status.__bool__ = lambda self: False

    handler._audio_callback(indata, 1024, {}, no_status)
    assert handler._overflow_count == 0
    assert handler._error is None


def test_stop_recording_stream_error():
    """stop_recording sets last_error if stream.stop() raises."""
    with patch("voice_debugger.voice.WhisperModel"):
        handler = VoiceHandler(whisper_model="tiny.en")

    mock_stream = MagicMock()
    mock_stream.stop.side_effect = RuntimeError("device lost")
    handler._stream = mock_stream
    handler._is_recording = True

    audio = handler.stop_recording()

    # Should still return empty array (no audio buffered)
    assert len(audio) == 0
    # Stream should be cleaned up
    assert handler._stream is None
    # Error should be set
    error = handler.last_error
    assert error is not None
    assert "Error stopping recording" in error


# --- RMS level tests ---


def test_get_current_rms_empty_buffer():
    """get_current_rms returns 0.0 when buffer is empty."""
    with patch("voice_debugger.voice.WhisperModel"):
        handler = VoiceHandler(whisper_model="tiny.en")
        assert handler.get_current_rms() == 0.0


def test_get_current_rms_positive_with_audio():
    """get_current_rms returns a positive value with audio data in buffer."""
    with patch("voice_debugger.voice.WhisperModel"):
        handler = VoiceHandler(whisper_model="tiny.en")
        # Simulate audio data in the buffer
        audio_chunk = np.random.randn(1024).astype(np.float32) * 0.1
        handler._audio_buffer.append(audio_chunk)
        rms = handler.get_current_rms()
        assert rms > 0.0


def test_get_current_rms_clamped_to_one():
    """get_current_rms is clamped to max 1.0 for very loud audio."""
    with patch("voice_debugger.voice.WhisperModel"):
        handler = VoiceHandler(whisper_model="tiny.en")
        # Very loud audio chunk (amplitude 5.0) -- rms*10 will exceed 1.0
        loud_chunk = np.ones(1024, dtype=np.float32) * 5.0
        handler._audio_buffer.append(loud_chunk)
        rms = handler.get_current_rms()
        assert rms == 1.0


def test_get_current_rms_uses_latest_buffer():
    """get_current_rms uses the latest (most recent) buffer entry."""
    with patch("voice_debugger.voice.WhisperModel"):
        handler = VoiceHandler(whisper_model="tiny.en")
        # First chunk: silence
        silent_chunk = np.zeros(1024, dtype=np.float32)
        # Second chunk: audible signal
        loud_chunk = np.ones(1024, dtype=np.float32) * 0.5
        handler._audio_buffer.append(silent_chunk)
        handler._audio_buffer.append(loud_chunk)
        rms = handler.get_current_rms()
        # Should reflect the loud chunk, not the silent one
        assert rms > 0.0
