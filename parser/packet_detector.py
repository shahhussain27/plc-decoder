"""
PacketDetector – responsible for finding valid packet boundaries within
a continuous hex stream.

Strategy:
  1. Try config-specified packet markers / start sequences first.
  2. Fall back to heuristic timestamp detection (look for valid year–month–day
     windows using 16-bit big-endian words).
  3. If all else fails, split stream by fixed packet length from config.
"""

import re
from typing import Optional
from utils.helpers import hex_to_int, is_plausible_year, is_plausible_month, is_plausible_day
from utils.logger import AppLogger

log = AppLogger()


class PacketBoundary:
    """Represents a detected packet start/end within a hex stream."""

    def __init__(self, start: int, end: int, confidence: float, method: str):
        self.start = start    # hex-char index
        self.end = end        # hex-char index (exclusive)
        self.confidence = confidence  # 0.0 – 1.0
        self.method = method  # detection method label

    def __repr__(self):
        return (f"PacketBoundary(start={self.start}, end={self.end}, "
                f"conf={self.confidence:.2f}, method={self.method!r})")


class PacketDetector:
    """
    Detects packet boundaries in a raw hex stream using multiple strategies.

    Detection strategies (tried in order):
        1. Marker-based  – fixed start/end hex markers from config
        2. Length-based  – fixed packet_size_bytes from config
        3. Timestamp-based heuristic – locate year/month/day triplets
    """

    def __init__(self, config: dict):
        self.config = config
        self._packet_def = config.get("packet_definition", {})
        self._markers: list[str] = [
            m.upper()
            for m in self._packet_def.get("start_markers", [])
        ]
        self._fixed_size_bytes: Optional[int] = self._packet_def.get("packet_size_bytes")
        self._header_size_bytes: int = self._packet_def.get("header_size_bytes", 0)
        self._timestamp_offset_words: Optional[int] = (
            config.get("timestamp", {}).get("word_offset")
        )

    # ------------------------------------------------------------------
    # Primary entry point
    # ------------------------------------------------------------------

    def find_packets(self, hex_data: str) -> list[PacketBoundary]:
        """
        Find all packet boundaries in hex_data.
        Returns list of PacketBoundary objects in order.
        """
        # Strategy 1 — marker-based
        if self._markers:
            boundaries = self._detect_by_markers(hex_data)
            if boundaries:
                log.info("Packet detection: marker-based, found %d packets.", len(boundaries))
                return boundaries

        # Strategy 2 — fixed length
        if self._fixed_size_bytes:
            boundaries = self._detect_by_fixed_length(hex_data)
            log.info("Packet detection: fixed-length (%d B), found %d packets.",
                     self._fixed_size_bytes, len(boundaries))
            return boundaries

        # Strategy 3 — timestamp heuristic
        boundaries = self._detect_by_timestamp(hex_data)
        if boundaries:
            log.info("Packet detection: timestamp-heuristic, found %d packets.", len(boundaries))
            return boundaries

        # Fallback — treat entire stream as one packet
        log.warning("No packet boundaries detected — treating stream as single packet.")
        return [PacketBoundary(0, len(hex_data), 0.3, "single")]

    # ------------------------------------------------------------------
    # Strategy 1: Marker-based
    # ------------------------------------------------------------------

    def _detect_by_markers(self, hex_data: str) -> list[PacketBoundary]:
        boundaries: list[PacketBoundary] = []
        data = hex_data.upper()

        for marker in self._markers:
            starts: list[int] = [m.start() for m in re.finditer(marker, data)]
            if not starts:
                continue

            for i, start in enumerate(starts):
                end = starts[i + 1] if i + 1 < len(starts) else len(data)
                # If packet size is known, cap the end
                if self._fixed_size_bytes:
                    end = min(start + self._fixed_size_bytes * 2, len(data))
                boundaries.append(PacketBoundary(start, end, 0.95, f"marker:{marker}"))
            break  # use first matching marker set

        return boundaries

    # ------------------------------------------------------------------
    # Strategy 2: Fixed length
    # ------------------------------------------------------------------

    def _detect_by_fixed_length(self, hex_data: str) -> list[PacketBoundary]:
        size_chars = self._fixed_size_bytes * 2
        boundaries: list[PacketBoundary] = []
        offset = self._header_size_bytes * 2  # skip global header

        while offset + size_chars <= len(hex_data):
            boundaries.append(
                PacketBoundary(offset, offset + size_chars, 0.85, "fixed_length")
            )
            offset += size_chars

        return boundaries

    # ------------------------------------------------------------------
    # Strategy 3: Timestamp heuristic
    # ------------------------------------------------------------------

    def _detect_by_timestamp(self, hex_data: str) -> list[PacketBoundary]:
        """
        Walk through hex data 2 hex chars (1 byte) at a time and look for
        three consecutive 16-bit words that decode as (year, month, day).
        Each found position is treated as the start of a packet.
        """
        boundaries: list[PacketBoundary] = []
        # Search for year word (2000–2099 = 0x07D0–0x0823)
        data = hex_data.upper()
        i = 0
        step = 4  # 4 hex chars = 2 bytes (one word)

        # Heuristic: scan for plausible YEAR (word), MONTH (next), DAY (next)
        while i + 24 <= len(data):
            w1 = data[i: i + 4]
            w2 = data[i + 4: i + 8]
            w3 = data[i + 8: i + 12]
            year = hex_to_int(w1)
            month = hex_to_int(w2)
            day = hex_to_int(w3)

            if (year is not None and is_plausible_year(year)
                    and month is not None and is_plausible_month(month)
                    and day is not None and is_plausible_day(day)):
                # Found a timestamp — now figure out how far this packet extends
                # by looking for next timestamp or end of data
                next_start = self._find_next_timestamp(data, i + step)
                end = next_start if next_start else len(data)
                # Rewind to config-defined header before timestamp
                ts_offset_words = self._timestamp_offset_words or 0
                packet_start = max(0, i - ts_offset_words * 4)
                boundaries.append(
                    PacketBoundary(packet_start, end, 0.75, "timestamp_heuristic")
                )
                i = next_start if next_start else len(data)
                continue
            i += step

        return boundaries

    def _find_next_timestamp(self, data: str, start: int) -> Optional[int]:
        """Find the next timestamp signature after `start` position."""
        i = start
        step = 4
        while i + 12 <= len(data):
            w1 = data[i: i + 4]
            w2 = data[i + 4: i + 8]
            w3 = data[i + 8: i + 12]
            year = hex_to_int(w1)
            month = hex_to_int(w2)
            day = hex_to_int(w3)
            if (year is not None and is_plausible_year(year)
                    and month is not None and is_plausible_month(month)
                    and day is not None and is_plausible_day(day)):
                # Rewind by header offset
                ts_offset_words = self._timestamp_offset_words or 0
                return max(start, i - ts_offset_words * 4)
            i += step
        return None
