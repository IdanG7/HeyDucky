"""Main window for the HeyDucky Remote GUI."""

from __future__ import annotations

import asyncio
import socket
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from heyducky.remote.agent import get_adapter_command
from heyducky.remote.gui.process_list import ProcessListWidget
from heyducky.remote.gui.styles import (
    BLUE, GREEN, OVERLAY0, OVERLAY1, SURFACE1, SUBTEXT0, TEXT, YELLOW, RED,
)
from heyducky.remote.gui.widgets import (
    GradientHeader,
    ShadowPanel,
    StatusCard,
    StatusDot,
    VerticalSeparator,
)


class _SignalBridge(QObject):
    log_message = Signal(str)
    status_changed = Signal(str, str)


class MainWindow(QMainWindow):

    def __init__(self, loop: asyncio.AbstractEventLoop, parent=None):
        super().__init__(parent)
        self._loop = loop
        self._relay = None
        self._file_server = None
        self._bridge = _SignalBridge()
        self._bridge.log_message.connect(self._append_log)
        self._bridge.status_changed.connect(self._on_status_changed)
        self._attached = False

        self.setWindowTitle("HeyDucky Remote")
        self.resize(980, 760)
        self.setMinimumSize(760, 540)
        self._setup_menu()
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _setup_menu(self) -> None:
        menu = self.menuBar()
        file_menu = menu.addMenu("&File")
        file_menu.addAction("&Quit", self.close)
        help_menu = menu.addMenu("&Help")
        help_menu.addAction("&About", self._show_about)

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        self._header = GradientHeader()
        root.addWidget(self._header)

        # Body
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(18, 14, 18, 14)
        body_layout.setSpacing(12)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # --- PROCESSES panel ---
        proc_panel = ShadowPanel()
        proc_layout = QVBoxLayout(proc_panel)
        proc_layout.setContentsMargins(16, 16, 16, 12)
        proc_layout.setSpacing(10)

        proc_title = QLabel("PROCESSES")
        proc_title.setFont(QFont("Avenir Next", 10, QFont.Weight.Bold))
        proc_title.setStyleSheet(f"color: {BLUE};")
        proc_layout.addWidget(proc_title)

        self._process_list = ProcessListWidget()
        self._process_list.table.selectionModel().selectionChanged.connect(
            self._on_selection_changed
        )
        self._process_list.table.doubleClicked.connect(self._on_attach_clicked)
        proc_layout.addWidget(self._process_list)
        splitter.addWidget(proc_panel)

        # --- DEBUGGER panel ---
        debug_panel = ShadowPanel()
        debug_layout = QVBoxLayout(debug_panel)
        debug_layout.setContentsMargins(16, 16, 16, 16)
        debug_layout.setSpacing(14)

        debug_title = QLabel("DEBUGGER")
        debug_title.setFont(QFont("Avenir Next", 10, QFont.Weight.Bold))
        debug_title.setStyleSheet(f"color: {BLUE};")
        debug_layout.addWidget(debug_title)

        # Controls row
        controls = QHBoxLayout()
        controls.setSpacing(10)

        lang_lbl = QLabel("Language")
        lang_lbl.setFont(QFont("Avenir Next", 11, QFont.Weight.Medium))
        lang_lbl.setStyleSheet(f"color: {OVERLAY1};")
        controls.addWidget(lang_lbl)
        self._language_combo = QComboBox()
        self._language_combo.addItem("Python (debugpy)", "python")
        controls.addWidget(self._language_combo)

        controls.addSpacing(10)
        port_lbl = QLabel("Port")
        port_lbl.setFont(QFont("Avenir Next", 11, QFont.Weight.Medium))
        port_lbl.setStyleSheet(f"color: {OVERLAY1};")
        controls.addWidget(port_lbl)
        self._port_spin = QSpinBox()
        self._port_spin.setRange(1024, 65535)
        self._port_spin.setValue(5678)
        controls.addWidget(self._port_spin)

        controls.addStretch()

        self._attach_btn = QPushButton("Attach")
        self._attach_btn.setObjectName("attachBtn")
        self._attach_btn.setEnabled(False)
        self._attach_btn.clicked.connect(self._on_attach_clicked)
        controls.addWidget(self._attach_btn)

        self._detach_btn = QPushButton("Detach")
        self._detach_btn.setObjectName("detachBtn")
        self._detach_btn.setVisible(False)
        self._detach_btn.clicked.connect(self._on_detach_clicked)
        controls.addWidget(self._detach_btn)

        debug_layout.addLayout(controls)

        # Status cards row
        cards = QHBoxLayout()
        cards.setSpacing(20)

        status_col = QVBoxLayout()
        status_col.setSpacing(4)
        s_label = QLabel("STATUS")
        s_label.setFont(QFont("Avenir Next", 9, QFont.Weight.DemiBold))
        s_label.setStyleSheet(f"color: {OVERLAY0};")
        status_col.addWidget(s_label)

        dot_row = QHBoxLayout()
        dot_row.setSpacing(8)
        self._status_dot = StatusDot()
        dot_row.addWidget(self._status_dot)
        self._status_label = QLabel("Idle")
        self._status_label.setFont(QFont("Avenir Next", 14, QFont.Weight.DemiBold))
        self._status_label.setStyleSheet(f"color: {SURFACE1};")
        dot_row.addWidget(self._status_label)
        dot_row.addStretch()
        status_col.addLayout(dot_row)
        cards.addLayout(status_col)

        cards.addWidget(VerticalSeparator())

        self._dap_card = StatusCard("DAP PORT")
        cards.addWidget(self._dap_card)
        cards.addWidget(VerticalSeparator())
        self._file_card = StatusCard("FILE PORT")
        cards.addWidget(self._file_card)
        cards.addWidget(VerticalSeparator())
        self._ip_card = StatusCard("YOUR IP")
        self._ip_card.set_value(_get_local_ip(), BLUE)
        cards.addWidget(self._ip_card)

        cards.addStretch()

        # Peer info (appears on connect)
        self._peer_card = StatusCard("CLIENT")
        self._peer_card.setVisible(False)
        cards.addWidget(self._peer_card)

        debug_layout.addLayout(cards)
        splitter.addWidget(debug_panel)

        # --- LOG panel ---
        log_panel = ShadowPanel()
        log_layout = QVBoxLayout(log_panel)
        log_layout.setContentsMargins(16, 16, 16, 12)
        log_layout.setSpacing(8)

        log_title = QLabel("ACTIVITY LOG")
        log_title.setFont(QFont("Avenir Next", 10, QFont.Weight.Bold))
        log_title.setStyleSheet(f"color: {BLUE};")
        log_layout.addWidget(log_title)

        self._log_view = QPlainTextEdit()
        self._log_view.setObjectName("logView")
        self._log_view.setReadOnly(True)
        self._log_view.setMaximumBlockCount(5000)
        self._log_view.setFont(QFont("Menlo", 11))
        log_layout.addWidget(self._log_view)
        splitter.addWidget(log_panel)

        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 3)

        body_layout.addWidget(splitter)
        root.addWidget(body, 1)

    # ------------------------------------------------------------------
    # Status helper
    # ------------------------------------------------------------------

    def _set_status(self, state: str, text: str) -> None:
        color_map = {
            "idle": SURFACE1,
            "waiting": YELLOW,
            "connected": GREEN,
            "error": RED,
        }
        color = color_map.get(state, SURFACE1)
        self._status_dot.set_color(color)
        self._status_label.setText(text)
        self._status_label.setStyleSheet(f"color: {color};")
        self._header.set_status(state, text)

        if state == "waiting":
            self._status_dot.start_pulse()
        else:
            self._status_dot.stop_pulse()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_selection_changed(self) -> None:
        has_selection = self._process_list.selected_process() is not None
        self._attach_btn.setEnabled(has_selection and not self._attached)
        proc = self._process_list.selected_process()
        if proc and "python" in proc.name.lower():
            self._language_combo.setCurrentIndex(0)

    @Slot()
    def _on_attach_clicked(self) -> None:
        proc = self._process_list.selected_process()
        if not proc or self._attached:
            return
        self._do_attach(proc.pid, proc.name, self._language_combo.currentData(), self._port_spin.value())

    @Slot()
    def _on_detach_clicked(self) -> None:
        self._do_detach()

    @Slot(str)
    def _append_log(self, text: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self._log_view.appendPlainText(f" {ts}  {text}")

    @Slot(str, str)
    def _on_status_changed(self, event: str, detail: str) -> None:
        if event == "client_connected":
            self._set_status("connected", "Connected")
            self._peer_card.set_value(detail, GREEN)
            self._peer_card.setVisible(True)
            self._bridge.log_message.emit(f"TUI client connected from {detail}")
        elif event == "client_disconnected":
            self._set_status("waiting", "Waiting")
            self._peer_card.setVisible(False)
            self._bridge.log_message.emit("TUI client disconnected")

    def _show_about(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.about(
            self,
            "HeyDucky Remote",
            "HeyDucky \u2014 Remote Debug Agent\n\n"
            "Run this on the machine you want to debug.\n"
            "Connect with HeyDucky on your local machine.\n\n"
            "github.com/IdanG7/HeyDucky",
        )

    # ------------------------------------------------------------------
    # Attach / detach
    # ------------------------------------------------------------------

    def _do_attach(self, pid: int, name: str, language: str, port: int) -> None:
        adapter_cmd = get_adapter_command(language)
        if not adapter_cmd:
            self._append_log(f"No adapter configured for {language}")
            return

        self._attached = True
        self._attach_btn.setEnabled(False)
        self._attach_btn.setVisible(False)
        self._detach_btn.setVisible(True)
        self._port_spin.setEnabled(False)
        self._language_combo.setEnabled(False)
        self._set_status("waiting", "Starting\u2026")
        self._append_log(f"Attaching to PID {pid} ({name}) via {language}\u2026")

        asyncio.ensure_future(
            self._async_attach(pid, language, adapter_cmd, port), loop=self._loop
        )

    async def _async_attach(
        self, pid: int, language: str, adapter_cmd: list[str], port: int
    ) -> None:
        from heyducky.remote.relay import DAPRelay
        from heyducky.remote.file_server import FileServer

        try:
            import psutil as _psutil
            try:
                project_root = _psutil.Process(pid).cwd()
            except Exception:
                project_root = str(Path.home())

            def on_relay_message(direction: str, msg: dict) -> None:
                if direction == "status":
                    self._bridge.status_changed.emit(
                        msg.get("event", ""), msg.get("peer", "")
                    )
                    return
                msg_type = msg.get("type", "")
                if msg_type == "event":
                    ev = msg.get("event", "?")
                    summary = _summarize(msg.get("body", {}))
                    extra = f"  {summary}" if summary else ""
                    self._bridge.log_message.emit(f"\u25b6 {ev}{extra}")
                elif msg_type == "response":
                    cmd = msg.get("command", "?")
                    ok = "\u2713" if msg.get("success") else "\u2717"
                    self._bridge.log_message.emit(f"{ok} {cmd}")
                elif msg_type == "request":
                    self._bridge.log_message.emit(f"\u2192 {msg.get('command', '?')}")

            self._relay = DAPRelay(
                adapter_cmd=adapter_cmd,
                host="0.0.0.0",
                port=port,
                on_message=on_relay_message,
                attach_inject={"processId": pid},
            )
            dap_port = await self._relay.start()

            self._file_server = FileServer(project_root, host="0.0.0.0", port=0)
            file_port = await self._file_server.start()

            self._bridge.log_message.emit(
                f"Relay :{dap_port}  \u2502  Files :{file_port}  \u2502  {project_root}"
            )

            self._dap_card.set_value(str(dap_port), BLUE)
            self._file_card.set_value(str(file_port), BLUE)
            self._set_status("waiting", "Waiting")

        except Exception as exc:
            self._bridge.log_message.emit(f"Failed: {exc}")
            self._reset_ui()

    def _do_detach(self) -> None:
        self._append_log("Detaching\u2026")
        asyncio.ensure_future(self._async_detach(), loop=self._loop)

    async def _async_detach(self) -> None:
        if self._relay:
            await self._relay.stop()
            self._relay = None
        if self._file_server:
            await self._file_server.stop()
            self._file_server = None
        self._bridge.log_message.emit("Detached.")
        self._reset_ui()

    def _reset_ui(self) -> None:
        self._attached = False
        self._attach_btn.setVisible(True)
        self._attach_btn.setEnabled(self._process_list.selected_process() is not None)
        self._detach_btn.setVisible(False)
        self._port_spin.setEnabled(True)
        self._language_combo.setEnabled(True)
        self._set_status("idle", "Idle")
        self._dap_card.set_value("\u2014")
        self._file_card.set_value("\u2014")
        self._peer_card.setVisible(False)

    def closeEvent(self, event) -> None:
        if self._attached:
            asyncio.ensure_future(self._async_detach(), loop=self._loop)
        super().closeEvent(event)


def _get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _summarize(body: dict) -> str:
    parts = []
    if "reason" in body:
        parts.append(body["reason"])
    if "threadId" in body:
        parts.append(f"thread {body['threadId']}")
    if "output" in body:
        parts.append(f'"{body["output"].strip()[:60]}"')
    if "source" in body and isinstance(body["source"], dict):
        p = body["source"].get("path", "")
        if p:
            parts.append(Path(p).name)
    if "line" in body:
        parts.append(f"L{body['line']}")
    return " \u00b7 ".join(parts) if parts else ""
