"""QApplication setup with asyncio integration via qasync."""

from __future__ import annotations

import asyncio
import sys

import qasync
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

from heyducky.remote.gui.styles import (
    BASE,
    BLUE,
    CRUST,
    MANTLE,
    OVERLAY0,
    STYLESHEET,
    SUBTEXT0,
    SURFACE0,
    SURFACE1,
    TEXT,
)


def _build_palette() -> QPalette:
    """Build a dark palette matching the Catppuccin Mocha theme."""
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window, QColor(BASE))
    p.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    p.setColor(QPalette.ColorRole.Base, QColor(MANTLE))
    p.setColor(QPalette.ColorRole.AlternateBase, QColor(BASE))
    p.setColor(QPalette.ColorRole.ToolTipBase, QColor(MANTLE))
    p.setColor(QPalette.ColorRole.ToolTipText, QColor(TEXT))
    p.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    p.setColor(QPalette.ColorRole.Button, QColor(SURFACE0))
    p.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
    p.setColor(QPalette.ColorRole.BrightText, QColor(TEXT))
    p.setColor(QPalette.ColorRole.Highlight, QColor(BLUE))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(CRUST))
    p.setColor(QPalette.ColorRole.PlaceholderText, QColor(OVERLAY0))
    p.setColor(QPalette.ColorRole.Mid, QColor(SURFACE1))
    p.setColor(QPalette.ColorRole.Dark, QColor(CRUST))
    p.setColor(QPalette.ColorRole.Light, QColor(SUBTEXT0))

    # Disabled state
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(SURFACE1))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(SURFACE1))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(SURFACE1))
    return p


def run_gui() -> None:
    """Launch the remote debugger GUI."""
    app = QApplication(sys.argv)
    app.setApplicationName("HeyDucky Remote")
    app.setOrganizationName("HeyDucky")

    # Set palette before stylesheet so base colors are correct
    app.setPalette(_build_palette())
    app.setStyleSheet(STYLESHEET)

    # Default font
    app.setFont(QFont("Avenir Next", 13))

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    from heyducky.remote.gui.main_window import MainWindow

    window = MainWindow(loop)
    window.show()

    with loop:
        loop.run_forever()
