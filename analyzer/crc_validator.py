"""
CRCValidator – optional CRC/checksum validation for PLC packets.
Supports CRC-16 (Modbus), CRC-16 (CCITT), XOR-sum, and simple byte sum.
"""

from typing import Optional
from utils.helpers import hex_to_bytes
from utils.logger import AppLogger

log = AppLogger()


class CRCValidator:
    """
    Provides CRC and checksum validation for PLC packets.
    The validator reads the CRC type and byte position from config.
    """

    SUPPORTED_MODES = ("crc16_modbus", "crc16_ccitt", "xor_sum", "byte_sum", "none")

    def __init__(self, crc_config: dict | None = None):
        """
        Args:
            crc_config: {
                "mode": "crc16_modbus",
                "crc_position": -2,   # -2 = last 2 bytes (little-endian)
                "data_range": [0, -2] # byte range to compute CRC over
            }
        """
        cfg = crc_config or {}
        self.mode: str = cfg.get("mode", "none")
        self.crc_position: int = cfg.get("crc_position", -2)  # negative = from end
        self.data_range: list = cfg.get("data_range", [0, -2])
        self.enabled = self.mode != "none"

    def validate(self, packet_hex: str) -> Optional[bool]:
        """
        Validate CRC for a hex packet.

        Returns:
            True if valid, False if invalid, None if validation not applicable/enabled.
        """
        if not self.enabled:
            return None
        raw = hex_to_bytes(packet_hex)
        if raw is None or len(raw) < 4:
            return None
        try:
            start = self.data_range[0]
            end = self.data_range[1] if self.data_range[1] != -2 else len(raw) - 2
            data_bytes = raw[start:end]
            crc_bytes = raw[end : end + 2]
            stored_crc = int.from_bytes(crc_bytes, "little")

            if self.mode == "crc16_modbus":
                computed = self._crc16_modbus(data_bytes)
            elif self.mode == "crc16_ccitt":
                computed = self._crc16_ccitt(data_bytes)
            elif self.mode == "xor_sum":
                computed = self._xor_sum(data_bytes)
            elif self.mode == "byte_sum":
                computed = self._byte_sum(data_bytes)
            else:
                return None

            ok = computed == stored_crc
            if not ok:
                log.debug("CRC mismatch: computed=0x%04X stored=0x%04X", computed, stored_crc)
            return ok
        except Exception as exc:
            log.debug("CRC validation error: %s", exc)
            return None

    # ------------------------------------------------------------------
    # CRC algorithms
    # ------------------------------------------------------------------

    @staticmethod
    def _crc16_modbus(data: bytes) -> int:
        """CRC-16/MODBUS algorithm."""
        crc = 0xFFFF
        for b in data:
            crc ^= b
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc

    @staticmethod
    def _crc16_ccitt(data: bytes) -> int:
        """CRC-16/CCITT (XModem variant)."""
        crc = 0x0000
        for b in data:
            crc ^= b << 8
            for _ in range(8):
                if crc & 0x8000:
                    crc = (crc << 1) ^ 0x1021
                else:
                    crc <<= 1
            crc &= 0xFFFF
        return crc

    @staticmethod
    def _xor_sum(data: bytes) -> int:
        """Simple XOR checksum."""
        result = 0
        for b in data:
            result ^= b
        return result

    @staticmethod
    def _byte_sum(data: bytes) -> int:
        """Byte sum (modulo 256)."""
        return sum(data) & 0xFF
