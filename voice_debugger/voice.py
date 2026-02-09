"""Voice input handler - recording and transcription."""

from __future__ import annotations

import threading

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel


def trim_silence(
    audio: np.ndarray,
    threshold: float = 0.02,
    sr: int = 16000,
    frame_length: int = 1024,
) -> np.ndarray:
    """Trim leading and trailing silence from audio.

    Args:
        audio: 1D float32 audio array.
        threshold: RMS threshold below which frames are considered silent.
        sr: Sample rate (unused but kept for API clarity).
        frame_length: Number of samples per analysis frame.

    Returns:
        Trimmed audio array, or empty array if all silent.
    """
    if len(audio) == 0:
        return audio

    # Calculate RMS energy per frame
    n_frames = len(audio) // frame_length
    if n_frames == 0:
        rms = np.sqrt(np.mean(audio ** 2))
        return audio if rms > threshold else np.array([], dtype=np.float32)

    frames = audio[: n_frames * frame_length].reshape(n_frames, frame_length)
    rms = np.sqrt(np.mean(frames ** 2, axis=1))

    # Find first and last frames above threshold
    active = np.where(rms > threshold)[0]
    if len(active) == 0:
        return np.array([], dtype=np.float32)

    start = active[0] * frame_length
    end = min((active[-1] + 1) * frame_length, len(audio))
    return audio[start:end]


class VoiceHandler:
    """Handles audio recording and speech-to-text transcription."""

    def __init__(
        self,
        whisper_model: str = "base.en",
        sample_rate: int = 16000,
        silence_threshold: float = 0.02,
    ):
        self.sample_rate = sample_rate
        self.silence_threshold = silence_threshold
        self._model = WhisperModel(whisper_model, device="cpu", compute_type="int8")
        self._is_recording = False
        self._audio_buffer: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()

    def start_recording(self) -> None:
        """Start recording audio from microphone."""
        if self._is_recording:
            return
        self._audio_buffer = []
        self._is_recording = True
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            callback=self._audio_callback,
            blocksize=1024,
        )
        self._stream.start()

    def stop_recording(self) -> np.ndarray:
        """Stop recording and return the audio buffer.

        Returns:
            1D numpy array of recorded audio, trimmed of silence.
        """
        self._is_recording = False
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        with self._lock:
            if not self._audio_buffer:
                return np.array([], dtype=np.float32)
            audio = np.concatenate(self._audio_buffer).flatten()
            self._audio_buffer = []

        return trim_silence(audio, threshold=self.silence_threshold, sr=self.sample_rate)

    def transcribe(self, audio: np.ndarray) -> str:
        """Transcribe audio to text using Whisper.

        Args:
            audio: 1D float32 audio array at self.sample_rate.

        Returns:
            Transcribed text, stripped of whitespace.
        """
        if len(audio) == 0:
            return ""
        segments, _info = self._model.transcribe(audio, beam_size=5, language="en")
        text = " ".join(seg.text for seg in segments)
        return text.strip()

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    def _audio_callback(
        self, indata: np.ndarray, frames: int, time_info: object, status: object
    ) -> None:
        """sounddevice callback - runs in audio thread."""
        if status:
            pass  # Could log status warnings
        if self._is_recording:
            with self._lock:
                self._audio_buffer.append(indata.copy())
