# voice_debugger/app.py
"""Main Textual TUI application."""

from __future__ import annotations

import os

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.widgets import Header, Footer
from textual.worker import Worker, get_current_worker

from voice_debugger.config import Config
from voice_debugger.widgets import SourceView, ConversationView, VoiceStatusBar


class VoiceDebuggerApp(App):
    """Voice-controlled AI debugging assistant."""

    TITLE = "Voice Debugger"
    SUB_TITLE = "AI Pair Programming"

    CSS = """
    Screen {
        background: $surface;
    }

    #main-container {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("space", "toggle_recording", "Talk", show=True),
    ]

    def __init__(self):
        super().__init__()
        self.config = Config.load()
        self._voice = None
        self._orchestrator = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            SourceView(id="source-view"),
            ConversationView(id="conversation"),
            VoiceStatusBar(id="status-bar"),
            id="main-container",
        )
        yield Footer()

    def on_mount(self) -> None:
        """Initialize components after mount."""
        conv = self.query_one("#conversation", ConversationView)
        conv.add_system_message("Welcome to Voice Debugger. Press Space to talk.")

        # Lazy-load heavy components
        self._init_components()

    def _init_components(self) -> None:
        """Initialize voice and AI components."""
        # Initialize voice handler in background
        self._init_voice_worker()

        # Initialize AI
        api_key = self.config.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if api_key:
            from voice_debugger.ai.claude import ClaudeProvider
            from voice_debugger.ai.orchestrator import Orchestrator

            provider = ClaudeProvider(api_key=api_key, model=self.config.ai_model)
            self._orchestrator = Orchestrator(provider=provider)
        else:
            conv = self.query_one("#conversation", ConversationView)
            conv.add_system_message(
                "No API key configured. Set ANTHROPIC_API_KEY env var or run with --setup."
            )

    @work(thread=True, exclusive=True, group="voice-init")
    def _init_voice_worker(self) -> None:
        """Load Whisper model in background thread."""
        try:
            from voice_debugger.voice import VoiceHandler

            self._voice = VoiceHandler(
                whisper_model=self.config.whisper_model,
                sample_rate=self.config.sample_rate,
                silence_threshold=self.config.silence_threshold,
            )
            self.call_from_thread(self._on_voice_ready)
        except Exception as e:
            self.call_from_thread(self._on_voice_error, str(e))

    def _on_voice_ready(self) -> None:
        conv = self.query_one("#conversation", ConversationView)
        conv.add_system_message("Voice ready. Press Space to talk.")

    def _on_voice_error(self, error: str) -> None:
        conv = self.query_one("#conversation", ConversationView)
        conv.add_system_message(f"Voice init failed: {error}")

    def action_toggle_recording(self) -> None:
        """Toggle voice recording on/off."""
        if self._voice is None:
            conv = self.query_one("#conversation", ConversationView)
            conv.add_system_message("Voice not ready yet. Please wait...")
            return

        status = self.query_one("#status-bar", VoiceStatusBar)

        if self._voice.is_recording:
            # Stop recording and process
            status.is_recording = False
            self._process_recording()
        else:
            # Start recording
            self._voice.start_recording()
            status.is_recording = True

    @work(thread=True, exclusive=True, group="voice-process")
    def _process_recording(self) -> None:
        """Stop recording, transcribe, and send to AI."""
        audio = self._voice.stop_recording()
        if len(audio) == 0:
            self.call_from_thread(self._show_system_message, "No speech detected.")
            return

        # Transcribe
        transcript = self._voice.transcribe(audio)
        if not transcript:
            self.call_from_thread(self._show_system_message, "Could not transcribe audio.")
            return

        # Show user message
        self.call_from_thread(self._show_user_message, transcript)

        # Send to AI
        if self._orchestrator is None:
            self.call_from_thread(
                self._show_system_message, "No AI provider configured."
            )
            return

        import asyncio
        loop = asyncio.new_event_loop()
        try:
            response = loop.run_until_complete(self._orchestrator.chat(transcript))
        finally:
            loop.close()

        # Show tool calls if any
        for tc in response.tool_calls:
            self.call_from_thread(self._show_tool_call, tc.name, tc.arguments)

        # Show AI response
        self.call_from_thread(self._show_ai_message, response.text)

        # Update cost
        self.call_from_thread(self._update_cost, self._orchestrator.total_cost)

    def _show_user_message(self, text: str) -> None:
        conv = self.query_one("#conversation", ConversationView)
        conv.add_user_message(text)

    def _show_ai_message(self, text: str) -> None:
        conv = self.query_one("#conversation", ConversationView)
        conv.add_ai_message(text)

    def _show_system_message(self, text: str) -> None:
        conv = self.query_one("#conversation", ConversationView)
        conv.add_system_message(text)

    def _show_tool_call(self, name: str, args: dict) -> None:
        conv = self.query_one("#conversation", ConversationView)
        conv.add_tool_message(name, args)

    def _update_cost(self, cost: float) -> None:
        status = self.query_one("#status-bar", VoiceStatusBar)
        status.session_cost = cost
