"""
FieldExtractor – extracts individual named fields from a hex packet
based on a JSON format definition.

Each field definition looks like:
{
  "name": "year",
  "word_offset": 1,        # 0-based word (16-bit) index from packet start
  "size_words": 1,         # 1 = 16-bit, 2 = 32-bit
  "byteorder": "big",      # "big" or "little"
  "signed": false,
  "description": "Calendar year"
}
"""

from typing import Any, Optional
from utils.helpers import hex_to_int, clean_hex_string
from utils.logger import AppLogger

log = AppLogger()


class FieldExtractor:
    """
    Extracts named fields from a hex packet according to a field definition list.

    Usage:
        extractor = FieldExtractor(config["fields"])
        fields = extractor.extract(packet_hex)
    """

    def __init__(self, field_definitions: list[dict]):
        """
        Args:
            field_definitions: List of field spec dicts from JSON config.
        """
        self._defs = field_definitions

    def extract(self, packet_hex: str) -> dict[str, Any]:
        """
        Extract all defined fields from packet_hex.

        Returns:
            dict mapping field name → {
                "decimal": int | None,
                "raw_hex": str,
                "description": str,
                "word_offset": int,
            }
        """
        data = clean_hex_string(packet_hex)
        results: dict[str, Any] = {}

        for fdef in self._defs:
            name = fdef.get("name", "unknown")
            word_offset = fdef.get("word_offset", 0)
            size_words = fdef.get("size_words", 1)
            byteorder = fdef.get("byteorder", "big")
            signed = fdef.get("signed", False)
            description = fdef.get("description", "")
            scale = fdef.get("scale", 1)
            register = fdef.get("register", "")
            data_type = fdef.get("data_type", "uint16")

            # Calculate hex char positions
            char_start = word_offset * 4            # each word = 4 hex chars
            char_end = char_start + size_words * 4

            if char_end > len(data):
                log.debug(
                    "Field '%s': packet too short (need %d chars, have %d).",
                    name, char_end, len(data)
                )
                results[name] = {
                    "decimal": None,
                    "raw_hex": "",
                    "description": description,
                    "word_offset": word_offset,
                    "register": register,
                    "error": "packet_too_short",
                }
                continue

            raw_hex = data[char_start:char_end]

            # Handle special data types
            decimal = self._decode_value(raw_hex, byteorder, signed, data_type, scale)

            results[name] = {
                "decimal": decimal,
                "raw_hex": raw_hex,
                "description": description,
                "word_offset": word_offset,
                "register": register,
                "size_words": size_words,
                "scale": scale,
            }

        return results

    def extract_registers(self, packet_hex: str) -> dict[str, dict]:
        """
        Extract register-mapped fields (using 'register' key in field def).
        Returns dict keyed by register address.
        """
        raw = self.extract(packet_hex)
        regs: dict[str, dict] = {}
        for fname, info in raw.items():
            reg = info.get("register", fname)
            regs[reg] = {
                "name": fname,
                "decimal": info.get("decimal"),
                "raw_hex": info.get("raw_hex", ""),
                "description": info.get("description", ""),
            }
        return regs

    # ------------------------------------------------------------------
    # Internal decoders
    # ------------------------------------------------------------------

    @staticmethod
    def _decode_value(raw_hex: str, byteorder: str, signed: bool,
                      data_type: str, scale: float) -> Optional[Any]:
        """Decode raw hex to Python value based on data_type."""
        if not raw_hex:
            return None

        try:
            if data_type in ("uint8", "int8"):
                val = hex_to_int(raw_hex[-2:], signed=(data_type == "int8"), byteorder="big")
            elif data_type in ("uint16", "int16"):
                val = hex_to_int(raw_hex, signed=(data_type == "int16"), byteorder=byteorder)
            elif data_type in ("uint32", "int32"):
                val = hex_to_int(raw_hex, signed=(data_type == "int32"), byteorder=byteorder)
            elif data_type == "float32":
                import struct
                b = bytes.fromhex(raw_hex)
                if byteorder == "little":
                    b = bytes(reversed(b))
                val = struct.unpack(">f", b)[0]
                return round(val * scale, 4)
            elif data_type == "bcd":
                # Binary Coded Decimal
                val = int("".join(str(nibble) for nibble in
                                  (int(raw_hex[j], 16) for j in range(len(raw_hex)))))
            else:
                val = hex_to_int(raw_hex, signed=signed, byteorder=byteorder)

            if val is None:
                return None
            return val * scale if scale != 1 else val

        except Exception as exc:
            log.debug("Decode error for hex '%s': %s", raw_hex, exc)
            return None
