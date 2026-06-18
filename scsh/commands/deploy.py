"""deploy 子系统命令注册。

deploy — 部署管理子系统
  install      安装 CAP 文件（支持 --step/--force/--load-only/--install-only/--params/--privs/--default）
  delete       删除 Package/Applet
  load         仅加载 CAP（不 INSTALL）
  provision    按 Profile 蓝图自动编排
  plan         显示 Profile 预期变更

v0.6.0: install 增强 + Profile 蓝图 + deploy plan/provision。
"""

from __future__ import annotations

import os
from typing import Any

from scsh.session import Session
from scsh.exceptions import GPBridgeError
from scsh.bridge.gp_jar import GPJarBridge
from scsh.commands.help_data import DEPLOY_HELP
from scsh.commands._sw_guidance import sw_tip


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


# ── deploy install（v0.6.0 增强）───────────────────────────


def _parse_install_args(args: str) -> dict[str, Any]:
    """解析 deploy install 参数。

    支持选项：
    --applet <AID>     指定 applet AID
    --params <hex>     安装参数
    --privs <str>      安装权限
    --default          设为默认 Applet
    --force            强制重装（先删除再装）
    --step             分步模式（每步暂停确认）
    --load-only        仅 LOAD 不 INSTALL
    --install-only     仅 INSTALL（前提：包已加载）

    Returns:
        dict with cap_path and all parsed options.
    """
    parts = args.strip().split()
    if not parts:
        return {}

    result: dict[str, Any] = {
        "cap_path": parts[0],
        "applet_aid": None,
        "params": None,
        "privs": None,
        "default": False,
        "force": False,
        "step": False,
        "load_only": False,
        "install_only": False,
    }

    i = 1
    while i < len(parts):
        if parts[i] == "--applet" and i + 1 < len(parts):
            result["applet_aid"] = parts[i + 1]
            i += 2
        elif parts[i] == "--params" and i + 1 < len(parts):
            result["params"] = parts[i + 1]
            i += 2
        elif parts[i] == "--privs" and i + 1 < len(parts):
            result["privs"] = parts[i + 1]
            i += 2
        elif parts[i] == "--default":
            result["default"] = True
            i += 1
        elif parts[i] in ("-f", "--force"):
            result["force"] = True
            i += 1
        elif parts[i] == "--step":
            result["step"] = True
            i += 1
        elif parts[i] == "--load-only":
            result["load_only"] = True
            i += 1
        elif parts[i] == "--install-only":
            result["install_only"] = True
            i += 1
        else:
            i += 1

    return result


def _find_profile_path(session: Session) -> str | None:
    """查找项目 scsh.toml 文件路径。"""
    # 先从 config_manager 的项目目录查找
    config_mgr = getattr(session, "config_manager", None)
    if config_mgr and hasattr(config_mgr, "_project_dir") and config_mgr._project_dir:
        path = os.path.join(config_mgr._project_dir, "scsh.toml")
        if os.path.isfile(path):
            return path

    # 再从当前工作目录查找
    cwd = os.getcwd()
    path = os.path.join(cwd, "scsh.toml")
    if os.path.isfile(path):
        return path

    return None


def cmd_deploy_install(args: str, session: Session) -> None:
    """deploy install — 安装 CAP 文件。

    v0.6.0 增强：支持 --step/--force/--load-only/--install-only/--params/--privs/--default/--applet。
    """
    parsed = _parse_install_args(args)
    if not parsed:
        print("用法: deploy install <CAP路径> [选项]")
        print("选项: --applet <AID> --params <hex> --privs <str> --default")
        print("      --force --step --load-only --install-only")
        return

    bridge = _get_bridge(session)
    if not bridge:
        return

    cap_path = parsed["cap_path"]

    # ── 路径验证 ──
    if not os.path.isfile(cap_path):
        # 尝试相对于项目目录解析
        config_mgr = getattr(session, "config_manager", None)
        if config_mgr and hasattr(config_mgr, "_project_dir") and config_mgr._project_dir:
            alt_path = os.path.join(config_mgr._project_dir, cap_path)
            if os.path.isfile(alt_path):
                cap_path = alt_path
            else:
                print(f"CAP 文件不存在: {cap_path}")
                return
        else:
            print(f"CAP 文件不存在: {cap_path}")
            return

    # ── --force 模式：先删除再装 ──
    if parsed["force"]:
        # 确定 AID（用于删除）
        target_aid = parsed.get("applet_aid")
        if not target_aid:
            # 尝试从 CAP 解析 AID
            try:
                pkg_aid, app_aid = GPJarBridge._parse_cap_aids(cap_path)
                target_aid = app_aid or pkg_aid
            except Exception:
                target_aid = None

        if target_aid:
            # 查找别名
            target_aid = _resolve_aid(target_aid, session)
            print(f"[force] 先删除已有: {target_aid}")
            try:
                bridge.delete(target_aid)
                print("[force] 删除成功，重新安装...")
            except GPBridgeError as exc:
                # 如果不存在，继续安装
                if "6A82" not in str(exc):
                    print(f"[force] 删除失败: {exc}")
                    sw_tip(exc, "deploy delete")
                    return
                print("[force] 包不存在，直接安装...")
        else:
            # 无法确定 AID，直接用 gp.jar -f（它内部处理 force）
            print("[force] 无法确定 AID，使用 gp.jar -f 模式...")

    # ── --load-only 模式 ──
    if parsed["load_only"]:
        print(f"[Step] LOAD: 加载 {cap_path} 到卡片...")
        if parsed["step"]:
            confirm = input("确认? [y/n]: ").strip().lower()
            if confirm not in ("y", "yes"):
                print("已取消。")
                return
        try:
            bridge.load(cap_path)
        except GPBridgeError as exc:
            print(f"加载失败: {exc}")
            sw_tip(exc, "deploy load")
            return
        print("CAP 文件已加载。")
        return

    # ── --install-only 模式 ──
    if parsed["install_only"]:
        applet_aid = parsed.get("applet_aid")
        if not applet_aid:
            print("--install-only 需要指定 --applet <AID>")
            return
        applet_aid = _resolve_aid(applet_aid, session)
        print(f"[Step] INSTALL: 安装 {applet_aid}...")
        if parsed["step"]:
            confirm = input("确认? [y/n]: ").strip().lower()
            if confirm not in ("y", "yes"):
                print("已取消。")
                return
        # install-only 使用 gp.jar --install 模式
        try:
            result = bridge.install(
                cap_path,
                params=parsed.get("params"),
                privs=parsed.get("privs"),
                make_default=parsed.get("default", False),
            )
        except GPBridgeError as exc:
            print(f"安装失败: {exc}")
            sw_tip(exc, "deploy install")
            return
        print("安装成功。")
        return

    # ── --step 分步模式 ──
    if parsed["step"]:
        print(f"[Step 1] LOAD: 将 {cap_path} 加载到卡片")
        confirm = input("确认? [y/n]: ").strip().lower()
        if confirm not in ("y", "yes"):
            print("已取消。")
            return

        try:
            bridge.load(cap_path)
        except GPBridgeError as exc:
            # 可能已加载，gp.jar 会处理
            if "6985" in str(exc):
                print("[Step 1] 包可能已加载，尝试继续...")
            else:
                print(f"加载失败: {exc}")
                sw_tip(exc, "deploy load")
                return

        print("[Step 1] LOAD 完成。")

        # 确定安装 AID
        applet_aid = parsed.get("applet_aid")
        if not applet_aid:
            try:
                _, app_aid = GPJarBridge._parse_cap_aids(cap_path)
                applet_aid = app_aid
            except Exception:
                print("无法从 CAP 解析 AID，请用 --applet 指定。")
                return

        applet_aid = _resolve_aid(applet_aid, session)

        print(f"[Step 2] INSTALL for install: 创建实例 {applet_aid}")
        confirm = input("确认? [y/n]: ").strip().lower()
        if confirm not in ("y", "yes"):
            print("已取消（包已加载但未安装实例）。")
            return

        try:
            result = bridge.install(
                cap_path,
                params=parsed.get("params"),
                privs=parsed.get("privs"),
                make_default=parsed.get("default", False),
            )
        except GPBridgeError as exc:
            print(f"安装失败: {exc}")
            sw_tip(exc, "deploy install")
            return

        print("[Step 2] INSTALL 完成。")
        print("[Done] 安装完成。")
        return

    # ── 标准模式：一次完成 ──
    try:
        result = bridge.install(
            cap_path,
            params=parsed.get("params"),
            privs=parsed.get("privs"),
            make_default=parsed.get("default", False),
            force=parsed.get("force", False),
        )
    except GPBridgeError as exc:
        print(f"安装失败: {exc}")
        sw_tip(exc, "deploy install")
        return

    print("安装成功。")


# ── deploy delete ────────────────────────────────────────


def cmd_deploy_delete(args: str, session: Session) -> None:
    """deploy delete — 删除 Package/Applet。"""
    if not args:
        print("用法: deploy delete <AID>")
        return

    bridge = _get_bridge(session)
    if not bridge:
        return

    aid = _resolve_aid(args, session)
    try:
        bridge.delete(aid)
    except GPBridgeError as exc:
        print(f"删除失败: {exc}")
        sw_tip(exc, "deploy delete")
        return

    print("删除成功。")


# ── deploy load ──────────────────────────────────────────


def cmd_deploy_load(args: str, session: Session) -> None:
    """deploy load — 仅加载 CAP（不 INSTALL）。"""
    if not args:
        print("用法: deploy load <CAP路径>")
        return

    bridge = _get_bridge(session)
    if not bridge:
        return

    try:
        bridge.load(args.strip())
    except GPBridgeError as exc:
        print(f"加载失败: {exc}")
        sw_tip(exc, "deploy load")
        return

    print("CAP 文件已加载。")


# ── deploy plan（v0.6.0 新增）─────────────────────────────


def cmd_deploy_plan(args: str, session: Session) -> None:
    """deploy plan — 显示 Profile vs 卡片差异。"""
    profile_path = _find_profile_path(session)
    if not profile_path:
        print("未找到 scsh.toml Profile 文件。")
        print("请在项目目录下创建 scsh.toml 定义部署蓝图。")
        print("示例: config load <path> 或手动创建 ~/.scsh/config.toml")
        return

    try:
        from scsh.profile import Profile, diff_profile_vs_card
        profile = Profile.from_toml(profile_path)
    except Exception as exc:
        print(f"Profile 加载失败: {exc}")
        return

    bridge = _get_bridge(session)
    if not bridge:
        return

    # 获取卡片当前状态
    try:
        card_state = bridge.list()
    except GPBridgeError as exc:
        print(f"无法获取卡片状态: {exc}")
        sw_tip(exc, "card list")
        return

    # 计算差异
    diffs = diff_profile_vs_card(profile, card_state)

    if not diffs:
        print("[Plan] 卡片状态与 Profile 完全一致，无需操作。")
        return

    print(f"[Plan] 基于 {profile_path}:")
    for diff in diffs:
        action = diff["action"]
        detail = diff["detail"]
        prefix = {"+": "  +", "=": "  =", "?": "  ?"}
        print(f"{prefix[action]} {detail}")

    # 统计
    to_install = sum(1 for d in diffs if d["action"] == "+")
    to_skip = sum(1 for d in diffs if d["action"] == "=")
    to_review = sum(1 for d in diffs if d["action"] == "?")
    print(f"\n总计: {to_install} 需安装, {to_skip} 已存在, {to_review} 待审核")


# ── deploy provision（v0.6.0 新增）────────────────────────


def cmd_deploy_provision(args: str, session: Session) -> None:
    """deploy provision — 按 Profile 蓝图自动编排部署。"""
    profile_path = _find_profile_path(session)
    if not profile_path:
        print("未找到 scsh.toml Profile 文件。")
        print("请在项目目录下创建 scsh.toml 定义部署蓝图。")
        return

    try:
        from scsh.profile import Profile, diff_profile_vs_card
        profile = Profile.from_toml(profile_path)
    except Exception as exc:
        print(f"Profile 加载失败: {exc}")
        return

    bridge = _get_bridge(session)
    if not bridge:
        return

    # 解析选项
    dry_run = "--dry-run" in args
    step_mode = "--step" in args

    # 获取卡片当前状态
    try:
        card_state = bridge.list()
    except GPBridgeError as exc:
        print(f"无法获取卡片状态: {exc}")
        sw_tip(exc, "card list")
        return

    # 计算差异
    diffs = diff_profile_vs_card(profile, card_state)

    # 过滤：只处理 + (需安装)
    to_install = [d for d in diffs if d["action"] == "+"]

    if not to_install:
        print("[Provision] 所有 Profile 中定义的包已存在，无需操作。")
        # 显示 ? 项（待审核）
        to_review = [d for d in diffs if d["action"] == "?"]
        if to_review:
            print("[Provision] 以下包不在 Profile 中:")
            for d in to_review:
                print(f"  ? {d['detail']}")
        return

    print(f"[Provision] 基于 {profile_path}:")
    print(f"  需安装: {len(to_install)} 个包")

    if dry_run:
        print("[Provision] --dry-run 模式，只显示计划:")
        for diff in to_install:
            pkg = diff["package"]
            cap_path = profile.resolve_cap_path(pkg)
            print(f"  + install {pkg.name} ({diff['aid']}) → {cap_path}")
            if pkg.params:
                print(f"    params: {pkg.params}")
            if pkg.privs:
                print(f"    privs: {pkg.privs}")
            if pkg.default:
                print(f"    default: true")
            if pkg.force:
                print(f"    force: true")
        return

    # ── 执行安装 ──
    for diff in to_install:
        pkg = diff["package"]
        cap_path = profile.resolve_cap_path(pkg)

        if step_mode:
            print(f"\n[Provision] 准备安装: {pkg.name} ({diff['aid']}) → {cap_path}")
            confirm = input("确认? [y/n/s(skip)]: ").strip().lower()
            if confirm in ("s", "skip"):
                print(f"[Provision] 跳过 {pkg.name}")
                continue
            if confirm not in ("y", "yes"):
                print("[Provision] 已取消。")
                return

        print(f"[Provision] 安装 {pkg.name}...")
        try:
            result = bridge.install(
                cap_path,
                params=pkg.params if pkg.params else None,
                privs=pkg.privs if pkg.privs else None,
                make_default=pkg.default,
                force=pkg.force,
            )
        except GPBridgeError as exc:
            print(f"[Provision] 安装 {pkg.name} 失败: {exc}")
            sw_tip(exc, "deploy install")
            if step_mode:
                confirm = input("继续下一个? [y/n]: ").strip().lower()
                if confirm not in ("y", "yes"):
                    print("[Provision] 已中止。")
                    return
            continue

        print(f"[Provision] {pkg.name} 安装成功。")

    print("[Provision] 完成。")


# ── 注册 ──────────────────────────────────────────────────


def register_deploy_subsystem(registry: Any) -> None:
    """注册 deploy 子系统及其子命令和别名。"""

    registry.register_subsystem("deploy", "部署管理子系统")

    # 子命令 — v0.6.0 install 使用新 handler，其余保持旧 handler
    registry.register_subcommand(
        "deploy", "install", "安装 CAP 文件（支持分步/强制模式）",
        cmd_deploy_install, DEPLOY_HELP["install"]
    )
    registry.register_subcommand(
        "deploy", "delete", "删除 Package/Applet",
        cmd_deploy_delete, DEPLOY_HELP["delete"]
    )
    registry.register_subcommand(
        "deploy", "load", "仅加载 CAP（不 INSTALL）",
        cmd_deploy_load, DEPLOY_HELP["load"]
    )
    registry.register_subcommand(
        "deploy", "provision", "按 Profile 蓝图自动编排",
        cmd_deploy_provision, DEPLOY_HELP["provision"]
    )
    registry.register_subcommand(
        "deploy", "plan", "显示 Profile 预期变更",
        cmd_deploy_plan, DEPLOY_HELP["plan"]
    )

    # 别名
    registry.register_alias("gp-install", "deploy", "install")
    registry.register_alias("gp-delete", "deploy", "delete")
    registry.register_alias("gp-load", "deploy", "load")
    registry.register_alias("gp-uninstall", "deploy", "delete", "(别名 → deploy delete) 卸载 CAP")
