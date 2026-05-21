"""
BaseParser – abstract base class for all PLC parsers.
Defines the standard interface and shared state management.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
import time


@dataclass
class ParsedRecord:
    """
    A single decoded PLC data record.
    All fields are stored as their decoded human-readable values plus raw hex.
    """
    # ---------- Identification ----------
    record_index: int = 0
    packet_offset: int = 0          # Byte offset in source data
    raw_hex: str = ""               # Full raw hex for this record
    raw_hex_spaced: str = ""        # Space-separated version for display

    # ---------- LiraNET Header ----------
    sub_client_id: Optional[int] = None   # e.g. 0x03E9 = 1001
    protocol_id: Optional[int] = None

    # ---------- Timestamp ----------
    year: Optional[int] = None
    month: Optional[int] = None
    day: Optional[int] = None
    hour: Optional[int] = None
    minute: Optional[int] = None
    second: Optional[int] = None
    millisecond: Optional[int] = None
    timestamp_str: str = ""         # Human-readable "YYYY-MM-DD HH:MM:SS"

    # ---------- Data Registers ----------
    registers: dict[str, Any] = field(default_factory=dict)
    # {register_address: {"name": str, "raw_hex": str, "decimal": int, "description": str}}

    # ---------- Quality ----------
    is_valid: bool = True
    parse_errors: list[str] = field(default_factory=list)
    crc_valid: Optional[bool] = None

    def to_flat_dict(self) -> dict[str, Any]:
        """Flatten record to a dict suitable for DataFrame/Excel row."""
        row = {
            "Record #": self.record_index,
            "Offset (bytes)": self.packet_offset // 2,
            "Timestamp": self.timestamp_str,
            "Year": self.year,
            "Month": self.month,
            "Day": self.day,
            "Hour": self.hour,
            "Minute": self.minute,
            "Second": self.second,
            "Millisecond": self.millisecond,
            "SubClient ID": self.sub_client_id,
            "Valid": "✓" if self.is_valid else "✗",
        }
        # Flatten registers
        for addr, info in self.registers.items():
            col_name = f"{addr} ({info.get('name', '')})"
            row[col_name] = info.get("decimal")
        row["Raw Hex"] = self.raw_hex_spaced
        row["Parse Errors"] = "; ".join(self.parse_errors) if self.parse_errors else ""
        return row


@dataclass
class ParseStats:
    """Aggregated statistics from a parse run."""
    total_packets: int = 0
    valid_packets: int = 0
    invalid_packets: int = 0
    total_bytes: int = 0
    parse_duration_s: float = 0.0
    timestamp_range: tuple[str, str] = ("", "")
    error_summary: dict[str, int] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        if self.total_packets == 0:
            return 0.0
        return (self.valid_packets / self.total_packets) * 100


class BaseParser(ABC):
    """
    Abstract base for all PLC parsers.
    Subclasses must implement `parse_hex_stream()`.
    """

    def __init__(self, config: dict):
        """
        Args:
            config: Parsed JSON config (format definition).
        """
        self.config = config
        self._records: list[ParsedRecord] = []
        self._stats = ParseStats()
        self._errors: list[dict] = []   # [{offset, error, raw_hex}]

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def parse_hex_stream(self, hex_data: str) -> list[ParsedRecord]:
        """
        Parse a raw hex string and return decoded records.
        Must populate self._records and self._stats.
        """

    # ------------------------------------------------------------------
    # Common helpers available to all subclasses
    # ------------------------------------------------------------------

    def get_records(self) -> list[ParsedRecord]:
        return self._records

    def get_stats(self) -> ParseStats:
        return self._stats

    def get_errors(self) -> list[dict]:
        return self._errors

    def _record_error(self, offset: int, message: str, raw_hex: str = ""):
        """Log a packet-level error."""
        self._errors.append(
            {"offset": offset, "error": message, "raw_hex": raw_hex[:64]}
        )
        self._stats.error_summary[message] = (
            self._stats.error_summary.get(message, 0) + 1
        )

    def _start_timer(self):
        self._t0 = time.perf_counter()

    def _stop_timer(self):
        self._stats.parse_duration_s = time.perf_counter() - self._t0

    def _update_timestamp_range(self):
        """Compute min/max timestamp across all valid records."""
        stamps = [r.timestamp_str for r in self._records if r.timestamp_str and r.is_valid]
        if stamps:
            self._stats.timestamp_range = (min(stamps), max(stamps))
