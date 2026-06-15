"""硬件层命令：readers / connect / reconnect / info / reset。"""

from __future__ import annotations

from typing import Any

from scsh.exceptions import (
    CardDisconnectedError,
    NoReadersError,
    TransportError,
)
from scsh.session import Session


def cmd_readers(args: str, session: Session) -> None:
    """列出所有读卡器。"""
    try:
        readers = session.transport.list_readers()
    except NoReadersError:
        print("未检测到读卡器")
        return

    if not readers:
        print("没有已连接的读卡器")
        return

    print(f"找到 {len(readers)} 个读卡器:")
    for i, r in enumerate(readers):
        if r.get("card_present"):
            if r.get("muted"):
                status = "🔇 有卡(无响应)"
            elif r.get("unpowered"):
                status = "⚡ 有卡(未供电)"
            else:
                status = "✅ 有卡"
        else:
            status = " 空槽"
        line = f"  [{i}] {r['name']}  {status}"
        if r.get("event_state"):
            line += f"  [state=0x{r['event_state']:04x}]"
        print(line)


def cmd_connect(args: str, session: Session) -> None:
    """连接到指定读卡器。"""
    if not args:
        print("用法: connect <读卡器编号>")
        return

    try:
        index = int(args)
    except ValueError:
        print("错误: 读卡器编号必须是数字")
        return

    try:
        result = session.transport.connect(index)
    except (IndexError, TransportError) as exc:
        print(f"连接失败: {exc}")
        return

    atr = result["atr"].hex().upper()
    proto = "T=1" if result["protocol"] == 2 else "T=0"
    print(f"已连接到: {result['reader_name']}")
    print(f"ATR: {atr}")
    print(f"协议: {proto}")


def cmd_info(args: str, session: Session) -> None:
    """显示当前卡片信息。"""
    if session.transport._reader_name is None:
        print("未连接读卡器")
        return

    try:
        atr, protocol = session.transport._get_atr_and_protocol()
    except CardDisconnectedError:
        print("卡片已断开，请执行 connect 重新连接")
        return

    proto = "T=1" if protocol == 2 else "T=0"
    print(f"读卡器: {session.transport._reader_name}")
    print(f"协议:   {proto}")
    print(f"ATR:    {atr.hex().upper()}")


def cmd_reset(args: str, session: Session) -> None:
    """卡片冷复位。"""
    try:
        atr = session.transport.reset()
    except CardDisconnectedError:
        print("未连接读卡器")
        return

    print(f"复位成功 — ATR: {atr.hex().upper()}")


def cmd_reconnect(args: str, session: Session) -> None:
    """断开并重新连接读卡器。"""
    try:
        result = session.transport.reconnect()
    except CardDisconnectedError:
        print("未连接读卡器")
        return

    atr = result["atr"].hex().upper()
    proto = "T=1" if result["protocol"] == 2 else "T=0"
    print(f"重连成功")
    print(f"ATR: {atr}")
    print(f"协议: {proto}")


def cmd_config(args: str, session: Session) -> None:
    """查看/设置配置。"""
    parts = args.strip().split()

    if not parts:
        # 显示所有配置
        print("当前配置:")
        for key, val in session.config.items():
            print(f"  {key}: {val}")
        return

    if parts[0] == "set" and len(parts) >= 3:
        key = parts[1]
        val = parts[2]
        session.config[key] = val
        print(f"已设置 {key} = {val}")
    elif parts[0] == "get" and len(parts) >= 2:
        key = parts[1]
        val = session.config.get(key, "未设置")
        print(f"{key}: {val}")
    else:
        print("用法: config [set <key> <value> | get <key>]")
