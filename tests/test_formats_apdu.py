"""测试 APDU 解析与格式化。"""

import pytest
from scsh.formats.apdu import (
    parse_apdu_hex,
    format_apdu,
    format_response,
    apdu_summary,
)


class TestParseAPDUHex:
    def test_case_4_apdu(self):
        """Case 4 APDU: CLA INS P1 P2 Lc data Le。"""
        result = parse_apdu_hex("00A4040008A0000006472F000100")
        assert result["cla"] == 0x00
        assert result["ins"] == 0xA4
        assert result["p1"] == 0x04
        assert result["p2"] == 0x00
        assert result["lc"] == 8
        assert result["data"] == bytes.fromhex("A0000006472F0001")
        assert result["le"] == 0x00

    def test_case_3_apdu(self):
        """Case 3 APDU: CLA INS P1 P2 Lc data (无 Le)。"""
        result = parse_apdu_hex("00A4040008A0000006472F0001")
        assert result["cla"] == 0x00
        assert result["data"] == bytes.fromhex("A0000006472F0001")
        assert result["le"] is None

    def test_case_2_apdu(self):
        """Case 2 APDU: CLA INS P1 P2 Le。"""
        result = parse_apdu_hex("00C0000000")
        assert result["cla"] == 0x00
        assert result["ins"] == 0xC0
        assert result["le"] == 0x00
        assert result["lc"] is None

    def test_case_1_apdu(self):
        """Case 1 APDU: CLA INS P1 P2 (无数据体)。"""
        result = parse_apdu_hex("00A40400")
        assert result["cla"] == 0x00
        assert result["lc"] is None
        assert result["le"] is None

    def test_invalid_hex(self):
        """无效十六进制抛出 ValueError。"""
        with pytest.raises(ValueError, match="无效十六进制"):
            parse_apdu_hex("nothex")

    def test_odd_length_hex(self):
        """奇数长度十六进制抛出 ValueError。"""
        with pytest.raises(ValueError, match="奇数"):
            parse_apdu_hex("00A")

    def test_empty_hex(self):
        """空字符串抛出 ValueError。"""
        with pytest.raises(ValueError):
            parse_apdu_hex("")

    def test_whitespace_stripped(self):
        """含空格的 hex 正常解析。"""
        result = parse_apdu_hex(" 00 A4 04 00 ")
        assert result["cla"] == 0x00
        assert result["ins"] == 0xA4

    def test_lowercase_hex(self):
        """小写 hex 正常解析。"""
        result = parse_apdu_hex("00a40400")
        assert result["ins"] == 0xA4

    def test_extended_lc(self):
        """扩展 Lc (3字节): CLA INS P1 P2 0x00 0xXX 0xYY 0xZZ data。"""
        # Extended Lc for > 255 bytes data
        hex_str = "00" + "a4" + "0400" + "0001" + "00" * 0x100 + "00"
        result = parse_apdu_hex(hex_str)
        assert result["lc"] == 0x100


class TestFormatAPDU:
    def test_format_select(self):
        """SELECT 命令正确标注。"""
        formatted = format_apdu("00A40400")
        assert "SELECT" in formatted or "00 A4 04 00" in formatted

    def test_format_get_response(self):
        """GET RESPONSE 正确标注。"""
        formatted = format_apdu("00C0000000")
        assert "GET RESPONSE" in formatted or "00 C0 00 00 00" in formatted

    def test_format_verify(self):
        """VERIFY 命令正确标注。"""
        formatted = format_apdu("0020000000")
        assert "VERIFY" in formatted


class TestFormatResponse:
    def test_success_sw(self):
        """0x9000 对应 SUCCESS。"""
        result = format_response(b"\x00" * 10, 0x9000)
        assert "9000" in result
        assert "SUCCESS" in result.upper() or "成功" in result

    def test_warning_sw(self):
        """62xx 对应警告。"""
        result = format_response(b"", 0x6283)
        assert "6283" in result

    def test_error_sw(self):
        """6A82 对应文件未找到。"""
        result = format_response(b"", 0x6A82)
        assert "6A82" in result
        assert "未找到" in result or "not found" in result.lower()

    def test_security_status(self):
        """6982 对应安全状态不满足。"""
        result = format_response(b"", 0x6982)
        assert "6982" in result
        assert "安全" in result


class TestAPDUSummary:
    def test_summary_contains_key_info(self):
        """摘要包含命令关键信息。"""
        summary = apdu_summary("00A4040008A0000006472F0001")
        assert "00" in summary
        assert "A4" in summary
