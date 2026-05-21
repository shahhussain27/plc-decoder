"""
HexViewer – displays raw hex data with offset ruler and ASCII sidebar.
Supports navigation and highlighting of selected byte ranges.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel,
    QSpinBox, QPushButton, QScrollBar,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QTextCharFormat, QColor, QTextCursor

COLS = 16  # bytes per row


class HexViewer(QWidget):
    """
    Read-only hex dump viewer with:
      - Offset column
      - Hex bytes (grouped in pairs/words)
      - ASCII representation sidebar
      - Page navigation for large files
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hex_data: str = ""
        self._page_size_bytes = 512
        self._page_offset = 0
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Top bar
        top = QHBoxLayout()
        title = QLabel("🔢  Hex Viewer")
        title.setStyleSheet("color: #90CAF9; font-weight: bold; font-size: 13px;")
        top.addWidget(title)
        top.addStretch()

        page_lbl = QLabel("Bytes/page:")
        page_lbl.setStyleSheet("color: #8899aa; font-size: 11px;")
        self._page_spin = QSpinBox()
        self._page_spin.setRange(64, 16384)
        self._page_spin.setValue(512)
        self._page_spin.setSingleStep(256)
        self._page_spin.setStyleSheet("""
            QSpinBox {
                background-color: #252840;
                border: 1px solid #2a3050;
                border-radius: 4px;
                padding: 2px 4px;
                color: #e0e0e0;
                font-size: 11px;
                width: 80px;
            }
        """)
        self._page_spin.valueChanged.connect(self._on_page_size_change)
        top.addWidget(page_lbl)
        top.addWidget(self._page_spin)

        layout.addLayout(top)

        # Main hex display
        self._hex_text = QTextEdit()
        self._hex_text.setReadOnly(True)
        self._hex_text.setFont(QFont("Courier New", 9))
        self._hex_text.setStyleSheet("""
            QTextEdit {
                background-color: #0d1117;
                color: #c9d1d9;
                border: 1px solid #2a3050;
                border-radius: 8px;
                selection-background-color: #1565C0;
                font-family: 'Courier New';
                font-size: 9pt;
            }
        """)
        layout.addWidget(self._hex_text, 1)

        # Navigation bar
        nav = QHBoxLayout()
        self._prev_btn = QPushButton("◀ Prev")
        self._next_btn = QPushButton("Next ▶")
        self._page_label = QLabel("Page 1/1")
        self._page_label.setStyleSheet("color: #8899aa; font-size: 11px;")
        for btn in (self._prev_btn, self._next_btn):
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #252840;
                    color: #90CAF9;
                    border: 1px solid #2a3050;
                    border-radius: 5px;
                    padding: 4px 14px;
                    font-size: 12px;
                }
                QPushButton:hover { background-color: #2196F3; color: white; }
                QPushButton:disabled { color: #444466; }
            """)
        self._prev_btn.clicked.connect(self._on_prev_page)
        self._next_btn.clicked.connect(self._on_next_page)
        nav.addWidget(self._prev_btn)
        nav.addStretch()
        nav.addWidget(self._page_label)
        nav.addStretch()
        nav.addWidget(self._next_btn)
        layout.addLayout(nav)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_hex(self, hex_data: str):
        """Load hex string into the viewer."""
        self._hex_data = hex_data.upper()
        self._page_offset = 0
        self._render_page()

    def highlight_offset(self, byte_offset: int, length: int = 2):
        """Scroll to and highlight bytes at the given offset."""
        # TODO: implement per-byte highlighting
        pass

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render_page(self):
        """Render the current page of hex data."""
        if not self._hex_data:
            self._hex_text.setPlainText("(no data loaded)")
            return

        page_bytes = self._page_spin.value()
        total_bytes = len(self._hex_data) // 2

        start_byte = self._page_offset
        end_byte = min(start_byte + page_bytes, total_bytes)

        hex_slice = self._hex_data[start_byte * 2: end_byte * 2]
        lines = self._format_hex_dump(hex_slice, start_byte)
        self._hex_text.setPlainText(lines)

        total_pages = max(1, (total_bytes + page_bytes - 1) // page_bytes)
        current_page = self._page_offset // page_bytes + 1
        self._page_label.setText(f"Page {current_page}/{total_pages} "
                                  f"({start_byte}–{end_byte} of {total_bytes} bytes)")
        self._prev_btn.setEnabled(self._page_offset > 0)
        self._next_btn.setEnabled(end_byte < total_bytes)

    @staticmethod
    def _format_hex_dump(hex_slice: str, start_byte: int) -> str:
        """Format hex slice as annotated hex dump."""
        lines = []
        # Header ruler
        ruler = "Offset    " + " ".join(f"{i:02X}" for i in range(COLS))
        ruler += "  " + "".join(f"{i:X}" for i in range(COLS))
        lines.append(ruler)
        lines.append("─" * len(ruler))

        raw = bytes.fromhex(hex_slice) if len(hex_slice) % 2 == 0 else bytes.fromhex(hex_slice[:-1])
        for i in range(0, len(raw), COLS):
            chunk = raw[i: i + COLS]
            offset = f"{start_byte + i:08X}  "
            hex_part = " ".join(f"{b:02X}" for b in chunk)
            # Pad to full width
            hex_part = hex_part.ljust(COLS * 3 - 1)
            ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            lines.append(f"{offset}{hex_part}  {ascii_part}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _on_prev_page(self):
        page_bytes = self._page_spin.value()
        self._page_offset = max(0, self._page_offset - page_bytes)
        self._render_page()

    def _on_next_page(self):
        page_bytes = self._page_spin.value()
        total_bytes = len(self._hex_data) // 2
        self._page_offset = min(self._page_offset + page_bytes, total_bytes - 1)
        self._render_page()

    def _on_page_size_change(self):
        self._page_offset = 0
        self._render_page()
