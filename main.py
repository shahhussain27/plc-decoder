#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PLC Decoder Pro — main entry point.

Usage:
    python main.py                  # Launch GUI
    python main.py --cli <file>     # CLI mode (parse + export to Excel)
    python main.py --analyze <file> # Auto-analyze structure only
"""

import sys
import argparse
from pathlib import Path


def launch_gui():
    """Launch the PySide6 desktop application."""
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QIcon, QFont
    from ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("PLC Decoder Pro")
    app.setOrganizationName("PLCDecoder")
    app.setApplicationVersion("1.0.0")

    # Set default font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


def run_cli(input_file: str, output_file: str | None, config_file: str | None):
    """Run parser from command line without GUI."""
    import json
    from utils.file_reader import FileReader, FileReadError
    from utils.logger import AppLogger
    from parser.hex_parser import HexParser
    from exporters.excel_exporter import ExcelExporter

    log = AppLogger()

    # Load config
    if config_file:
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
    else:
        # Default: LiraNET FX5U
        default_cfg = Path(__file__).parent / "configs/plc_templates/liranet_fx5u.json"
        with open(default_cfg, "r", encoding="utf-8") as f:
            config = json.load(f)

    # Read input
    try:
        reader = FileReader(input_file)
        hex_data = reader.hex_data
    except FileReadError as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    # Parse
    parser = HexParser(config)
    records = parser.parse_hex_stream(hex_data)
    stats = parser.get_stats()
    errors = parser.get_errors()

    # Ensure UTF-8 output on Windows
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"\n[OK] Parsed: {stats.valid_packets}/{stats.total_packets} valid packets")
    print(f"   Duration: {stats.parse_duration_s:.3f}s")
    if stats.timestamp_range[0]:
        print(f"   Timestamp range: {stats.timestamp_range[0]} -- {stats.timestamp_range[1]}")

    # Export
    out = output_file or Path(input_file).stem + "_decoded.xlsx"
    exporter = ExcelExporter(out, config)
    saved = exporter.export(records, stats, errors, Path(input_file).name)
    print(f"   Excel saved: {saved}\n")


def run_analyze(input_file: str):
    """Auto-analyze structure and print suggestions."""
    from utils.file_reader import FileReader, FileReadError
    from analyzer.structure_analyzer import StructureAnalyzer
    import json

    try:
        reader = FileReader(input_file)
        hex_data = reader.hex_data
    except FileReadError as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    analyzer = StructureAnalyzer()
    result = analyzer.analyze(hex_data)
    print("\n=== Structure Analysis ===\n")
    print(result["summary"])
    print("\n=== Suggested Config ===\n")
    print(json.dumps(result["suggested_config"], indent=2))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="PLC Decoder Pro — Binary/Hex to Excel converter"
    )
    parser.add_argument("--cli", metavar="INPUT_FILE",
                        help="Run in CLI mode (no GUI), parse INPUT_FILE")
    parser.add_argument("--output", metavar="OUTPUT_FILE",
                        help="Output Excel file path (CLI mode)")
    parser.add_argument("--config", metavar="CONFIG_JSON",
                        help="Path to JSON config template")
    parser.add_argument("--analyze", metavar="INPUT_FILE",
                        help="Auto-analyze structure of INPUT_FILE (no GUI)")

    args = parser.parse_args()

    if args.analyze:
        run_analyze(args.analyze)
    elif args.cli:
        run_cli(args.cli, args.output, args.config)
    else:
        launch_gui()
