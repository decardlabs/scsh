"""card 子系统命令注册。

card — 卡片管理子系统
  list         列出 ISD/Package/Applet
  info         完整卡片信息（info+scp+status 合并）
  lifecycle    卡片生命周期管理 (init/secure/lock/unlock/terminate)
  applet-state Applet 级状态控制 (selectable/locked/blocked)
  store-data   写入个人化数据
  create-domain 创建 SSD
  rename-isd   重命名 ISD
  make-selectable 设为可选
  set-cplc     设置 CPLC 日期

v0.5.0: lifecycle 增加 terminate + 状态机验证 + 不可逆操作保护。
       applet-state 增加 blocked + SET STATUS APDU + 状态查询。
"""

from __future__ import annotations

from typing import Any

from scsh.exceptions import GPBridgeError
from scsh.session import Session
from scsh.commands.help_data import CARD_HELP
from scsh.commands._safety import (
    LIFECYCLE_STATES,
    LIFECYCLE_ACTION_MAP,
    APPLET_STATES,
    APPLET_STATE_NAMES,
    confirm_irreversible,
    is_irreversible,
    validate_transition,
)
from scsh.commands._sw_guidance import sw_tip


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
    config_mgr = getattr(session, "config_manager", None)
    if config_mgr:
        config_aliases = config_mgr.get("aliases", {})
        if isinstance(config_aliases, dict):
            aliases = {**aliases, **config_aliases}
    return aliases.get(args.strip(), args.strip())


def _get_current_lifecycle(session: Session) -> str:
    """查询当前卡片生命周期状态。"""
    bridge = _get_bridge(session)
    if not bridge:
        return "未知"
    try:
        list_result = bridge.list()
        return list_result.get("isd_state") or "未知"
    except GPBridgeError:
        return "未知"


# ── card info ──

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
        sw_tip(exc, "card info")
        return

    from scsh.commands.gp import _format_gp_info, _format_gp_status

    for line in _format_gp_info(info_result):
        print(line)

    print("")
    for line in _format_gp_status(list_result, info_result):
        print(line)


# ── card lifecycle ──

def cmd_card_lifecycle(args: str, session: Session) -> None:
    """card lifecycle — 卡片生命周期管理（v0.5.0 增强）。

    无参数：显示当前状态 + 状态机图 + 允许的转换。
    有参数：执行状态转换，验证合法性，不可逆操作需二次确认。

    状态机: OP_READY → INITIALIZED → SECURED → CARD_LOCKED → TERMINATED
    """
    if not args:
        _show_lifecycle_status(session)
        return

    action = args.strip().split()[0]
    target_state = LIFECYCLE_ACTION_MAP.get(action)
    if not target_state:
        print(f"未知生命周期操作: {action}")
        print("可用操作: init, secure, lock, unlock, terminate")
        return

    # 查询当前状态
    current_state = _get_current_lifecycle(session)
    if current_state == "未知":
        print("无法查询当前卡片状态。继续执行可能不安全。")
        print("输入 'yes' 继续:")
        try:
            answer = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("操作已取消。")
            return
        if answer != "yes":
            print("操作已取消。")
            return

    # 验证状态转换合法性
    allowed, reason = validate_transition(current_state, action)
    if not allowed:
        print(f"❌ {reason}")
        return

    # 不可逆操作确认
    if is_irreversible(action):
        if not confirm_irreversible(action, session):
            return

    # 执行
    bridge = _get_bridge(session)
    if not bridge:
        return

    try:
        if action == "init":
            bridge.initialize_card()
            print(f"✅ 卡片已初始化（{current_state} → INITIALIZED）")
        elif action == "secure":
            bridge.secure_card()
            print(f"✅ 卡片已安全化（{current_state} → SECURED）")
        elif action == "lock":
            bridge.lock_card()
            print(f"✅ 卡片已锁定（{current_state} → CARD_LOCKED）")
        elif action == "unlock":
            bridge.unlock_card()
            print(f"✅ 卡片已解锁（{current_state} → SECURED）")
        elif action == "terminate":
            bridge.terminate_card()
            print(f"✅ 卡片已终止（{current_state} → TERMINATED）")
            print("⚠️ 此操作不可逆，卡片永久无法使用。")
    except GPBridgeError as exc:
        print(f"❌ 操作失败: {exc}")
        sw_tip(exc, "card lifecycle")


def _show_lifecycle_status(session: Session) -> None:
    """显示当前生命周期状态 + 状态机图 + 允许的转换。"""
    current = _get_current_lifecycle(session)

    # 当前状态
    state_info = LIFECYCLE_STATES.get(current)
    if state_info:
        print(f"当前生命周期: {current}")
        print(f"  → {state_info['desc']}")
    else:
        print(f"当前生命周期: {current}（非标准状态）")

    # 状态机图
    print("")
    print("生命周期状态机:")
    print("  OP_READY ──init──→ INITIALIZED ──secure──→ SECURED ──lock──→ CARD_LOCKED ──terminate──→ TERMINATED")
    print("     ↑                  │                    │↑                     │")
    print("     └──────────────────┘           unlock──┘└──unlock─────────────┘")

    # 允许的转换
    allowed_next = state_info.get("allowed_next", []) if state_info else []
    if allowed_next:
        print("")
        print(f"从 {current} 可执行的转换:")
        for next_state in allowed_next:
            # 反查 action
            for act, target in LIFECYCLE_ACTION_MAP.items():
                if target == next_state:
                    print(f"  card lifecycle {act}  →  {next_state}")
    elif current == "TERMINATED":
        print("")
        print("卡片已终止，无可执行操作。")
    else:
        print("")
        print("当前状态无已知允许的转换。")


# ── card applet-state ──

def cmd_card_applet_state(args: str, session: Session) -> None:
    """card applet-state — Applet 级状态控制（v0.5.0 增强）。

    通过 SET STATUS APDU 直接设置 Applet 级状态。
    支持 selectable/locked/blocked 三种状态。
    无状态参数时从 card list 查询当前状态。
    """
    if not args:
        print("用法: card applet-state <AID> [selectable|locked|blocked]")
        return

    parts = args.strip().split()
    aid = _resolve_aid(parts[0], session)

    if len(parts) == 1:
        # 查询当前状态
        _query_applet_state(aid, session)
        return

    state_name = parts[1].lower()
    status_code = APPLET_STATES.get(state_name)
    if not status_code:
        print(f"未知 Applet 状态: {state_name}")
        print("可用状态: selectable, locked, blocked")
        return

    bridge = _get_bridge(session)
    if not bridge:
        return

    try:
        result = bridge.set_applet_status(aid, status_code)
        state_label = APPLET_STATE_NAMES.get(status_code, state_name)
        print(f"✅ Applet {aid} 状态已设置为: {state_label}")
        if result:
            print(result)
    except GPBridgeError as exc:
        print(f"❌ 设置 Applet 状态失败: {exc}")
        sw_tip(exc, "card applet-state")


def _query_applet_state(aid: str, session: Session) -> None:
    """从 card list 结果中查询 Applet 当前状态。"""
    bridge = _get_bridge(session)
    if not bridge:
        return

    try:
        list_result = bridge.list()
    except GPBridgeError as exc:
        print(f"查询失败: {exc}")
        return

    # 在 packages 中搜索目标 AID
    found = False
    for pkg in list_result.get("packages", []):
        for app in pkg.get("applets", []):
            if app["aid"] == aid:
                state = app.get("state") or "未知"
                print(f"Applet {aid}")
                print(f"  状态: {state}")
                # 状态说明
                state_desc = {
                    "SELECTABLE": "可选 — 正常状态，可被 SELECT",
                    "LOCKED": "锁定 — 不可 SELECT，需 card applet-state selectable 解锁",
                    "BLOCKED": "阻塞 — 完全禁用",
                    "PERSONALIZED": "已个人化",
                }.get(state, "")
                if state_desc:
                    print(f"  → {state_desc}")
                found = True
                break

    if not found:
        print(f"Applet {aid} 未在卡片上找到。")
        print("可用 card list 查看所有已安装 Applet。")


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

    # 别名
    registry.register_alias("gp-list", "card", "list")
    registry.register_alias("gp-info", "card", "info")
    registry.register_alias("gp-scp", "card", "info", "(别名 → card info) SCP 信息（已合并到 card info）")
    registry.register_alias("gp-status", "card", "info", "(别名 → card info) 卡片状态（已合并到 card info）")
    registry.register_alias("gp-init-card", "card", "lifecycle")
    registry.register_alias("gp-secure-card", "card", "lifecycle")
    registry.register_alias("gp-lock-card", "card", "lifecycle")
    registry.register_alias("gp-unlock-card", "card", "lifecycle")
    registry.register_alias("gp-terminate-card", "card", "lifecycle", "(别名 → card lifecycle terminate) ⚠️不可逆")
    registry.register_alias("gp-lock", "card", "applet-state", "(别名 → card applet-state) 锁定 Applet")
    registry.register_alias("gp-unlock", "card", "applet-state", "(别名 → card applet-state) 解锁 Applet")
    registry.register_alias("gp-store-data", "card", "store-data")
    registry.register_alias("gp-create-domain", "card", "create-domain")
    registry.register_alias("gp-rename-isd", "card", "rename-isd")
    registry.register_alias("gp-make-selectable", "card", "make-selectable")
    registry.register_alias("gp-set-default", "card", "make-selectable", "(别名 → card make-selectable) 设为默认 Applet")
    registry.register_alias("gp-set-cplc", "card", "set-cplc")
