"""
PatternDetector – analyzes a hex stream to find repeating patterns,
probable field widths, and data structure hints.

Used in the "Analyze" / debug mode to help reverse-engineer unknown PLC formats.
"""

import re
from collections import Counter
from typing import Optional
from utils.helpers import hex_to_int, chunk_hex, clean_hex_string
from utils.logger import AppLogger

log = AppLogger()


class PatternResult:
    """Result from a pattern analysis run."""

    def __init__(self):
        self.detected_period: Optional[int] = None   # likely packet period in words
        self.repeating_values: dict[int, list] = {}   # word_offset → [values seen]
        self.probable_fields: list[dict] = []          # [{word, label, confidence}]
        self.zero_word_offsets: list[int] = []         # words that are always 0
        self.suggestions: list[str] = []               # human-readable suggestions


class PatternDetector:
    """
    Analyzes repeating structure in a hex stream to assist with format discovery.

    Algorithm:
        1. Split stream into words (16-bit chunks)
        2. Test various periods (16, 20, 24, 32 … words) for auto-correlation
        3. At the best period, compute statistics per word position
        4. Flag word positions with typical timestamp-like or constant values
    """

    CANDIDATE_PERIODS = [8, 10, 12, 14, 16, 18, 20, 22, 24, 28, 32, 40, 48, 64]

    def __init__(self):
        pass

    def analyze(self, hex_data: str, max_packets: int = 100) -> PatternResult:
        """
        Perform full pattern analysis on hex_data.

        Args:
            hex_data:    Raw hex string
            max_packets: Cap packets analyzed for performance
        Returns:
            PatternResult with findings
        """
        result = PatternResult()
        data = clean_hex_string(hex_data)
        words = chunk_hex(data, 4)  # 16-bit words

        if len(words) < 8:
            result.suggestions.append("Not enough data for pattern analysis (need ≥ 8 words).")
            return result

        # 1) Detect probable period
        period = self._detect_period(words[:max_packets * 64])
        result.detected_period = period

        if period:
            result.suggestions.append(
                f"Probable packet period: {period} words ({period * 2} bytes)."
            )
            # 2) Per-position statistics
            self._analyze_positions(words, period, result, max_packets)

        # 3) Detect always-zero words
        result.zero_word_offsets = self._find_zero_positions(words, period or 16)
        if result.zero_word_offsets:
            result.suggestions.append(
                f"Word positions always zero (padding?): {result.zero_word_offsets}"
            )

        return result

    # ------------------------------------------------------------------
    # Period detection via autocorrelation
    # ------------------------------------------------------------------

    def _detect_period(self, words: list[str]) -> Optional[int]:
        """
        Find the period P such that words[i] == words[i+P] most often.
        Uses simple autocorrelation score.
        """
        best_period = None
        best_score = 0

        for period in self.CANDIDATE_PERIODS:
            if period >= len(words):
                continue
            matches = sum(
                1 for i in range(len(words) - period)
                if words[i] == words[i + period]
            )
            score = matches / max(len(words) - period, 1)
            if score > best_score and score > 0.3:
                best_score = score
                best_period = period

        log.debug("Period detection: best_period=%s score=%.3f", best_period, best_score)
        return best_period

    # ------------------------------------------------------------------
    # Per-position analysis
    # ------------------------------------------------------------------

    def _analyze_positions(self, words: list[str], period: int,
                            result: PatternResult, max_packets: int):
        """For each word offset within one period, collect value stats."""
        # Organize into matrix [packet][word_offset]
        packets = []
        for start in range(0, min(len(words), max_packets * period), period):
            packet_words = words[start: start + period]
            if len(packet_words) == period:
                packets.append(packet_words)

        if not packets:
            return

        for pos in range(period):
            values = [hex_to_int(p[pos]) for p in packets if hex_to_int(p[pos]) is not None]
            if not values:
                continue
            result.repeating_values[pos] = values
            unique = len(set(values))
            min_val = min(values)
            max_val = max(values)

            # Heuristic labeling
            label, confidence = self._label_word(pos, values, min_val, max_val, unique)
            if label:
                result.probable_fields.append({
                    "word_offset": pos,
                    "byte_offset": pos * 2,
                    "label": label,
                    "confidence": confidence,
                    "min": min_val,
                    "max": max_val,
                    "unique_count": unique,
                    "sample": values[:5],
                })

    @staticmethod
    def _label_word(pos: int, values: list, min_val: int, max_val: int,
                    unique: int) -> tuple[Optional[str], float]:
        """Apply heuristics to guess what a word position represents."""
        # Always same → constant / ID / padding
        if unique == 1:
            if min_val == 0:
                return "padding/reserved", 0.6
            return f"constant (0x{min_val:04X}={min_val})", 0.7

        # Year pattern
        if 2000 <= min_val and max_val <= 2100 and unique <= 20:
            return "year", 0.92

        # Month (1–12)
        if 1 <= min_val and max_val <= 12 and unique <= 12:
            return "month", 0.85

        # Day (1–31)
        if 1 <= min_val and max_val <= 31 and unique <= 31:
            return "day", 0.75

        # Hour (0–23)
        if 0 <= min_val and max_val <= 23 and unique <= 24:
            return "hour", 0.70

        # Minute/second (0–59)
        if 0 <= min_val and max_val <= 59 and unique <= 60:
            return "minute/second", 0.65

        # Milliseconds (0–999)
        if 0 <= min_val and max_val <= 999:
            return "millisecond?", 0.50

        # Plausible sensor reading (0–9999 → common in Mitsubishi PLCs)
        if 0 <= min_val and max_val <= 9999:
            return "sensor_register", 0.45

        return None, 0.0

    # ------------------------------------------------------------------
    # Zero-position finder
    # ------------------------------------------------------------------

    def _find_zero_positions(self, words: list[str], period: int) -> list[int]:
        """Return word offsets that are 0x0000 in every packet."""
        result = []
        packets = [words[i: i + period] for i in range(0, len(words) - period + 1, period)
                   if len(words[i: i + period]) == period]
        if not packets:
            return result
        for pos in range(period):
            if all(p[pos] == "0000" for p in packets[:50]):
                result.append(pos)
        return result
