"""GP 管理命令：gp-list / gp-info / gp-aid / gp-scp / gp-status。"""

from __future__ import annotations

from typing import Any

from scsh.exceptions import GPBridgeError


def _get_bridge(transport: Any) -> Any | None:
    """获取 GP bridge 对象或 None。"""
    bridge = getattr(transport, "gp_bridge", None)
    if bridge is None:
        print("GP 桥接未就绪。需要安装 Java 和 GlobalPlatformPro (gp.jar)。")
        return None
    return bridge


def cmd_gp_list(args: str, transport: Any) -> None:
    """列出已安装的 ISD / Package / Applet。"""
    bridge = _get_bridge(transport)
    if not bridge:
        return

    try:
        result = bridge.list()
    except GPBridgeError as exc:
        print(f"GP list 失败: {exc}")
        return

    print("已安装内容:")
    if result["isd"]:
        print(f"  ISD: {result['isd']}")

    for pkg in result["packages"]:
        state_str = f" ({pkg['state']})" if pkg['state'] else ""
        print(f"  ├─ PKG: {pkg['aid']}{state_str}")
        for app in pkg["applets"]:
            app_state = f" ({app['state']})" if app['state'] else ""
            print(f"  │  └─ Applet: {app['aid']}{app_state}")

    if not result["packages"]:
        print("  (无已安装内容)")


def cmd_gp_info(args: str, transport: Any) -> None:
    """显示 GP 详细信息。"""
    bridge = _get_bridge(transport)
    if not bridge:
        return

    try:
        result = bridge.info()
    except GPBridgeError as exc:
        print(f"GP info 失败: {exc}")
        return

    for key, label in [
        ("gp_version", "GP 版本"),
        ("scp", "SCP"),
        ("key_version", "密钥版本"),
        ("security_level", "安全级别"),
    ]:
        val = result.get(key)
        if val:
            print(f"  {label}: {val}")


def cmd_gp_aid(args: str, transport: Any) -> None:
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

    if not hasattr(transport, "_aid_aliases"):
        transport._aid_aliases = {}

    transport._aid_aliases[alias] = aid
    print(f"AID 别名已注册: {alias} → {aid}")


def cmd_gp_scp(args: str, transport: Any) -> None:
    """查看安全通道信息。"""
    bridge = _get_bridge(transport)
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


def cmd_gp_status(args: str, transport: Any) -> None:
    """查询卡片生命周期状态。"""
    bridge = _get_bridge(transport)
    if not bridge:
        return

    try:
        result = bridge.info()
    except GPBridgeError as exc:
        print(f"GP status 失败: {exc}")
        return

    print(f"GP 版本:     {result.get('gp_version', '未知')}")
    print(f"SCP:         {result.get('scp', '未知')}")
    print(f"安全级别:    {result.get('security_level', '未知')}")


# ── M4: GP 操作命令 ──────────────────────────────────────


def cmd_gp_install(args: str, transport: Any) -> None:
    """安装 CAP 文件。"""
    if not args:
        print("用法: gp-install <CAP文件路径>")
        return

    bridge = _get_bridge(transport)
    if not bridge:
        return

    path = args.strip()
    try:
        result = bridge.install(path)
    except GPBridgeError as exc:
        print(f"安装失败: {exc}")
        return

    print(f"安装成功: {result}")


def cmd_gp_delete(args: str, transport: Any) -> None:
    """删除 Applet/Package。"""
    if not args:
        print("用法: gp-delete <AID>")
        return

    bridge = _get_bridge(transport)
    if not bridge:
        return

    aid = args.strip()
    try:
        result = bridge.delete(aid)
    except GPBridgeError as exc:
        print(f"删除失败: {exc}")
        return

    print(f"删除成功: {result}")


def cmd_gp_lock(args: str, transport: Any) -> None:
    """锁定 Applet。"""
    if not args:
        print("用法: gp-lock <AID>")
        return

    bridge = _get_bridge(transport)
    if not bridge:
        return

    aid = args.strip()
    try:
        result = bridge.lock(aid)
    except GPBridgeError as exc:
        print(f"锁定失败: {exc}")
        return

    print(f"锁定成功: {result}")


def cmd_gp_unlock(args: str, transport: Any) -> None:
    """解锁 Applet。"""
    if not args:
        print("用法: gp-unlock <AID>")
        return

    bridge = _get_bridge(transport)
    if not bridge:
        return

    aid = args.strip()
    try:
        result = bridge.unlock(aid)
    except GPBridgeError as exc:
        print(f"解锁失败: {exc}")
        return

    print(f"解锁成功: {result}")


def cmd_gp_create(args: str, transport: Any) -> None:
    """创建 Applet 实例。"""
    if not args:
        print("用法: gp-create <AID>")
        return

    bridge = _get_bridge(transport)
    if not bridge:
        return

    aid = args.strip()
    print(f"正在创建 Applet 实例: {aid} ...")

    try:
        result = bridge.execute_apdu(f"--create {aid}")
    except GPBridgeError as exc:
        print(f"创建失败: {exc}")
        return

    print(f"创建成功: {result}")


def cmd_gp_key(args: str, transport: Any) -> None:
    """设置 GP 密钥。"""
    if not args:
        print("用法: gp-key <十六进制密钥>")
        return

    bridge = _get_bridge(transport)
    if not bridge:
        return

    key_hex = args.strip()
    print(f"GP 密钥已设置为: {key_hex[:8]}...{key_hex[-4:]}")
    transport._gp_key = key_hex


# ── M4 补充：安装参数与高级操作 ──────────────────────────

def cmd_gp_install(args: str, transport: Any) -> None:
    """安装 CAP 文件。

    Usage:
        gp-install <cap_path> [--params <hex>] [--privs <privs>] [--default] [-f]
    """
    if not args:
        print("用法: gp-install <CAP文件路径> [--params <hex>] [--privs <privs>] [--default] [-f]")
        return

    bridge = _get_bridge(transport)
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


def cmd_gp_set_default(args: str, transport: Any) -> None:
    """设置指定 AID 为默认 Applet（NFC 刷卡自动选择）。"""
    if not args:
        print("用法: gp-set-default <AID>")
        return

    bridge = _get_bridge(transport)
    if not bridge:
        return

    aid = args.strip()
    try:
        bridge.make_default(aid)
    except GPBridgeError as exc:
        print(f"设置默认 Applet 失败: {exc}")
        return

    print(f"已设置默认 Applet: {aid}")


def cmd_gp_lock_card(args: str, transport: Any) -> None:
    """锁定卡片（SECURED → CARD_LOCKED）。"""
    bridge = _get_bridge(transport)
    if not bridge:
        return

    try:
        bridge.lock_card()
    except GPBridgeError as exc:
        print(f"锁定卡片失败: {exc}")
        return

    print("卡片已锁定。")


def cmd_gp_unlock_card(args: str, transport: Any) -> None:
    """解锁卡片（CARD_LOCKED → SECURED）。"""
    bridge = _get_bridge(transport)
    if not bridge:
        return

    try:
        bridge.unlock_card()
    except GPBridgeError as exc:
        print(f"解锁卡片失败: {exc}")
        return

    print("卡片已解锁。")


def cmd_gp_init_card(args: str, transport: Any) -> None:
    """初始化卡片（OP_READY → INITIALIZED）。"""
    bridge = _get_bridge(transport)
    if not bridge:
        return

    try:
        bridge.initialize_card()
    except GPBridgeError as exc:
        print(f"初始化卡片失败: {exc}")
        return

    print("卡片已初始化（OP_READY → INITIALIZED）。")


def cmd_gp_secure_card(args: str, transport: Any) -> None:
    """安全化卡片（INITIALIZED → SECURED）。"""
    bridge = _get_bridge(transport)
    if not bridge:
        return

    try:
        bridge.secure_card()
    except GPBridgeError as exc:
        print(f"安全化卡片失败: {exc}")
        return

    print("卡片已安全化（INITIALIZED → SECURED）。")


def cmd_gp_put_key(args: str, transport: Any) -> None:
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

    bridge = _get_bridge(transport)
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


def cmd_gp_delete_key(args: str, transport: Any) -> None:
    """删除指定版本的密钥。"""
    if not args:
        print("用法: gp-delete-key <版本号>")
        return

    bridge = _get_bridge(transport)
    if not bridge:
        return

    ver = args.strip()
    try:
        bridge.delete_key(ver)
    except GPBridgeError as exc:
        print(f"删除密钥失败: {exc}")
        return

    print(f"密钥版本 {ver} 已删除。")


def cmd_gp_store_data(args: str, transport: Any) -> None:
    """写入个人化数据（GP STORE DATA）。"""
    if not args:
        print("用法: gp-store-data <十六进制数据>")
        return

    bridge = _get_bridge(transport)
    if not bridge:
        return

    data_hex = args.strip()
    try:
        bridge.store_data(data_hex)
    except GPBridgeError as exc:
        print(f"写入数据失败: {exc}")
        return

    print("个人化数据已写入。")


def cmd_gp_create_domain(args: str, transport: Any) -> None:
    """创建补充安全域（SSD）。"""
    if not args:
        print("用法: gp-create-domain <AID>")
        return

    bridge = _get_bridge(transport)
    if not bridge:
        return

    aid = args.strip()
    try:
        bridge.create_domain(aid)
    except GPBridgeError as exc:
        print(f"创建安全域失败: {exc}")
        return

    print(f"补充安全域已创建: {aid}")


def cmd_gp_rename_isd(args: str, transport: Any) -> None:
    """重命名 ISD AID。"""
    if not args:
        print("用法: gp-rename-isd <新AID>")
        return

    bridge = _get_bridge(transport)
    if not bridge:
        return

    new_aid = args.strip()
    try:
        bridge.rename_isd(new_aid)
    except GPBridgeError as exc:
        print(f"重命名 ISD 失败: {exc}")
        return

    print(f"ISD 已重命名为: {new_aid}")


def cmd_gp_load(args: str, transport: Any) -> None:
    """仅加载 CAP 文件到卡片（不 INSTALL，分步操作）。"""
    if not args:
        print("用法: gp-load <CAP文件路径>")
        return

    bridge = _get_bridge(transport)
    if not bridge:
        return

    cap_path = args.strip()
    try:
        bridge.load(cap_path)
    except GPBridgeError as exc:
        print(f"加载失败: {exc}")
        return

    print(f"CAP 文件已加载: {cap_path}")


def cmd_gp_uninstall(args: str, transport: Any) -> None:
    """卸载 CAP 文件。"""
    if not args:
        print("用法: gp-uninstall <CAP文件路径或AID>")
        return

    bridge = _get_bridge(transport)
    if not bridge:
        return

    target = args.strip()
    try:
        bridge.uninstall(target)
    except GPBridgeError as exc:
        print(f"卸载失败: {exc}")
        return

    print(f"已卸载: {target}")


def cmd_gp_set_cplc(args: str, transport: Any) -> None:
    """设置 CPLC 个人化日期。

    Usage:
        gp-set-cplc --pre-perso <hex> --perso <hex>
        gp-set-cplc --today
    """
    bridge = _get_bridge(transport)
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


def cmd_gp_secure_apdu(args: str, transport: Any) -> None:
    """通过 SCP 安全通道发送 APDU。"""
    if not args:
        print("用法: gp-secure-apdu <APDU十六进制>")
        return

    bridge = _get_bridge(transport)
    if not bridge:
        return

    apdu_hex = args.strip()
    try:
        result = bridge.send_secure_apdu(apdu_hex)
    except GPBridgeError as exc:
        print(f"安全 APDU 发送失败: {exc}")
        return

    print(result)


def cmd_gp_mode(args: str, transport: Any) -> None:
    """设置 SCP 安全通道模式（CLR/MAC/ENC/RMAC）。"""
    if not args:
        print("用法: gp-mode <模式>")
        print("模式: CLR, MAC, ENC, RMAC, 或组合如 MAC+ENC")
        return

    bridge = _get_bridge(transport)
    if not bridge:
        return

    mode = args.strip()
    try:
        bridge.set_mode(mode)
    except GPBridgeError as exc:
        print(f"设置模式失败: {exc}")
        return

    print(f"SCP 模式已设置为: {mode}")
