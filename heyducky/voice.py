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
        rms = np.sqrt(np.mean(audio**2))
        return audio if rms > threshold else np.array([], dtype=np.float32)

    frames = audio[: n_frames * frame_length].reshape(n_frames, frame_length)
    rms = np.sqrt(np.mean(frames**2, axis=1))

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
        silence_duration: float = 1.5,
        preloaded_model: WhisperModel | None = None,
    ):
        self.sample_rate = sample_rate
        self.silence_threshold = silence_threshold
        self._model = preloaded_model or WhisperModel(
            whisper_model, device="cpu", compute_type="int8"
        )
        self._is_recording = False
        self._audio_buffer: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()
        self._error: str | None = None
        self._overflow_count: int = 0

        # Auto-stop: trigger after silence_duration seconds of silence,
        # but only after speech has been detected at least once.
        self._max_silence_frames = int(silence_duration * sample_rate / 1024)
        self._silence_frames: int = 0
        self._has_speech: bool = False
        self._silence_triggered: bool = False

    @property
    def last_error(self) -> str | None:
        """Return and clear the last error message."""
        err = self._error
        self._error = None
        return err

    def start_recording(self) -> None:
        """Start recording audio from microphone."""
        if self._is_recording:
            return
        self._audio_buffer = []
        self._overflow_count = 0
        self._silence_frames = 0
        self._has_speech = False
        self._silence_triggered = False
        self._is_recording = True
        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                callback=self._audio_callback,
                blocksize=1024,
            )
            self._stream.start()
        except sd.PortAudioError as e:
            self._is_recording = False
            self._stream = None
            self._error = f"Microphone error: {e}"
        except Exception as e:
            self._is_recording = False
            self._stream = None
            self._error = f"Could not start recording: {e}"

    def stop_recording(self) -> np.ndarray:
        """Stop recording and return the audio buffer.

        Returns:
            1D numpy array of recorded audio, trimmed of silence.
        """
        self._is_recording = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:
                self._error = f"Error stopping recording: {e}"
            finally:
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
        try:
            segments, _info = self._model.transcribe(audio, beam_size=5, language="en")
            text = " ".join(seg.text for seg in segments)
            return text.strip()
        except Exception as e:
            self._error = f"Transcription failed: {e}"
            return ""

    def get_current_rms(self) -> float:
        """Return RMS level of most recent audio chunk, normalized 0.0 to 1.0."""
        with self._lock:
            if not self._audio_buffer:
                return 0.0
            latest = self._audio_buffer[-1]
        rms = float(np.sqrt(np.mean(latest**2)))
        return min(1.0, rms * 10)  # Scale up and clamp to 0-1

    def check_silence_timeout(self) -> bool:
        """Return True (once) if silence auto-stop was triggered.

        Called by the app's voice-level polling timer to know when to
        automatically stop recording after the user finishes speaking.
        """
        if self._silence_triggered:
            self._silence_triggered = False
            return True
        return False

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    def _audio_callback(
        self, indata: np.ndarray, frames: int, time_info: object, status: sd.CallbackFlags
    ) -> None:
        """sounddevice callback - runs in audio thread."""
        if status and status.input_overflow:
            self._overflow_count += 1
            if self._overflow_count >= 10:
                self._error = "Microphone may have disconnected"
        if self._is_recording:
            with self._lock:
                self._audio_buffer.append(indata.copy())

            # Auto-stop silence detection
            rms = float(np.sqrt(np.mean(indata**2)))
            if rms > self.silence_threshold:
                self._has_speech = True
                self._silence_frames = 0
            elif self._has_speech:
                # Only count silence after user has spoken
                self._silence_frames += 1
                if self._silence_frames >= self._max_silence_frames:
                    self._silence_triggered = True
