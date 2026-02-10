# voice_debugger/app.py
"""Main Textual TUI application with tabbed debug interface."""

from __future__ import annotations

import os
from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Header, Footer, TabbedContent, TabPane

from voice_debugger.chat_history import ChatHistory
from voice_debugger.config import Config
from voice_debugger.project import detect_project_root
from voice_debugger.widgets import (
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
)


class VoiceDebuggerApp(App):
    """Voice-controlled AI debugging assistant."""

    TITLE = "Voice Debugger"
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
        Binding("f5", "debug_continue", "Continue", show=False),
        Binding("f10", "debug_step_over", "Step Over", show=False),
        Binding("f11", "debug_step_into", "Step Into", show=False),
    ]

    def __init__(self, target: str | None = None, project: str | None = None):
        super().__init__()
        self.config = Config.load()
        self._target = target
        self._voice = None
        self._orchestrator = None
        self._dap_client = None
        self._debug_session = None
        self._chat_history = ChatHistory()

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
            "1-5 switch tabs | t tree/source | o open project | h history | s settings"
        )
        conv.add_system_message(f"Project: {self._project_root}")
        self._init_components()

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

        # Update orchestrator compaction toggle if it exists
        if self._orchestrator:
            self._orchestrator._compaction_enabled = result.compaction_enabled

    def _init_components(self) -> None:
        """Initialize voice and AI components."""
        self._init_voice_worker()

        api_key = self.config.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if api_key:
            from voice_debugger.ai.claude import ClaudeProvider
            from voice_debugger.ai.orchestrator import Orchestrator

            provider = ClaudeProvider(api_key=api_key, model=self.config.ai_model)
            self._orchestrator = Orchestrator(
                provider=provider,
                compaction_enabled=self.config.compaction_enabled,
            )
            self._orchestrator._on_compaction = self._on_compaction_occurred

            # Set up git-only tool executor if no debug session
            if not self._target:
                from voice_debugger.debugger.tool_executor import ToolExecutor
                self._orchestrator._tool_executor = ToolExecutor(
                    dap_client=None,
                    project_root=str(self._project_root),
                )
        else:
            conv = self.query_one("#conversation-view", ConversationView)
            conv.add_system_message(
                "No API key configured. Set ANTHROPIC_API_KEY env var or run with --setup."
            )

        # Start debug session if target provided
        if self._target:
            self._start_debug_session()

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
            self._process_recording()
        else:
            self._voice.start_recording()
            status.is_recording = True

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

    @work(thread=True, exclusive=True, group="voice-process")
    def _process_recording(self) -> None:
        """Stop recording, transcribe, and send to AI with streaming."""
        audio = self._voice.stop_recording()
        if len(audio) == 0:
            self.call_from_thread(self._show_system_message, "No speech detected.")
            return

        transcript = self._voice.transcribe(audio)
        if not transcript:
            self.call_from_thread(self._show_system_message, "Could not transcribe audio.")
            return

        self.call_from_thread(self._show_user_message, transcript)

        if self._orchestrator is None:
            self.call_from_thread(self._show_system_message, "No AI provider configured.")
            return

        import asyncio

        async def _stream():
            self.call_from_thread(self._start_ai_stream)

            async for event in self._orchestrator.chat_streaming(transcript):
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

        asyncio.run(_stream())

    def _show_user_message(self, text: str) -> None:
        self.query_one("#conversation-view", ConversationView).add_user_message(text)
        self._chat_history.add("user", text)

    def _show_ai_message(self, text: str) -> None:
        self.query_one("#conversation-view", ConversationView).add_ai_message(text)
        self._chat_history.add("assistant", text)

    def _start_ai_stream(self) -> None:
        """Begin streaming AI response in the conversation view."""
        self.query_one("#conversation-view", ConversationView).start_ai_stream()

    def _append_ai_chunk(self, text: str) -> None:
        """Append a text chunk to the streaming AI response."""
        self.query_one("#conversation-view", ConversationView).append_ai_chunk(text)

    def _finish_ai_stream(self, full_text: str) -> None:
        """Finish the streaming AI response and record in chat history."""
        self.query_one("#conversation-view", ConversationView).finish_ai_stream()
        self._chat_history.add("assistant", full_text)

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
        """Start a debug session for the target program."""
        import asyncio
        from voice_debugger.debugger.session import DebugSession
        from voice_debugger.debugger.tool_executor import ToolExecutor

        async def run():
            self._debug_session = DebugSession(
                on_state_change=self._on_debug_state_change,
                on_output=self._on_debug_output,
            )
            await self._debug_session.start(self._target)

            # Connect tool executor to orchestrator
            if self._orchestrator and self._debug_session.client:
                executor = ToolExecutor(
                    self._debug_session.client,
                    project_root=str(self._project_root),
                )
                self._orchestrator._tool_executor = executor

            # Also expose the DAP client for keybinding actions
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

    async def _on_debug_state_change(self, state: str, frames: list) -> None:
        """Handle debugger state changes (called from async context)."""
        self.call_from_thread(self._update_debug_state, state, frames)

    async def _on_debug_output(self, category: str, text: str) -> None:
        """Handle program output."""
        self.call_from_thread(self._add_debug_output, category, text)

    def _update_debug_state(self, state: str, frames: list) -> None:
        """Update UI with debug state."""
        status = self.query_one("#status-bar", VoiceStatusBar)
        status.debug_state = state

        if state == "paused" and frames:
            top = frames[0]
            source = top.get("source", {})
            file_path = source.get("path", "") if isinstance(source, dict) else ""
            line = top.get("line", 0)

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
            try:
                tree = self.query_one("#project-tree", ProjectTree)
                tree.reveal_path(file_path)
            except Exception:
                pass  # Tree may not be ready

            # Switch to source tab
            self.query_one(TabbedContent).active = "source"

    def _add_debug_output(self, category: str, text: str) -> None:
        """Add program output to the output panel."""
        output = self.query_one("#output-view", DebugOutputView)
        if category == "stderr":
            output.add_stderr(text)
        else:
            output.add_stdout(text)
