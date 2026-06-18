"""apdu 子系统命令注册。

apdu — APDU 交互子系统
  send         发送原始 APDU
  select       SELECT AID 快捷
  get-response GET RESPONSE
  send-file    从文件批量发送
  repeat       重复上一条
  timing       耗时开关
  secure-send  SCP 安全通道发送
"""

from __future__ import annotations

from typing import Any

from scsh.commands.help_data import APDU_HELP


def register_apdu_subsystem(registry: Any) -> None:
    """注册 apdu 子系统及其子命令和别名。"""
    from scsh.commands.apdu import (
        cmd_send,
        cmd_select,
        cmd_get_response,
        cmd_send_file,
        cmd_repeat,
        cmd_timing,
    )
    from scsh.commands.gp import cmd_gp_secure_apdu

    registry.register_subsystem("apdu", "APDU 交互子系统")

    registry.register_subcommand(
        "apdu", "send", "发送原始 APDU", cmd_send, APDU_HELP["send"]
    )
    registry.register_subcommand(
        "apdu", "select", "SELECT AID 快捷", cmd_select, APDU_HELP["select"]
    )
    registry.register_subcommand(
        "apdu", "get-response", "GET RESPONSE", cmd_get_response, APDU_HELP["get-response"]
    )
    registry.register_subcommand(
        "apdu", "send-file", "从文件批量发送 APDU", cmd_send_file
    )
    registry.register_subcommand(
        "apdu", "repeat", "重复上一条 APDU", cmd_repeat
    )
    registry.register_subcommand(
        "apdu", "timing", "切换 APDU 耗时显示", cmd_timing
    )
    registry.register_subcommand(
        "apdu", "secure-send", "通过 SCP 安全通道发送 APDU", cmd_gp_secure_apdu, APDU_HELP["secure-send"]
    )

    # 别名：旧扁平命令名 → subsystem handler
    registry.register_alias("send", "apdu", "send")
    registry.register_alias("select", "apdu", "select")
    registry.register_alias("get-response", "apdu", "get-response")
    registry.register_alias("send-file", "apdu", "send-file")
    registry.register_alias("repeat", "apdu", "repeat")
    registry.register_alias("timing", "apdu", "timing")
    registry.register_alias("gp-secure-apdu", "apdu", "secure-send")
