"""
Main Window – root PySide6 application window.
Orchestrates all UI panels and the parse/export workflow.
"""

import json
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QSplitter, QVBoxLayout, QHBoxLayout,
    QStatusBar, QTabWidget, QMessageBox, QProgressBar, QLabel,
    QApplication, QMenuBar, QMenu, QFileDialog, QToolBar,
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QIcon, QFont, QAction, QColor, QPalette

from ui.file_panel import FilePanel
from ui.config_panel import ConfigPanel
from ui.preview_table import PreviewTable
from ui.hex_viewer import HexViewer
from ui.stats_panel import StatsPanel
from ui.log_panel import LogPanel

from utils.file_reader import FileReader, FileReadError
from utils.logger import AppLogger
from parser.hex_parser import HexParser
from parser.base_parser import ParsedRecord, ParseStats
from analyzer.structure_analyzer import StructureAnalyzer
from exporters.excel_exporter import ExcelExporter
from exporters.csv_exporter import CsvExporter

log = AppLogger()

APP_TITLE = "PLC Decoder Pro — LiraNET / Mitsubishi FX5U"
VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Background parse worker
# ---------------------------------------------------------------------------

class ParseWorker(QThread):
    """Runs the parser in a background thread to keep the UI responsive."""

    finished = Signal(list, object, list)  # records, stats, errors
    error = Signal(str)
    progress = Signal(int)  # 0–100

    def __init__(self, hex_data: str, config: dict):
        super().__init__()
        self._hex_data = hex_data
        self._config = config

    def run(self):
        try:
            self.progress.emit(10)
            parser = HexParser(self._config)
            self.progress.emit(30)
            records = parser.parse_hex_stream(self._hex_data)
            self.progress.emit(85)
            stats = parser.get_stats()
            errors = parser.get_errors()
            self.progress.emit(100)
            self.finished.emit(records, stats, errors)
        except Exception as exc:
            log.error("ParseWorker error: %s", exc)
            self.error.emit(str(exc))


class AnalyzeWorker(QThread):
    """Runs the structure analyzer in a background thread."""

    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, hex_data: str):
        super().__init__()
        self._hex_data = hex_data

    def run(self):
        try:
            analyzer = StructureAnalyzer()
            result = analyzer.analyze(self._hex_data)
            self.finished.emit(result)
        except Exception as exc:
            log.error("AnalyzeWorker error: %s", exc)
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    """
    Primary application window.
    Layout:
        Left column  → FilePanel + ConfigPanel
        Right column → TabWidget(PreviewTable | HexViewer | StatsPanel | LogPanel)
        Bottom       → StatusBar with progress
    """

    def __init__(self):
        super().__init__()
        self._hex_data: str = ""
        self._records: list[ParsedRecord] = []
        self._stats: Optional[ParseStats] = None
        self._errors: list[dict] = []
        self._config: dict = {}
        self._source_file: str = ""
        self._parse_worker: Optional[ParseWorker] = None
        self._analyze_worker: Optional[AnalyzeWorker] = None

        self._setup_window()
        self._build_menu()
        self._build_toolbar()
        self._build_central()
        self._build_statusbar()
        self._apply_dark_theme()

        log.info("PLC Decoder %s started.", VERSION)

    # ------------------------------------------------------------------
    # Window setup
    # ------------------------------------------------------------------

    def _setup_window(self):
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(1280, 800)
        self.resize(1440, 900)

    def _build_menu(self):
        bar = self.menuBar()

        # File
        file_menu = bar.addMenu("&File")
        open_act = QAction("&Open Data File…", self)
        open_act.setShortcut("Ctrl+O")
        open_act.triggered.connect(self._on_open_file)
        file_menu.addAction(open_act)

        load_cfg_act = QAction("Load &Config Template…", self)
        load_cfg_act.triggered.connect(self._on_load_config)
        file_menu.addAction(load_cfg_act)

        file_menu.addSeparator()
        export_xlsx_act = QAction("Export to &Excel…", self)
        export_xlsx_act.setShortcut("Ctrl+E")
        export_xlsx_act.triggered.connect(self._on_export_excel)
        file_menu.addAction(export_xlsx_act)

        export_csv_act = QAction("Export to &CSV…", self)
        export_csv_act.triggered.connect(self._on_export_csv)
        file_menu.addAction(export_csv_act)

        file_menu.addSeparator()
        file_menu.addAction("E&xit", self.close, "Ctrl+Q")

        # Tools
        tools_menu = bar.addMenu("&Tools")
        analyze_act = QAction("&Analyze Structure (Auto-detect)…", self)
        analyze_act.setShortcut("Ctrl+A")
        analyze_act.triggered.connect(self._on_analyze_structure)
        tools_menu.addAction(analyze_act)

        batch_act = QAction("&Batch Process Folder…", self)
        batch_act.triggered.connect(self._on_batch_process)
        tools_menu.addAction(batch_act)

        # Help
        help_menu = bar.addMenu("&Help")
        help_menu.addAction("&About", self._on_about)

    def _build_toolbar(self):
        tb = self.addToolBar("Main")
        tb.setMovable(False)
        tb.setFloatable(False)

        open_act = QAction("📂  Open File", self)
        open_act.triggered.connect(self._on_open_file)
        tb.addAction(open_act)

        parse_act = QAction("▶  Parse", self)
        parse_act.triggered.connect(self._on_parse)
        tb.addAction(parse_act)

        analyze_act = QAction("🔍  Auto-Analyze", self)
        analyze_act.triggered.connect(self._on_analyze_structure)
        tb.addAction(analyze_act)

        tb.addSeparator()
        export_act = QAction("💾  Export Excel", self)
        export_act.triggered.connect(self._on_export_excel)
        tb.addAction(export_act)

    def _build_central(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(8)

        # Main horizontal splitter
        splitter = QSplitter(Qt.Horizontal)

        # ---- Left panel ----
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.file_panel = FilePanel()
        self.file_panel.file_selected.connect(self._on_file_selected)
        self.file_panel.parse_requested.connect(self._on_parse)
        left_layout.addWidget(self.file_panel)

        self.config_panel = ConfigPanel()
        self.config_panel.config_changed.connect(self._on_config_changed)
        left_layout.addWidget(self.config_panel)

        left_widget.setMinimumWidth(320)
        left_widget.setMaximumWidth(400)

        # ---- Right panel (tabs) ----
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        self.preview_table = PreviewTable()
        self.tabs.addTab(self.preview_table, "📋  Records")

        self.hex_viewer = HexViewer()
        self.tabs.addTab(self.hex_viewer, "🔢  Hex Viewer")

        self.stats_panel = StatsPanel()
        self.tabs.addTab(self.stats_panel, "📊  Statistics")

        self.log_panel = LogPanel()
        self.tabs.addTab(self.log_panel, "📝  Error Log")

        splitter.addWidget(left_widget)
        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([340, 1100])

        root_layout.addWidget(splitter)

    def _build_statusbar(self):
        self._status = QStatusBar()
        self.setStatusBar(self._status)

        self._status_label = QLabel("Ready — load a PLC data file to begin.")
        self._status.addPermanentWidget(self._status_label, 1)

        self._progress = QProgressBar()
        self._progress.setFixedWidth(200)
        self._progress.setVisible(False)
        self._status.addPermanentWidget(self._progress)

    # ------------------------------------------------------------------
    # Dark theme
    # ------------------------------------------------------------------

    def _apply_dark_theme(self):
        """Apply a professional dark theme using Qt stylesheets."""
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #1a1d2e;
                color: #e0e0e0;
                font-family: 'Segoe UI', 'Inter', sans-serif;
                font-size: 13px;
            }
            QMenuBar {
                background-color: #12151f;
                color: #c0c8d8;
                padding: 2px;
                border-bottom: 1px solid #2a2d3e;
            }
            QMenuBar::item:selected { background-color: #2196F3; color: white; }
            QMenu {
                background-color: #1e2130;
                border: 1px solid #2a2d3e;
                color: #e0e0e0;
            }
            QMenu::item:selected { background-color: #2196F3; }

            QToolBar {
                background-color: #12151f;
                border-bottom: 1px solid #2a2d3e;
                spacing: 4px;
                padding: 4px 8px;
            }
            QToolBar QToolButton {
                background-color: #252840;
                color: #90CAF9;
                border: 1px solid #2a2d3e;
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 13px;
            }
            QToolBar QToolButton:hover { background-color: #2196F3; color: white; }

            QTabWidget::pane {
                border: 1px solid #2a3050;
                border-radius: 8px;
                background-color: #1e2130;
            }
            QTabBar::tab {
                background-color: #12151f;
                color: #8899aa;
                padding: 8px 18px;
                border-radius: 6px 6px 0 0;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
            }
            QTabBar::tab:hover:!selected { background-color: #252840; color: #c0d0f0; }

            QSplitter::handle { background-color: #2a2d3e; width: 4px; }

            QStatusBar {
                background-color: #12151f;
                color: #8899aa;
                border-top: 1px solid #2a2d3e;
            }
            QProgressBar {
                background-color: #252840;
                border: 1px solid #2a2d3e;
                border-radius: 4px;
                text-align: center;
                color: white;
            }
            QProgressBar::chunk { background-color: #2196F3; border-radius: 4px; }

            QScrollBar:vertical {
                background: #1a1d2e;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #3a4060;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover { background: #2196F3; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open PLC Data File",
            "",
            "All Supported (*.txt *.csv *.bin *.hex *.log *.dat);;"
            "Text Files (*.txt);;CSV Files (*.csv);;Binary Files (*.bin *.dat);;All Files (*)",
        )
        if path:
            self.file_panel.set_file(path)
            self._on_file_selected(path)

    def _on_file_selected(self, path: str):
        """Load file, read hex data, update hex viewer."""
        try:
            self._status_label.setText(f"Loading: {Path(path).name}…")
            reader = FileReader(path)
            self._hex_data = reader.hex_data
            self._source_file = Path(path).name
            self.hex_viewer.load_hex(self._hex_data)
            self.file_panel.update_info(
                size_kb=reader.file_size_kb,
                hex_chars=len(self._hex_data),
                fmt=reader.detect_format(),
            )
            self._status_label.setText(
                f"Loaded '{self._source_file}' — {reader.file_size_kb:.1f} KB "
                f"({len(self._hex_data)//2} bytes of hex data)"
            )
            log.info("File loaded: %s", path)
        except FileReadError as exc:
            QMessageBox.critical(self, "File Read Error", str(exc))
            self._status_label.setText("Error loading file.")

    def _on_load_config(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Config Template", "configs/plc_templates",
            "JSON Config (*.json);;All Files (*)"
        )
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                self.config_panel.load_config(config)
                self._config = self.config_panel.get_config()
                self._status_label.setText(f"Config loaded: {Path(path).name}")
            except (OSError, json.JSONDecodeError) as exc:
                QMessageBox.critical(self, "Config Load Error", str(exc))

    def _on_config_changed(self, config: dict):
        self._config = config

    def _on_parse(self):
        if not self._hex_data:
            QMessageBox.information(self, "No Data", "Please load a PLC data file first.")
            return

        config = self.config_panel.get_config()
        self._config = config
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._status_label.setText("Parsing PLC data…")
        self.tabs.setCurrentIndex(0)

        self._parse_worker = ParseWorker(self._hex_data, config)
        self._parse_worker.progress.connect(self._progress.setValue)
        self._parse_worker.finished.connect(self._on_parse_done)
        self._parse_worker.error.connect(self._on_parse_error)
        self._parse_worker.start()

    def _on_parse_done(self, records: list, stats: object, errors: list):
        self._records = records
        self._stats = stats
        self._errors = errors
        self._progress.setVisible(False)

        self.preview_table.load_records(records, self._config)
        self.stats_panel.load_stats(stats)
        self.log_panel.load_errors(errors, log.get_records())

        self._status_label.setText(
            f"Parsed {stats.valid_packets} valid / {stats.total_packets} total packets "
            f"in {stats.parse_duration_s:.2f}s"
        )
        log.info("Parse done: %d/%d valid", stats.valid_packets, stats.total_packets)

    def _on_parse_error(self, msg: str):
        self._progress.setVisible(False)
        self._status_label.setText(f"Parse error: {msg}")
        QMessageBox.critical(self, "Parse Error", msg)

    def _on_analyze_structure(self):
        if not self._hex_data:
            QMessageBox.information(self, "No Data", "Please load a PLC data file first.")
            return
        self._status_label.setText("Analyzing structure (auto-detection)…")
        self._analyze_worker = AnalyzeWorker(self._hex_data)
        self._analyze_worker.finished.connect(self._on_analyze_done)
        self._analyze_worker.error.connect(lambda e: QMessageBox.critical(self, "Error", e))
        self._analyze_worker.start()

    def _on_analyze_done(self, result: dict):
        summary = result.get("summary", "No summary.")
        suggested = result.get("suggested_config", {})

        # Offer to load the suggested config
        reply = QMessageBox.question(
            self,
            "Structure Analysis Complete",
            f"{summary}\n\nApply suggested parsing config?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.config_panel.load_config(suggested)
            self._config = self.config_panel.get_config()
            self._status_label.setText("Auto-detected config applied — click Parse.")
        else:
            self._status_label.setText("Analysis complete.")

    def _on_export_excel(self):
        if not self._records:
            QMessageBox.information(self, "No Records", "Parse the data first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Excel Report", "output/plc_decoded.xlsx",
            "Excel Workbook (*.xlsx)"
        )
        if not path:
            return
        try:
            exporter = ExcelExporter(path, self._config)
            saved = exporter.export(
                self._records, self._stats, self._errors, self._source_file
            )
            self._status_label.setText(f"Excel exported: {saved}")
            QMessageBox.information(self, "Export Complete", f"Saved to:\n{saved}")
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", str(exc))
            log.error("Excel export error: %s", exc)

    def _on_export_csv(self):
        if not self._records:
            QMessageBox.information(self, "No Records", "Parse the data first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save CSV", "output/plc_decoded.csv", "CSV (*.csv)"
        )
        if not path:
            return
        try:
            exporter = CsvExporter(path)
            saved = exporter.export(self._records)
            self._status_label.setText(f"CSV exported: {saved}")
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", str(exc))

    def _on_batch_process(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder for Batch Processing")
        if not folder:
            return
        folder_path = Path(folder)
        files = list(folder_path.glob("*.txt")) + list(folder_path.glob("*.csv")) + \
                list(folder_path.glob("*.bin"))
        if not files:
            QMessageBox.information(self, "Batch Process", "No supported files found in folder.")
            return
        output_dir = folder_path / "decoded_output"
        output_dir.mkdir(exist_ok=True)
        success = 0
        config = self.config_panel.get_config()
        for file in files:
            try:
                reader = FileReader(file)
                parser = HexParser(config)
                records = parser.parse_hex_stream(reader.hex_data)
                out = output_dir / f"{file.stem}_decoded.xlsx"
                ExcelExporter(out, config).export(
                    records, parser.get_stats(), parser.get_errors(), file.name
                )
                success += 1
            except Exception as exc:
                log.error("Batch: failed on %s: %s", file.name, exc)
        QMessageBox.information(
            self, "Batch Complete",
            f"Processed {success}/{len(files)} files.\nOutput: {output_dir}"
        )

    def _on_about(self):
        QMessageBox.about(
            self,
            "About PLC Decoder Pro",
            f"<b>PLC Decoder Pro v{VERSION}</b><br>"
            "<br>Industrial-grade PLC binary/hex data decoder.<br>"
            "Supports LiraNET / Mitsubishi FX5U protocol.<br><br>"
            "<i>Features: auto packet detection, timestamp recognition,<br>"
            "Excel export, hex viewer, batch processing.</i><br><br>"
            "© 2024 — Production build",
        )
