"""
FilePanel – left-side file drop/select panel with file metadata display.
"""

from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QGroupBox, QGridLayout, QFileDialog,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent


class FilePanel(QWidget):
    """
    Panel for selecting PLC data files.
    Emits `file_selected(path: str)` when a file is chosen.
    Emits `parse_requested()` when Parse button is clicked.
    Supports drag-and-drop.
    """

    file_selected = Signal(str)
    parse_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._current_file: str = ""
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Drop zone
        group = QGroupBox("📂  Input File")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 13px;
                color: #90CAF9;
                border: 1px solid #2a3050;
                border-radius: 10px;
                margin-top: 14px;
                padding: 10px;
                background-color: #1e2130;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: #2196F3;
            }
        """)
        g_layout = QVBoxLayout(group)

        # Drop area
        self._drop_label = QLabel(
            "Drag & Drop\nPLC Data File Here\n\n.txt  .csv  .bin  .hex"
        )
        self._drop_label.setAlignment(Qt.AlignCenter)
        self._drop_label.setMinimumHeight(110)
        self._drop_label.setStyleSheet("""
            QLabel {
                border: 2px dashed #2196F3;
                border-radius: 10px;
                color: #5577aa;
                font-size: 13px;
                background-color: #12151f;
                padding: 10px;
            }
        """)
        g_layout.addWidget(self._drop_label)

        # Browse button
        browse_btn = QPushButton("Browse File…")
        browse_btn.setCursor(Qt.PointingHandCursor)
        browse_btn.clicked.connect(self._on_browse)
        browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #1565C0;
                color: white;
                border: none;
                border-radius: 7px;
                padding: 8px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1976D2; }
            QPushButton:pressed { background-color: #0D47A1; }
        """)
        g_layout.addWidget(browse_btn)

        # File info grid
        self._info_grid = QGridLayout()
        self._info_grid.setColumnStretch(1, 1)
        labels = ["File:", "Size:", "Format:", "Hex bytes:"]
        self._info_values: dict[str, QLabel] = {}
        for row, label in enumerate(labels):
            key_lbl = QLabel(label)
            key_lbl.setStyleSheet("color: #8899aa; font-size: 11px;")
            val_lbl = QLabel("—")
            val_lbl.setStyleSheet("color: #e0e0e0; font-size: 11px;")
            val_lbl.setWordWrap(True)
            self._info_grid.addWidget(key_lbl, row, 0)
            self._info_grid.addWidget(val_lbl, row, 1)
            self._info_values[label] = val_lbl
        g_layout.addLayout(self._info_grid)

        # Parse button
        self._parse_btn = QPushButton("▶  Parse Data")
        self._parse_btn.setCursor(Qt.PointingHandCursor)
        self._parse_btn.setEnabled(False)
        self._parse_btn.clicked.connect(self.parse_requested.emit)
        self._parse_btn.setStyleSheet("""
            QPushButton {
                background-color: #388E3C;
                color: white;
                border: none;
                border-radius: 7px;
                padding: 10px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #43A047; }
            QPushButton:pressed { background-color: #2E7D32; }
            QPushButton:disabled { background-color: #2a3050; color: #555577; }
        """)
        g_layout.addWidget(self._parse_btn)

        layout.addWidget(group)
        layout.addStretch()

    # ------------------------------------------------------------------
    # Drag-and-Drop
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._drop_label.setStyleSheet("""
                QLabel {
                    border: 2px dashed #4CAF50;
                    border-radius: 10px;
                    color: #4CAF50;
                    font-size: 13px;
                    background-color: #1a2a1a;
                    padding: 10px;
                }
            """)

    def dragLeaveEvent(self, event):
        self._reset_drop_style()

    def dropEvent(self, event: QDropEvent):
        self._reset_drop_style()
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            self.set_file(path)
            self.file_selected.emit(path)

    def _reset_drop_style(self):
        self._drop_label.setStyleSheet("""
            QLabel {
                border: 2px dashed #2196F3;
                border-radius: 10px;
                color: #5577aa;
                font-size: 13px;
                background-color: #12151f;
                padding: 10px;
            }
        """)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_file(self, path: str):
        self._current_file = path
        fname = Path(path).name
        self._drop_label.setText(f"✅  {fname}")
        self._parse_btn.setEnabled(True)
        self._info_values["File:"].setText(fname)

    def update_info(self, size_kb: float, hex_chars: int, fmt: str):
        self._info_values["Size:"].setText(f"{size_kb:.1f} KB")
        self._info_values["Format:"].setText(fmt)
        self._info_values["Hex bytes:"].setText(f"{hex_chars // 2:,}")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open PLC Data File", "",
            "All Supported (*.txt *.csv *.bin *.hex *.log *.dat);;All Files (*)"
        )
        if path:
            self.set_file(path)
            self.file_selected.emit(path)
