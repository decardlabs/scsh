"""Tests for scsh.apdu module."""

import pytest

from scsh.apdu import (
    CommandApdu,
    ResponseApdu,
    bytes_from_hex,
    bytes_to_hex,
    describe_sw,
    parse_script_line,
)
from scsh.exceptions import ApduError


# ---------------------------------------------------------------------------
# bytes_from_hex / bytes_to_hex
# ---------------------------------------------------------------------------

class TestBytesFromHex:
    def test_plain_hex(self):
        assert bytes_from_hex("00A40400") == b"\x00\xa4\x04\x00"

    def test_spaced_hex(self):
        assert bytes_from_hex("00 A4 04 00") == b"\x00\xa4\x04\x00"

    def test_colon_separated(self):
        assert bytes_from_hex("00:A4:04:00") == b"\x00\xa4\x04\x00"

    def test_lowercase(self):
        assert bytes_from_hex("deadbeef") == b"\xde\xad\xbe\xef"

    def test_empty(self):
        assert bytes_from_hex("") == b""

    def test_odd_length_raises(self):
        with pytest.raises(ValueError, match="Odd-length"):
            bytes_from_hex("0A4")

    def test_invalid_chars_raise(self):
        with pytest.raises(ValueError):
            bytes_from_hex("GG")


class TestBytesToHex:
    def test_default_sep(self):
        assert bytes_to_hex(b"\x00\xa4") == "00 A4"

    def test_no_sep(self):
        assert bytes_to_hex(b"\x00\xa4", sep="") == "00A4"

    def test_empty(self):
        assert bytes_to_hex(b"") == ""


# ---------------------------------------------------------------------------
# describe_sw
# ---------------------------------------------------------------------------

class TestDescribeSw:
    def test_success(self):
        assert "success" in describe_sw(0x90, 0x00).lower()

    def test_file_not_found(self):
        assert "file not found" in describe_sw(0x6A, 0x82).lower()

    def test_unknown(self):
        result = describe_sw(0xFF, 0xFF)
        assert "unknown" in result.lower()

    def test_counter_warning(self):
        result = describe_sw(0x63, 0xC3)
        assert "3" in result


# ---------------------------------------------------------------------------
# CommandApdu
# ---------------------------------------------------------------------------

class TestCommandApduFromBytes:
    def test_case1(self):
        apdu = CommandApdu.from_bytes(b"\x00\x84\x00\x00")
        assert apdu.cla == 0x00
        assert apdu.ins == 0x84
        assert apdu.data == b""
        assert apdu.le is None

    def test_case2_le(self):
        apdu = CommandApdu.from_bytes(b"\x00\xCA\x9F\x7F\x00")
        assert apdu.le == 256  # 0x00 -> 256

    def test_case2_le_nonzero(self):
        apdu = CommandApdu.from_bytes(b"\x00\xCA\x9F\x7F\x08")
        assert apdu.le == 8

    def test_case3_data(self):
        apdu = CommandApdu.from_bytes(b"\x00\xA4\x04\x00\x07" + b"\xA0\x00\x00\x00\x03\x10\x10")
        assert apdu.ins == 0xA4
        assert len(apdu.data) == 7
        assert apdu.le is None

    def test_case4_data_le(self):
        apdu = CommandApdu.from_bytes(b"\x00\xA4\x04\x00\x07" + b"\xA0\x00\x00\x00\x03\x10\x10\x00")
        assert len(apdu.data) == 7
        assert apdu.le == 256

    def test_too_short_raises(self):
        with pytest.raises(ApduError):
            CommandApdu.from_bytes(b"\x00\xA4")


class TestCommandApduFromHex:
    def test_select(self):
        apdu = CommandApdu.from_hex("00 A4 04 00 07 A0 00 00 00 03 10 10 00")
        assert apdu.ins == 0xA4
        assert len(apdu.data) == 7

    def test_invalid_hex(self):
        with pytest.raises(ValueError):
            CommandApdu.from_hex("ZZ")


class TestCommandApduToBytes:
    def test_roundtrip_case1(self):
        raw = b"\x00\x84\x00\x00"
        assert CommandApdu.from_bytes(raw).to_bytes() == raw

    def test_roundtrip_case3(self):
        raw = b"\x00\x20\x00\x00\x04\x31\x32\x33\x34"
        assert CommandApdu.from_bytes(raw).to_bytes() == raw

    def test_to_list(self):
        apdu = CommandApdu(0x00, 0xA4, 0x04, 0x00)
        assert apdu.to_list() == [0x00, 0xA4, 0x04, 0x00]

    def test_to_hex(self):
        apdu = CommandApdu(0x00, 0xA4, 0x04, 0x00)
        assert apdu.to_hex() == "00 A4 04 00"
        assert apdu.to_hex(sep="") == "00A40400"


class TestCommandApduFactories:
    def test_select_by_aid(self):
        aid = bytes.fromhex("A0000000031010")
        apdu = CommandApdu.select_by_aid(aid)
        assert apdu.cla == 0x00
        assert apdu.ins == 0xA4
        assert apdu.p1 == 0x04
        assert apdu.data == aid
        assert apdu.le == 0

    def test_get_response(self):
        apdu = CommandApdu.get_response(0x20)
        assert apdu.ins == 0xC0
        assert apdu.le == 0x20


# ---------------------------------------------------------------------------
# ResponseApdu
# ---------------------------------------------------------------------------

class TestResponseApdu:
    def test_from_bytes_ok(self):
        resp = ResponseApdu.from_bytes(b"\x01\x02\x90\x00")
        assert resp.data == b"\x01\x02"
        assert resp.sw1 == 0x90
        assert resp.sw2 == 0x00
        assert resp.ok is True
        assert resp.sw == 0x9000

    def test_from_list(self):
        resp = ResponseApdu.from_list([0x6A, 0x82])
        assert resp.sw1 == 0x6A
        assert resp.sw2 == 0x82
        assert resp.ok is False

    def test_too_short_raises(self):
        with pytest.raises(ApduError):
            ResponseApdu.from_bytes(b"\x90")

    def test_to_hex(self):
        resp = ResponseApdu(data=b"\xDE\xAD", sw1=0x90, sw2=0x00)
        assert resp.to_hex() == "DE AD 90 00"

    def test_description(self):
        resp = ResponseApdu.from_bytes(b"\x90\x00")
        assert "success" in resp.description.lower()


# ---------------------------------------------------------------------------
# parse_script_line
# ---------------------------------------------------------------------------

class TestParseScriptLine:
    def test_blank_returns_none(self):
        assert parse_script_line("") is None

    def test_comment_returns_none(self):
        assert parse_script_line("# this is a comment") is None

    def test_whitespace_only(self):
        assert parse_script_line("   ") is None

    def test_inline_comment_stripped(self):
        apdu = parse_script_line("00 A4 04 00  # SELECT")
        assert apdu is not None
        assert apdu.ins == 0xA4

    def test_valid_apdu(self):
        apdu = parse_script_line("00 84 00 00 08")
        assert apdu is not None
        assert apdu.ins == 0x84
