"""
StatsPanel – displays parse statistics as visual cards and a summary table.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout, QFrame,
    QProgressBar, QGroupBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from parser.base_parser import ParseStats


def _card(title: str, value: str, color: str = "#2196F3") -> QFrame:
    """Create a metric card widget."""
    frame = QFrame()
    frame.setStyleSheet(f"""
        QFrame {{
            background-color: #1e2130;
            border: 1px solid {color}44;
            border-radius: 10px;
            padding: 10px;
        }}
    """)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(12, 8, 12, 8)

    val_lbl = QLabel(value)
    val_lbl.setAlignment(Qt.AlignCenter)
    val_lbl.setFont(QFont("Segoe UI", 22, QFont.Bold))
    val_lbl.setStyleSheet(f"color: {color}; border: none;")

    title_lbl = QLabel(title)
    title_lbl.setAlignment(Qt.AlignCenter)
    title_lbl.setStyleSheet("color: #8899aa; font-size: 11px; border: none;")

    layout.addWidget(val_lbl)
    layout.addWidget(title_lbl)
    return frame


class StatsPanel(QWidget):
    """Displays parse statistics with metric cards and details."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(14)

        title = QLabel("📊  Parse Statistics")
        title.setStyleSheet("color: #90CAF9; font-weight: bold; font-size: 15px;")
        layout.addWidget(title)

        # Metric cards row
        self._cards_row = QHBoxLayout()
        self._card_total = _card("Total Packets", "—", "#2196F3")
        self._card_valid = _card("Valid", "—", "#4CAF50")
        self._card_invalid = _card("Invalid", "—", "#F44336")
        self._card_rate = _card("Success Rate", "—", "#FF9800")
        for card in (self._card_total, self._card_valid, self._card_invalid, self._card_rate):
            self._cards_row.addWidget(card)
        layout.addLayout(self._cards_row)

        # Success progress bar
        prog_row = QHBoxLayout()
        self._prog_lbl = QLabel("Parse quality:")
        self._prog_lbl.setStyleSheet("color: #8899aa;")
        self._prog_bar = QProgressBar()
        self._prog_bar.setRange(0, 100)
        self._prog_bar.setValue(0)
        self._prog_bar.setStyleSheet("""
            QProgressBar {
                background-color: #252840;
                border: 1px solid #2a3050;
                border-radius: 6px;
                height: 18px;
                text-align: center;
                color: white;
                font-size: 11px;
            }
            QProgressBar::chunk { background-color: #4CAF50; border-radius: 6px; }
        """)
        prog_row.addWidget(self._prog_lbl)
        prog_row.addWidget(self._prog_bar, 1)
        layout.addLayout(prog_row)

        # Detail table
        detail_group = QGroupBox("Details")
        detail_group.setStyleSheet("""
            QGroupBox {
                color: #90CAF9;
                border: 1px solid #2a3050;
                border-radius: 8px;
                margin-top: 10px;
                padding: 8px;
                background-color: #1e2130;
            }
            QGroupBox::title { left: 10px; color: #2196F3; }
        """)
        self._detail_grid = QGridLayout(detail_group)
        self._detail_grid.setColumnStretch(1, 1)
        layout.addWidget(detail_group)

        layout.addStretch()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_stats(self, stats: ParseStats):
        """Populate the statistics view."""
        # Update cards
        self._set_card_value(self._card_total, str(stats.total_packets))
        self._set_card_value(self._card_valid, str(stats.valid_packets))
        self._set_card_value(self._card_invalid, str(stats.invalid_packets))
        self._set_card_value(self._card_rate, f"{stats.success_rate:.1f}%")

        # Progress bar
        self._prog_bar.setValue(int(stats.success_rate))
        if stats.success_rate >= 80:
            self._prog_bar.setStyleSheet(self._prog_bar.styleSheet().replace(
                "#4CAF50", "#4CAF50"
            ))
        elif stats.success_rate >= 50:
            self._prog_bar.setStyleSheet(self._prog_bar.styleSheet().replace(
                "#4CAF50", "#FF9800"
            ))
        else:
            self._prog_bar.setStyleSheet(self._prog_bar.styleSheet().replace(
                "#4CAF50", "#F44336"
            ))

        # Details grid
        for i in reversed(range(self._detail_grid.count())):
            self._detail_grid.itemAt(i).widget().deleteLater()

        details = [
            ("Data size:", f"{stats.total_bytes:,} bytes"),
            ("Parse time:", f"{stats.parse_duration_s:.3f} s"),
            ("Timestamp start:", stats.timestamp_range[0] or "—"),
            ("Timestamp end:", stats.timestamp_range[1] or "—"),
        ]
        if stats.error_summary:
            details.append(("── Errors ──", ""))
            for err, count in sorted(stats.error_summary.items(), key=lambda x: -x[1])[:8]:
                details.append((f"  {err}:", str(count)))

        for row, (key, val) in enumerate(details):
            k = QLabel(key)
            v = QLabel(val)
            k.setStyleSheet("color: #8899aa; font-size: 11px;")
            v.setStyleSheet("color: #e0e0e0; font-size: 11px;")
            self._detail_grid.addWidget(k, row, 0)
            self._detail_grid.addWidget(v, row, 1)

    @staticmethod
    def _set_card_value(card: QFrame, value: str):
        """Update the value label in a metric card."""
        for child in card.children():
            if isinstance(child, QLabel):
                font = child.font()
                if font.pointSize() >= 18:
                    child.setText(value)
                    break
