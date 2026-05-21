"""
CsvExporter – lightweight CSV export for parsed PLC records.
Used as a fast alternative when Excel is not needed.
"""

import csv
from pathlib import Path
from parser.base_parser import ParsedRecord
from utils.logger import AppLogger

log = AppLogger()


class CsvExporter:
    """Export parsed records to CSV."""

    def __init__(self, output_path: str | Path):
        self.output_path = Path(output_path)

    def export(self, records: list[ParsedRecord]) -> Path:
        """Write records to CSV. Returns path to saved file."""
        if not records:
            log.warning("No records to export to CSV.")
            return self.output_path

        rows = [r.to_flat_dict() for r in records]
        fieldnames = list(rows[0].keys())

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        log.info("CSV exported: %s (%d records)", self.output_path, len(records))
        return self.output_path
