"""scsh 入口点 — 依赖检查、参数解析与 REPL 启动。

v0.4.0: 子系统命令架构 + ConfigManager + gp 透传 + gp-create 废弃。
"""

from __future__ import annotations

import argparse
import importlib.metadata
import os
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
    # macOS: PC/SC 内置于 PCSC.framework XPC 服务，无独立 pcscd 二进制
    # Linux: 需要 pcsc-lite 提供的 pcscd 服务
    if not shutil.which("pcscd"):
        if sys.platform == "darwin":
            # macOS 上 PCSC.framework 存在即表示 PC/SC 可用
            pcsc_framework = "/System/Library/Frameworks/PCSC.framework"
            if not os.path.isdir(pcsc_framework):
                missing.append("PC/SC 服务 (pcscd)  —  brew install pcsc-lite")
        else:
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
    """构建命令注册表，注册所有子系统、子命令和别名。

    v0.4.0 架构：
    - 6 个子系统：card / deploy / config / key / apdu / session
    - 所有旧 gp-xxx 命令注册为别名（指向子系统子命令 handler）
    - gp <raw_args> 透传命令
    - version 独立扁平命令
    - gp-create 已废弃（不再注册）
    """
    from scsh.commands import CommandRegistry

    registry = CommandRegistry()

    # ── 子系统 ──
    from scsh.commands.card import register_card_subsystem
    from scsh.commands.deploy import register_deploy_subsystem
    from scsh.commands.config_cmd import register_config_subsystem
    from scsh.commands.key_cmd import register_key_subsystem
    from scsh.commands.apdu_subsys import register_apdu_subsystem
    from scsh.commands.session_cmd import register_session_subsystem

    register_card_subsystem(registry)
    register_deploy_subsystem(registry)
    register_config_subsystem(registry)
    register_key_subsystem(registry)
    register_apdu_subsystem(registry)
    register_session_subsystem(registry)

    # ── gp 透传 ──
    from scsh.commands.passthrough import register_gp_passthrough
    register_gp_passthrough(registry)

    # ── 扁平命令（不属于任何子系统）──
    from scsh.commands.system import cmd_version
    registry.register("version", "显示 scsh 版本信息", cmd_version)

    # ── 废弃：gp-create 不再注册 ──

    return registry


# ── 参数解析 ──────────────────────────────────────────────


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析命令行参数。"""
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
    """执行脚本文件中的命令。

    v0.4.0: 使用 execute_line() 支持子系统命令。
    """
    with open(path) as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            registry.execute_line(stripped, session)


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
    from scsh.transport.pcsc import PCSCTransport
    from scsh.bridge.gp_jar import GPJarBridge
    from scsh.config import ConfigManager
    from scsh.session import Session

    transport = PCSCTransport()
    scsh_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    gp_jar_path = os.path.join(scsh_dir, "tools", "gp.jar")
    gp_bridge = GPJarBridge(jar_path=gp_jar_path) if os.path.isfile(gp_jar_path) else GPJarBridge()

    # v0.4.0: 初始化 ConfigManager
    config_mgr = ConfigManager()
    config_mgr.load_all(scsh_dir)

    session = Session(
        transport=transport,
        gp_bridge=gp_bridge,
        config_manager=config_mgr,
    )

    # v0.4.0: 同步配置到 session 和 bridge
    from scsh.commands.config_cmd import _sync_config_to_session
    _sync_config_to_session(session)

    registry = build_registry()

    if args.command:
        registry.execute_line(args.command, session)
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
