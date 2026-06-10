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
