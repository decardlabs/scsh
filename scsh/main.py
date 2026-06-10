"""scsh 入口点 — 参数解析与 REPL 启动。"""

from __future__ import annotations

import argparse
from typing import Any

from scsh.commands import CommandRegistry
from scsh.commands.hardware import (
    cmd_connect,
    cmd_info,
    cmd_reconnect,
    cmd_readers,
    cmd_reset,
    cmd_config,
)
from scsh.commands.apdu import (
    cmd_send,
    cmd_select,
    cmd_get_response,
    cmd_send_file,
    cmd_repeat,
    cmd_timing,
    cmd_record,
)
from scsh.commands.gp import (
    cmd_gp_list,
    cmd_gp_info,
    cmd_gp_aid,
    cmd_gp_scp,
    cmd_gp_status,
    cmd_gp_install,
    cmd_gp_delete,
    cmd_gp_lock,
    cmd_gp_unlock,
    cmd_gp_create,
    cmd_gp_key,
)
from scsh.transport.pcsc import PCSCTransport
from scsh.bridge.gp_jar import GPJarBridge


def build_registry() -> CommandRegistry:
    """构建命令注册表，注册所有可用命令。"""
    registry = CommandRegistry()

    # M1 — 硬件层
    registry.register("readers", "列出所有读卡器", cmd_readers)
    registry.register("connect", "连接指定编号的读卡器", cmd_connect)
    registry.register("reconnect", "断开并重连当前读卡器", cmd_reconnect)
    registry.register("info", "显示当前卡片信息（ATR、协议）", cmd_info)
    registry.register("reset", "卡片冷复位", cmd_reset)

    # M2 — APDU 层
    registry.register("send", "发送原始 APDU 指令", cmd_send)
    registry.register("select", "SELECT AID 快捷命令", cmd_select)
    registry.register("get-response", "GET RESPONSE 命令", cmd_get_response)
    registry.register("send-file", "从文件读取 APDU 并逐条发送", cmd_send_file)

    # M3 — GP 查询
    registry.register("gp-list", "列出已安装的 ISD/Package/Applet", cmd_gp_list)
    registry.register("gp-info", "显示 GP 详细信息", cmd_gp_info)
    registry.register("gp-aid", "注册 AID 别名", cmd_gp_aid)
    registry.register("gp-scp", "查看安全通道信息", cmd_gp_scp)
    registry.register("gp-status", "查询卡片生命周期状态", cmd_gp_status)

    # M4 — GP 操作
    registry.register("gp-install", "安装 CAP 文件", cmd_gp_install)
    registry.register("gp-delete", "删除 Applet/Package", cmd_gp_delete)
    registry.register("gp-lock", "锁定 Applet", cmd_gp_lock)
    registry.register("gp-unlock", "解锁 Applet", cmd_gp_unlock)
    registry.register("gp-create", "创建 Applet 实例", cmd_gp_create)
    registry.register("gp-key", "设置 GP 密钥", cmd_gp_key)

    # M5 — 辅助功能
    registry.register("repeat", "重复上一条 APDU", cmd_repeat)
    registry.register("timing", "切换 APDU 耗时显示", cmd_timing)
    registry.register("config", "查看/设置配置", cmd_config)
    registry.register("record", "录制当前会话到文件", cmd_record)

    return registry


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析命令行参数。

    Args:
        argv: 参数列表，默认使用 sys.argv。

    Returns:
        解析后的参数命名空间。
    """
    parser = argparse.ArgumentParser(
        prog="scsh",
        description="Smart Card Shell — 统一的 REPL 交互式智能卡测试工具",
    )
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="批量执行脚本文件（每行一条命令）",
    )
    parser.add_argument(
        "--command",
        type=str,
        default=None,
        help="单次执行命令后退出（非交互模式）",
    )
    return parser.parse_args(argv)


def execute_script(path: str, registry: CommandRegistry, transport: Any) -> None:
    """执行脚本文件中的命令。"""
    with open(path) as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            name, args = registry.parse_line(stripped)
            registry.execute(name, args, transport)


def main() -> None:
    """scsh 主入口。"""
    args = parse_args()

    transport = PCSCTransport()
    # 在 scsh 项目目录查找 gp.jar
    import os
    scsh_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    gp_jar_path = os.path.join(scsh_dir, "gp.jar")
    if os.path.isfile(gp_jar_path):
        transport.gp_bridge = GPJarBridge(jar_path=gp_jar_path)
    else:
        transport.gp_bridge = GPJarBridge()
    transport._aid_aliases = {}
    registry = build_registry()

    if args.command:
        name, cmd_args = registry.parse_line(args.command)
        registry.execute(name, cmd_args, transport)
        return

    if args.file:
        execute_script(args.file, registry, transport)
        return

    # 交互式 REPL
    from scsh.repl import ScshRepl

    repl = ScshRepl(registry=registry, transport=transport)
    repl.run()


if __name__ == "__main__":
    main()
