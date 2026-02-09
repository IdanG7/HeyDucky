# voice_debugger/app.py
"""Main Textual TUI application with tabbed debug interface."""

from __future__ import annotations

import os
from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Header, Footer, TabbedContent, TabPane, Input

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
        Binding("q", "quit", "Quit"),
        Binding("space", "toggle_recording", "Talk", show=True),
        Binding("1", "show_tab('source')", "Source", show=False),
        Binding("2", "show_tab('conversation')", "Chat", show=False),
        Binding("3", "show_tab('variables')", "Vars", show=False),
        Binding("4", "show_tab('callstack')", "Stack", show=False),
        Binding("5", "show_tab('output')", "Output", show=False),
        Binding("t", "toggle_tree_focus", "Tree", show=False),
        Binding("o", "open_project", "Open", show=False),
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
        conv = self.query_one("#conversation-view", ConversationView)
        conv.add_system_message("Welcome to Voice Debugger. Press Space to talk.")
        conv.add_system_message(
            "Tabs: 1=Source 2=Chat 3=Vars 4=Stack 5=Output | "
            "t=Tree focus | o=Open project"
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
        """Prompt for a project folder path and switch to it."""
        conv = self.query_one("#conversation-view", ConversationView)
        # Switch to conversation tab to show the input
        self.query_one(TabbedContent).active = "conversation"
        conv.add_system_message(
            f"Current project: {self._project_root}\n"
            "Type a new folder path below and press Enter (or Escape to cancel):"
        )
        # Mount an input widget inside the conversation tab
        input_widget = Input(
            placeholder="Enter project folder path...",
            id="project-path-input",
        )
        conv.mount(input_widget)
        input_widget.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle submitted project path from the input widget."""
        if event.input.id != "project-path-input":
            return
        path_str = event.value.strip()
        event.input.remove()

        conv = self.query_one("#conversation-view", ConversationView)

        if not path_str:
            conv.add_system_message("Cancelled.")
            return

        new_root = Path(path_str).expanduser().resolve()
        if not new_root.is_dir():
            conv.add_system_message(f"Not a valid directory: {new_root}")
            return

        self._project_root = new_root
        conv.add_system_message(f"Project changed to: {self._project_root}")

        # Replace the tree widget with a new one pointing at the new root
        old_tree = self.query_one("#project-tree", ProjectTree)
        new_tree = ProjectTree(self._project_root, id="project-tree")
        old_tree.replace(new_tree)

        # Update git tool executor project root if it exists
        if self._orchestrator and self._orchestrator._tool_executor:
            self._orchestrator._tool_executor._project_root = str(self._project_root)

        # Switch to source tab to show the new tree
        self.query_one(TabbedContent).active = "source"

    def _init_components(self) -> None:
        """Initialize voice and AI components."""
        self._init_voice_worker()

        api_key = self.config.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if api_key:
            from voice_debugger.ai.claude import ClaudeProvider
            from voice_debugger.ai.orchestrator import Orchestrator

            provider = ClaudeProvider(api_key=api_key, model=self.config.ai_model)
            self._orchestrator = Orchestrator(provider=provider)

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
        """Stop recording, transcribe, and send to AI."""
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
        response = asyncio.run(self._orchestrator.chat(transcript))

        # Handle tool calls
        for tc in response.tool_calls:
            self.call_from_thread(self._show_tool_call, tc.name, tc.arguments)

        self.call_from_thread(self._show_ai_message, response.text)
        self.call_from_thread(self._update_cost, self._orchestrator.total_cost)

    def _show_user_message(self, text: str) -> None:
        self.query_one("#conversation-view", ConversationView).add_user_message(text)

    def _show_ai_message(self, text: str) -> None:
        self.query_one("#conversation-view", ConversationView).add_ai_message(text)

    def _show_system_message(self, text: str) -> None:
        self.query_one("#conversation-view", ConversationView).add_system_message(text)

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
