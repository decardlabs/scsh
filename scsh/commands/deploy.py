"""deploy 子系统命令注册。

deploy — 部署管理子系统
  install      安装 CAP 文件
  delete       删除 Package/Applet
  load         仅加载 CAP（不 INSTALL）
  provision    按 Profile 蓝图自动编排（v0.6.0 增强）
  plan         显示 Profile 预期变更（v0.6.0 增强）
"""

from __future__ import annotations

from typing import Any

from scsh.session import Session
from scsh.commands.help_data import DEPLOY_HELP


def _get_bridge(session: Session) -> Any | None:
    """获取 GP bridge 对象或 None。"""
    bridge = getattr(session, "gp_bridge", None)
    if bridge is None:
        print("GP 桥接未就绪。需要安装 Java 和 GlobalPlatformPro (gp.jar)。")
        return None
    return bridge


def _resolve_aid(args: str, session: Session) -> str:
    """解析 AID 参数，支持别名展开。"""
    aliases = getattr(session, "aid_aliases", {})
    config_mgr = getattr(session, "config_manager", None)
    if config_mgr:
        config_aliases = config_mgr.get("aliases", {})
        if isinstance(config_aliases, dict):
            aliases = {**aliases, **config_aliases}
    return aliases.get(args.strip(), args.strip())


def cmd_deploy_provision(args: str, session: Session) -> None:
    """deploy provision — 按 Profile 蓝图自动编排。

    v0.4.0 占位：提示将在 v0.6.0 实现。
    """
    print("deploy provision 将在 v0.6.0 实现（Profile 蓝图系统）。")
    print("当前可用: deploy install, deploy delete, deploy load")


def cmd_deploy_plan(args: str, session: Session) -> None:
    """deploy plan — 显示 Profile 预期变更。

    v0.4.0 占位：提示将在 v0.6.0 实现。
    """
    print("deploy plan 将在 v0.6.0 实现（Profile 蓝图系统）。")
    print("当前可用: card list 查看卡片状态")


def register_deploy_subsystem(registry: Any) -> None:
    """注册 deploy 子系统及其子命令和别名。"""
    from scsh.commands.gp import (
        cmd_gp_install,
        cmd_gp_delete,
        cmd_gp_load,
        cmd_gp_uninstall,
    )

    registry.register_subsystem("deploy", "部署管理子系统")

    # 子命令
    registry.register_subcommand(
        "deploy", "install", "安装 CAP 文件", cmd_gp_install, DEPLOY_HELP["install"]
    )
    registry.register_subcommand(
        "deploy", "delete", "删除 Package/Applet", cmd_gp_delete, DEPLOY_HELP["delete"]
    )
    registry.register_subcommand(
        "deploy", "load", "仅加载 CAP（不 INSTALL）", cmd_gp_load, DEPLOY_HELP["load"]
    )
    registry.register_subcommand(
        "deploy", "provision", "按 Profile 蓝图自动编排", cmd_deploy_provision, DEPLOY_HELP["provision"]
    )
    registry.register_subcommand(
        "deploy", "plan", "显示 Profile 预期变更", cmd_deploy_plan, DEPLOY_HELP["plan"]
    )

    # 别名
    registry.register_alias("gp-install", "deploy", "install")
    registry.register_alias("gp-delete", "deploy", "delete")
    registry.register_alias("gp-load", "deploy", "load")
    registry.register_alias("gp-uninstall", "deploy", "delete", "(别名 → deploy delete) 卸载 CAP")
