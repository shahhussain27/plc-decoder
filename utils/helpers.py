"""
Low-level hex/binary utility functions used across all modules.
"""

import struct
import re
from typing import Optional


def validate_hex_string(hex_str: str) -> bool:
    """Return True if the string is a valid hex sequence (even length, hex chars only)."""
    cleaned = hex_str.strip().replace(" ", "").replace("\n", "")
    if not cleaned:
        return False
    return bool(re.fullmatch(r"[0-9A-Fa-f]+", cleaned)) and len(cleaned) % 2 == 0


def clean_hex_string(hex_str: str) -> str:
    """Strip whitespace, '0x'/'0X' prefixes, and colons from a hex string."""
    # Remove 0x/0X prefix (must be done before removing other chars)
    result = re.sub(r"0[xX]", "", hex_str)
    # Remove whitespace and colons
    result = re.sub(r"[\s:]", "", result)
    return result.upper()


def chunk_hex(hex_str: str, word_size: int = 4) -> list[str]:
    """
    Split a hex string into chunks of `word_size` characters (2 chars = 1 byte).
    Default word_size=4 means 2-byte (16-bit) words.
    """
    cleaned = clean_hex_string(hex_str)
    return [cleaned[i : i + word_size] for i in range(0, len(cleaned), word_size)]


def hex_to_int(hex_str: str, signed: bool = False, byteorder: str = "big") -> Optional[int]:
    """
    Convert a hex string to integer.

    Args:
        hex_str:   Hex characters (e.g. '03E9')
        signed:    Interpret as signed integer
        byteorder: 'big' or 'little'
    Returns:
        Integer value or None on error
    """
    try:
        cleaned = clean_hex_string(hex_str)
        if not cleaned:
            return None
        byte_len = len(cleaned) // 2
        raw = bytes.fromhex(cleaned)
        if byteorder == "little":
            raw = bytes(reversed(raw))
        return int.from_bytes(raw, byteorder="big", signed=signed)
    except (ValueError, OverflowError):
        return None


def int_to_hex(value: int, width: int = 4) -> str:
    """Convert integer to uppercase hex string padded to `width` characters."""
    try:
        return format(value & (16 ** width - 1), f"0{width}X")
    except (TypeError, ValueError):
        return "0" * width


def swap_bytes(hex_str: str) -> str:
    """Swap byte order within each 2-byte word (little↔big endian)."""
    cleaned = clean_hex_string(hex_str)
    words = [cleaned[i : i + 4] for i in range(0, len(cleaned), 4)]
    swapped = [w[2:] + w[:2] for w in words if len(w) == 4]
    return "".join(swapped)


def hex_to_bytes(hex_str: str) -> Optional[bytes]:
    """Convert hex string to raw bytes object."""
    try:
        return bytes.fromhex(clean_hex_string(hex_str))
    except ValueError:
        return None


def bytes_to_hex(data: bytes, sep: str = " ") -> str:
    """Format bytes as spaced hex groups (e.g. 'AA BB CC')."""
    return sep.join(f"{b:02X}" for b in data)


def unpack_16bit(hex_word: str, signed: bool = False, byteorder: str = "big") -> Optional[int]:
    """Unpack a 4-character hex string as 16-bit integer."""
    return hex_to_int(hex_word, signed=signed, byteorder=byteorder)


def unpack_32bit(hex_dword: str, signed: bool = False, byteorder: str = "big") -> Optional[int]:
    """Unpack an 8-character hex string as 32-bit integer."""
    return hex_to_int(hex_dword, signed=signed, byteorder=byteorder)


def format_hex_dump(hex_str: str, cols: int = 16) -> str:
    """
    Create a formatted hex dump (like xxd) showing offset, hex bytes, and ASCII.

    Args:
        hex_str: Input hex string
        cols:    Number of bytes per row
    Returns:
        Formatted multiline string
    """
    cleaned = clean_hex_string(hex_str)
    raw = bytes.fromhex(cleaned)
    lines = []
    for i in range(0, len(raw), cols):
        chunk = raw[i : i + cols]
        offset = f"{i:08X}"
        hex_part = " ".join(f"{b:02X}" for b in chunk).ljust(cols * 3 - 1)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{offset}  {hex_part}  |{ascii_part}|")
    return "\n".join(lines)


def is_plausible_year(value: int) -> bool:
    """Heuristic: does this integer look like a plausible year (2000–2100)?"""
    return 2000 <= value <= 2100


def is_plausible_month(value: int) -> bool:
    return 1 <= value <= 12


def is_plausible_day(value: int) -> bool:
    return 1 <= value <= 31


def is_plausible_hour(value: int) -> bool:
    return 0 <= value <= 23


def is_plausible_minute_second(value: int) -> bool:
    return 0 <= value <= 59
