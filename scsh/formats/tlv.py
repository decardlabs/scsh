"""BER-TLV 解码与编码。"""

from __future__ import annotations

from typing import Any


class TLV:
    """BER-TLV 数据对象。

    Attributes:
        tag: 标签值（可多字节）。
        value: 值字节。
        constructed: 是否为 constructed 类型。
        children: 子 TLV（仅 constructed 类型有）。
    """

    def __init__(
        self,
        tag: int,
        value: bytes = b"",
        constructed: bool = False,
        children: list[TLV] | None = None,
    ) -> None:
        self.tag = tag
        self.value = value
        self.constructed = constructed
        self.children = children or []

    @property
    def hex(self) -> str:
        """值的十六进制表示。"""
        return self.value.hex().upper()

    def find(self, tag: int) -> Any:
        """递归查找指定 tag 的子 TLV。"""
        if self.tag == tag:
            return self
        for child in self.children:
            found = child.find(tag)
            if found:
                return found
        return None

    def __repr__(self) -> str:
        tag_hex = f"{self.tag:X}"
        if self.constructed:
            return f"<TLV {tag_hex} [constructed] {len(self.children)} children>"
        return f"<TLV {tag_hex} {self.hex[:20]}{'...' if len(self.value) > 10 else ''}>"


def _decode_tag(data: bytes, offset: int) -> tuple[int, int]:
    """从 data[offset:] 解码一个 BER-TLV tag，返回 (tag_value, consumed_bytes)。"""
    first = data[offset]

    # 多字节 tag: 第一字节的 bits 5-1 = 11111
    if (first & 0x1F) == 0x1F:
        tag = first
        consumed = 1
        while offset + consumed < len(data):
            byte = data[offset + consumed]
            tag = (tag << 8) | byte
            consumed += 1
            if not (byte & 0x80):
                break
        return (tag, consumed)
    else:
        return (first, 1)


def _decode_length(data: bytes, offset: int) -> tuple[int, int]:
    """从 data[offset:] 解码 BER-TLV 长度，返回 (length, consumed_bytes)。"""
    first = data[offset]

    if first < 0x80:
        # 短形式
        return (first, 1)
    elif first == 0x80:
        # 不定长 — 简单处理
        return (len(data) - offset - 1, 1)
    else:
        # 长形式: 0x81 XX, 0x82 XX YY, ...
        num_bytes = first & 0x7F
        length = 0
        for i in range(num_bytes):
            length = (length << 8) | data[offset + 1 + i]
        return (length, 1 + num_bytes)


def _tag_first_byte(tag: int) -> int:
    """获取 tag 编码中的第一字节（用于判断 constructed/class）。"""
    if tag < 0x100:
        return tag
    # 多字节 tag：第一个字节包含 class 和 constructed 位
    # 通过 tag 的 top-most byte 来确定
    bytes_needed = (tag.bit_length() + 7) // 8
    shift = (bytes_needed - 1) * 8
    return (tag >> shift) & 0xFF


def _is_constructed(tag: int) -> bool:
    """判断 tag 是否为 constructed 类型（bit 6 set in first byte）。"""
    return bool(_tag_first_byte(tag) & 0x20)


def decode_tlv(data: bytes, offset: int = 0) -> list[TLV]:
    """递归解码 BER-TLV 数据。

    Args:
        data: 原始字节数据。
        offset: 解析起始偏移（默认 0）。

    Returns:
        TLV 对象列表。
    """
    result: list[TLV] = []

    while offset < len(data):
        # Tag
        tag, tag_consumed = _decode_tag(data, offset)
        offset += tag_consumed

        if offset >= len(data):
            break

        # Length
        length, len_consumed = _decode_length(data, offset)
        offset += len_consumed

        if length < 0:
            break

        # Value
        value_end = offset + length
        value = data[offset:value_end] if value_end <= len(data) else data[offset:]
        offset = value_end

        constructed = _is_constructed(tag)

        if constructed and value:
            children = decode_tlv(value)
            result.append(TLV(tag=tag, value=value, constructed=True, children=children))
        else:
            result.append(TLV(tag=tag, value=value, constructed=False))

    return result


def encode_tlv(tlv: TLV) -> bytes:
    """将 TLV 对象编码为字节。"""
    tag_bytes = _encode_tag(tlv.tag)
    value_bytes = b""
    if tlv.children:
        for child in tlv.children:
            value_bytes += encode_tlv(child)
    else:
        value_bytes = tlv.value

    length_bytes = _encode_length(len(value_bytes))
    return tag_bytes + length_bytes + value_bytes


def _encode_tag(tag: int) -> bytes:
    """编码 tag 为字节序列。

    BER-TLV 规则:
    - 单字节: bits 5-1 != 11111
    - 多字节: 首字节 bits 5-1 = 11111, 后续字节 bit 7 表示是否继续
    """
    if tag < 0x100:
        # 单字节（0x00-0xFF）
        return bytes([tag & 0xFF])
    else:
        # 多字节
        result = bytearray()
        t = tag
        while t:
            result.insert(0, t & 0xFF)
            t >>= 8
        # 所有非末位字节的 bit 7 置 1
        for i in range(len(result) - 1):
            result[i] |= 0x80
        return bytes(result)


def _encode_length(length: int) -> bytes:
    """编码长度为字节序列。"""
    if length < 0x80:
        return bytes([length])
    elif length < 0x100:
        return bytes([0x81, length])
    elif length < 0x10000:
        return bytes([0x82, (length >> 8) & 0xFF, length & 0xFF])
    else:
        return bytes([0x83, (length >> 16) & 0xFF, (length >> 8) & 0xFF, length & 0xFF])
