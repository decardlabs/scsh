"""scsh 入口点 — 依赖检查、参数解析与 REPL 启动。"""

from __future__ import annotations

import argparse
import importlib.metadata
import shutil
import sys


# ── 运行环境预检 ──────────────────────────────────────────────


def _check_python_packages() -> list[str]:
    """检查 Python 依赖包是否已安装（用 metadata 查，不触发 import）。"""
    missing: list[str] = []
    packages: dict[str, str] = {
        "pyscard": "pyscard>=2.1",
        "prompt_toolkit": "prompt-toolkit>=3.0",
        "rich": "rich>=13",
    }
    for pkg_name, label in packages.items():
        try:
            importlib.metadata.distribution(pkg_name)
        except importlib.metadata.PackageNotFoundError:
            missing.append(label)
    return missing


def _check_system_services() -> list[str]:
    """检查系统服务和外部工具（pcscd、java 等）。"""
    missing: list[str] = []
    if not shutil.which("pcscd"):
        missing.append("PC/SC 服务 (pcscd)  —  brew install pcsc-lite")
    java = shutil.which("java")
    if not java:
        missing.append("Java Runtime       —  用于 GP 功能 (brew install java)")
    return missing


def check_environment() -> list[str]:
    """检查运行环境，返回所有缺失项列表。"""
    return _check_python_packages() + _check_system_services()


def print_missing(missing: list[str]) -> None:
    """将缺失项格式化输出到 stderr。"""
    print("scsh: 缺少运行依赖，请先安装：\n", file=sys.stderr)
    for item in missing:
        print(f"  • {item}", file=sys.stderr)
    print(file=sys.stderr)
    print("安装所有依赖：  pip install -e .", file=sys.stderr)
    print("开发模式：       pip install -e \".[dev]\"", file=sys.stderr)


# ── 命令注册表 ──────────────────────────────────────────────


def build_registry() -> "CommandRegistry":
    """构建命令注册表，注册所有可用命令。"""
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
        # M4 补充
        cmd_gp_set_default,
        cmd_gp_lock_card,
        cmd_gp_unlock_card,
        cmd_gp_init_card,
        cmd_gp_secure_card,
        cmd_gp_put_key,
        cmd_gp_delete_key,
        cmd_gp_store_data,
        cmd_gp_create_domain,
        cmd_gp_rename_isd,
        cmd_gp_load,
        cmd_gp_uninstall,
        cmd_gp_set_cplc,
        cmd_gp_secure_apdu,
        cmd_gp_mode,
        cmd_gp_make_selectable,
    )
    from scsh.commands.system import cmd_version

    registry = CommandRegistry()

    # M0 — 系统命令
    registry.register("version", "显示 scsh 版本信息", cmd_version)

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
    registry.register("gp-set-default", "设置默认 Applet（NFC）", cmd_gp_set_default)
    registry.register("gp-lock-card", "锁定卡片", cmd_gp_lock_card)
    registry.register("gp-unlock-card", "解锁卡片", cmd_gp_unlock_card)
    registry.register("gp-init-card", "初始化卡片（OP_READY→INITIALIZED）", cmd_gp_init_card)
    registry.register("gp-secure-card", "安全化卡片（INITIALIZED→SECURED）", cmd_gp_secure_card)
    registry.register("gp-put-key", "更新 SCP 密钥", cmd_gp_put_key)
    registry.register("gp-delete-key", "删除指定版本密钥", cmd_gp_delete_key)
    registry.register("gp-store-data", "写入个人化数据", cmd_gp_store_data)
    registry.register("gp-create-domain", "创建补充安全域（SSD）", cmd_gp_create_domain)
    registry.register("gp-rename-isd", "重命名 ISD AID", cmd_gp_rename_isd)
    registry.register("gp-load", "仅加载 CAP（不分 INSTALL）", cmd_gp_load)
    registry.register("gp-uninstall", "卸载 CAP/Package", cmd_gp_uninstall)
    registry.register("gp-set-cplc", "设置 CPLC 个人化日期", cmd_gp_set_cplc)
    registry.register("gp-secure-apdu", "通过 SCP 安全通道发送 APDU", cmd_gp_secure_apdu)
    registry.register("gp-mode", "设置 SCP 安全通道模式", cmd_gp_mode)
    registry.register("gp-make-selectable", "将已安装 Applet 设为可选", cmd_gp_make_selectable)

    # M5 — 辅助功能
    registry.register("repeat", "重复上一条 APDU", cmd_repeat)
    registry.register("timing", "切换 APDU 耗时显示", cmd_timing)
    registry.register("config", "查看/设置配置", cmd_config)
    registry.register("record", "录制当前会话到文件", cmd_record)

    return registry


# ── 参数解析 ──────────────────────────────────────────────


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


# ── 脚本执行 ──────────────────────────────────────────────


def execute_script(path: str, registry: "CommandRegistry", session: "Session") -> None:
    """执行脚本文件中的命令。"""
    with open(path) as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            name, args = registry.parse_line(stripped)
            registry.execute(name, args, session)


# ── 入口 ──────────────────────────────────────────────


def main() -> None:
    """scsh 主入口。"""
    # 第一步：预检运行环境
    args = parse_args()
    missing = check_environment()
    if missing:
        print_missing(missing)
        sys.exit(1)

    # 第二步：预检通过，加载 scsh 模块（延迟 import）
    import os

    from scsh.transport.pcsc import PCSCTransport
    from scsh.bridge.gp_jar import GPJarBridge
    from scsh.session import Session

    transport = PCSCTransport()
    scsh_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    gp_jar_path = os.path.join(scsh_dir, "tools", "gp.jar")
    gp_bridge = GPJarBridge(jar_path=gp_jar_path) if os.path.isfile(gp_jar_path) else GPJarBridge()
    session = Session(transport=transport, gp_bridge=gp_bridge)
    registry = build_registry()

    if args.command:
        name, cmd_args = registry.parse_line(args.command)
        registry.execute(name, cmd_args, session)
        return

    if args.file:
        execute_script(args.file, registry, session)
        return

    # 交互式 REPL
    from scsh.repl import ScshRepl

    repl = ScshRepl(registry=registry, session=session)
    repl.run()


if __name__ == "__main__":
    main()
