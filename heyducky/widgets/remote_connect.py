# heyducky/widgets/remote_connect.py
"""Modal screen for connecting to a remote debug adapter."""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static


@dataclass
class RemoteTarget:
    """Result from the remote connect dialog."""

    host: str
    port: int
    language: str
    path_map: dict[str, str]
    file_port: int | None = None


class RemoteConnectScreen(ModalScreen[RemoteTarget | None]):
    """Modal for entering remote debug adapter connection details."""

    DEFAULT_CSS = """
    RemoteConnectScreen {
        align: center middle;
    }

    #remote-container {
        width: 72;
        height: auto;
        max-height: 80%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }

    #remote-title {
        text-align: center;
        text-style: bold;
        width: 100%;
        margin-bottom: 1;
    }

    #remote-subtitle {
        text-align: center;
        color: $text-muted;
        width: 100%;
        margin-bottom: 1;
    }

    .field-label {
        margin-top: 1;
        margin-bottom: 0;
    }

    .host-port-row {
        height: auto;
        margin-top: 0;
    }

    .host-port-row .host-col {
        width: 2fr;
        height: auto;
        margin-right: 1;
    }

    .host-port-row .port-col {
        width: 1fr;
        height: auto;
    }

    #remote-hint {
        margin-top: 1;
        color: $text-muted;
    }

    #path-map-section {
        margin-top: 1;
        height: auto;
    }

    #path-map-section Label {
        margin-bottom: 0;
    }

    .path-map-row {
        height: auto;
    }

    .path-map-row .remote-col {
        width: 1fr;
        height: auto;
        margin-right: 1;
    }

    .path-map-row .local-col {
        width: 1fr;
        height: auto;
    }

    #remote-error {
        color: $error;
        text-align: center;
        margin-top: 1;
        display: none;
    }

    #remote-buttons {
        margin-top: 2;
        height: auto;
        align: center middle;
    }

    #remote-buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="remote-container"):
            yield Label("Connect to Remote Debugger", id="remote-title")
            yield Static(
                "Enter the address of a running debug adapter",
                id="remote-subtitle",
            )

            # Host + Port
            with Horizontal(classes="host-port-row"):
                with Vertical(classes="host-col"):
                    yield Label("Host", classes="field-label")
                    yield Input(
                        placeholder="192.168.1.50",
                        id="remote-host",
                    )
                with Vertical(classes="port-col"):
                    yield Label("Port", classes="field-label")
                    yield Input(
                        placeholder="5678",
                        id="remote-port",
                        type="integer",
                    )

            # Language
            yield Label("Language", classes="field-label")
            yield Select(
                [
                    ("Python (debugpy)", "python"),
                    ("C / C++ (lldb-dap)", "cpp"),
                    ("Go (delve)", "go"),
                    ("Rust (codelldb)", "rust"),
                ],
                value="python",
                id="remote-language",
                allow_blank=False,
            )

            # File server port (from ducky-remote agent)
            yield Label("File Server Port (optional)", classes="field-label")
            yield Input(
                placeholder="auto-detected from agent output",
                id="remote-file-port",
                type="integer",
            )
            yield Static(
                "[dim]If using ducky-remote, enter the file port it shows.[/dim]\n"
                "[dim]This lets the AI browse and read files on the remote machine.[/dim]",
                markup=True,
            )

            # Path mapping (manual fallback)
            with Vertical(id="path-map-section"):
                yield Label("Path Mapping (if not using agent)", classes="field-label")
                with Horizontal(classes="path-map-row"):
                    with Vertical(classes="remote-col"):
                        yield Label("Remote prefix", classes="field-label")
                        yield Input(
                            placeholder="/home/user/project",
                            id="remote-path-prefix",
                        )
                    with Vertical(classes="local-col"):
                        yield Label("Local prefix", classes="field-label")
                        yield Input(
                            placeholder="/Users/me/project",
                            id="local-path-prefix",
                        )

            # Hint
            yield Static(
                "[dim]On the remote machine run:[/dim]\n"
                "  [bold]ducky-remote script.py[/bold]\n"
                "[dim]It will show the host, port, and file port to enter here.[/dim]",
                id="remote-hint",
                markup=True,
            )

            yield Label("", id="remote-error")

            # Buttons
            with Horizontal(id="remote-buttons"):
                yield Button("Connect", variant="primary", id="remote-connect-btn")
                yield Button("Cancel", variant="default", id="remote-cancel-btn")

    def on_mount(self) -> None:
        self.query_one("#remote-host", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "remote-connect-btn":
            self._try_connect()
        elif event.button.id == "remote-cancel-btn":
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _show_error(self, msg: str) -> None:
        err = self.query_one("#remote-error", Label)
        err.update(msg)
        err.styles.display = "block"

    def _try_connect(self) -> None:
        host = self.query_one("#remote-host", Input).value.strip()
        port_str = self.query_one("#remote-port", Input).value.strip()
        language = self.query_one("#remote-language", Select).value

        if not host:
            self._show_error("Host is required")
            return
        if not port_str:
            self._show_error("Port is required")
            return

        try:
            port = int(port_str)
            if port < 1 or port > 65535:
                raise ValueError
        except ValueError:
            self._show_error("Port must be a number between 1 and 65535")
            return

        # File port (optional)
        file_port: int | None = None
        file_port_str = self.query_one("#remote-file-port", Input).value.strip()
        if file_port_str:
            try:
                file_port = int(file_port_str)
                if file_port < 1 or file_port > 65535:
                    self._show_error("File port must be between 1 and 65535")
                    return
            except ValueError:
                self._show_error("File port must be a number")
                return

        # Build path map
        path_map: dict[str, str] = {}
        remote_prefix = self.query_one("#remote-path-prefix", Input).value.strip()
        local_prefix = self.query_one("#local-path-prefix", Input).value.strip()
        if remote_prefix and local_prefix:
            path_map[remote_prefix] = local_prefix

        self.dismiss(RemoteTarget(
            host=host,
            port=port,
            language=language,
            path_map=path_map,
            file_port=file_port,
        ))
