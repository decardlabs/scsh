"""session 子系统命令注册。

session — 会话管理子系统
  info         当前卡片信息
  readers      列出读卡器
  connect      连接读卡器
  reconnect    重连
  reset        冷复位
  record       录制会话
"""

from __future__ import annotations

from typing import Any

from scsh.commands.help_data import SESSION_HELP


def register_session_subsystem(registry: Any) -> None:
    """注册 session 子系统及其子命令和别名。"""
    from scsh.commands.hardware import (
        cmd_info,
        cmd_readers,
        cmd_connect,
        cmd_reconnect,
        cmd_reset,
    )
    from scsh.commands.apdu import cmd_record

    registry.register_subsystem("session", "会话管理子系统")

    registry.register_subcommand(
        "session", "info", "显示当前卡片信息（ATR、协议）", cmd_info, SESSION_HELP["info"]
    )
    registry.register_subcommand(
        "session", "readers", "列出所有读卡器", cmd_readers, SESSION_HELP["readers"]
    )
    registry.register_subcommand(
        "session", "connect", "连接指定编号的读卡器", cmd_connect, SESSION_HELP["connect"]
    )
    registry.register_subcommand(
        "session", "reconnect", "断开并重连当前读卡器", cmd_reconnect, SESSION_HELP["reconnect"]
    )
    registry.register_subcommand(
        "session", "reset", "卡片冷复位", cmd_reset, SESSION_HELP["reset"]
    )
    registry.register_subcommand(
        "session", "record", "录制当前会话到文件", cmd_record, SESSION_HELP["record"]
    )

    # 别名
    registry.register_alias("readers", "session", "readers")
    registry.register_alias("connect", "session", "connect")
    registry.register_alias("reconnect", "session", "reconnect")
    registry.register_alias("info", "session", "info")
    registry.register_alias("reset", "session", "reset")
    registry.register_alias("record", "session", "record")
