"""
PreviewTable – live data table showing decoded PLC records.
Features: sortable columns, search/filter, color-coded validity rows.
"""

import pandas as pd
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QLabel, QLineEdit, QPushButton, QComboBox, QAbstractItemView,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QBrush

from parser.base_parser import ParsedRecord

VALID_BG = QColor(30, 60, 40)
INVALID_BG = QColor(80, 20, 25)
HEADER_BG = QColor(18, 21, 31)
ALT_BG = QColor(28, 32, 50)


class PreviewTable(QWidget):
    """
    Displays decoded records as an interactive, filterable table.
    """

    record_selected = Signal(int)  # emits record index

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_rows: list[dict] = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # Top bar: filter + stats
        top_bar = QHBoxLayout()

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("🔍  Filter records… (timestamp, value, etc.)")
        self._search_edit.textChanged.connect(self._apply_filter)
        self._search_edit.setStyleSheet("""
            QLineEdit {
                background-color: #1e2130;
                border: 1px solid #2a3050;
                border-radius: 6px;
                padding: 5px 10px;
                color: #e0e0e0;
                font-size: 12px;
            }
        """)

        self._filter_col_combo = QComboBox()
        self._filter_col_combo.addItem("All columns")
        self._filter_col_combo.setStyleSheet("""
            QComboBox {
                background-color: #1e2130;
                border: 1px solid #2a3050;
                border-radius: 6px;
                padding: 4px 8px;
                color: #90CAF9;
                min-width: 130px;
            }
        """)

        self._valid_only_btn = QPushButton("Valid only")
        self._valid_only_btn.setCheckable(True)
        self._valid_only_btn.setStyleSheet("""
            QPushButton { background-color: #1e2130; border: 1px solid #2a3050;
                          border-radius: 5px; padding: 4px 10px; color: #90CAF9; }
            QPushButton:checked { background-color: #2E7D32; color: white; border-color: #43A047; }
        """)
        self._valid_only_btn.toggled.connect(lambda _: self._apply_filter(self._search_edit.text()))

        self._count_label = QLabel("0 records")
        self._count_label.setStyleSheet("color: #8899aa; font-size: 11px;")

        top_bar.addWidget(self._search_edit, 3)
        top_bar.addWidget(self._filter_col_combo, 1)
        top_bar.addWidget(self._valid_only_btn)
        top_bar.addStretch()
        top_bar.addWidget(self._count_label)
        layout.addLayout(top_bar)

        # Table
        self._table = QTableWidget()
        self._table.setAlternatingRowColors(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSortingEnabled(True)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self._table.verticalHeader().setDefaultSectionSize(22)
        self._table.setShowGrid(True)
        self._table.setStyleSheet("""
            QTableWidget {
                background-color: #12151f;
                alternate-background-color: #1a1d2e;
                color: #e0e0e0;
                gridline-color: #1e2540;
                border: none;
                font-size: 11px;
                font-family: 'Segoe UI';
            }
            QHeaderView::section {
                background-color: #1E2D40;
                color: #90CAF9;
                font-weight: bold;
                font-size: 11px;
                padding: 4px;
                border: none;
                border-right: 1px solid #2a3050;
            }
            QTableWidget::item:selected {
                background-color: #1565C0;
                color: white;
            }
        """)
        layout.addWidget(self._table)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_records(self, records: list[ParsedRecord], config: dict):
        """Populate table from parsed records."""
        self._all_rows = [r.to_flat_dict() for r in records]

        if not self._all_rows:
            self._table.setRowCount(0)
            self._table.setColumnCount(0)
            self._count_label.setText("0 records")
            return

        columns = list(self._all_rows[0].keys())
        self._table.setColumnCount(len(columns))
        self._table.setHorizontalHeaderLabels(columns)

        # Update filter column combo
        self._filter_col_combo.clear()
        self._filter_col_combo.addItem("All columns")
        self._filter_col_combo.addItems(columns)

        self._render_rows(self._all_rows)
        self._count_label.setText(f"{len(records)} records")

    def _render_rows(self, rows: list[dict]):
        """Render given rows to the table widget."""
        if not rows:
            self._table.setRowCount(0)
            return

        columns = list(rows[0].keys())
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(rows))

        mono_font = QFont("Courier New", 9)

        for row_idx, row in enumerate(rows):
            is_valid = str(row.get("Valid", "✓")).strip() == "✓"
            row_color = VALID_BG if is_valid else INVALID_BG
            alt_color = ALT_BG if row_idx % 2 == 0 else QColor("#12151f")

            for col_idx, col_name in enumerate(columns):
                value = row.get(col_name, "")
                item = QTableWidgetItem(str(value) if value is not None else "")
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                # Monospace for Raw Hex column
                if "Raw Hex" in col_name or "Hex" in col_name:
                    item.setFont(mono_font)

                # Row color
                if not is_valid:
                    item.setBackground(QBrush(row_color))
                else:
                    item.setBackground(QBrush(alt_color))

                # Status column special color
                if col_name == "Valid":
                    if is_valid:
                        item.setForeground(QBrush(QColor("#4CAF50")))
                    else:
                        item.setForeground(QBrush(QColor("#F44336")))

                self._table.setItem(row_idx, col_idx, item)

        self._table.setSortingEnabled(True)
        self._table.resizeColumnsToContents()
        # Cap column widths
        for col in range(self._table.columnCount()):
            if self._table.columnWidth(col) > 300:
                self._table.setColumnWidth(col, 300)

    def _apply_filter(self, text: str):
        """Filter rows by search text."""
        if not self._all_rows:
            return

        valid_only = self._valid_only_btn.isChecked()
        col_filter = self._filter_col_combo.currentText()
        search = text.strip().lower()

        def matches(row: dict) -> bool:
            if valid_only and str(row.get("Valid", "✓")).strip() != "✓":
                return False
            if not search:
                return True
            if col_filter == "All columns":
                return any(search in str(v).lower() for v in row.values())
            val = row.get(col_filter, "")
            return search in str(val).lower()

        filtered = [r for r in self._all_rows if matches(r)]
        self._render_rows(filtered)
        self._count_label.setText(f"{len(filtered)} / {len(self._all_rows)} records")
