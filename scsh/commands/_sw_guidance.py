"""SW 自动引导工具。

v0.7.0 新增：当 GP 命令失败时，自动提取 SW 状态字并显示诊断帮助。

使用方式：在各 subsystem handler 的 GPBridgeError catch 中调用 sw_tip(exc, context)。
"""

from __future__ import annotations

import re
from typing import Any

from scsh.commands.help_data import (
    CARD_HELP, DEPLOY_HELP, CONFIG_HELP, KEY_HELP, APDU_HELP, SESSION_HELP,
)


# ── 全局 SW → diagnostic 索引 ──

ALL_HELP_DATA: dict[str, dict[str, Any]] = {}


def _build_help_index() -> None:
    """构建全局 SW → diagnostic 索引。"""
    ALL_HELP_DATA.clear()
    ALL_HELP_DATA.update(CARD_HELP)
    ALL_HELP_DATA.update(DEPLOY_HELP)
    ALL_HELP_DATA.update(CONFIG_HELP)
    ALL_HELP_DATA.update(KEY_HELP)
    ALL_HELP_DATA.update(APDU_HELP)
    ALL_HELP_DATA.update(SESSION_HELP)


_build_help_index()


def sw_guidance(sw_code: str, context: str = "") -> str | None:
    """查找 SW 状态字的诊断帮助。

    Args:
        sw_code: SW 状态字（如 "6985", "6A82"）。
        context: 命令上下文（如 "card list", "deploy install"），用于精确匹配。

    Returns:
        诊断字符串，或 None（找不到时）。
    """
    # 优先在指定上下文中查找
    if context:
        parts = context.strip().split()
        subcmd = parts[-1] if len(parts) >= 2 else parts[0]
        help_data = ALL_HELP_DATA.get(subcmd)
        if help_data:
            diagnostic = help_data.get("diagnostic")
            if diagnostic and sw_code in diagnostic:
                info = diagnostic[sw_code]
                return f"SW {sw_code}: {info.get('cause', '')} → {info.get('fix', '')}"

    # 全局扫描所有 diagnostic
    for cmd_name, help_data in ALL_HELP_DATA.items():
        diagnostic = help_data.get("diagnostic")
        if diagnostic and sw_code in diagnostic:
            info = diagnostic[sw_code]
            return f"SW {sw_code}: {info.get('cause', '')} → {info.get('fix', '')}"

    # 兜底：通用 SW 码对照表
    generic_sw = {
        "6700": "SW 6700: Lc/Le 长度错误 → 检查 APDU 数据长度参数",
        "6D00": "SW 6D00: INS 不支持 → 检查指令码，该操作可能不被当前 AID 支持",
        "6E00": "SW 6E00: CLA 不支持 → 检查 CLA 值，安全通道命令需用 84",
        "6B00": "SW 6B00: P1/P2 参数错误 → 检查命令参数值",
        "6A86": "SW 6A86: P1/P2 不正确 → 检查命令参数是否匹配操作要求",
        "6A88": "SW 6A88: 引用数据未找到 → 检查目标 AID/密钥版本是否存在",
        "6A84": "SW 6A84: 存储空间不足 → 卡片内存已满，需删除不需要的包",
        "6100": "SW 61xx: 有响应数据待取 → 执行 apdu get-response 获取",
    }
    # 支持模糊匹配（61xx → 6100）
    result = generic_sw.get(sw_code)
    if not result and sw_code.startswith("61"):
        result = generic_sw.get("6100")
    if result:
        return result

    return None


def extract_sw_from_error(error_msg: str) -> str | None:
    """从错误消息中提取 SW 状态字。

    支持格式: "6985", "0x6985", "SW 6985", "返回 6985" 等。
    """
    # 匹配 4 位十六进制 SW（在错误文本中）
    patterns = [
        r'SW\s*(\d{4})',
        r'0x([0-9A-Fa-f]{4})',
        r'(?:返回|returned|response)\s*([0-9A-Fa-f]{4})',
        # 兜底：孤立的 4 位 hex SW（通常是 69xx/6Axx/90xx/61xx）
        r'(?:^|[\s(])([69][0-9A-Fa-f]{3}|90[0-9A-Fa-f]{2}|61[0-9A-Fa-f]{2})(?:$|[\s)])',
    ]
    for pattern in patterns:
        m = re.search(pattern, error_msg, re.IGNORECASE)
        if m:
            sw = m.group(1).upper()
            return sw
    return None


def sw_tip(exc: Exception, context: str = "") -> None:
    """在 GPBridgeError catch 中调用，自动显示 SW 诊断引导。

    Args:
        exc: 捕获的异常对象。
        context: 命令上下文（如 "card lifecycle", "deploy install"）。

    用法:
        try:
            bridge.some_command()
        except GPBridgeError as exc:
            print(f"❌ 操作失败: {exc}")
            sw_tip(exc, "card lifecycle")
    """
    error_msg = str(exc)
    sw = extract_sw_from_error(error_msg)
    if sw:
        guidance = sw_guidance(sw, context)
        if guidance:
            print(f"💡 {guidance}")
