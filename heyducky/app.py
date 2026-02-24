# heyducky/app.py
"""Main Textual TUI application with tabbed debug interface."""

from __future__ import annotations

import json
import os
from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Header, Footer, TabbedContent, TabPane

from heyducky.chat_history import ChatHistory
from heyducky.config import Config
from heyducky.project import detect_project_root
from heyducky.widgets import (
    SourceView,
    ConversationView,
    VoiceStatusBar,
    VariablesView,
    CallStackView,
    DebugOutputView,
    ProjectTree,
    FolderPickerScreen,
    HistoryScreen,
    SettingsScreen,
    RemoteConnectScreen,
)

AUTOSAVE_PATH = Path.home() / ".config" / "ducky" / "autosave.json"


class HeyDuckyApp(App):
    """Voice-controlled AI debugging assistant."""

    TITLE = "HeyDucky"
    SUB_TITLE = "AI Pair Programming"

    CSS = """
    Screen {
        background: $surface;
    }

    TabbedContent {
        height: 1fr;
    }

    #source-pane {
        height: 1fr;
    }

    #project-tree {
        width: 1fr;
        max-width: 40;
    }

    #source-view {
        width: 3fr;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("space", "toggle_recording", "Talk", show=True, priority=True),
        Binding("1", "show_tab('source')", "Source", show=False, priority=True),
        Binding("2", "show_tab('conversation')", "Chat", show=False, priority=True),
        Binding("3", "show_tab('variables')", "Vars", show=False, priority=True),
        Binding("4", "show_tab('callstack')", "Stack", show=False, priority=True),
        Binding("5", "show_tab('output')", "Output", show=False, priority=True),
        Binding("t", "toggle_tree_focus", "Tree", show=False, priority=True),
        Binding("o", "open_project", "Open", show=False, priority=True),
        Binding("h", "show_history", "History", show=False, priority=True),
        Binding("s", "show_settings", "Settings", show=False, priority=True),
        Binding("e", "export_session", "Export", show=False, priority=True),
        Binding("m", "toggle_tts", "Mute", show=False, priority=True),
        Binding("r", "remote_connect", "Remote", show=False, priority=True),
        Binding("f5", "debug_continue", "Continue", show=False),
        Binding("f10", "debug_step_over", "Step Over", show=False),
        Binding("f11", "debug_step_into", "Step Into", show=False),
    ]

    def __init__(
        self,
        target: str | None = None,
        project: str | None = None,
        attach_host: str | None = None,
        attach_port: int | None = None,
        attach_language: str | None = None,
        path_map: dict[str, str] | None = None,
    ):
        super().__init__()
        self.config = Config.load()
        self._target = target
        self._attach_host = attach_host
        self._attach_port = attach_port
        self._attach_language = attach_language
        self._path_map = path_map or {}
        self._voice = None
        self._orchestrator = None
        self._dap_client = None
        self._debug_session = None
        self._chat_history = ChatHistory()
        self._voice_level_timer = None
        self._tts = None
        self._tts_buffer = ""
        self._thinking_timer = None
        self._got_first_chunk = False
        self._preloaded_whisper = None

        # Pre-load Whisper model on the main thread (before Textual event loop)
        # to avoid "bad value in fds_to_keep" errors when ctranslate2 initializes
        # inside a worker thread on Python 3.13+.
        try:
            from faster_whisper import WhisperModel

            self._preloaded_whisper = WhisperModel(
                self.config.whisper_model, device="cpu", compute_type="int8"
            )
        except Exception:
            pass  # Will fall back to loading in worker thread

        # Determine project root
        if project:
            self._project_root = Path(project).resolve()
        elif target:
            self._project_root = detect_project_root(target)
        else:
            self._project_root = Path.cwd()

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(initial="conversation"):
            with TabPane("Source", id="source"):
                with Horizontal(id="source-pane"):
                    yield ProjectTree(self._project_root, id="project-tree")
                    yield SourceView(id="source-view")
            with TabPane("Conversation", id="conversation"):
                yield ConversationView(id="conversation-view")
            with TabPane("Variables", id="variables"):
                yield VariablesView(id="variables-view")
            with TabPane("Call Stack", id="callstack"):
                yield CallStackView(id="callstack-view")
            with TabPane("Output", id="output"):
                yield DebugOutputView(id="output-view")
        yield VoiceStatusBar(id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize components after mount."""
        # Apply saved theme
        if self.config.theme:
            try:
                self.theme = self.config.theme
            except Exception:
                pass  # Fallback to default if theme not found

        conv = self.query_one("#conversation-view", ConversationView)
        conv.add_system_message("Ready when you are. Press Space and talk to me.")
        conv.add_system_message(
            "1-5 switch tabs | t tree/source | o open project | r remote debug | h history | s settings"
        )
        conv.add_system_message(f"Project: {self._project_root}")
        self._init_components()

        # Restore from auto-save if recent
        self._try_restore_autosave()
        # Start auto-save timer
        self._autosave_timer = self.set_interval(30, self._auto_save_state)

    def on_directory_tree_file_selected(
        self, event: ProjectTree.FileSelected
    ) -> None:
        """Load selected file in source view."""
        source_view = self.query_one("#source-view", SourceView)
        source_view.load_source(str(event.path))

    def action_toggle_tree_focus(self) -> None:
        """Toggle focus between file tree and source view."""
        # Switch to source tab first if not there
        self.query_one(TabbedContent).active = "source"
        tree = self.query_one("#project-tree", ProjectTree)
        source = self.query_one("#source-view", SourceView)
        if tree.has_focus:
            source.focus()
        else:
            tree.focus()

    def action_open_project(self) -> None:
        """Open folder picker to choose a new project root."""
        self.push_screen(
            FolderPickerScreen(start_path=self._project_root),
            callback=self._on_folder_picked,
        )

    def _on_folder_picked(self, result: Path | None) -> None:
        """Handle the result from the folder picker modal."""
        if result is None:
            return

        new_root = result.resolve()
        self._project_root = new_root

        conv = self.query_one("#conversation-view", ConversationView)
        conv.add_system_message(f"Project changed to: {self._project_root}")

        # Update the existing tree to point at the new root
        tree = self.query_one("#project-tree", ProjectTree)
        tree.path = self._project_root
        tree.reload()

        # Update git tool executor project root if it exists
        if self._orchestrator and self._orchestrator._tool_executor:
            self._orchestrator._tool_executor._project_root = str(self._project_root)

        # Switch to source tab to show the new tree
        self.query_one(TabbedContent).active = "source"

    def action_show_history(self) -> None:
        """Open the chat history browser."""
        self.push_screen(
            HistoryScreen(self._chat_history),
            callback=self._on_history_selected,
        )

    def _on_history_selected(self, result: Path | None) -> None:
        """Load a past conversation into the conversation view."""
        if result is None:
            return

        messages = self._chat_history.load_session(result)
        conv = self.query_one("#conversation-view", ConversationView)

        # Switch to conversation tab and show the loaded session
        self.query_one(TabbedContent).active = "conversation"
        conv.clear()
        conv.add_system_message(f"Viewing saved session: {result.stem}")
        conv.add_system_message("---")

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user":
                conv.add_user_message(content)
            elif role == "assistant":
                conv.add_ai_message(content)

        conv.add_system_message("---")
        conv.add_system_message("End of saved session. Press Space to continue chatting.")

    def action_show_settings(self) -> None:
        """Open the settings screen."""
        self.push_screen(
            SettingsScreen(self.config),
            callback=self._on_settings_saved,
        )

    def _on_settings_saved(self, result: Config | None) -> None:
        """Apply and persist updated settings."""
        if result is None:
            return

        old_config = self.config
        result.save()
        self.config = result

        # Apply theme immediately
        if result.theme:
            try:
                self.theme = result.theme
            except Exception:
                pass

        conv = self.query_one("#conversation-view", ConversationView)
        conv.add_system_message("Settings saved.")

        # Rebuild AI provider if key or model changed
        api_key_changed = result.api_key != old_config.api_key
        model_changed = result.ai_model != old_config.ai_model

        if api_key_changed or model_changed:
            api_key = result.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
            if api_key:
                from heyducky.ai.claude import ClaudeProvider
                from heyducky.ai.orchestrator import Orchestrator

                provider = ClaudeProvider(api_key=api_key, model=result.ai_model)

                # Preserve tool executor from old orchestrator
                old_executor = None
                if self._orchestrator:
                    old_executor = self._orchestrator._tool_executor

                self._orchestrator = Orchestrator(
                    provider=provider,
                    compaction_enabled=result.compaction_enabled,
                )
                self._orchestrator._on_compaction = self._on_compaction_occurred
                if old_executor:
                    self._orchestrator._tool_executor = old_executor

                conv.add_system_message(f"AI provider updated: {result.ai_model}")
            else:
                self._orchestrator = None
                conv.add_system_message("No API key set. AI features disabled.")
        else:
            # Just update compaction toggle
            if self._orchestrator:
                self._orchestrator._compaction_enabled = result.compaction_enabled

        # Rebuild voice handler if whisper model or sample rate changed
        whisper_changed = result.whisper_model != old_config.whisper_model
        sample_rate_changed = result.sample_rate != old_config.sample_rate
        threshold_changed = result.silence_threshold != old_config.silence_threshold

        if whisper_changed or sample_rate_changed or threshold_changed:
            self._voice = None
            self._init_voice_worker()
            conv.add_system_message("Voice engine reloading...")

        # Rebuild TTS handler if TTS settings changed
        tts_changed = (
            result.tts_enabled != old_config.tts_enabled
            or result.tts_api_key != old_config.tts_api_key
            or result.tts_voice_id != old_config.tts_voice_id
        )
        if tts_changed:
            if self._tts:
                self._tts.shutdown()
                self._tts = None
            self._init_tts()
            if self._tts:
                conv.add_system_message("TTS enabled.")
            elif result.tts_enabled:
                conv.add_system_message("TTS enabled but no API key set.")
            else:
                conv.add_system_message("TTS disabled.")

    def action_remote_connect(self) -> None:
        """Open the remote debugger connection dialog."""
        if self._debug_session and self._dap_client:
            conv = self.query_one("#conversation-view", ConversationView)
            conv.add_system_message("A debug session is already active. Quit and relaunch to connect to a different target.")
            return
        self.push_screen(
            RemoteConnectScreen(),
            callback=self._on_remote_connect,
        )

    def _on_remote_connect(self, result) -> None:
        """Handle result from the remote connect dialog."""
        if result is None:
            return

        self._attach_host = result.host
        self._attach_port = result.port
        self._attach_language = result.language
        self._path_map = result.path_map
        self._remote_file_port = getattr(result, "file_port", None)

        conv = self.query_one("#conversation-view", ConversationView)
        conv.add_system_message(
            f"Connecting to {result.host}:{result.port} ({result.language})..."
        )
        self._start_remote_debug_session()

    def action_export_session(self) -> None:
        """Export the current conversation as a markdown file."""
        md = self._chat_history.export_current_markdown()
        if not md:
            conv = self.query_one("#conversation-view", ConversationView)
            conv.add_system_message("Nothing to export yet.")
            return
        export_path = Path.home() / "Desktop" / f"debug-session-{self._chat_history.session_id}.md"
        export_path.write_text(md)
        conv = self.query_one("#conversation-view", ConversationView)
        conv.add_system_message(f"Session exported to {export_path}")

    def _auto_save_state(self) -> None:
        """Periodically save orchestrator state for crash recovery."""
        if self._orchestrator and self._orchestrator._history:
            try:
                AUTOSAVE_PATH.parent.mkdir(parents=True, exist_ok=True)
                AUTOSAVE_PATH.write_text(json.dumps(self._orchestrator.get_state()))
            except Exception:
                pass  # Don't crash on autosave failure

    def _try_restore_autosave(self) -> None:
        """Restore AI context from autosave if it's recent (< 1 hour)."""
        if not AUTOSAVE_PATH.exists():
            return
        try:
            import time

            age_seconds = time.time() - AUTOSAVE_PATH.stat().st_mtime
            if age_seconds > 3600:  # Older than 1 hour
                AUTOSAVE_PATH.unlink(missing_ok=True)
                return
            state = json.loads(AUTOSAVE_PATH.read_text())
            if self._orchestrator and state.get("history"):
                self._orchestrator.restore_state(state)
                conv = self.query_one("#conversation-view", ConversationView)
                conv.add_system_message("Previous session context restored.")
                self.query_one(
                    "#status-bar", VoiceStatusBar
                ).session_cost = self._orchestrator.total_cost
                if self._orchestrator.compaction_count:
                    self.query_one(
                        "#status-bar", VoiceStatusBar
                    ).compaction_count = self._orchestrator.compaction_count
        except Exception:
            pass  # Don't crash on restore failure

    async def action_quit(self) -> None:
        """Clean quit -- shutdown TTS and remove autosave file."""
        if self._tts:
            self._tts.shutdown()
            self._tts = None
        try:
            AUTOSAVE_PATH.unlink(missing_ok=True)
        except Exception:
            pass
        await super().action_quit()

    def _init_components(self) -> None:
        """Initialize voice and AI components."""
        self._init_voice_worker()

        api_key = self.config.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if api_key:
            from heyducky.ai.claude import ClaudeProvider
            from heyducky.ai.orchestrator import Orchestrator

            provider = ClaudeProvider(api_key=api_key, model=self.config.ai_model)
            self._orchestrator = Orchestrator(
                provider=provider,
                compaction_enabled=self.config.compaction_enabled,
            )
            self._orchestrator._on_compaction = self._on_compaction_occurred

            # Set up git-only tool executor if no debug session pending
            if not self._target and not self._attach_host:
                from heyducky.debugger.tool_executor import ToolExecutor
                self._orchestrator._tool_executor = ToolExecutor(
                    dap_client=None,
                    project_root=str(self._project_root),
                    path_map=self._path_map,
                )
        else:
            conv = self.query_one("#conversation-view", ConversationView)
            conv.add_system_message(
                "No API key configured. Set ANTHROPIC_API_KEY env var or run with --setup."
            )

        # Initialize TTS if configured
        self._init_tts()

        # Start debug session — local launch or remote attach
        if self._attach_host and self._attach_port:
            self._start_remote_debug_session()
        elif self._target:
            self._start_debug_session()

    @work(thread=True, exclusive=True, group="voice-init")
    def _init_voice_worker(self) -> None:
        """Initialize VoiceHandler, using pre-loaded Whisper model if available."""
        try:
            from heyducky.voice import VoiceHandler

            self._voice = VoiceHandler(
                whisper_model=self.config.whisper_model,
                sample_rate=self.config.sample_rate,
                silence_threshold=self.config.silence_threshold,
                silence_duration=self.config.silence_duration,
                preloaded_model=self._preloaded_whisper,
            )
            self._preloaded_whisper = None  # Hand off ownership
            self.call_from_thread(self._on_voice_ready)
        except Exception as e:
            self.call_from_thread(self._on_voice_error, str(e))

    def _init_tts(self) -> None:
        """Initialize TTS handler if enabled and configured."""
        if self.config.tts_enabled and self.config.tts_api_key:
            try:
                from heyducky.tts import TTSHandler

                self._tts = TTSHandler(
                    api_key=self.config.tts_api_key,
                    voice_id=self.config.tts_voice_id,
                )
            except Exception as e:
                conv = self.query_one("#conversation-view", ConversationView)
                conv.add_system_message(f"TTS init failed: {e}")
                self._tts = None

    def action_toggle_tts(self) -> None:
        """Toggle TTS mute/unmute."""
        if self._tts is None:
            conv = self.query_one("#conversation-view", ConversationView)
            conv.add_system_message("TTS is not configured. Enable it in Settings.")
            return
        new_state = self._tts.toggle()
        label = "unmuted" if new_state else "muted"
        conv = self.query_one("#conversation-view", ConversationView)
        conv.add_system_message(f"TTS {label}.")

    def _on_voice_ready(self) -> None:
        conv = self.query_one("#conversation-view", ConversationView)
        conv.add_system_message("Voice ready. Press Space to talk.")

    def _on_voice_error(self, error: str) -> None:
        conv = self.query_one("#conversation-view", ConversationView)
        conv.add_system_message(f"Voice init failed: {error}")

    def action_show_tab(self, tab_id: str) -> None:
        """Switch to a tab by id."""
        self.query_one(TabbedContent).active = tab_id

    def action_toggle_recording(self) -> None:
        """Toggle voice recording on/off."""
        if self._voice is None:
            conv = self.query_one("#conversation-view", ConversationView)
            conv.add_system_message("Voice not ready yet. Please wait...")
            return

        status = self.query_one("#status-bar", VoiceStatusBar)

        if self._voice.is_recording:
            status.is_recording = False
            status.voice_level = 0.0
            if self._voice_level_timer:
                self._voice_level_timer.stop()
                self._voice_level_timer = None
            self._process_recording()
        else:
            # Clear any stale error before starting
            stale_error = self._voice.last_error
            if stale_error:
                conv = self.query_one("#conversation-view", ConversationView)
                conv.add_system_message(f"Previous error: {stale_error}")

            self._voice.start_recording()

            # Check if start_recording failed
            error = self._voice.last_error
            if error:
                conv = self.query_one("#conversation-view", ConversationView)
                conv.add_system_message(error)
                status.is_recording = False
            else:
                status.is_recording = True
                self._voice_level_timer = self.set_interval(
                    0.1, self._update_voice_level
                )

    def _update_voice_level(self) -> None:
        """Poll current RMS level from voice handler and update status bar."""
        if self._voice and self._voice.is_recording:
            level = self._voice.get_current_rms()
            self.query_one("#status-bar", VoiceStatusBar).voice_level = level

            # Auto-stop: if silence duration exceeded after speech was detected
            if self._voice.check_silence_timeout():
                status = self.query_one("#status-bar", VoiceStatusBar)
                status.is_recording = False
                status.voice_level = 0.0
                if self._voice_level_timer:
                    self._voice_level_timer.stop()
                    self._voice_level_timer = None
                self._process_recording()

    def action_debug_continue(self) -> None:
        """Continue debug execution."""
        if self._dap_client:
            self._run_debug_action("continue_execution")

    def action_debug_step_over(self) -> None:
        """Step over in debugger."""
        if self._dap_client:
            self._run_debug_action("step_over")

    def action_debug_step_into(self) -> None:
        """Step into in debugger."""
        if self._dap_client:
            self._run_debug_action("step_into")

    @work(thread=True, exclusive=True, group="debug-action")
    def _run_debug_action(self, action: str) -> None:
        """Execute a debug action in a worker thread."""
        import asyncio
        client = self._dap_client
        if client is None:
            return
        coro = getattr(client, action)()
        asyncio.run(coro)

    def _build_editor_context(self) -> str:
        """Build a context string from the current source view state.

        Returns a bracket-delimited context block the AI can reference,
        or an empty string if no file is open.  For small files (<=150
        lines) the entire file is included so the AI doesn't need a tool
        call to see it.
        """
        source_view = self.query_one("#source-view", SourceView)
        if not source_view.file_path:
            return ""

        parts = [f"[Editor context: {source_view.file_path}"]

        if source_view.current_line:
            parts.append(f" | line {source_view.current_line}")

        if source_view.breakpoint_lines:
            bp_str = ", ".join(str(ln) for ln in sorted(source_view.breakpoint_lines))
            parts.append(f" | breakpoints: {bp_str}")

        lines = source_view._source_lines
        total = len(lines)
        parts.append(f" | {total} lines]")

        if lines:
            if total <= 150:
                # Small file: include everything
                snippet_lines = []
                for i, line in enumerate(lines, 1):
                    marker = " >> " if i == source_view.current_line else "    "
                    snippet_lines.append(f"{marker}{i:4d} | {line}")
                parts.append("\n")
                parts.append("\n".join(snippet_lines))
            else:
                # Large file: show ~40 lines around current position
                center = (source_view.current_line or 1) - 1
                start = max(0, center - 20)
                end = min(total, center + 21)
                snippet_lines = []
                if start > 0:
                    snippet_lines.append(f"    ... (lines 1-{start} omitted)")
                for i in range(start, end):
                    marker = " >> " if (i + 1) == source_view.current_line else "    "
                    snippet_lines.append(f"{marker}{i + 1:4d} | {lines[i]}")
                if end < total:
                    snippet_lines.append(f"    ... (lines {end + 1}-{total} omitted, use read_source to see more)")
                parts.append("\n")
                parts.append("\n".join(snippet_lines))

        return "".join(parts)

    @work(thread=True, exclusive=True, group="voice-process")
    def _process_recording(self) -> None:
        """Stop recording, transcribe, and send to AI with streaming."""
        audio = self._voice.stop_recording()

        # Show thinking animation while transcribing + waiting for AI
        self.call_from_thread(self._set_ai_thinking)

        # Check for errors during recording/stop
        error = self._voice.last_error
        if error:
            self.call_from_thread(self._show_system_message, error)

        if len(audio) == 0:
            self.call_from_thread(self._show_system_message, "No speech detected.")
            self.call_from_thread(self._set_ai_idle)
            return

        transcript = self._voice.transcribe(audio)

        # Check for transcription errors
        error = self._voice.last_error
        if error:
            self.call_from_thread(self._show_system_message, error)

        if not transcript:
            self.call_from_thread(self._show_system_message, "Could not transcribe audio.")
            self.call_from_thread(self._set_ai_idle)
            return

        self.call_from_thread(self._show_user_message, transcript)

        if self._orchestrator is None:
            self.call_from_thread(self._show_system_message, "No AI provider configured.")
            self.call_from_thread(self._set_ai_idle)
            return

        # Build context-enriched message for the AI
        editor_ctx = self.call_from_thread(self._build_editor_context)
        if editor_ctx:
            ai_message = f"{editor_ctx}\n\n{transcript}"
        else:
            ai_message = transcript

        import asyncio

        async def _stream():
            self.call_from_thread(self._start_ai_stream)

            async for event in self._orchestrator.chat_streaming(ai_message):
                if event.type == "text":
                    self.call_from_thread(self._append_ai_chunk, event.text)
                elif event.type == "tool_call":
                    if event.tool_call:
                        self.call_from_thread(
                            self._show_tool_call,
                            event.tool_call.name,
                            event.tool_call.arguments,
                        )
                elif event.type == "done":
                    full_text = event.response.text if event.response else ""
                    self.call_from_thread(self._finish_ai_stream, full_text)
                    self.call_from_thread(
                        self._update_cost, self._orchestrator.total_cost
                    )

        try:
            asyncio.run(_stream())
        except Exception as e:
            self.call_from_thread(
                self._show_system_message, f"AI error: {e}"
            )
            self.call_from_thread(self._set_ai_idle)

    def _show_user_message(self, text: str) -> None:
        self.query_one("#conversation-view", ConversationView).add_user_message(text)
        self._chat_history.add("user", text)

    def _show_ai_message(self, text: str) -> None:
        self.query_one("#conversation-view", ConversationView).add_ai_message(text)
        self._chat_history.add("assistant", text)

    # --- AI state animation helpers ---

    def _set_ai_thinking(self) -> None:
        """Show animated 'Thinking...' spinner in the status bar."""
        status = self.query_one("#status-bar", VoiceStatusBar)
        status.ai_state = "thinking"
        status.spinner_frame = 0
        self._thinking_timer = self.set_interval(0.12, self._tick_spinner)

    def _set_ai_idle(self) -> None:
        """Reset status bar to idle state and stop spinner."""
        status = self.query_one("#status-bar", VoiceStatusBar)
        status.ai_state = "idle"
        if self._thinking_timer:
            self._thinking_timer.stop()
            self._thinking_timer = None

    def _tick_spinner(self) -> None:
        """Advance the thinking spinner by one frame."""
        status = self.query_one("#status-bar", VoiceStatusBar)
        status.spinner_frame = (status.spinner_frame + 1) % 10

    # --- Streaming AI response ---

    def _start_ai_stream(self) -> None:
        """Begin streaming AI response in the conversation view."""
        self._tts_buffer = ""
        self._got_first_chunk = False
        self.query_one("#conversation-view", ConversationView).start_ai_stream()

    def _append_ai_chunk(self, text: str) -> None:
        """Append a text chunk to the streaming AI response."""
        # Transition from "thinking" to "streaming" on the first chunk
        if not self._got_first_chunk:
            self._got_first_chunk = True
            status = self.query_one("#status-bar", VoiceStatusBar)
            status.ai_state = "streaming"
            if self._thinking_timer:
                self._thinking_timer.stop()
                self._thinking_timer = None

        self.query_one("#conversation-view", ConversationView).append_ai_chunk(text)

        # Sentence-level TTS: buffer text and speak on sentence boundaries
        if self._tts:
            from heyducky.tts import split_sentences

            self._tts_buffer += text
            sentences, self._tts_buffer = split_sentences(self._tts_buffer)
            for sentence in sentences:
                self._tts.speak(sentence)

    def _finish_ai_stream(self, full_text: str) -> None:
        """Finish the streaming AI response and record in chat history."""
        self.query_one("#conversation-view", ConversationView).finish_ai_stream()
        self._chat_history.add("assistant", full_text)

        # Speak any remaining buffered text
        if self._tts and self._tts_buffer.strip():
            self._tts.speak(self._tts_buffer)
        self._tts_buffer = ""

        # Reset status bar to idle
        self._set_ai_idle()

    def _show_system_message(self, text: str) -> None:
        self.query_one("#conversation-view", ConversationView).add_system_message(text)

    def _on_compaction_occurred(self, count: int, token_count: int) -> None:
        """Notify user that conversation was compacted."""
        self.call_from_thread(
            self._show_system_message,
            f"Context compacted ({count}x) — was {token_count:,} tokens. Conversation summary preserved.",
        )
        self.call_from_thread(self._update_compaction_count, count)

    def _update_compaction_count(self, count: int) -> None:
        self.query_one("#status-bar", VoiceStatusBar).compaction_count = count

    def _show_tool_call(self, name: str, args: dict) -> None:
        self.query_one("#conversation-view", ConversationView).add_tool_message(name, args)

    def _update_cost(self, cost: float) -> None:
        self.query_one("#status-bar", VoiceStatusBar).session_cost = cost

    @work(thread=True, exclusive=True, group="debug-session")
    def _start_debug_session(self) -> None:
        """Start a local debug session for the target program."""
        import asyncio
        from heyducky.debugger.session import DebugSession
        from heyducky.debugger.tool_executor import ToolExecutor

        async def run():
            self._debug_session = DebugSession(
                on_state_change=self._on_debug_state_change,
                on_output=self._on_debug_output,
            )
            await self._debug_session.start(self._target)

            if self._orchestrator and self._debug_session.client:
                executor = ToolExecutor(
                    self._debug_session.client,
                    project_root=str(self._project_root),
                    path_map=self._path_map,
                )
                self._orchestrator._tool_executor = executor

            self._dap_client = self._debug_session.client

        try:
            asyncio.run(run())
            self.call_from_thread(
                self._show_system_message,
                f"Debug session started for {self._target}",
            )
        except Exception as e:
            self.call_from_thread(
                self._show_system_message,
                f"Failed to start debug session: {e}",
            )

    @work(thread=True, exclusive=True, group="debug-session")
    def _start_remote_debug_session(self) -> None:
        """Attach to a remote debug adapter over TCP."""
        import asyncio
        from heyducky.debugger.session import DebugSession
        from heyducky.debugger.tool_executor import ToolExecutor

        host = self._attach_host
        port = self._attach_port
        lang = self._attach_language
        file_port = getattr(self, "_remote_file_port", None)

        async def run():
            # Connect to the remote file server if a file port was provided
            remote_files = None
            if file_port:
                from heyducky.remote.file_client import RemoteFileClient
                remote_files = RemoteFileClient(host, file_port)
                await remote_files.connect()
                remote_root = await remote_files.ping()
                if remote_root:
                    self.call_from_thread(
                        self._show_system_message,
                        f"File server connected (remote root: {remote_root})",
                    )

            self._debug_session = DebugSession(
                on_state_change=self._on_debug_state_change,
                on_output=self._on_debug_output,
            )
            await self._debug_session.start_attach(
                host, port, lang, path_map=self._path_map
            )

            if self._orchestrator and self._debug_session.client:
                executor = ToolExecutor(
                    self._debug_session.client,
                    project_root=str(self._project_root),
                    path_map=self._path_map,
                    dap_source_fallback=True,
                    remote_files=remote_files,
                )
                self._orchestrator._tool_executor = executor

            self._dap_client = self._debug_session.client

        try:
            asyncio.run(run())
            self.call_from_thread(
                self._show_system_message,
                f"Attached to remote debugger at {host}:{port} ({lang})",
            )
        except Exception as e:
            self.call_from_thread(
                self._show_system_message,
                f"Failed to attach to {host}:{port}: {e}",
            )

    async def _on_debug_state_change(self, state: str, frames: list) -> None:
        """Handle debugger state changes (called from async context)."""
        self.call_from_thread(self._update_debug_state, state, frames)

    async def _on_debug_output(self, category: str, text: str) -> None:
        """Handle program output."""
        self.call_from_thread(self._add_debug_output, category, text)

    def _translate_remote_path(self, remote_path: str) -> str:
        """Apply path mapping for remote debugging sessions."""
        for remote_prefix, local_prefix in self._path_map.items():
            if remote_path.startswith(remote_prefix):
                return remote_path.replace(remote_prefix, local_prefix, 1)
        return remote_path

    def _update_debug_state(self, state: str, frames: list) -> None:
        """Update UI with debug state."""
        status = self.query_one("#status-bar", VoiceStatusBar)
        status.debug_state = state

        if state == "paused" and frames:
            top = frames[0]
            source = top.get("source", {})
            file_path = source.get("path", "") if isinstance(source, dict) else ""
            line = top.get("line", 0)

            if self._path_map:
                file_path = self._translate_remote_path(file_path)

            status.debug_file = file_path
            status.debug_line = line

            # Update source view
            source_view = self.query_one("#source-view", SourceView)
            source_view.load_source(file_path)
            source_view.set_current_line(line)

            # Update call stack
            stack_view = self.query_one("#callstack-view", CallStackView)
            stack_view.update_frames(frames)

            # Sync file tree
            tree = self.query_one("#project-tree", ProjectTree)
            if not tree.reveal_path(file_path):
                conv = self.query_one("#conversation-view", ConversationView)
                conv.add_system_message(
                    f"Stepped into: {Path(file_path).name} (external)"
                )

            # Switch to source tab
            self.query_one(TabbedContent).active = "source"

    def _add_debug_output(self, category: str, text: str) -> None:
        """Add program output to the output panel."""
        output = self.query_one("#output-view", DebugOutputView)
        if category == "stderr":
            output.add_stderr(text)
        else:
            output.add_stdout(text)
