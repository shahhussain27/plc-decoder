"""
FileReader – handles reading raw PLC data from TXT, CSV, and binary files.
Normalizes all inputs to clean hex strings for downstream parsing.
"""

import re
import csv
from pathlib import Path
from typing import Generator, Optional
from .logger import AppLogger
from .helpers import validate_hex_string, clean_hex_string

log = AppLogger()

# Supported file extensions
SUPPORTED_EXTENSIONS = {".txt", ".csv", ".bin", ".hex", ".log", ".dat"}
# Max bytes to read per chunk for large-file streaming (32 KB)
CHUNK_SIZE_BYTES = 32 * 1024


class FileReadError(Exception):
    """Raised when a file cannot be read or decoded."""


class FileReader:
    """
    Reads PLC data files and normalizes content to hex strings.

    Supports:
        - Plain text files containing hex strings (one or many per line)
        - CSV files where hex data lives in a specified column
        - Binary files (raw bytes converted to hex)
    """

    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        self._validate_path()
        self._hex_data: Optional[str] = None
        self._raw_lines: list[str] = []
        self._file_size_bytes: int = self.file_path.stat().st_size

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def file_size_kb(self) -> float:
        return self._file_size_bytes / 1024

    @property
    def hex_data(self) -> str:
        """Full concatenated hex string (read-once cached)."""
        if self._hex_data is None:
            self._hex_data = self._read_and_normalize()
        return self._hex_data

    @property
    def raw_lines(self) -> list[str]:
        """Original file lines as strings."""
        return self._raw_lines

    def iter_hex_chunks(self, chunk_hex_chars: int = 65536) -> Generator[str, None, None]:
        """
        Yield hex string chunks for streaming large-file processing.
        chunk_hex_chars: number of hex characters per chunk (default ~32 KB of data).
        """
        full = self.hex_data
        for i in range(0, len(full), chunk_hex_chars):
            yield full[i : i + chunk_hex_chars]

    def detect_format(self) -> str:
        """
        Detect the input format: 'hex_text', 'csv', or 'binary'.
        """
        ext = self.file_path.suffix.lower()
        if ext == ".csv":
            return "csv"
        if ext in (".bin", ".dat"):
            return "binary"
        # Peek at first 256 bytes
        try:
            with open(self.file_path, "rb") as f:
                peek = f.read(256)
            # If high proportion of non-printable bytes → binary
            non_printable = sum(1 for b in peek if b not in range(32, 127) and b not in (9, 10, 13))
            if non_printable / max(len(peek), 1) > 0.3:
                return "binary"
        except OSError:
            pass
        return "hex_text"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_path(self):
        if not self.file_path.exists():
            raise FileReadError(f"File not found: {self.file_path}")
        if not self.file_path.is_file():
            raise FileReadError(f"Not a regular file: {self.file_path}")
        ext = self.file_path.suffix.lower()
        if ext and ext not in SUPPORTED_EXTENSIONS:
            log.warning(
                "Unsupported extension '%s' — will attempt text read anyway.", ext
            )

    def _read_and_normalize(self) -> str:
        """Dispatch to the appropriate reader and return clean hex string."""
        fmt = self.detect_format()
        log.info(
            "Reading '%s' as format='%s' (%.1f KB)",
            self.file_path.name,
            fmt,
            self.file_size_kb,
        )
        if fmt == "binary":
            return self._read_binary()
        if fmt == "csv":
            return self._read_csv()
        return self._read_text()

    def _read_text(self) -> str:
        """
        Read plain-text file, extract all hex tokens.
        Handles multiple hex strings per line and comment lines.
        """
        hex_parts: list[str] = []
        try:
            with open(self.file_path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    stripped = line.strip()
                    self._raw_lines.append(stripped)
                    # Skip comment lines
                    if stripped.startswith("#") or stripped.startswith("//"):
                        continue
                    # Extract hex tokens (sequences of hex chars ≥ 2 long)
                    tokens = re.findall(r"[0-9A-Fa-f]{2,}", stripped)
                    for token in tokens:
                        if len(token) % 2 == 0:
                            hex_parts.append(token.upper())
        except OSError as exc:
            raise FileReadError(f"Cannot read file: {exc}") from exc

        result = "".join(hex_parts)
        log.debug("Extracted %d hex chars from text file.", len(result))
        return result

    def _read_binary(self) -> str:
        """Read binary file and convert bytes to hex string."""
        try:
            with open(self.file_path, "rb") as f:
                data = f.read()
            self._raw_lines = [data.hex().upper()]
            hex_str = data.hex().upper()
            log.debug("Read %d bytes from binary file.", len(data))
            return hex_str
        except OSError as exc:
            raise FileReadError(f"Cannot read binary file: {exc}") from exc

    def _read_csv(self, hex_col: int = 0) -> str:
        """
        Read CSV and extract hex data from the most likely column.
        Auto-detects the column containing hex strings if hex_col guess is wrong.
        """
        hex_parts: list[str] = []
        try:
            with open(self.file_path, "r", encoding="utf-8", errors="replace", newline="") as f:
                reader = csv.reader(f)
                rows = list(reader)

            if not rows:
                return ""

            # Auto-detect hex column by scanning header or first data row
            target_col = self._detect_hex_column(rows)
            log.debug("CSV: using column index %d for hex data.", target_col)

            for row in rows:
                self._raw_lines.append(",".join(row))
                if len(row) <= target_col:
                    continue
                cell = row[target_col].strip()
                if validate_hex_string(cell):
                    hex_parts.append(clean_hex_string(cell))
        except OSError as exc:
            raise FileReadError(f"Cannot read CSV file: {exc}") from exc

        result = "".join(hex_parts)
        log.debug("Extracted %d hex chars from CSV.", len(result))
        return result

    @staticmethod
    def _detect_hex_column(rows: list[list[str]]) -> int:
        """
        Scan rows and return the column index with the highest proportion
        of valid hex tokens (preferring the longest continuous hex strings).
        """
        if not rows:
            return 0
        col_scores: dict[int, int] = {}
        for row in rows[:min(10, len(rows))]:
            for idx, cell in enumerate(row):
                cell = cell.strip()
                if validate_hex_string(cell):
                    col_scores[idx] = col_scores.get(idx, 0) + len(cell)
        if col_scores:
            return max(col_scores, key=lambda k: col_scores[k])
        return 0
