"""测试 BER-TLV 解码。"""

import pytest
from scsh.formats.tlv import decode_tlv, encode_tlv, TLV


class TestDecodeTLV:
    def test_primitive_tag_short(self):
        """单字节 primitive tag + 短长度。"""
        data = bytes.fromhex("8302AABB")
        result = decode_tlv(data)
        assert len(result) == 1
        assert result[0].tag == 0x83
        assert result[0].value == bytes.fromhex("AABB")
        assert result[0].constructed is False

    def test_multiple_tlvs(self):
        """多个相邻 TLV 连续解析。"""
        data = bytes.fromhex("8301AA8401BB")
        result = decode_tlv(data)
        assert len(result) == 2
        assert result[0].tag == 0x83
        assert result[0].value == bytes.fromhex("AA")
        assert result[1].tag == 0x84
        assert result[1].value == bytes.fromhex("BB")

    def test_constructed_tag(self):
        """constructed tag (bit 6 set) 递归解析子 TLV。"""
        # 0xA5 = 10100101 (constructed). Contains 0x8301AA
        data = bytes.fromhex("A5048301AA")
        result = decode_tlv(data)
        assert len(result) == 1
        assert result[0].tag == 0xA5
        assert result[0].constructed is True
        assert len(result[0].children) == 1
        assert result[0].children[0].tag == 0x83
        assert result[0].children[0].value == bytes.fromhex("AA")

    def test_two_byte_tag(self):
        """双字节 tag (0x1F + second byte)。"""
        # Tag = 0x9F 0x01
        data = bytes.fromhex("9F0101AA")
        result = decode_tlv(data)
        assert len(result) == 1
        assert result[0].tag == 0x9F01
        assert result[0].value == bytes.fromhex("AA")

    def test_long_length(self):
        """多字节长度编码 (0x81+)。"""
        # 0x83 tag, 0x81 0x80 = 128 bytes long value
        data = bytes.fromhex("838180" + "AA" * 128)
        result = decode_tlv(data)
        assert len(result) == 1
        assert result[0].tag == 0x83
        assert len(result[0].value) == 128

    def test_empty_tlv(self):
        """空数据返回空列表。"""
        assert decode_tlv(b"") == []

    def test_three_byte_tag(self):
        """三字节 tag。"""
        # Tag = 0x5F 0x80 0x01 (long form, 3 bytes)
        data = bytes.fromhex("5F800101FF")
        result = decode_tlv(data)
        assert result[0].tag >= 0x5F8001

    def test_nested_constructed(self):
        """多层嵌套 constructed TLV。"""
        # A4: constructed, contains A5, which contains 8301BB
        data = bytes.fromhex("A406A5048301BB")
        result = decode_tlv(data)
        assert result[0].tag == 0xA4
        assert len(result[0].children) == 1
        assert result[0].children[0].tag == 0xA5
        assert len(result[0].children[0].children) == 1
        assert result[0].children[0].children[0].value == bytes.fromhex("BB")


class TestTLVObject:
    def test_repr(self):
        """TLV 的 repr 包含 tag 信息。"""
        tlv = TLV(tag=0x83, value=bytes.fromhex("AABB"))
        assert "83" in repr(tlv)

    def test_hex_property(self):
        """hex 属性返回十六进制字符串。"""
        tlv = TLV(tag=0x83, value=bytes.fromhex("AABB"))
        assert "AABB" in tlv.hex or "aa" in tlv.hex.lower()

    def test_find(self):
        """find 按 tag 查找子 TLV。"""
        child = TLV(tag=0x83, value=bytes.fromhex("AA"))
        parent = TLV(tag=0xA5, value=b"", children=[child])
        found = parent.find(0x83)
        assert found is child

    def test_find_not_found(self):
        """find 未找到时返回 None。"""
        tlv = TLV(tag=0x83, value=bytes.fromhex("AA"))
        assert tlv.find(0x84) is None


class TestEncodeTLV:
    def test_encode_primitive(self):
        """编码 primitive TLV。"""
        tlv = TLV(tag=0x83, value=bytes.fromhex("AABB"))
        encoded = encode_tlv(tlv)
        assert encoded == bytes.fromhex("8302AABB")

    def test_encode_constructed(self):
        """编码 constructed TLV（含子项）。"""
        child = TLV(tag=0x83, value=bytes.fromhex("AA"))
        parent = TLV(tag=0xA5, value=b"", children=[child], constructed=True)
        encoded = encode_tlv(parent)
        assert encoded == bytes.fromhex("A5038301AA")
