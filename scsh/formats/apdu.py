"""APDU 指令解析与美化输出。"""

from __future__ import annotations

import re
from typing import Any

from scsh.formats.sw import SW_DATABASE, SWClass


# ── 指令名称数据库 ─────────────────────────────────────

INS_NAMES: dict[int, str] = {
    0x04: "DEACTIVATE FILE",
    0x20: "VERIFY",
    0x22: "MANAGE SECURITY ENV",
    0x24: "CHANGE PIN",
    0x2A: "PERFORM SCQL OPERATION",
    0x44: "ACTIVATE FILE",
    0x46: "GENERATE ASYMMETRIC KEY PAIR",
    0x70: "MANAGE CHANNEL",
    0x82: "EXTERNAL AUTHENTICATE",
    0x84: "GET CHALLENGE",
    0x88: "INTERNAL AUTHENTICATE",
    0xA0: "SEARCH BINARY",
    0xA2: "SEARCH RECORD",
    0xA4: "SELECT",
    0xB0: "READ BINARY",
    0xB1: "READ RECORD",
    0xB2: "READ RECORD(S)",
    0xB3: "READ KEY",
    0xC0: "GET RESPONSE",
    0xC2: "ENVELOPE",
    0xC4: "GET DATA",
    0xCA: "GET DATA",
    0xD0: "WRITE BINARY",
    0xD2: "WRITE RECORD",
    0xD6: "UPDATE BINARY",
    0xDA: "PUT DATA",
    0xDC: "UPDATE BINARY",
    0xDE: "UPDATE RECORD",
    0xE0: "CREATE FILE",
    0xE2: "APPEND RECORD",
    0xE4: "DELETE FILE",
    0xE6: "TERMINATE CARD USAGE",
    0xE8: "TERMINATE DF",
    0xEA: "GET STATUS",
    0xF0: "SEARCH RECORD",
}

CLA_NAMES: dict[int, str] = {
    0x00: "ISO",
    0x80: "Proprietary",
    0xA0: "GP (Sensitive)",
    0xB0: "GP (MAC)",
}


def _ins_name(ins: int) -> str:
    return INS_NAMES.get(ins, f"INS={ins:02X}")


def _cla_name(cla: int) -> str:
    return CLA_NAMES.get(cla & 0xF0, f"CLA={cla:02X}")


# ── APDU 解析 ──────────────────────────────────────────


def parse_apdu_hex(hex_str: str) -> dict[str, Any]:
    """解析十六进制 APDU 字符串为字段字典。

    Args:
        hex_str: 十六进制字符串（可含空格、大小写）。

    Returns:
        包含 cla/ins/p1/p2/lc/data/le 的字典。
        不存在的字段为 None。

    Raises:
        ValueError: 无效十六进制或格式错误。
    """
    cleaned = re.sub(r"\s+", "", hex_str)
    if not cleaned:
        raise ValueError("APDU 为空")

    if len(cleaned) % 2 != 0:
        raise ValueError(f"奇数长度的十六进制字符串: {cleaned}")

    try:
        raw = bytes.fromhex(cleaned)
    except ValueError as exc:
        raise ValueError(f"无效十六进制: {exc}") from exc

    if len(raw) < 4:
        raise ValueError(f"APDU 太短（需至少 4 字节 CLA INS P1 P2）: {len(raw)} 字节")

    result: dict[str, Any] = {
        "cla": raw[0],
        "ins": raw[1],
        "p1": raw[2],
        "p2": raw[3],
        "lc": None,
        "data": None,
        "le": None,
    }

    if len(raw) == 4:
        # Case 1: CLA INS P1 P2
        return result

    # 检查扩展 Lc (3字节, 第一字节为 0x00 表示扩展)
    if raw[4] == 0x00 and len(raw) > 6:
        # 扩展 Lc/Le
        if len(raw) >= 7:
            # Lc = 3字节
            lc = (raw[5] << 8) | raw[6]
            result["lc"] = lc
            data_start = 7
            if len(raw) > data_start:
                data_len = min(lc, len(raw) - data_start)
                result["data"] = raw[data_start : data_start + data_len]
                remaining = len(raw) - data_start - data_len
                if remaining >= 2:
                    result["le"] = (raw[-2] << 8) | raw[-1]
                elif remaining == 1:
                    result["le"] = raw[-1]
            elif len(raw) == 7:
                # 只有扩展 Lc 没有数据
                if lc == 0:
                    result["le"] = 0x10000  # Extended Le
                pass
        return result

    # 标准 (短) Lc
    lc = raw[4]
    if lc == 0:
        # Lc=0 表示 Case 2 或 Case 4 with Le
        if len(raw) == 5:
            # Case 2: CLA INS P1 P2 Le (Le=0 表示 256)
            result["le"] = 0x00
            return result
        else:
            # Case 4: CLA INS P1 P2 0x00 Lc_data Le
            # 但这种格式不符合规范，按 data 处理
            result["lc"] = 0
            result["data"] = b""
            result["le"] = 0x100 if len(raw) == 6 else None
            return result

    if len(raw) >= 5 + lc:
        data_end = 5 + lc
        result["data"] = raw[5:data_end]
        result["lc"] = lc

        if len(raw) > data_end:
            result["le"] = raw[data_end]
        elif lc == 0:
            result["le"] = 0x00
    else:
        result["lc"] = lc

    # 特殊: 如果最后 2 字节看起来是 Le (当 data 已解析完还有剩余)
    if result["data"] is not None:
        consumed = 5 + (result["lc"] or 0)
        if len(raw) > consumed:
            result["le"] = raw[consumed]

    return result


# ── 格式化 ─────────────────────────────────────────────


def format_apdu(hex_str: str) -> str:
    """格式化 APDU 为人类可读字符串。"""
    try:
        parsed = parse_apdu_hex(hex_str)
    except ValueError:
        return f"原始: {hex_str}"

    parts = [
        f"{parsed['cla']:02X} {parsed['ins']:02X} {parsed['p1']:02X} {parsed['p2']:02X}"
    ]

    ins_name = _ins_name(parsed["ins"])
    cla_name = _cla_name(parsed["cla"])

    info = f"{cla_name} / {ins_name}"

    return f"{'  '.join(parts)}  # {info}"


def format_response(data: bytes, sw: int) -> str:
    """格式化 APDU 响应。

    Args:
        data: 响应数据体。
        sw: 2 字节状态字。

    Returns:
        人类可读的响应字符串。
    """
    sw_info = SW_DATABASE.get(sw)
    sw_class = SW_DATABASE.get_class(sw)

    parts = []
    if data:
        truncated = data[:64]
        hex_data = truncated.hex().upper()
        if len(data) > 64:
            hex_data += f"... ({len(data)} 字节)"
        parts.append(f"数据: {hex_data}")

    sw_str = f"SW: {sw:04X}"
    if sw_info:
        sw_str += f" ({sw_info})"
    elif sw_class:
        sw_str += f" [{sw_class}]"
    parts.append(sw_str)

    return " | ".join(parts)


def apdu_summary(hex_str: str) -> str:
    """生成 APDU 单行摘要。"""
    try:
        parsed = parse_apdu_hex(hex_str)
        ins_name = _ins_name(parsed["ins"])
        cla = parsed["cla"]
        ins = parsed["ins"]
        p1p2 = f"{parsed['p1']:02X}{parsed['p2']:02X}"
        lc_info = f" Lc={parsed['lc']}" if parsed['lc'] is not None else ""
        return f"{cla:02X}{ins:02X}{p1p2}{lc_info}  [{ins_name}]"
    except ValueError:
        return hex_str


def log_apdu(path: str, apdu_hex: str, data: bytes, sw: int) -> None:
    """记录 APDU 到日志文件。

    Args:
        path: 日志文件路径。
        apdu_hex: APDU 十六进制字符串。
        data: 响应数据。
        sw: 状态字。
    """
    from datetime import datetime
    timestamp = datetime.now().isoformat(timespec="milliseconds")
    data_hex = data.hex().upper() if data else "(空)"
    line = f"[{timestamp}] → {apdu_hex} | ← {data_hex} SW={sw:04X}\n"
    try:
        with open(path, "a") as f:
            f.write(line)
    except OSError:
        pass
