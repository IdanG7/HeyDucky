# voice_debugger/widgets/settings_screen.py
"""Modal settings screen for user configuration."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Collapsible, Input, Label, Select, Switch

from voice_debugger.config import Config


class SettingsScreen(ModalScreen[Config | None]):
    """Settings screen that returns updated Config or None if cancelled."""

    DEFAULT_CSS = """
    SettingsScreen {
        align: center middle;
    }

    #settings-container {
        width: 70;
        height: 85%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
        overflow-y: auto;
    }

    #settings-title {
        text-align: center;
        text-style: bold;
        width: 100%;
        margin-bottom: 1;
    }

    .settings-label {
        margin-top: 1;
        margin-bottom: 0;
    }

    .settings-hint {
        color: $text-muted;
        margin-bottom: 1;
    }

    #settings-buttons {
        margin-top: 2;
        height: auto;
        align: center middle;
    }

    #settings-buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    def __init__(self, config: Config):
        super().__init__()
        self._config = config

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-container"):
            yield Label("Settings", id="settings-title")

            with Collapsible(title="AI Configuration", collapsed=False):
                yield Label("API Key:", classes="settings-label")
                yield Input(
                    value=self._config.api_key,
                    password=True,
                    placeholder="sk-ant-...",
                    id="setting-api-key",
                )
                yield Label(
                    "Your Anthropic API key. Stored locally.",
                    classes="settings-hint",
                )

                yield Label("Model:", classes="settings-label")
                yield Select(
                    [
                        ("Claude Sonnet 4.5", "claude-sonnet-4-5-20250929"),
                        ("Claude Haiku 3.5", "claude-haiku-3-5-20241022"),
                    ],
                    value=self._config.ai_model,
                    id="setting-model",
                    allow_blank=False,
                )

                yield Label("Auto-Compaction:", classes="settings-label")
                yield Switch(
                    value=self._config.compaction_enabled,
                    id="setting-compaction",
                )
                yield Label(
                    "Automatically summarize long conversations to stay within context limits.",
                    classes="settings-hint",
                )

                yield Label("Compaction Threshold (tokens):", classes="settings-label")
                yield Input(
                    value=str(self._config.compaction_threshold),
                    id="setting-compaction-threshold",
                    type="integer",
                )
                yield Label(
                    "Compact when conversation exceeds this many tokens. Default: 100,000.",
                    classes="settings-hint",
                )

            with Collapsible(title="Voice Configuration"):
                yield Label("Whisper Model:", classes="settings-label")
                yield Select(
                    [
                        ("tiny.en (fastest, least accurate)", "tiny.en"),
                        ("base.en (balanced)", "base.en"),
                        ("small.en (best quality, slower)", "small.en"),
                    ],
                    value=self._config.whisper_model,
                    id="setting-whisper",
                    allow_blank=False,
                )

                yield Label("Silence Threshold:", classes="settings-label")
                yield Input(
                    value=str(self._config.silence_threshold),
                    id="setting-silence-threshold",
                )
                yield Label(
                    "Volume level below which audio is considered silence. Default: 0.02.",
                    classes="settings-hint",
                )

                yield Label("Silence Duration (seconds):", classes="settings-label")
                yield Input(
                    value=str(self._config.silence_duration),
                    id="setting-silence-duration",
                )
                yield Label(
                    "How long silence must last before stopping recording. Default: 1.5s.",
                    classes="settings-hint",
                )

            with Horizontal(id="settings-buttons"):
                yield Button("Save", variant="primary", id="settings-save")
                yield Button("Cancel", variant="default", id="settings-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "settings-save":
            self._save_and_dismiss()
        elif event.button.id == "settings-cancel":
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _save_and_dismiss(self) -> None:
        """Read all form values, build a new Config, and dismiss."""
        try:
            new_config = Config(
                ai_provider=self._config.ai_provider,
                ai_model=self.query_one("#setting-model", Select).value,
                api_key=self.query_one("#setting-api-key", Input).value,
                compaction_enabled=self.query_one("#setting-compaction", Switch).value,
                compaction_threshold=int(
                    self.query_one("#setting-compaction-threshold", Input).value or "100000"
                ),
                max_compactions=self._config.max_compactions,
                whisper_model=self.query_one("#setting-whisper", Select).value,
                sample_rate=self._config.sample_rate,
                silence_threshold=float(
                    self.query_one("#setting-silence-threshold", Input).value or "0.02"
                ),
                silence_duration=float(
                    self.query_one("#setting-silence-duration", Input).value or "1.5"
                ),
            )
            self.dismiss(new_config)
        except (ValueError, TypeError):
            pass
