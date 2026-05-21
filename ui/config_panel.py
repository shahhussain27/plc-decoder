"""
ConfigPanel – panel for loading, editing, and managing PLC parsing configurations.
Displays key settings as editable fields and exposes full JSON editor.
"""

import json
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QFormLayout, QLabel,
    QComboBox, QSpinBox, QCheckBox, QTextEdit, QPushButton,
    QHBoxLayout, QFileDialog, QMessageBox, QTabWidget, QScrollArea,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont

# Default built-in config (LiraNET / Mitsubishi FX5U)
DEFAULT_CONFIG = {
    "format_name": "liranet_fx5u",
    "protocol": "LiraNET EtherNET",
    "metadata": {
        "protocol_name": "LiraNET Data Transmission Protocol on EtherNET",
        "copyright": "mrpl@2016",
        "plc_model": "Mitsubishi FX5U",
        "endianness_note": "FX5U uses Little-Endian for data storage"
    },
    "endianness": "big",
    "packet_definition": {
        "packet_size_bytes": 40,
        "header_size_bytes": 0,
        "start_markers": ["03E9"]
    },
    "timestamp": {
        "word_offset": 1,
        "fields": ["year", "month", "day", "hour", "minute", "second", "millisecond"]
    },
    "fields": [
        {"name": "sub_client_id", "word_offset": 0, "size_words": 1,
         "byteorder": "big", "signed": False, "data_type": "uint16",
         "description": "Sub-Client ID / Model identifier", "register": "D6500"},
        {"name": "year", "word_offset": 1, "size_words": 1,
         "byteorder": "big", "signed": False, "data_type": "uint16",
         "description": "Year (e.g. 0x07E8 = 2024)", "register": "D6501"},
        {"name": "month", "word_offset": 2, "size_words": 1,
         "byteorder": "big", "signed": False, "data_type": "uint16",
         "description": "Month (1–12)", "register": "D6502"},
        {"name": "day", "word_offset": 3, "size_words": 1,
         "byteorder": "big", "signed": False, "data_type": "uint16",
         "description": "Day (1–31)", "register": "D6503"},
        {"name": "hour", "word_offset": 4, "size_words": 1,
         "byteorder": "big", "signed": False, "data_type": "uint16",
         "description": "Hour (0–23)", "register": "D6504"},
        {"name": "minute", "word_offset": 5, "size_words": 1,
         "byteorder": "big", "signed": False, "data_type": "uint16",
         "description": "Minute (0–59)", "register": "D6505"},
        {"name": "second", "word_offset": 6, "size_words": 1,
         "byteorder": "big", "signed": False, "data_type": "uint16",
         "description": "Second (0–59)", "register": "D6506"},
        {"name": "millisecond", "word_offset": 7, "size_words": 1,
         "byteorder": "big", "signed": False, "data_type": "uint16",
         "description": "Millisecond (0–999)", "register": "D6507"},
        {"name": "d1600", "word_offset": 8, "size_words": 1,
         "byteorder": "big", "signed": False, "data_type": "uint16",
         "description": "INITIAL", "register": "D1600"},
        {"name": "d1610", "word_offset": 9, "size_words": 1,
         "byteorder": "big", "signed": False, "data_type": "uint16",
         "description": "VOL-, SEEK LEFT", "register": "D1610"},
        {"name": "d1620", "word_offset": 10, "size_words": 1,
         "byteorder": "big", "signed": False, "data_type": "uint16",
         "description": "VOL+, OK", "register": "D1620"},
        {"name": "d1630", "word_offset": 11, "size_words": 1,
         "byteorder": "big", "signed": False, "data_type": "uint16",
         "description": "MUTE, SEEK RIGHT", "register": "D1630"},
        {"name": "d1640", "word_offset": 12, "size_words": 1,
         "byteorder": "big", "signed": False, "data_type": "uint16",
         "description": "MODE, UP", "register": "D1640"},
        {"name": "d1650", "word_offset": 13, "size_words": 1,
         "byteorder": "big", "signed": False, "data_type": "uint16",
         "description": "PREV, DOWN", "register": "D1650"},
        {"name": "d1660", "word_offset": 14, "size_words": 1,
         "byteorder": "big", "signed": False, "data_type": "uint16",
         "description": "NEXT, INITIAL", "register": "D1660"},
        {"name": "d1670", "word_offset": 15, "size_words": 1,
         "byteorder": "big", "signed": False, "data_type": "uint16",
         "description": "INITIAL, VOL-", "register": "D1670"},
        {"name": "d1680", "word_offset": 16, "size_words": 1,
         "byteorder": "big", "signed": False, "data_type": "uint16",
         "description": "CRUZE, VOL+", "register": "D1680"},
        {"name": "d1690", "word_offset": 17, "size_words": 1,
         "byteorder": "big", "signed": False, "data_type": "uint16",
         "description": "RST+, MUTE", "register": "D1690"},
        {"name": "d1700", "word_offset": 18, "size_words": 1,
         "byteorder": "big", "signed": False, "data_type": "uint16",
         "description": "SET-, MODE", "register": "D1700"},
        {"name": "d1710", "word_offset": 19, "size_words": 1,
         "byteorder": "big", "signed": False, "data_type": "uint16",
         "description": "CANCEL, PREV", "register": "D1710"},
    ],
    "parser_options": {
        "skip_padding": True,
        "min_valid_bytes": 4,
        "validate_timestamps": True
    },
    "crc": {
        "mode": "none"
    }
}


class ConfigPanel(QWidget):
    """
    Configuration panel with quick settings and full JSON editor.
    Emits `config_changed(config: dict)` on any change.
    """

    config_changed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config = DEFAULT_CONFIG.copy()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("⚙️  Parsing Configuration")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 13px;
                color: #90CAF9;
                border: 1px solid #2a3050;
                border-radius: 10px;
                margin-top: 14px;
                padding: 8px;
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

        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabBar::tab { padding: 5px 10px; font-size: 11px; }
            QTabBar::tab:selected { background-color: #2196F3; }
        """)

        # ---- Quick settings tab ----
        quick_widget = QWidget()
        form = QFormLayout(quick_widget)
        form.setLabelAlignment(Qt.AlignRight)

        lbl_style = "color: #8899aa; font-size: 11px;"
        combo_style = """
            QComboBox {
                background-color: #252840;
                border: 1px solid #2a3050;
                border-radius: 4px;
                padding: 3px 6px;
                color: #e0e0e0;
                font-size: 11px;
            }
            QComboBox::drop-down { border: none; }
        """
        spin_style = """
            QSpinBox {
                background-color: #252840;
                border: 1px solid #2a3050;
                border-radius: 4px;
                padding: 3px;
                color: #e0e0e0;
                font-size: 11px;
            }
        """

        # Template selector
        self._template_combo = QComboBox()
        self._template_combo.setStyleSheet(combo_style)
        self._template_combo.addItems([
            "LiraNET / Mitsubishi FX5U (default)",
            "Generic Modbus RTU",
            "Custom (from JSON editor)",
        ])
        self._template_combo.currentIndexChanged.connect(self._on_template_change)
        form.addRow(self._make_lbl("Template:", lbl_style), self._template_combo)

        # Endianness
        self._endian_combo = QComboBox()
        self._endian_combo.setStyleSheet(combo_style)
        self._endian_combo.addItems(["big", "little"])
        form.addRow(self._make_lbl("Endianness:", lbl_style), self._endian_combo)

        # Packet size
        self._pkt_size_spin = QSpinBox()
        self._pkt_size_spin.setStyleSheet(spin_style)
        self._pkt_size_spin.setRange(0, 4096)
        self._pkt_size_spin.setValue(40)
        self._pkt_size_spin.setSuffix(" bytes (0=auto)")
        form.addRow(self._make_lbl("Packet size:", lbl_style), self._pkt_size_spin)

        # Start marker
        from PySide6.QtWidgets import QLineEdit
        self._marker_edit = QLineEdit("03E9")
        self._marker_edit.setStyleSheet("""
            QLineEdit {
                background-color: #252840;
                border: 1px solid #2a3050;
                border-radius: 4px;
                padding: 3px 6px;
                color: #e0e0e0;
                font-family: Courier New;
                font-size: 11px;
            }
        """)
        self._marker_edit.setPlaceholderText("Hex start marker, e.g. 03E9")
        form.addRow(self._make_lbl("Start marker:", lbl_style), self._marker_edit)

        # Skip padding
        self._skip_padding_cb = QCheckBox("Skip all-zero packets")
        self._skip_padding_cb.setChecked(True)
        self._skip_padding_cb.setStyleSheet("color: #e0e0e0; font-size: 11px;")
        form.addRow(self._make_lbl("Options:", lbl_style), self._skip_padding_cb)

        tabs.addTab(quick_widget, "Quick")

        # ---- JSON editor tab ----
        json_widget = QWidget()
        json_layout = QVBoxLayout(json_widget)
        self._json_editor = QTextEdit()
        self._json_editor.setFont(QFont("Courier New", 9))
        self._json_editor.setStyleSheet("""
            QTextEdit {
                background-color: #0d1117;
                color: #c9d1d9;
                border: 1px solid #2a3050;
                border-radius: 6px;
                font-family: 'Courier New';
                font-size: 10px;
            }
        """)
        self._json_editor.setPlainText(json.dumps(DEFAULT_CONFIG, indent=2))
        json_layout.addWidget(self._json_editor)

        apply_btn = QPushButton("Apply JSON Config")
        apply_btn.clicked.connect(self._on_apply_json)
        apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #1565C0;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 6px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #1976D2; }
        """)
        json_layout.addWidget(apply_btn)
        tabs.addTab(json_widget, "JSON Editor")

        g_layout.addWidget(tabs)

        # Save/Load buttons
        btn_row = QHBoxLayout()
        save_btn = QPushButton("💾 Save Config")
        save_btn.clicked.connect(self._on_save_config)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #37474F;
                color: #e0e0e0;
                border: none;
                border-radius: 5px;
                padding: 5px 10px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #455A64; }
        """)
        load_btn = QPushButton("📂 Load Config")
        load_btn.clicked.connect(self._on_load_config)
        load_btn.setStyleSheet(save_btn.styleSheet())
        btn_row.addWidget(save_btn)
        btn_row.addWidget(load_btn)
        g_layout.addLayout(btn_row)

        layout.addWidget(group)
        layout.addStretch()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_config(self) -> dict:
        """Return the current active config dict."""
        # Sync quick settings into config
        config = dict(self._config)
        config["endianness"] = self._endian_combo.currentText()
        marker = self._marker_edit.text().strip().upper()
        config.setdefault("packet_definition", {})
        config["packet_definition"]["packet_size_bytes"] = self._pkt_size_spin.value()
        config["packet_definition"]["start_markers"] = [marker] if marker else []
        config.setdefault("parser_options", {})
        config["parser_options"]["skip_padding"] = self._skip_padding_cb.isChecked()
        return config

    def load_config(self, config: dict):
        """Load an external config dict into the panel."""
        self._config = config
        # Update quick settings
        endian = config.get("endianness", "big")
        self._endian_combo.setCurrentText(endian)
        pkt_size = config.get("packet_definition", {}).get("packet_size_bytes", 40)
        self._pkt_size_spin.setValue(pkt_size)
        markers = config.get("packet_definition", {}).get("start_markers", [])
        self._marker_edit.setText(markers[0] if markers else "")
        skip = config.get("parser_options", {}).get("skip_padding", True)
        self._skip_padding_cb.setChecked(skip)
        # Update JSON editor
        self._json_editor.setPlainText(json.dumps(config, indent=2))
        self.config_changed.emit(config)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_template_change(self, index: int):
        if index == 0:
            self.load_config(DEFAULT_CONFIG)
        elif index == 1:
            from configs.config_loader import load_template
            try:
                cfg = load_template("modbus_template")
                self.load_config(cfg)
            except Exception:
                pass  # silently keep current config

    def _on_apply_json(self):
        try:
            config = json.loads(self._json_editor.toPlainText())
            self._config = config
            self.config_changed.emit(config)
        except json.JSONDecodeError as exc:
            QMessageBox.critical(self, "JSON Error", f"Invalid JSON:\n{exc}")

    def _on_save_config(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Config", "configs/plc_templates/custom_config.json",
            "JSON (*.json)"
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(self.get_config(), f, indent=2)
                QMessageBox.information(self, "Saved", f"Config saved to:\n{path}")
            except OSError as exc:
                QMessageBox.critical(self, "Save Error", str(exc))

    def _on_load_config(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Config", "configs/plc_templates", "JSON (*.json)"
        )
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                self.load_config(config)
            except (OSError, json.JSONDecodeError) as exc:
                QMessageBox.critical(self, "Load Error", str(exc))

    @staticmethod
    def _make_lbl(text: str, style: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(style)
        return lbl
