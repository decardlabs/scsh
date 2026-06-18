"""config 子系统命令注册。

config — 配置管理子系统
  show         显示全部配置
  set          设置配置项
  get          查看单项
  save         持久化到 TOML
  load         从 TOML 加载
  key          设置本地连接密钥（BUG 修复：实际注入 bridge）
  aid          AID 别名
  mode         SCP 通道模式
"""

from __future__ import annotations

from typing import Any

from scsh.session import Session
from scsh.commands.help_data import CONFIG_HELP


def cmd_config_show(args: str, session: Session) -> None:
    """config show — 显示全部配置。"""
    config_mgr = getattr(session, "config_manager", None)

    # 显示 session.config（运行时）
    print("运行时配置 (session.config):")
    if session.config:
        for key, val in session.config.items():
            print(f"  {key}: {val}")
    else:
        print("  (空)")

    # 显示 config_manager 配置（持久化）
    if config_mgr:
        print("")
        print("持久化配置 (config.toml):")
        merged = config_mgr.all()
        if merged:
            _print_config_dict(merged)
        else:
            print("  (空)")
    else:
        print("  (未初始化 ConfigManager)")


def _print_config_dict(data: dict, indent: int = 0) -> None:
    """递归打印配置字典。"""
    prefix = "  " * (indent + 1)
    for key, value in data.items():
        if isinstance(value, dict):
            print(f"{prefix}{key}:")
            _print_config_dict(value, indent + 1)
        else:
            # 密钥脱敏
            if key == "key" and isinstance(value, str) and len(value) >= 8:
                display = f"{value[:8]}...{value[-4:]}"
            else:
                display = value
            print(f"{prefix}{key}: {display}")


def cmd_config_set(args: str, session: Session) -> None:
    """config set — 设置配置项。"""
    if not args:
        print("用法: config set <key> <value>")
        print("示例: config set connection.key 404142434445464748494A4B4C4D4E4F")
        return

    parts = args.strip().split()
    if len(parts) < 2:
        print("用法: config set <key> <value>")
        return

    key = parts[0]
    value = parts[1]

    # 写入 session.config
    session.config[key] = value

    # 写入 config_manager（如果存在）
    config_mgr = getattr(session, "config_manager", None)
    if config_mgr:
        config_mgr.set(key, value)

        # 特殊处理：connection.key → 同时注入 bridge
        if key == "connection.key" or key == "key":
            bridge = getattr(session, "gp_bridge", None)
            if bridge and hasattr(bridge, "set_key"):
                bridge.set_key(value)

        # 特殊处理：connection.scp
        if key == "connection.scp" or key == "scp":
            bridge = getattr(session, "gp_bridge", None)
            if bridge and hasattr(bridge, "set_scp_type"):
                bridge.set_scp_type(value)

        # 特殊处理：connection.mode
        if key == "connection.mode" or key == "mode":
            bridge = getattr(session, "gp_bridge", None)
            if bridge and hasattr(bridge, "set_mode_param"):
                bridge.set_mode_param(value)

    print(f"已设置 {key} = {value}")


def cmd_config_get(args: str, session: Session) -> None:
    """config get — 查看单项配置。"""
    if not args:
        print("用法: config get <key>")
        return

    key = args.strip()
    config_mgr = getattr(session, "config_manager", None)

    # 先查 config_manager，再查 session.config
    if config_mgr:
        value = config_mgr.get(key)
        if value is not None:
            # 密钥脱敏
            if key.endswith("key") and isinstance(value, str) and len(value) >= 8:
                display = f"{value[:8]}...{value[-4:]}"
            else:
                display = value
            print(f"{key}: {display}")
            return

    value = session.config.get(key, "未设置")
    print(f"{key}: {value}")


def cmd_config_save(args: str, session: Session) -> None:
    """config save — 持久化到 TOML 文件。"""
    config_mgr = getattr(session, "config_manager", None)
    if not config_mgr:
        print("ConfigManager 未初始化，无法保存。")
        return

    # 同步 session.config 到 config_manager
    _sync_session_to_config(session)

    config_mgr.save_global()
    print("配置已保存到 ~/.scsh/config.toml")


def cmd_config_load(args: str, session: Session) -> None:
    """config load — 从 TOML 加载配置。"""
    config_mgr = getattr(session, "config_manager", None)
    if not config_mgr:
        print("ConfigManager 未初始化。")
        return

    if args:
        # 加载指定路径
        path = args.strip()
        print(f"从 {path} 加载配置...")
        config_mgr.load_project(path)
    else:
        # 加载全局 + 项目
        print("加载全局 + 项目配置...")
        config_mgr.load_all()

    # 同步 config_manager 到 session 和 bridge
    _sync_config_to_session(session)
    print("配置已加载。")


def cmd_config_key(args: str, session: Session) -> None:
    """config key — 设置本地连接密钥（BUG 修复版）。

    v0.4.0 修复：密钥不仅存入 session，还实际注入 GPJarBridge._run()。
    """
    if not args:
        print("用法: config key <十六进制密钥>")
        return

    key_hex = args.strip()
    session.gp_key = key_hex

    # BUG 修复：注入到 bridge
    bridge = getattr(session, "gp_bridge", None)
    if bridge and hasattr(bridge, "set_key"):
        bridge.set_key(key_hex)

    # 同时写入 config_manager
    config_mgr = getattr(session, "config_manager", None)
    if config_mgr:
        config_mgr.set("connection.key", key_hex)

    print(f"GP 密钥已设置: {key_hex[:8]}...{key_hex[-4:]}")
    print("密钥已注入所有后续 GP 命令。")


def cmd_config_aid(args: str, session: Session) -> None:
    """config aid — 注册 AID 别名。"""
    if not args:
        print("用法: config aid <别名> <AID>")
        return

    parts = args.strip().split()
    if len(parts) < 2:
        print("用法: config aid <别名> <AID>")
        return

    alias = parts[0]
    aid = parts[1]

    session.aid_aliases[alias] = aid

    # 同时写入 config_manager
    config_mgr = getattr(session, "config_manager", None)
    if config_mgr:
        config_mgr.set(f"aliases.{alias}", aid)

    print(f"AID 别名已注册: {alias} → {aid}")


def cmd_config_mode(args: str, session: Session) -> None:
    """config mode — 设置 SCP 安全通道模式。"""
    if not args:
        print("用法: config mode <模式>")
        print("模式: CLR, MAC, ENC, RMAC, 或组合如 MAC+ENC")
        return

    mode = args.strip()

    # 写入 config_manager
    config_mgr = getattr(session, "config_manager", None)
    if config_mgr:
        config_mgr.set("connection.mode", mode)

    # 注入到 bridge
    bridge = getattr(session, "gp_bridge", None)
    if bridge and hasattr(bridge, "set_mode_param"):
        bridge.set_mode_param(mode)

    print(f"SCP 模式已设置: {mode}")


# ── 内部同步函数 ──

def _sync_session_to_config(session: Session) -> None:
    """将 session 中的运行时配置同步到 config_manager。"""
    config_mgr = getattr(session, "config_manager", None)
    if not config_mgr:
        return

    # gp_key → connection.key
    if session.gp_key:
        config_mgr.set("connection.key", session.gp_key)

    # aid_aliases → aliases.*
    for alias, aid in session.aid_aliases.items():
        config_mgr.set(f"aliases.{alias}", aid)

    # session.config → 各项
    for key, value in session.config.items():
        config_mgr.set(key, value)


def _sync_config_to_session(session: Session) -> None:
    """将 config_manager 中的配置同步到 session 和 bridge。"""
    config_mgr = getattr(session, "config_manager", None)
    if not config_mgr:
        return

    # connection.key → session.gp_key + bridge
    key = config_mgr.get("connection.key")
    if key:
        session.gp_key = key
        bridge = getattr(session, "gp_bridge", None)
        if bridge and hasattr(bridge, "set_key"):
            bridge.set_key(key)

    # aliases → session.aid_aliases
    aliases = config_mgr.get("aliases", {})
    if isinstance(aliases, dict):
        for alias, aid in aliases.items():
            session.aid_aliases[alias] = aid

    # connection.scp → bridge
    scp = config_mgr.get("connection.scp")
    if scp:
        bridge = getattr(session, "gp_bridge", None)
        if bridge and hasattr(bridge, "set_scp_type"):
            bridge.set_scp_type(scp)

    # connection.mode → bridge
    mode = config_mgr.get("connection.mode")
    if mode:
        bridge = getattr(session, "gp_bridge", None)
        if bridge and hasattr(bridge, "set_mode_param"):
            bridge.set_mode_param(mode)


def register_config_subsystem(registry: Any) -> None:
    """注册 config 子系统及其子命令和别名。"""
    registry.register_subsystem("config", "配置管理子系统")

    registry.register_subcommand(
        "config", "show", "显示全部配置", cmd_config_show, CONFIG_HELP["show"]
    )
    registry.register_subcommand(
        "config", "set", "设置配置项", cmd_config_set, CONFIG_HELP["set"]
    )
    registry.register_subcommand(
        "config", "get", "查看单项配置", cmd_config_get, CONFIG_HELP["get"]
    )
    registry.register_subcommand(
        "config", "save", "持久化到 TOML 文件", cmd_config_save, CONFIG_HELP["save"]
    )
    registry.register_subcommand(
        "config", "load", "从 TOML 加载配置", cmd_config_load, CONFIG_HELP["load"]
    )
    registry.register_subcommand(
        "config", "key", "设置本地连接密钥（注入 bridge）", cmd_config_key, CONFIG_HELP["key"]
    )
    registry.register_subcommand(
        "config", "aid", "注册 AID 别名", cmd_config_aid, CONFIG_HELP["aid"]
    )
    registry.register_subcommand(
        "config", "mode", "设置 SCP 安全通道模式", cmd_config_mode, CONFIG_HELP["mode"]
    )

    # 别名
    registry.register_alias("gp-key", "config", "key")
    registry.register_alias("gp-aid", "config", "aid")
    registry.register_alias("gp-mode", "config", "mode")

    # v0.7.0: 移除旧 config 扁平命令注册
    # config 输入会先匹配子系统路由，旧扁平注册永远不生效
