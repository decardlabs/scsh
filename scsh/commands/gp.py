"""GP 管理命令：gp-list / gp-info / gp-aid / gp-scp / gp-status。"""

from __future__ import annotations

import functools
from typing import Any

from scsh.exceptions import GPBridgeError
from scsh.session import Session


def _get_bridge(session: Session) -> Any | None:
    """获取 GP bridge 对象或 None。"""
    bridge = getattr(session, "gp_bridge", None)
    if bridge is None:
        print("GP 桥接未就绪。需要安装 Java 和 GlobalPlatformPro (gp.jar)。")
        return None
    return bridge


def _resolve_aid(args: str, session: Session) -> str:
    """解析 AID 参数，支持别名展开。

    如果 args 是已注册的别名，返回对应的 AID；否则原样返回。
    """
    aliases = getattr(session, "aid_aliases", {})
    return aliases.get(args.strip(), args.strip())


def gp_command(func):
    """装饰器：自动获取 bridge 并捕获 GPBridgeError。

    被装饰的命令函数接收 (args, session, bridge) 而非 (args, session)。
    """
    @functools.wraps(func)
    def wrapper(args: str, session: Session) -> None:
        bridge = _get_bridge(session)
        if not bridge:
            return
        try:
            func(args, session, bridge)
        except GPBridgeError as exc:
            print(f"{func.__name__} 失败: {exc}")
    return wrapper


def cmd_gp_list(args: str, session: Session) -> None:
    """列出已安装的 ISD / Package / Applet。"""
    bridge = _get_bridge(session)
    if not bridge:
        return

    try:
        result = bridge.list()
    except GPBridgeError as exc:
        print(f"GP list 失败: {exc}")
        return

    for line in _format_gp_list(result):
        print(line)


def _format_gp_list(result: dict) -> list[str]:
    """格式化 gp-list 输出为行列表。"""
    lines: list[str] = []

    if result["isd"]:
        state_str = f" ({result['isd_state']})" if result.get("isd_state") else ""
        lines.append(f"ISD: {result['isd']}{state_str}")

    for pkg in result["packages"]:
        state_str = f" ({pkg['state']})" if pkg['state'] else ""
        lines.append(f"  PKG: {pkg['aid']}{state_str}")
        for app in pkg["applets"]:
            app_state = f" ({app['state']})" if app['state'] else ""
            lines.append(f"    Applet: {app['aid']}{app_state}")

    if not result["packages"] and not result.get("isd"):
        lines.append("(卡片未检测到或无已安装内容)")

    return lines


def cmd_gp_info(args: str, session: Session) -> None:
    """显示 GP 详细信息。"""
    bridge = _get_bridge(session)
    if not bridge:
        return

    try:
        result = bridge.info()
    except GPBridgeError as exc:
        print(f"GP info 失败: {exc}")
        return

    for line in _format_gp_info(result):
        print(line)


# ── CPLC 厂商名称映射 ──────────────────────────────────────

IC_FABRICATOR_NAMES = {
    "0081": "NXP (原 Philips)",
    "4470": "Infineon (原 Siemens)",
    "4250": "Samsung",
    "4950": "STMicroelectronics",
    "0440": "Renesas",
    "0040": "Toshiba",
    "2070": "Gemalto / Thales",
    "1090": "IBM",
    "4254": "SK Hynix",
    "0090": "G&D (Giesecke & Devrient)",
    "5010": "Goldpac",
    "FFFF": "测试芯片",
}

OS_ID_NAMES = {
    "0081": "JCOP (NXP)",
    "4470": "Infineon OS",
    "4250": "Samsung OS",
    "4950": "ST OS",
}

ICC_MANUFACTURER_NAMES = {
    "0081": "NXP",
    "4470": "Infineon",
    "4250": "Samsung",
    "4950": "STMicroelectronics",
    "2070": "Gemalto / Thales",
    "0090": "G&D",
    "5010": "Goldpac",
}


def _lookup_name(mapping: dict[str, str], val: str) -> str:
    """查找厂商名，找不到则原样返回。"""
    name = mapping.get(val)
    return f"{val} ({name})" if name else val


def _format_gp_info(result: dict) -> list[str]:
    """格式化 gp-info 输出为行列表。"""
    lines: list[str] = []

    # 基本信息
    lines.append("基本信息:")
    if result.get("jc_version"):
        lines.append(f"  JavaCard:    {result['jc_version']}")
    if result.get("gp_version"):
        lines.append(f"  GP 版本:     {result['gp_version']}")
    if result.get("scp"):
        lines.append(f"  SCP:         {result['scp']}")
    if result.get("key_version"):
        lines.append(f"  密钥版本:    {result['key_version']}")
    if result.get("security_level"):
        lines.append(f"  安全级别:    {result['security_level']}")

    # CPLC
    cplc = result.get("cplc", {})
    if cplc:
        lines.append("")
        lines.append("CPLC (卡片生产信息):")
        for key, cplc_label, lookup in [
            ("ICSerialNumber", "芯片序列号", None),
            ("ICFabricator", "制造商", IC_FABRICATOR_NAMES),
            ("ICType", "芯片型号", None),
            ("OperatingSystemID", "OS ID", OS_ID_NAMES),
            ("OperatingSystemReleaseDate", "OS 发布日期", None),
            ("OperatingSystemReleaseLevel", "OS 版本", None),
            ("ICFabricationDate", "生产日期", None),
            ("ICBatchIdentifier", "批次号", None),
            ("ICCManufacturer", "卡片制造商", ICC_MANUFACTURER_NAMES),
            ("ICPrePersonalizer", "预个人化方", None),
            ("ICPersonalizer", "个人化方", None),
        ]:
            val = cplc.get(key)
            if val:
                if lookup:
                    display = _lookup_name(lookup, val)
                else:
                    display = val
                lines.append(f"  {cplc_label}: {display}")

    # Card Data
    card_data = result.get("card_data", [])
    if card_data:
        lines.append("")
        lines.append("Card Data:")
        for entry in card_data:
            tag = entry["tag"]
            oid = entry["oid"]
            desc = entry.get("desc", "")
            if desc:
                lines.append(f"  Tag {tag}:  {oid}")
                lines.append(f"    → {desc}")
            else:
                lines.append(f"  Tag {tag}:  {oid}")

    # Card Capabilities
    caps = result.get("card_capabilities", [])
    if caps:
        lines.append("")
        lines.append("密钥能力:")
        for cap in caps:
            note = f" ({cap['note']})" if cap.get("note") else ""
            lines.append(
                f"  版本={cap['version']} ID={cap['id']} "
                f"类型={cap['type']} 长度={cap['length']}{note}"
            )

    return lines


def cmd_gp_aid(args: str, session: Session) -> None:
    """注册 AID 别名。"""
    if not args:
        print("用法: gp-aid <别名> <AID>")
        return

    parts = args.strip().split()
    if len(parts) < 2:
        print("用法: gp-aid <别名> <AID>")
        return

    alias = parts[0]
    aid = parts[1]

    if not hasattr(session, "aid_aliases"):
        session.aid_aliases = {}

    session.aid_aliases[alias] = aid
    print(f"AID 别名已注册: {alias} → {aid}")


def cmd_gp_scp(args: str, session: Session) -> None:
    """查看安全通道信息。"""
    bridge = _get_bridge(session)
    if not bridge:
        return

    try:
        result = bridge.info()
    except GPBridgeError as exc:
        print(f"SCP 查询失败: {exc}")
        return

    scp = result.get("scp", "未知")
    kv = result.get("key_version", "未知")
    sl = result.get("security_level", "未知")

    print(f"安全通道: SCP{scp}")
    print(f"密钥版本: {kv}")
    print(f"安全级别: {sl}")


def cmd_gp_status(args: str, session: Session) -> None:
    """查询卡片生命周期状态。"""
    bridge = _get_bridge(session)
    if not bridge:
        return

    # 生命周期的状态从 --list 的 ISD 行提取
    try:
        list_result = bridge.list()
        info_result = bridge.info()
    except GPBridgeError as exc:
        print(f"GP status 失败: {exc}")
        return

    lines = _format_gp_status(list_result, info_result)
    for line in lines:
        print(line)


def _format_gp_status(list_result: dict, info_result: dict) -> list[str]:
    """格式化 gp-status 输出为行列表。"""
    lines: list[str] = []

    # 卡片生命周期
    state = list_result.get("isd_state") or "未知"
    state_desc = {
        "OP_READY": "出厂就绪，可用默认密钥连接和管理",
        "INITIALIZED": "已初始化，LOAD/INSTALL 受限",
        "SECURED": "安全状态，需要密钥认证才能管理",
        "CARD_LOCKED": "卡片已锁定，仅可解锁",
        "TERMINATED": "已终止",
    }.get(state, "")
    lines.append(f"Card Status: {state}")
    if state_desc:
        lines.append(f"  → {state_desc}")

    # 详细版本信息
    lines.append("")
    lines.append("版本信息:")
    if info_result.get("jc_version"):
        lines.append(f"  JavaCard:    {info_result['jc_version']}")
    if info_result.get("gp_version"):
        lines.append(f"  GP 版本:     {info_result['gp_version']}")
    if info_result.get("scp"):
        lines.append(f"  SCP:         {info_result['scp']}")

    # ISD 信息
    if list_result.get("isd"):
        lines.append(f"  ISD AID:     {list_result['isd']}")

    return lines


# ── M4: GP 操作命令 ──────────────────────────────────────


def cmd_gp_delete(args: str, session: Session) -> None:
    """删除 Applet/Package。"""
    if not args:
        print("用法: gp-delete <AID>")
        return

    bridge = _get_bridge(session)
    if not bridge:
        return

    aid = _resolve_aid(args, session)
    try:
        bridge.delete(aid)
    except GPBridgeError as exc:
        print(f"删除失败: {exc}")
        return

    print("删除成功")


def cmd_gp_lock(args: str, session: Session) -> None:
    """锁定 Applet。"""
    if not args:
        print("用法: gp-lock <AID>")
        return

    bridge = _get_bridge(session)
    if not bridge:
        return

    aid = _resolve_aid(args, session)
    try:
        bridge.lock(aid)
    except GPBridgeError as exc:
        print(f"锁定失败: {exc}")
        return

    print("锁定成功")


def cmd_gp_unlock(args: str, session: Session) -> None:
    """解锁 Applet。"""
    if not args:
        print("用法: gp-unlock <AID>")
        return

    bridge = _get_bridge(session)
    if not bridge:
        return

    aid = _resolve_aid(args, session)
    try:
        bridge.unlock(aid)
    except GPBridgeError as exc:
        print(f"解锁失败: {exc}")
        return

    print("解锁成功")


@gp_command
def cmd_gp_create(args: str, session: Session, bridge: Any) -> None:
    """创建 Applet 实例。"""
    if not args:
        print("用法: gp-create <AID>")
        return

    aid = _resolve_aid(args, session)
    print(f"正在创建 Applet 实例: {aid} ...")
    bridge.execute_apdu(f"--create {aid}")
    print("创建成功")


def cmd_gp_key(args: str, session: Session) -> None:
    """设置 GP 密钥。"""
    if not args:
        print("用法: gp-key <十六进制密钥>")
        return

    bridge = _get_bridge(session)
    if not bridge:
        return

    key_hex = args.strip()
    print(f"GP 密钥已设置为: {key_hex[:8]}...{key_hex[-4:]}")
    session.gp_key = key_hex


# ── M4 补充：安装参数与高级操作 ──────────────────────────

def cmd_gp_install(args: str, session: Session) -> None:
    """安装 CAP 文件。

    Usage:
        gp-install <cap_path> [--params <hex>] [--privs <privs>] [--default] [-f]
    """
    if not args:
        print("用法: gp-install <CAP文件路径> [--params <hex>] [--privs <privs>] [--default] [-f]")
        return

    bridge = _get_bridge(session)
    if not bridge:
        return

    parts = args.strip().split()
    cap_path = parts[0]
    params = None
    privs = None
    make_default = False
    force = False

    i = 1
    while i < len(parts):
        if parts[i] == "--params" and i + 1 < len(parts):
            params = parts[i + 1]
            i += 2
        elif parts[i] == "--privs" and i + 1 < len(parts):
            privs = parts[i + 1]
            i += 2
        elif parts[i] == "--default":
            make_default = True
            i += 1
        elif parts[i] in ("-f", "--force"):
            force = True
            i += 1
        else:
            i += 1

    try:
        result = bridge.install(
            cap_path, params=params, privs=privs,
            make_default=make_default, force=force,
        )
    except GPBridgeError as exc:
        print(f"安装失败: {exc}")
        return

    print(f"安装成功。")


@gp_command
def cmd_gp_set_default(args: str, session: Session, bridge: Any) -> None:
    """设置指定 AID 为默认 Applet（NFC 刷卡自动选择）。"""
    if not args:
        print("用法: gp-set-default <AID>")
        return

    aid = _resolve_aid(args, session)
    bridge.make_default(aid)
    print(f"已设置默认 Applet: {aid}")


@gp_command
def cmd_gp_lock_card(args: str, session: Session, bridge: Any) -> None:
    """锁定卡片（SECURED → CARD_LOCKED）。"""
    bridge.lock_card()
    print("卡片已锁定。")


@gp_command
def cmd_gp_unlock_card(args: str, session: Session, bridge: Any) -> None:
    """解锁卡片（CARD_LOCKED → SECURED）。"""
    bridge.unlock_card()
    print("卡片已解锁。")


@gp_command
def cmd_gp_init_card(args: str, session: Session, bridge: Any) -> None:
    """初始化卡片（OP_READY → INITIALIZED）。"""
    bridge.initialize_card()
    print("卡片已初始化（OP_READY → INITIALIZED）。")


@gp_command
def cmd_gp_secure_card(args: str, session: Session, bridge: Any) -> None:
    """安全化卡片（INITIALIZED → SECURED）。"""
    bridge.secure_card()
    print("卡片已安全化（INITIALIZED → SECURED）。")


def cmd_gp_put_key(args: str, session: Session) -> None:
    """更新 SCP 密钥。

    Usage:
        gp-put-key --master <hex>           # 主密钥派生三把密钥
        gp-put-key --enc <hex> --mac <hex> --dek <hex>
        gp-put-key --master <hex> --new-keyver <ver> --kdf <template>
    """
    if not args:
        print("用法: gp-put-key --master <hex> | --enc <hex> --mac <hex> --dek <hex>")
        print("选项: --key-ver <ver> --new-keyver <ver> --kdf <template>")
        return

    bridge = _get_bridge(session)
    if not bridge:
        return

    parts = args.strip().split()
    master_key = None
    key_enc = None
    key_mac = None
    key_dek = None
    key_ver = None
    new_key_ver = None
    kdf = None

    i = 0
    while i < len(parts):
        if parts[i] == "--master" and i + 1 < len(parts):
            master_key = parts[i + 1]
            i += 2
        elif parts[i] == "--enc" and i + 1 < len(parts):
            key_enc = parts[i + 1]
            i += 2
        elif parts[i] == "--mac" and i + 1 < len(parts):
            key_mac = parts[i + 1]
            i += 2
        elif parts[i] == "--dek" and i + 1 < len(parts):
            key_dek = parts[i + 1]
            i += 2
        elif parts[i] == "--key-ver" and i + 1 < len(parts):
            key_ver = parts[i + 1]
            i += 2
        elif parts[i] == "--new-keyver" and i + 1 < len(parts):
            new_key_ver = parts[i + 1]
            i += 2
        elif parts[i] == "--kdf" and i + 1 < len(parts):
            kdf = parts[i + 1]
            i += 2
        else:
            i += 1

    try:
        bridge.put_key(
            master_key=master_key, key_enc=key_enc, key_mac=key_mac,
            key_dek=key_dek, key_ver=key_ver, new_key_ver=new_key_ver,
            kdf=kdf,
        )
    except GPBridgeError as exc:
        print(f"更新密钥失败: {exc}")
        return

    print("SCP 密钥已更新。")


@gp_command
def cmd_gp_delete_key(args: str, session: Session, bridge: Any) -> None:
    """删除指定版本的密钥。"""
    if not args:
        print("用法: gp-delete-key <版本号>")
        return

    bridge.delete_key(args.strip())
    print(f"密钥版本 {args.strip()} 已删除。")


@gp_command
def cmd_gp_store_data(args: str, session: Session, bridge: Any) -> None:
    """写入个人化数据（GP STORE DATA）。"""
    if not args:
        print("用法: gp-store-data <十六进制数据>")
        return

    bridge.store_data(args.strip())
    print("个人化数据已写入。")


@gp_command
def cmd_gp_create_domain(args: str, session: Session, bridge: Any) -> None:
    """创建补充安全域（SSD）。"""
    if not args:
        print("用法: gp-create-domain <AID>")
        return

    aid = _resolve_aid(args, session)
    bridge.create_domain(aid)
    print(f"补充安全域已创建: {aid}")


@gp_command
def cmd_gp_rename_isd(args: str, session: Session, bridge: Any) -> None:
    """重命名 ISD AID。"""
    if not args:
        print("用法: gp-rename-isd <新AID>")
        return

    new_aid = _resolve_aid(args, session)
    bridge.rename_isd(new_aid)
    print(f"ISD 已重命名为: {new_aid}")


@gp_command
def cmd_gp_load(args: str, session: Session, bridge: Any) -> None:
    """仅加载 CAP 文件到卡片（不 INSTALL，分步操作）。"""
    if not args:
        print("用法: gp-load <CAP文件路径>")
        return

    bridge.load(args.strip())
    print("CAP 文件已加载。")


@gp_command
def cmd_gp_uninstall(args: str, session: Session, bridge: Any) -> None:
    """卸载 CAP 文件。"""
    if not args:
        print("用法: gp-uninstall <CAP文件路径或AID>")
        return

    target = _resolve_aid(args, session)
    bridge.uninstall(target)
    print(f"已卸载: {target}")


def cmd_gp_set_cplc(args: str, session: Session) -> None:
    """设置 CPLC 个人化日期。

    Usage:
        gp-set-cplc --pre-perso <hex> --perso <hex>
        gp-set-cplc --today
    """
    bridge = _get_bridge(session)
    if not bridge:
        return

    parts = args.strip().split() if args else []
    pre_perso = None
    perso = None
    today = False

    i = 0
    while i < len(parts):
        if parts[i] == "--pre-perso" and i + 1 < len(parts):
            pre_perso = parts[i + 1]
            i += 2
        elif parts[i] == "--perso" and i + 1 < len(parts):
            perso = parts[i + 1]
            i += 2
        elif parts[i] == "--today":
            today = True
            i += 1
        else:
            i += 1

    if not pre_perso and not perso and not today:
        print("用法: gp-set-cplc --pre-perso <hex> --perso <hex> [--today]")
        return

    try:
        bridge.set_cplc(pre_perso=pre_perso, perso=perso, today=today)
    except GPBridgeError as exc:
        print(f"设置 CPLC 失败: {exc}")
        return

    print("CPLC 数据已更新。")


@gp_command
def cmd_gp_secure_apdu(args: str, session: Session, bridge: Any) -> None:
    """通过 SCP 安全通道发送 APDU。"""
    if not args:
        print("用法: gp-secure-apdu <APDU十六进制>")
        return

    result = bridge.send_secure_apdu(args.strip())
    print(result)


@gp_command
def cmd_gp_mode(args: str, session: Session, bridge: Any) -> None:
    """设置 SCP 安全通道模式（CLR/MAC/ENC/RMAC）。"""
    if not args:
        print("用法: gp-mode <模式>")
        print("模式: CLR, MAC, ENC, RMAC, 或组合如 MAC+ENC")
        return

    bridge.set_mode(args.strip())
    print(f"SCP 模式已设置为: {args.strip()}")
