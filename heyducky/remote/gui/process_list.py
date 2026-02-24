"""Process list widget — QTableView backed by psutil."""

from __future__ import annotations

from dataclasses import dataclass

import psutil
from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QSortFilterProxyModel,
    Qt,
    QTimer,
)
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QPushButton,
    QStyledItemDelegate,
    QTableView,
    QVBoxLayout,
    QWidget,
)


@dataclass
class ProcessInfo:
    pid: int
    name: str
    cmdline: str
    username: str


class _RowDelegate(QStyledItemDelegate):
    """Forces consistent row height for a more spacious table."""

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        size.setHeight(32)
        return size


class ProcessTableModel(QAbstractTableModel):

    HEADERS = ["PID", "Name", "Command Line", "User"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._processes: list[ProcessInfo] = []

    def refresh(self) -> None:
        self.beginResetModel()
        self._processes = []
        for proc in psutil.process_iter(["pid", "name", "cmdline", "username"]):
            try:
                info = proc.info
                parts = info.get("cmdline") or []
                self._processes.append(ProcessInfo(
                    pid=info["pid"],
                    name=info.get("name") or "",
                    cmdline=" ".join(parts) if parts else "",
                    username=info.get("username") or "",
                ))
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        self._processes.sort(key=lambda p: p.name.lower())
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self._processes)

    def columnCount(self, parent=QModelIndex()):
        return len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        proc = self._processes[index.row()]
        col = index.column()
        if col == 0:
            return str(proc.pid)
        if col == 1:
            return proc.name
        if col == 2:
            return proc.cmdline
        if col == 3:
            return proc.username
        return None

    def process_at(self, row: int) -> ProcessInfo | None:
        if 0 <= row < len(self._processes):
            return self._processes[row]
        return None


class ProcessFilterModel(QSortFilterProxyModel):

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()
        pattern = self.filterRegularExpression().pattern().lower()
        if not pattern:
            return True
        for col in (1, 2):
            idx = model.index(source_row, col, source_parent)
            text = (model.data(idx) or "").lower()
            if pattern in text:
                return True
        return False


class ProcessListWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._model.refresh()
        self._auto_refresh = QTimer(self)
        self._auto_refresh.timeout.connect(self._model.refresh)
        self._auto_refresh.start(5000)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(8)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter processes\u2026")
        self._search.setClearButtonEnabled(True)
        self._search.setFont(QFont("Avenir Next", 13))
        self._search.textChanged.connect(self._on_filter_changed)
        top.addWidget(self._search, 1)

        self._refresh_btn = QPushButton("\u21bb  Refresh")
        self._refresh_btn.setObjectName("ghostBtn")
        self._refresh_btn.clicked.connect(self._on_refresh)
        top.addWidget(self._refresh_btn)
        layout.addLayout(top)

        self._model = ProcessTableModel(self)
        self._proxy = ProcessFilterModel(self)
        self._proxy.setSourceModel(self._model)

        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setItemDelegate(_RowDelegate(self._table))
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setFrameShape(QTableView.Shape.NoFrame)
        self._table.setFont(QFont("Menlo", 12))

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setHighlightSections(False)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(self._table)

    @property
    def table(self) -> QTableView:
        return self._table

    def selected_process(self) -> ProcessInfo | None:
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            return None
        source_row = self._proxy.mapToSource(indexes[0]).row()
        return self._model.process_at(source_row)

    def _on_filter_changed(self, text: str) -> None:
        self._proxy.setFilterFixedString(text)

    def _on_refresh(self) -> None:
        self._model.refresh()
