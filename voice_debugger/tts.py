"""Text-to-speech handler using ElevenLabs SDK."""

from __future__ import annotations

import logging
import queue
import re
import threading

logger = logging.getLogger(__name__)


# Sentence boundary pattern: period, exclamation, or question mark
# followed by a space or end of string, or a newline.
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+|\n")


def split_sentences(text: str) -> tuple[list[str], str]:
    """Split text into complete sentences and a remainder.

    Returns a tuple of (complete_sentences, leftover_text).
    A sentence is considered complete when followed by whitespace after
    sentence-ending punctuation (. ! ?) or at a newline boundary.
    """
    parts = _SENTENCE_BOUNDARY.split(text)
    if len(parts) <= 1:
        # No sentence boundary found -- everything is remainder
        return [], text

    # All parts except the last are complete sentences
    sentences = [s for s in parts[:-1] if s.strip()]
    remainder = parts[-1]
    return sentences, remainder


class TTSHandler:
    """Streams text to ElevenLabs TTS and plays audio in a background thread.

    ElevenLabs is an optional dependency. The constructor will raise
    a RuntimeError with a helpful message if the package is not installed.
    """

    def __init__(
        self,
        api_key: str,
        voice_id: str = "JBFqnCBsd6RMkjVDRZzb",
        model_id: str = "eleven_multilingual_v2",
    ):
        try:
            from elevenlabs.client import ElevenLabs
        except ImportError:
            raise RuntimeError(
                "ElevenLabs SDK is not installed. "
                "Install it with: pip install 'voice-debugger[tts]'"
            )

        self._client = ElevenLabs(api_key=api_key)
        self._voice_id = voice_id
        self._model_id = model_id
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._enabled = True
        self._thread = threading.Thread(target=self._playback_loop, daemon=True)
        self._thread.start()

    def speak(self, text: str) -> None:
        """Enqueue text for TTS playback. No-op if muted."""
        if self._enabled and text.strip():
            self._queue.put(text)

    def stop(self) -> None:
        """Drain the playback queue, discarding pending items."""
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def toggle(self) -> bool:
        """Flip enabled state. Returns the new state (True = unmuted)."""
        self._enabled = not self._enabled
        if not self._enabled:
            self.stop()
        return self._enabled

    def shutdown(self) -> None:
        """Signal the playback thread to exit."""
        self.stop()
        self._queue.put(None)

    def _playback_loop(self) -> None:
        """Background thread: pull text from queue and play via ElevenLabs."""
        from elevenlabs import stream as play_stream

        while True:
            text = self._queue.get()
            if text is None:
                break
            try:
                audio = self._client.text_to_speech.convert_as_stream(
                    text=text,
                    voice_id=self._voice_id,
                    model_id=self._model_id,
                )
                play_stream(audio)
            except Exception:
                logger.debug("TTS playback error", exc_info=True)
