"""card 子系统命令注册。

card — 卡片管理子系统
  list         列出 ISD/Package/Applet
  info         完整卡片信息（info+scp+status 合并）
  lifecycle    卡片生命周期管理 (init/secure/lock/unlock)
  applet-state Applet 级状态控制 (selectable/locked/blocked)
  store-data   写入个人化数据
  create-domain 创建 SSD
  rename-isd   重命名 ISD
  make-selectable 设为可选
  set-cplc     设置 CPLC 日期

v0.4.0: lifecycle/applet-state 使用现有 handler 桥接，v0.5.0 增强。
"""

from __future__ import annotations

from typing import Any

from scsh.exceptions import GPBridgeError
from scsh.session import Session
from scsh.commands.help_data import CARD_HELP


# ── 工具函数 ──

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
    # 也从 config_manager 获取别名
    config_mgr = getattr(session, "config_manager", None)
    if config_mgr:
        config_aliases = config_mgr.get("aliases", {})
        if isinstance(config_aliases, dict):
            aliases = {**aliases, **config_aliases}
    return aliases.get(args.strip(), args.strip())


# ── 新 handler：合并 card info ──

def cmd_card_info(args: str, session: Session) -> None:
    """card info — 合并 gp-info + gp-scp + gp-status 三合一。

    一条命令输出完整卡片信息：基本信息 + CPLC + SCP 通道 + 生命周期状态。
    """
    bridge = _get_bridge(session)
    if not bridge:
        return

    try:
        info_result = bridge.info()
        list_result = bridge.list()
    except GPBridgeError as exc:
        print(f"card info 失败: {exc}")
        return

    from scsh.commands.gp import _format_gp_info, _format_gp_status

    for line in _format_gp_info(info_result):
        print(line)

    print("")
    for line in _format_gp_status(list_result, info_result):
        print(line)


# ── 新 handler：card lifecycle ──

def cmd_card_lifecycle(args: str, session: Session) -> None:
    """card lifecycle — 卡片生命周期管理。

    无参数时显示当前生命周期状态。
    有参数时执行对应状态转换。
    """
    from scsh.commands.gp import (
        cmd_gp_init_card,
        cmd_gp_secure_card,
        cmd_gp_lock_card,
        cmd_gp_unlock_card,
    )

    if not args:
        # 显示当前状态
        bridge = _get_bridge(session)
        if not bridge:
            return
        try:
            list_result = bridge.list()
        except GPBridgeError as exc:
            print(f"查询失败: {exc}")
            return
        state = list_result.get("isd_state") or "未知"
        state_desc = {
            "OP_READY": "出厂就绪，可用默认密钥连接和管理",
            "INITIALIZED": "已初始化，LOAD/INSTALL 受限",
            "SECURED": "安全状态，需要密钥认证才能管理",
            "CARD_LOCKED": "卡片已锁定，仅可解锁",
            "TERMINATED": "已终止（不可逆）",
        }.get(state, "")
        print(f"当前生命周期: {state}")
        if state_desc:
            print(f"  → {state_desc}")
        print("")
        print("可用操作: init, secure, lock, unlock")
        return

    action = args.strip().split()[0]  # 只取第一个词
    actions = {
        "init": cmd_gp_init_card,
        "secure": cmd_gp_secure_card,
        "lock": cmd_gp_lock_card,
        "unlock": cmd_gp_unlock_card,
    }

    handler = actions.get(action)
    if handler:
        handler("", session)
    else:
        print(f"未知生命周期操作: {action}")
        print("可用操作: init, secure, lock, unlock")


# ── 新 handler：card applet-state（v0.5.0 增强，v0.4.0 桥接现有 lock/unlock）─

def cmd_card_applet_state(args: str, session: Session) -> None:
    """card applet-state — Applet 级状态控制。

    v0.4.0 桥接版：selectable → gp-unlock, locked → gp-lock
    v0.5.0 增强：直接 SET STATUS APDU + blocked 状态
    """
    from scsh.commands.gp import cmd_gp_lock, cmd_gp_unlock

    if not args:
        print("用法: card applet-state <AID> [selectable|locked|blocked]")
        return

    parts = args.strip().split()
    if len(parts) < 1:
        print("用法: card applet-state <AID> [selectable|locked|blocked]")
        return

    aid = _resolve_aid(parts[0], session)

    if len(parts) == 1:
        # 只查看，不设置（v0.5.0 实现）
        print(f"Applet {aid} — 状态查询将在 v0.5.0 实现")
        return

    state = parts[1].lower()
    if state == "locked":
        cmd_gp_lock(aid, session)
    elif state == "selectable":
        cmd_gp_unlock(aid, session)
    elif state == "blocked":
        print("blocked 状态将在 v0.5.0 实现（需要 SET STATUS APDU）")
    else:
        print(f"未知 Applet 状态: {state}")
        print("可用状态: selectable, locked, blocked")


# ── 注册函数 ──

def register_card_subsystem(registry: Any) -> None:
    """注册 card 子系统及其子命令和别名。"""
    from scsh.commands.gp import (
        cmd_gp_list,
        cmd_gp_store_data,
        cmd_gp_create_domain,
        cmd_gp_rename_isd,
        cmd_gp_make_selectable,
        cmd_gp_set_default,
        cmd_gp_set_cplc,
    )

    registry.register_subsystem("card", "卡片管理子系统")

    # 子命令
    registry.register_subcommand(
        "card", "list", "列出 ISD/Package/Applet", cmd_gp_list, CARD_HELP["list"]
    )
    registry.register_subcommand(
        "card", "info", "完整卡片信息（info+scp+status 合并）", cmd_card_info, CARD_HELP["info"]
    )
    registry.register_subcommand(
        "card", "lifecycle", "卡片生命周期管理", cmd_card_lifecycle, CARD_HELP["lifecycle"]
    )
    registry.register_subcommand(
        "card", "applet-state", "Applet 级状态控制", cmd_card_applet_state, CARD_HELP["applet-state"]
    )
    registry.register_subcommand(
        "card", "store-data", "写入个人化数据", cmd_gp_store_data, CARD_HELP["store-data"]
    )
    registry.register_subcommand(
        "card", "create-domain", "创建补充安全域（SSD）", cmd_gp_create_domain, CARD_HELP["create-domain"]
    )
    registry.register_subcommand(
        "card", "rename-isd", "重命名 ISD AID", cmd_gp_rename_isd, CARD_HELP["rename-isd"]
    )
    registry.register_subcommand(
        "card", "make-selectable", "将已安装 Applet 设为可选/默认",
        cmd_gp_make_selectable, CARD_HELP["make-selectable"]
    )
    registry.register_subcommand(
        "card", "set-cplc", "设置 CPLC 个人化日期", cmd_gp_set_cplc, CARD_HELP["set-cplc"]
    )

    # 别名（保留旧 gp-xxx 命令名）
    registry.register_alias("gp-list", "card", "list")
    registry.register_alias("gp-info", "card", "info")
    registry.register_alias("gp-scp", "card", "info", "(别名 → card info) SCP 信息（已合并到 card info）")
    registry.register_alias("gp-status", "card", "info", "(别名 → card info) 卡片状态（已合并到 card info）")
    registry.register_alias("gp-init-card", "card", "lifecycle")
    registry.register_alias("gp-secure-card", "card", "lifecycle")
    registry.register_alias("gp-lock-card", "card", "lifecycle")
    registry.register_alias("gp-unlock-card", "card", "lifecycle")
    registry.register_alias("gp-lock", "card", "applet-state", "(别名 → card applet-state) 锁定 Applet")
    registry.register_alias("gp-unlock", "card", "applet-state", "(别名 → card applet-state) 解锁 Applet")
    registry.register_alias("gp-store-data", "card", "store-data")
    registry.register_alias("gp-create-domain", "card", "create-domain")
    registry.register_alias("gp-rename-isd", "card", "rename-isd")
    registry.register_alias("gp-make-selectable", "card", "make-selectable")
    registry.register_alias("gp-set-default", "card", "make-selectable", "(别名 → card make-selectable) 设为默认 Applet")
    registry.register_alias("gp-set-cplc", "card", "set-cplc")
