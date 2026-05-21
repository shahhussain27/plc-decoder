"""
TimestampDetector – scans hex data and locates all plausible timestamp
sequences, returning their positions and decoded values.
"""

from typing import Optional
from utils.helpers import (
    hex_to_int, chunk_hex, clean_hex_string,
    is_plausible_year, is_plausible_month, is_plausible_day,
    is_plausible_hour, is_plausible_minute_second,
)
from utils.logger import AppLogger

log = AppLogger()


class DetectedTimestamp:
    """A single detected timestamp occurrence."""

    def __init__(self, word_offset: int, year: int, month: int, day: int,
                 hour: Optional[int], minute: Optional[int], second: Optional[int],
                 ms: Optional[int]):
        self.word_offset = word_offset
        self.byte_offset = word_offset * 2
        self.year = year
        self.month = month
        self.day = day
        self.hour = hour
        self.minute = minute
        self.second = second
        self.millisecond = ms

    def __repr__(self):
        return (f"DetectedTimestamp(@word {self.word_offset}: "
                f"{self.year:04d}-{self.month:02d}-{self.day:02d} "
                f"{self.hour or 0:02d}:{self.minute or 0:02d}:{self.second or 0:02d})")

    @property
    def datetime_str(self) -> str:
        return (f"{self.year:04d}-{self.month:02d}-{self.day:02d} "
                f"{self.hour or 0:02d}:{self.minute or 0:02d}:{self.second or 0:02d}")


class TimestampDetector:
    """
    Scans a hex stream for all plausible timestamp word-sequences.

    Looks for 3–7 consecutive 16-bit big-endian words matching:
        YEAR (2000–2100), MONTH (1–12), DAY (1–31),
        optionally HOUR (0–23), MINUTE (0–59), SECOND (0–59), MS (0–999)
    """

    def detect_all(self, hex_data: str) -> list[DetectedTimestamp]:
        """Return all detected timestamp positions in order."""
        data = clean_hex_string(hex_data)
        words = chunk_hex(data, 4)
        results: list[DetectedTimestamp] = []

        i = 0
        while i < len(words) - 2:
            year = hex_to_int(words[i])
            month = hex_to_int(words[i + 1])
            day = hex_to_int(words[i + 2])

            if (year and is_plausible_year(year)
                    and month and is_plausible_month(month)
                    and day and is_plausible_day(day)):

                hour = hex_to_int(words[i + 3]) if i + 3 < len(words) else None
                minute = hex_to_int(words[i + 4]) if i + 4 < len(words) else None
                second = hex_to_int(words[i + 5]) if i + 5 < len(words) else None
                ms = hex_to_int(words[i + 6]) if i + 6 < len(words) else None

                # Validate optional fields
                if hour is not None and not is_plausible_hour(hour):
                    hour = None
                if minute is not None and not is_plausible_minute_second(minute):
                    minute = None
                if second is not None and not is_plausible_minute_second(second):
                    second = None
                if ms is not None and ms > 999:
                    ms = None

                ts = DetectedTimestamp(i, year, month, day, hour, minute, second, ms)
                results.append(ts)
                log.debug("Timestamp found: %s", ts)
                # Skip forward past this timestamp
                i += 7
                continue
            i += 1

        log.info("TimestampDetector found %d timestamps.", len(results))
        return results

    def detect_period(self, timestamps: list[DetectedTimestamp]) -> Optional[int]:
        """
        Estimate the packet period (in words) from the spacing between timestamps.
        """
        if len(timestamps) < 2:
            return None
        gaps = [
            timestamps[i + 1].word_offset - timestamps[i].word_offset
            for i in range(len(timestamps) - 1)
        ]
        if not gaps:
            return None
        from collections import Counter
        most_common = Counter(gaps).most_common(1)[0][0]
        return most_common
