"""
LogPanel – displays parse error logs and application logs in a filterable table.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QLabel, QPushButton, QComboBox, QFileDialog,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QFont

LEVEL_COLORS = {
    "DEBUG":    QColor(100, 110, 140),
    "INFO":     QColor(70, 150, 220),
    "WARNING":  QColor(240, 160, 40),
    "ERROR":    QColor(240, 80, 80),
    "CRITICAL": QColor(255, 50, 50),
}


class LogPanel(QWidget):
    """
    Displays application and packet error logs.
    Shows both packet-level errors (from parser) and app-level logs.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_records: list[dict] = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Top bar
        top = QHBoxLayout()
        title = QLabel("📝  Log Viewer")
        title.setStyleSheet("color: #90CAF9; font-weight: bold; font-size: 13px;")

        self._level_combo = QComboBox()
        self._level_combo.addItems(["All levels", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self._level_combo.setStyleSheet("""
            QComboBox {
                background-color: #1e2130;
                border: 1px solid #2a3050;
                border-radius: 5px;
                padding: 3px 8px;
                color: #90CAF9;
                font-size: 11px;
                min-width: 110px;
            }
        """)
        self._level_combo.currentIndexChanged.connect(self._apply_filter)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #37474F;
                color: #e0e0e0;
                border: none;
                border-radius: 5px;
                padding: 4px 12px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #B71C1C; }
        """)

        export_btn = QPushButton("Export Log")
        export_btn.clicked.connect(self._export_log)
        export_btn.setStyleSheet(clear_btn.styleSheet())

        self._count_lbl = QLabel("0 entries")
        self._count_lbl.setStyleSheet("color: #8899aa; font-size: 11px;")

        top.addWidget(title)
        top.addStretch()
        top.addWidget(self._level_combo)
        top.addWidget(clear_btn)
        top.addWidget(export_btn)
        top.addWidget(self._count_lbl)
        layout.addLayout(top)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Time", "Level", "Module", "Message"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.verticalHeader().hide()
        self._table.setShowGrid(True)
        self._table.setStyleSheet("""
            QTableWidget {
                background-color: #0d1117;
                color: #c9d1d9;
                gridline-color: #1e2540;
                border: none;
                font-size: 11px;
                font-family: 'Courier New';
            }
            QHeaderView::section {
                background-color: #1E2D40;
                color: #90CAF9;
                font-weight: bold;
                font-size: 11px;
                padding: 4px;
                border: none;
            }
            QTableWidget::item:selected { background-color: #1565C0; }
        """)
        layout.addWidget(self._table, 1)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_errors(self, errors: list[dict], log_records: list[dict]):
        """Load packet errors + app log records."""
        self._all_records = []

        # Convert packet errors to log-style records
        for err in errors:
            self._all_records.append({
                "time": "—",
                "level": "ERROR",
                "module": "parser",
                "message": f"Offset {err.get('offset','?')}: {err.get('error','?')} "
                            f"[{err.get('raw_hex','')[:24]}…]",
            })

        # Add application logs
        self._all_records.extend(log_records)

        self._apply_filter()

    def append_log(self, record: dict):
        """Add a single log record (live update)."""
        self._all_records.append(record)
        self._apply_filter()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _apply_filter(self):
        level_filter = self._level_combo.currentText()
        filtered = [
            r for r in self._all_records
            if level_filter == "All levels" or r.get("level") == level_filter
        ]
        self._render(filtered)
        self._count_lbl.setText(f"{len(filtered)} entries")

    def _render(self, records: list[dict]):
        self._table.setRowCount(len(records))
        mono = QFont("Courier New", 9)
        for row_idx, rec in enumerate(records):
            level = rec.get("level", "INFO")
            color = LEVEL_COLORS.get(level, QColor(200, 200, 200))
            cols = [
                rec.get("time", ""),
                level,
                rec.get("module", ""),
                rec.get("message", ""),
            ]
            for col_idx, val in enumerate(cols):
                item = QTableWidgetItem(str(val))
                item.setForeground(QBrush(color))
                if col_idx == 3:
                    item.setFont(mono)
                self._table.setItem(row_idx, col_idx, item)

    def _clear(self):
        self._all_records.clear()
        self._table.setRowCount(0)
        self._count_lbl.setText("0 entries")

    def _export_log(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Log", "logs/export.txt", "Text File (*.txt);;All (*)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                for rec in self._all_records:
                    f.write(
                        f"[{rec.get('time','')}] [{rec.get('level','')}] "
                        f"{rec.get('module','')}: {rec.get('message','')}\n"
                    )
        except OSError as exc:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Export Error", str(exc))
