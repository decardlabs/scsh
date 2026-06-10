"""APDU (Application Protocol Data Unit) utilities.

This module provides helpers for building, parsing, and formatting ISO/IEC 7816
APDU commands and responses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from scsh.exceptions import ApduError

# ---------------------------------------------------------------------------
# Status word catalogue
# ---------------------------------------------------------------------------

_SW_DESCRIPTIONS: dict[int, str] = {
    0x9000: "Normal processing – success",
    0x6100: "Normal processing – SW2 indicates the number of response bytes available",
    0x6200: "Warning – no information given, non-volatile memory unchanged",
    0x6282: "Warning – end of file or record reached before reading Ne bytes",
    0x6283: "Warning – selected file invalidated",
    0x6284: "Warning – FCI not formatted according to ISO 7816-4",
    0x6300: "Warning – no information given, non-volatile memory changed",
    0x6381: "Warning – file filled up by last write",
    0x6581: "Error – memory failure",
    0x6700: "Error – wrong length",
    0x6800: "Error – functions in CLA not supported",
    0x6881: "Error – logical channel not supported",
    0x6882: "Error – secure messaging not supported",
    0x6900: "Error – command not allowed",
    0x6981: "Error – command incompatible with file structure",
    0x6982: "Error – security status not satisfied",
    0x6983: "Error – authentication method blocked",
    0x6984: "Error – referenced data invalidated",
    0x6985: "Error – conditions of use not satisfied",
    0x6986: "Error – command not allowed (no current EF)",
    0x6987: "Error – expected SM data objects missing",
    0x6988: "Error – SM data objects incorrect",
    0x6A00: "Error – wrong parameters P1-P2",
    0x6A80: "Error – incorrect parameters in the command data field",
    0x6A81: "Error – function not supported",
    0x6A82: "Error – file not found",
    0x6A83: "Error – record not found",
    0x6A84: "Error – not enough memory space in the file",
    0x6A85: "Error – Lc inconsistent with TLV structure",
    0x6A86: "Error – incorrect parameters P1-P2",
    0x6A87: "Error – Lc inconsistent with P1-P2",
    0x6A88: "Error – referenced data not found",
    0x6B00: "Error – wrong parameters P1-P2",
    0x6C00: "Error – wrong length Le; SW2 indicates the exact length",
    0x6D00: "Error – instruction code not supported or invalid",
    0x6E00: "Error – class not supported",
    0x6F00: "Error – no precise diagnosis",
}


def describe_sw(sw1: int, sw2: int) -> str:
    """Return a human-readable description for a status word pair."""
    exact = (sw1 << 8) | sw2
    if exact in _SW_DESCRIPTIONS:
        return _SW_DESCRIPTIONS[exact]
    # Counter warning (63Cx) must be checked before the generic 6300 template.
    if sw1 == 0x63 and (sw2 & 0xF0) == 0xC0:
        return f"Warning – counter = {sw2 & 0x0F}"
    # Generic template matches (e.g. 61xx, 6Cxx)
    template = (sw1 << 8) | 0x00
    if template in _SW_DESCRIPTIONS and sw2 != 0x00:
        return _SW_DESCRIPTIONS[template]
    return "Unknown status word"


# ---------------------------------------------------------------------------
# Byte-sequence helpers
# ---------------------------------------------------------------------------

def bytes_from_hex(hex_str: str) -> bytes:
    """Parse a hex string (with or without spaces/colons) into bytes.

    Examples::

        bytes_from_hex("00 A4 04 00")  -> b'\\x00\\xa4\\x04\\x00'
        bytes_from_hex("00A40400")     -> b'\\x00\\xa4\\x04\\x00'
        bytes_from_hex("00:A4:04:00")  -> b'\\x00\\xa4\\x04\\x00'
    """
    cleaned = re.sub(r"[\s:]+", "", hex_str)
    if len(cleaned) % 2 != 0:
        raise ValueError(f"Odd-length hex string: {hex_str!r}")
    try:
        return bytes.fromhex(cleaned)
    except ValueError as exc:
        raise ValueError(f"Invalid hex string {hex_str!r}: {exc}") from exc


def bytes_to_hex(data: bytes, sep: str = " ") -> str:
    """Format *data* as an uppercase hex string with *sep* between bytes."""
    return sep.join(f"{b:02X}" for b in data)


# ---------------------------------------------------------------------------
# APDU dataclasses
# ---------------------------------------------------------------------------

@dataclass
class CommandApdu:
    """Represents an ISO/IEC 7816-4 command APDU (C-APDU)."""

    cla: int
    ins: int
    p1: int
    p2: int
    data: bytes = field(default_factory=bytes)
    le: Optional[int] = None  # None means no Le field

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    @classmethod
    def from_bytes(cls, raw: bytes) -> "CommandApdu":
        """Parse a raw byte sequence into a :class:`CommandApdu`."""
        if len(raw) < 4:
            raise ApduError(f"APDU too short ({len(raw)} bytes, need at least 4)")
        cla, ins, p1, p2 = raw[0], raw[1], raw[2], raw[3]
        body = raw[4:]
        if len(body) == 0:
            return cls(cla, ins, p1, p2)
        if len(body) == 1:
            # Case 2S: Le only
            le = body[0] if body[0] != 0 else 256
            return cls(cla, ins, p1, p2, le=le)
        # Case 3S / 4S
        lc = body[0]
        if len(body) < 1 + lc:
            raise ApduError(f"Lc={lc} but only {len(body) - 1} data bytes present")
        data = body[1 : 1 + lc]
        rest = body[1 + lc :]
        le: Optional[int] = None
        if rest:
            le = rest[0] if rest[0] != 0 else 256
        return cls(cla, ins, p1, p2, data=data, le=le)

    @classmethod
    def from_hex(cls, hex_str: str) -> "CommandApdu":
        """Parse a hex string into a :class:`CommandApdu`."""
        return cls.from_bytes(bytes_from_hex(hex_str))

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_bytes(self) -> bytes:
        """Serialise to a byte sequence suitable for transmission."""
        header = bytes([self.cla, self.ins, self.p1, self.p2])
        if not self.data and self.le is None:
            # Case 1
            return header
        if not self.data and self.le is not None:
            # Case 2S
            return header + bytes([self.le & 0xFF])
        if self.data and self.le is None:
            # Case 3S
            return header + bytes([len(self.data)]) + self.data
        # Case 4S
        return header + bytes([len(self.data)]) + self.data + bytes([self.le & 0xFF])  # type: ignore[operator]

    def to_list(self) -> List[int]:
        """Return the APDU as a list of integers (required by pyscard)."""
        return list(self.to_bytes())

    def to_hex(self, sep: str = " ") -> str:
        """Return the APDU as an uppercase hex string."""
        return bytes_to_hex(self.to_bytes(), sep=sep)

    # ------------------------------------------------------------------
    # Convenience class methods for common commands
    # ------------------------------------------------------------------

    @classmethod
    def select_by_aid(cls, aid: bytes, p2: int = 0x00) -> "CommandApdu":
        """Build a SELECT (by AID) command."""
        return cls(cla=0x00, ins=0xA4, p1=0x04, p2=p2, data=aid, le=0)

    @classmethod
    def get_response(cls, length: int) -> "CommandApdu":
        """Build a GET RESPONSE command."""
        return cls(cla=0x00, ins=0xC0, p1=0x00, p2=0x00, le=length)

    def __repr__(self) -> str:
        return (
            f"CommandApdu(CLA={self.cla:02X} INS={self.ins:02X} "
            f"P1={self.p1:02X} P2={self.p2:02X} "
            f"data=[{bytes_to_hex(self.data)}] Le={self.le})"
        )


@dataclass
class ResponseApdu:
    """Represents an ISO/IEC 7816-4 response APDU (R-APDU)."""

    data: bytes
    sw1: int
    sw2: int

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_bytes(cls, raw: bytes) -> "ResponseApdu":
        """Parse raw bytes (data + SW1 SW2) into a :class:`ResponseApdu`."""
        if len(raw) < 2:
            raise ApduError(f"Response APDU too short ({len(raw)} bytes)")
        return cls(data=raw[:-2], sw1=raw[-2], sw2=raw[-1])

    @classmethod
    def from_list(cls, response: List[int]) -> "ResponseApdu":
        """Parse a pyscard-style ``[data..., SW1, SW2]`` list."""
        return cls.from_bytes(bytes(response))

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def sw(self) -> int:
        """Combined status word."""
        return (self.sw1 << 8) | self.sw2

    @property
    def ok(self) -> bool:
        """``True`` if SW is 9000 (success)."""
        return self.sw == 0x9000

    @property
    def description(self) -> str:
        """Human-readable status word description."""
        return describe_sw(self.sw1, self.sw2)

    def to_hex(self, sep: str = " ") -> str:
        """Return the full response (data + SW) as uppercase hex."""
        full = self.data + bytes([self.sw1, self.sw2])
        return bytes_to_hex(full, sep=sep)

    def __repr__(self) -> str:
        return (
            f"ResponseApdu(data=[{bytes_to_hex(self.data)}] "
            f"SW={self.sw1:02X}{self.sw2:02X})"
        )


# ---------------------------------------------------------------------------
# Script line parser
# ---------------------------------------------------------------------------

def parse_script_line(line: str) -> Optional[CommandApdu]:
    """Parse a single script line into a :class:`CommandApdu`.

    Returns ``None`` for blank lines and comment lines (``#`` prefix).
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    # Remove inline comments
    code = stripped.split("#")[0].strip()
    if not code:
        return None
    return CommandApdu.from_hex(code)
