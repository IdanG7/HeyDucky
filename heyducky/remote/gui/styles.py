"""Qt stylesheet for the HeyDucky Remote GUI.

Catppuccin Mocha palette. Avenir Next for UI, Menlo for data.
Designed for macOS native feel with developer-tool density.
"""

# -- Catppuccin Mocha tokens --
CRUST = "#11111b"
MANTLE = "#181825"
BASE = "#1e1e2e"
SURFACE0 = "#313244"
SURFACE1 = "#45475a"
SURFACE2 = "#585b70"
OVERLAY0 = "#6c7086"
OVERLAY1 = "#7f849c"
SUBTEXT0 = "#a6adc8"
TEXT = "#cdd6f4"
BLUE = "#89b4fa"
GREEN = "#a6e3a1"
YELLOW = "#f9e2af"
RED = "#f38ba8"
PEACH = "#fab387"
TEAL = "#94e2d5"
LAVENDER = "#b4befe"

FONT_UI = '"Avenir Next", "Helvetica Neue", sans-serif'
FONT_MONO = '"Menlo", "Courier New", monospace'

STYLESHEET = f"""
/* ============ BASE ============ */
QMainWindow {{
    background-color: {BASE};
}}
QWidget {{
    color: {TEXT};
    font-family: {FONT_UI};
    font-size: 13px;
}}

/* ============ PANELS ============ */
QFrame#panel {{
    background-color: {MANTLE};
    border: 1px solid {SURFACE0};
    border-radius: 12px;
}}

/* ============ TABLE ============ */
QTableView {{
    background-color: {MANTLE};
    alternate-background-color: rgba(30, 30, 46, 0.6);
    border: none;
    gridline-color: transparent;
    selection-background-color: rgba(137, 180, 250, 0.15);
    selection-color: {TEXT};
    font-family: {FONT_MONO};
    font-size: 12px;
    outline: none;
}}
QTableView::item {{
    padding: 6px 10px;
    border-bottom: 1px solid rgba(49, 50, 68, 0.4);
}}
QTableView::item:selected {{
    background-color: rgba(137, 180, 250, 0.15);
    border-left: 3px solid {BLUE};
}}
QTableView::item:hover:!selected {{
    background-color: rgba(49, 50, 68, 0.35);
}}
QHeaderView {{
    background-color: transparent;
}}
QHeaderView::section {{
    background-color: {MANTLE};
    color: {OVERLAY0};
    border: none;
    border-bottom: 2px solid {SURFACE0};
    padding: 10px 10px;
    font-family: {FONT_UI};
    font-weight: 600;
    font-size: 10px;
}}

/* ============ BUTTONS ============ */
QPushButton {{
    background-color: {SURFACE0};
    border: 1px solid {SURFACE1};
    border-radius: 8px;
    padding: 7px 16px;
    color: {SUBTEXT0};
    font-weight: 600;
    font-size: 12px;
}}
QPushButton:hover {{
    background-color: {SURFACE1};
    color: {TEXT};
}}
QPushButton:pressed {{
    background-color: {SURFACE2};
}}
QPushButton:disabled {{
    background-color: {BASE};
    color: {OVERLAY0};
    border-color: {SURFACE0};
}}
QPushButton#attachBtn {{
    background-color: {BLUE};
    color: {CRUST};
    font-weight: 700;
    padding: 10px 36px;
    font-size: 13px;
    border: none;
    border-radius: 8px;
}}
QPushButton#attachBtn:hover {{
    background-color: {LAVENDER};
}}
QPushButton#attachBtn:disabled {{
    background-color: {SURFACE0};
    color: {OVERLAY0};
}}
QPushButton#detachBtn {{
    background-color: {RED};
    color: {CRUST};
    font-weight: 700;
    padding: 10px 36px;
    font-size: 13px;
    border: none;
    border-radius: 8px;
}}
QPushButton#detachBtn:hover {{
    background-color: #f5a6bd;
}}
QPushButton#ghostBtn {{
    background-color: transparent;
    border: 1px solid {SURFACE0};
    color: {OVERLAY1};
    padding: 7px 14px;
}}
QPushButton#ghostBtn:hover {{
    background-color: {SURFACE0};
    color: {TEXT};
    border-color: {SURFACE1};
}}

/* ============ INPUTS ============ */
QLineEdit {{
    background-color: {BASE};
    border: 1px solid {SURFACE0};
    border-radius: 8px;
    padding: 8px 14px;
    color: {TEXT};
    font-family: {FONT_UI};
    font-size: 13px;
    selection-background-color: {BLUE};
    selection-color: {CRUST};
}}
QLineEdit:focus {{
    border-color: {BLUE};
}}
QComboBox {{
    background-color: {BASE};
    border: 1px solid {SURFACE0};
    border-radius: 8px;
    padding: 7px 14px;
    color: {TEXT};
    font-size: 12px;
    min-width: 150px;
}}
QComboBox:hover, QComboBox:focus {{
    border-color: {SURFACE1};
}}
QComboBox::drop-down {{
    border: none;
    width: 28px;
}}
QComboBox QAbstractItemView {{
    background-color: {MANTLE};
    border: 1px solid {SURFACE0};
    border-radius: 8px;
    selection-background-color: {SURFACE0};
    color: {TEXT};
    padding: 4px;
}}
QSpinBox {{
    background-color: {BASE};
    border: 1px solid {SURFACE0};
    border-radius: 8px;
    padding: 7px 14px;
    color: {TEXT};
    font-family: {FONT_MONO};
    font-size: 13px;
    min-width: 90px;
}}
QSpinBox:focus {{
    border-color: {BLUE};
}}

/* ============ LOG ============ */
QPlainTextEdit#logView {{
    background-color: {CRUST};
    border: none;
    border-radius: 8px;
    color: {SUBTEXT0};
    font-family: {FONT_MONO};
    font-size: 11px;
    padding: 10px 12px;
    selection-background-color: {SURFACE0};
}}

/* ============ SCROLLBARS ============ */
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 4px 1px;
}}
QScrollBar::handle:vertical {{
    background: {SURFACE1};
    border-radius: 3px;
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{
    background: {SURFACE2};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
    height: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 6px;
    margin: 1px 4px;
}}
QScrollBar::handle:horizontal {{
    background: {SURFACE1};
    border-radius: 3px;
    min-width: 28px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: transparent;
    width: 0;
}}

/* ============ MENU ============ */
QMenuBar {{
    background-color: transparent;
    border: none;
    padding: 2px 8px;
    font-size: 13px;
    color: {SUBTEXT0};
}}
QMenuBar::item {{
    padding: 4px 10px;
    border-radius: 6px;
}}
QMenuBar::item:selected {{
    background-color: {SURFACE0};
    color: {TEXT};
}}
QMenu {{
    background-color: {MANTLE};
    border: 1px solid {SURFACE0};
    border-radius: 10px;
    padding: 6px;
}}
QMenu::item {{
    padding: 8px 24px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background-color: {SURFACE0};
}}
QMenu::separator {{
    height: 1px;
    background-color: {SURFACE0};
    margin: 4px 8px;
}}

/* ============ TOOLTIP ============ */
QToolTip {{
    background-color: {MANTLE};
    color: {TEXT};
    border: 1px solid {SURFACE0};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}}

/* ============ SPLITTER ============ */
QSplitter::handle {{
    background: transparent;
    height: 8px;
}}
"""
