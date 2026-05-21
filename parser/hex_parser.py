"""
HexParser – the primary parser implementation for LiraNET / Mitsubishi FX5U
PLC protocol (and generic PLC hex streams).

Orchestrates: PacketDetector → FieldExtractor → ParsedRecord assembly.
Supports configurable JSON format definitions.
"""

import re
from datetime import datetime
from typing import Optional
from .base_parser import BaseParser, ParsedRecord, ParseStats
from .packet_detector import PacketDetector
from .field_extractor import FieldExtractor
from utils.helpers import (
    hex_to_int, clean_hex_string, chunk_hex,
    is_plausible_year, is_plausible_month, is_plausible_day,
    is_plausible_hour, is_plausible_minute_second,
)
from utils.logger import AppLogger

log = AppLogger()

# Null/padding pattern — long runs of 0x00
PADDING_RE = re.compile(r"^(00)+$")


class HexParser(BaseParser):
    """
    Parses a continuous hex data stream into structured PLC records.

    Capabilities:
        - Marker-based, fixed-length, or heuristic timestamp packet detection
        - 16-bit and 32-bit field extraction
        - Big-endian and little-endian support (per-field)
        - Padding detection and skipping
        - Graceful handling of corrupt/truncated packets
        - Raw hex preserved alongside decoded values
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self._detector = PacketDetector(config)
        field_defs = config.get("fields", [])
        self._extractor = FieldExtractor(field_defs)
        self._ts_config = config.get("timestamp", {})
        self._min_packet_hex_len = config.get("packet_definition", {}).get(
            "packet_size_bytes", 10
        ) * 2
        # Minimum valid non-zero bytes to consider a packet non-empty
        self._min_valid_bytes = config.get("parser_options", {}).get(
            "min_valid_bytes", 4
        )

    # ------------------------------------------------------------------
    # BaseParser contract
    # ------------------------------------------------------------------

    def parse_hex_stream(self, hex_data: str) -> list[ParsedRecord]:
        """
        Main entry point. Parse full hex stream and return decoded records.
        """
        self._start_timer()
        self._records.clear()
        self._errors.clear()
        self._stats = ParseStats()

        data = clean_hex_string(hex_data)
        if not data:
            log.warning("Empty hex stream provided — nothing to parse.")
            self._stop_timer()
            return []

        log.info("Starting parse: %d hex chars (%.1f KB)", len(data), len(data) / 2048)
        self._stats.total_bytes = len(data) // 2

        # 1) Detect packet boundaries
        boundaries = self._detector.find_packets(data)
        self._stats.total_packets = len(boundaries)

        # 2) Parse each packet
        for idx, boundary in enumerate(boundaries):
            packet_hex = data[boundary.start: boundary.end]

            if self._is_padding(packet_hex):
                log.debug("Packet %d at offset %d is all-zeros padding, skipping.",
                          idx, boundary.start)
                self._stats.total_packets -= 1
                continue

            record = self._parse_single_packet(packet_hex, idx, boundary.start)
            self._records.append(record)
            if record.is_valid:
                self._stats.valid_packets += 1
            else:
                self._stats.invalid_packets += 1

        self._update_timestamp_range()
        self._stop_timer()

        log.info(
            "Parse complete: %d/%d valid records in %.2fs",
            self._stats.valid_packets,
            self._stats.total_packets,
            self._stats.parse_duration_s,
        )
        return self._records

    # ------------------------------------------------------------------
    # Single-packet parsing
    # ------------------------------------------------------------------

    def _parse_single_packet(self, packet_hex: str, idx: int, offset: int) -> ParsedRecord:
        """Decode one hex packet into a ParsedRecord."""
        record = ParsedRecord()
        record.record_index = idx + 1
        record.packet_offset = offset
        record.raw_hex = packet_hex
        record.raw_hex_spaced = " ".join(
            packet_hex[i: i + 4] for i in range(0, len(packet_hex), 4)
        )

        try:
            # 1) Extract all named fields from config
            fields = self._extractor.extract(packet_hex)
            record.registers = self._extractor.extract_registers(packet_hex)

            # 2) Populate timestamp fields
            self._populate_timestamp(record, fields, packet_hex)

            # 3) Populate identification fields
            self._populate_id_fields(record, fields, packet_hex)

            # 4) Validate record
            record.is_valid = self._validate_record(record)

        except Exception as exc:
            record.is_valid = False
            record.parse_errors.append(f"Unexpected error: {exc}")
            self._record_error(offset, str(exc), packet_hex)
            log.error("Packet %d parse error: %s", idx, exc)

        return record

    # ------------------------------------------------------------------
    # Timestamp population
    # ------------------------------------------------------------------

    def _populate_timestamp(self, record: ParsedRecord, fields: dict, packet_hex: str):
        """
        Populate year/month/day/hour/minute/second from extracted fields.
        Falls back to heuristic scan if fields not present in config.
        """
        # Named field approach (from config)
        year = self._get_field_value(fields, "year")
        month = self._get_field_value(fields, "month")
        day = self._get_field_value(fields, "day")
        hour = self._get_field_value(fields, "hour")
        minute = self._get_field_value(fields, "minute")
        second = self._get_field_value(fields, "second")
        ms = self._get_field_value(fields, "millisecond")

        # Heuristic fallback: scan for Y/M/D pattern in packet words
        if year is None or month is None or day is None:
            ts = self._heuristic_timestamp_scan(packet_hex)
            if ts:
                year, month, day, hour, minute, second, ms = (
                    ts.get("year"), ts.get("month"), ts.get("day"),
                    ts.get("hour"), ts.get("minute"), ts.get("second"),
                    ts.get("millisecond"),
                )
                record.parse_errors.append("timestamp:heuristic_fallback")

        record.year = year
        record.month = month
        record.day = day
        record.hour = hour
        record.minute = minute
        record.second = second
        record.millisecond = ms

        # Build human-readable timestamp string
        if all(v is not None for v in (year, month, day)):
            try:
                h = hour or 0
                m = minute or 0
                s = second or 0
                record.timestamp_str = (
                    f"{year:04d}-{month:02d}-{day:02d} {h:02d}:{m:02d}:{s:02d}"
                )
                # Validate using datetime constructor
                datetime(year, month, day, h, m, s)
            except (ValueError, TypeError) as exc:
                record.parse_errors.append(f"invalid_timestamp:{exc}")
                record.timestamp_str = (
                    f"{year or '?'}-{month or '?'}-{day or '?'}"
                )

    def _heuristic_timestamp_scan(self, packet_hex: str) -> Optional[dict]:
        """
        Walk through packet words and find the first Y/M/D/H/Min/Sec sequence.
        Works for big-endian 16-bit words (most common in LiraNET protocol).
        """
        words = chunk_hex(packet_hex, 4)  # 4 hex chars per word
        for i in range(len(words) - 5):
            year = hex_to_int(words[i])
            month = hex_to_int(words[i + 1])
            day = hex_to_int(words[i + 2])
            hour = hex_to_int(words[i + 3])
            minute = hex_to_int(words[i + 4])
            second = hex_to_int(words[i + 5]) if i + 5 < len(words) else None
            ms = hex_to_int(words[i + 6]) if i + 6 < len(words) else None

            if (year and is_plausible_year(year)
                    and month and is_plausible_month(month)
                    and day and is_plausible_day(day)
                    and (hour is None or is_plausible_hour(hour))
                    and (minute is None or is_plausible_minute_second(minute))):
                return {
                    "year": year, "month": month, "day": day,
                    "hour": hour, "minute": minute, "second": second,
                    "millisecond": ms, "word_index": i,
                }
        return None

    # ------------------------------------------------------------------
    # ID fields
    # ------------------------------------------------------------------

    def _populate_id_fields(self, record: ParsedRecord, fields: dict, packet_hex: str):
        """Populate sub_client_id and protocol_id from config fields."""
        record.sub_client_id = self._get_field_value(fields, "sub_client_id")
        record.protocol_id = self._get_field_value(fields, "protocol_id")

        # If sub_client_id not in config but packet starts with recognisable header
        if record.sub_client_id is None and len(packet_hex) >= 4:
            candidate = hex_to_int(packet_hex[:4])
            # LiraNET packets typically start with sub-client-id (e.g. 0x03E9 = 1001)
            if candidate and 1 <= candidate <= 9999:
                record.sub_client_id = candidate

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_record(self, record: ParsedRecord) -> bool:
        """Run validation checks; return False if any hard failure."""
        errors = []

        # Timestamp sanity
        if record.year and not is_plausible_year(record.year):
            errors.append(f"implausible_year:{record.year}")
        if record.month and not is_plausible_month(record.month):
            errors.append(f"implausible_month:{record.month}")
        if record.day and not is_plausible_day(record.day):
            errors.append(f"implausible_day:{record.day}")
        if record.hour is not None and not is_plausible_hour(record.hour):
            errors.append(f"implausible_hour:{record.hour}")
        if record.minute is not None and not is_plausible_minute_second(record.minute):
            errors.append(f"implausible_minute:{record.minute}")
        if record.second is not None and not is_plausible_minute_second(record.second):
            errors.append(f"implausible_second:{record.second}")

        # Register sanity — filter out 9999 sentinel values
        for reg, info in record.registers.items():
            val = info.get("decimal")
            if val == 9999:
                info["decimal"] = None   # treat 9999 as "no data"

        record.parse_errors.extend(errors)
        # Only HARD failures cause is_valid=False
        hard_failures = [e for e in errors if "implausible_year" in e
                         or "implausible_month" in e or "implausible_day" in e]
        return len(hard_failures) == 0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_field_value(fields: dict, name: str) -> Optional[int]:
        """Safely get decimal value from extracted fields dict."""
        if name in fields:
            return fields[name].get("decimal")
        return None

    @staticmethod
    def _is_padding(packet_hex: str) -> bool:
        """Return True if packet is entirely zeros (padding bytes)."""
        return bool(PADDING_RE.fullmatch(packet_hex))
