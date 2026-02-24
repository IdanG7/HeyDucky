# heyducky/widgets/settings_screen.py
"""Modal settings screen for user configuration."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Collapsible, Input, Label, Select, Static, Switch

from heyducky.config import Config

THEMES = [
    ("Textual Dark", "textual-dark"),
    ("Textual Light", "textual-light"),
    ("Dracula", "dracula"),
    ("Monokai", "monokai"),
    ("Nord", "nord"),
    ("Tokyo Night", "tokyo-night"),
    ("Catppuccin Mocha", "catppuccin-mocha"),
    ("Catppuccin Latte", "catppuccin-latte"),
    ("Gruvbox", "gruvbox"),
    ("Rose Pine", "rose-pine"),
    ("Rose Pine Moon", "rose-pine-moon"),
    ("Rose Pine Dawn", "rose-pine-dawn"),
    ("Solarized Dark", "solarized-dark"),
    ("Solarized Light", "solarized-light"),
    ("Atom One Dark", "atom-one-dark"),
    ("Atom One Light", "atom-one-light"),
    ("Flexoki", "flexoki"),
    ("ANSI", "textual-ansi"),
]

KEYBINDINGS_TEXT = """\
[cyan]Space[/]  Talk          [cyan]1[/]-[cyan]5[/]  Tabs          [cyan]q[/]    Quit
[cyan]t[/]      Tree/Source   [cyan]o[/]    Open project  [cyan]Esc[/]  Close modal
[cyan]h[/]      History       [cyan]s[/]    Settings      [cyan]e[/]    Export
[cyan]m[/]      Mute TTS      [cyan]r[/]    Remote debug  [cyan]F5[/]   Continue
[cyan]F10[/]    Step over     [cyan]F11[/]  Step into"""


class SettingsScreen(ModalScreen[Config | None]):
    """Settings screen that returns updated Config or None if cancelled."""

    DEFAULT_CSS = """
    SettingsScreen {
        align: center middle;
    }

    #settings-container {
        width: 86;
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

    .field-label {
        margin-top: 1;
        margin-bottom: 0;
    }

    .switch-row {
        height: auto;
        margin-top: 1;
    }

    .switch-row Label {
        width: auto;
        margin-right: 2;
        padding-top: 1;
    }

    .inline-fields {
        height: auto;
        margin-top: 1;
    }

    .inline-fields Vertical {
        width: 1fr;
        height: auto;
        margin-right: 1;
    }

    #keybindings-ref {
        padding: 1 2;
        height: auto;
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

            # ── AI ────────────────────────────────────
            with Collapsible(title="AI", collapsed=False):
                yield Label("API Key", classes="field-label")
                yield Input(
                    value=self._config.api_key,
                    password=True,
                    placeholder="sk-ant-...",
                    id="setting-api-key",
                )

                yield Label("Model", classes="field-label")
                yield Select(
                    [
                        ("Claude Sonnet 4.5", "claude-sonnet-4-5-20250929"),
                        ("Claude Haiku 3.5", "claude-haiku-3-5-20241022"),
                    ],
                    value=self._config.ai_model,
                    id="setting-model",
                    allow_blank=False,
                )

                with Horizontal(classes="switch-row"):
                    yield Label("Auto-Compaction")
                    yield Switch(
                        value=self._config.compaction_enabled,
                        id="setting-compaction",
                    )

            # ── Appearance ────────────────────────────
            with Collapsible(title="Appearance", collapsed=False):
                yield Label("Theme", classes="field-label")
                yield Select(
                    THEMES,
                    value=self._config.theme,
                    id="setting-theme",
                    allow_blank=False,
                )

            # ── Voice ────────────────────────────────
            with Collapsible(title="Voice"):
                yield Label("Whisper Model", classes="field-label")
                yield Select(
                    [
                        ("tiny.en  — fastest", "tiny.en"),
                        ("base.en  — balanced", "base.en"),
                        ("small.en — best quality", "small.en"),
                    ],
                    value=self._config.whisper_model,
                    id="setting-whisper",
                    allow_blank=False,
                )

                with Horizontal(classes="inline-fields"):
                    with Vertical():
                        yield Label("Silence Threshold", classes="field-label")
                        yield Input(
                            value=str(self._config.silence_threshold),
                            placeholder="0.02",
                            id="setting-silence-threshold",
                        )
                    with Vertical():
                        yield Label("Silence Duration (s)", classes="field-label")
                        yield Input(
                            value=str(self._config.silence_duration),
                            placeholder="1.5",
                            id="setting-silence-duration",
                        )
                    with Vertical():
                        yield Label("Sample Rate (Hz)", classes="field-label")
                        yield Input(
                            value=str(self._config.sample_rate),
                            placeholder="16000",
                            id="setting-sample-rate",
                            type="integer",
                        )

            # ── TTS (Text-to-Speech) ─────────────────
            with Collapsible(title="TTS (Text-to-Speech)"):
                with Horizontal(classes="switch-row"):
                    yield Label("Enable TTS")
                    yield Switch(
                        value=self._config.tts_enabled,
                        id="setting-tts-enabled",
                    )

                yield Label("ElevenLabs API Key", classes="field-label")
                yield Input(
                    value=self._config.tts_api_key,
                    password=True,
                    placeholder="sk_...",
                    id="setting-tts-api-key",
                )

                yield Label("Voice ID", classes="field-label")
                yield Input(
                    value=self._config.tts_voice_id,
                    placeholder="JBFqnCBsd6RMkjVDRZzb",
                    id="setting-tts-voice-id",
                )

            # ── Keyboard Shortcuts ────────────────────
            with Collapsible(title="Keyboard Shortcuts"):
                yield Static(KEYBINDINGS_TEXT, id="keybindings-ref", markup=True)

            # ── Buttons ──────────────────────────────
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
                theme=self.query_one("#setting-theme", Select).value,
                whisper_model=self.query_one("#setting-whisper", Select).value,
                sample_rate=int(
                    self.query_one("#setting-sample-rate", Input).value or "16000"
                ),
                silence_threshold=float(
                    self.query_one("#setting-silence-threshold", Input).value or "0.02"
                ),
                silence_duration=float(
                    self.query_one("#setting-silence-duration", Input).value or "1.5"
                ),
                tts_enabled=self.query_one("#setting-tts-enabled", Switch).value,
                tts_api_key=self.query_one("#setting-tts-api-key", Input).value,
                tts_voice_id=self.query_one("#setting-tts-voice-id", Input).value,
            )
            self.dismiss(new_config)
        except (ValueError, TypeError):
            pass
