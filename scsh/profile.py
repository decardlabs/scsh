"""Profile 蓝图系统。

解析 scsh.toml 文件，定义卡片目标状态。

Profile 不存储连接密钥——它引用 Config 中的配置名。
Config = 连接层（怎么连卡），Profile = 目标层（卡片应该是什么状态）。

v0.6.0 新增。
"""

from __future__ import annotations

import os
import tomllib
from typing import Any


class ProfileError(Exception):
    """Profile 解析或验证错误。"""


class PackageSpec:
    """单个 Package 的部署规格。"""

    def __init__(
        self,
        name: str,
        cap: str,
        aid: str | None = None,
        applet_aid: str | None = None,
        params: str = "",
        privs: str = "",
        default: bool = False,
        force: bool = False,
    ) -> None:
        self.name = name
        self.cap = cap
        self.aid = aid
        self.applet_aid = applet_aid
        self.params = params
        self.privs = privs
        self.default = default
        self.force = force

    def __repr__(self) -> str:
        return f"<PackageSpec '{self.name}' cap={self.cap}>"


class Profile:
    """卡片部署蓝图。

    从 scsh.toml 加载，定义：
    - card: 连接参数引用（isd_aid, use_config, target_lifecycle）
    - packages: 需要安装的 CAP 文件列表
    - aliases: AID 别名映射

    Profile 与 Config 的关系：
    - Profile 不存密钥，通过 use_config 引用 Config 配置名
    - Profile 定义"卡片应该是什么状态"，Config 定义"怎么连这张卡"
    """

    def __init__(self) -> None:
        self.isd_aid: str | None = None
        self.target_lifecycle: str | None = None
        self.use_config: str = "default"
        self.packages: list[PackageSpec] = []
        self.aliases: dict[str, str] = {}
        self._path: str | None = None

    @classmethod
    def from_toml(cls, path: str) -> Profile:
        """从 TOML 文件加载 Profile。

        Args:
            path: scsh.toml 文件路径。

        Raises:
            ProfileError: 文件不存在或格式错误。
        """
        if not os.path.isfile(path):
            raise ProfileError(f"Profile 文件不存在: {path}")

        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
        except tomllib.TOMLDecodeError as exc:
            raise ProfileError(f"Profile TOML 解析失败: {exc}")

        profile = cls()
        profile._path = path

        # ── [card] section ──
        card = data.get("card", {})
        profile.isd_aid = card.get("isd_aid")
        profile.target_lifecycle = card.get("target_lifecycle")
        profile.use_config = card.get("use_config", "default")

        # ── [packages.*] section ──
        packages = data.get("packages", {})
        for name, spec in packages.items():
            if not isinstance(spec, dict):
                continue
            pkg = PackageSpec(
                name=name,
                cap=spec.get("cap", ""),
                aid=spec.get("aid"),
                applet_aid=spec.get("applet_aid"),
                params=spec.get("params", ""),
                privs=spec.get("privs", ""),
                default=spec.get("default", False),
                force=spec.get("force", False),
            )
            if not pkg.cap:
                raise ProfileError(f"Package '{name}' 缺少 cap 字段")
            profile.packages.append(pkg)

        # ── [aliases] section ──
        aliases = data.get("aliases", {})
        if isinstance(aliases, dict):
            profile.aliases = aliases

        return profile

    def resolve_cap_path(self, pkg: PackageSpec, base_dir: str | None = None) -> str:
        """将相对 CAP 路径转为绝对路径。

        如果 cap_path 已经是绝对路径，直接返回。
        否则基于 Profile 文件所在目录或 base_dir 解析。
        """
        if os.path.isabs(pkg.cap):
            return pkg.cap

        # 基于项目目录（Profile 文件所在目录）
        base = base_dir or (os.path.dirname(self._path) if self._path else os.getcwd())
        resolved = os.path.join(base, pkg.cap)
        return resolved

    def __repr__(self) -> str:
        return f"<Profile {len(self.packages)} packages>"


def diff_profile_vs_card(profile: Profile, card_state: dict[str, Any]) -> list[dict[str, Any]]:
    """计算 Profile 与卡片当前状态的差异。

    Args:
        profile: 部署蓝图。
        card_state: bridge.list() 返回的卡片状态。

    Returns:
        差异列表，每个元素包含：
        - action: "+" (需安装), "=" (已存在), "?" (卡上有但Profile没有)
        - package: PackageSpec | None
        - aid: str
        - detail: str
    """
    diffs: list[dict[str, Any]] = []

    # 卡片上已有的 AID 集合（package + applet）
    existing_pkg_aids: set[str] = set()
    existing_app_aids: set[str] = set()
    for pkg in card_state.get("packages", []):
        existing_pkg_aids.add(pkg.get("aid", ""))
        for app in pkg.get("applets", []):
            existing_app_aids.add(app.get("aid", ""))

    # ── Profile 中定义的包 ──
    for pkg_spec in profile.packages:
        target_aid = pkg_spec.aid or pkg_spec.applet_aid or ""
        # 检查包或 applet 是否已存在
        if target_aid in existing_pkg_aids or target_aid in existing_app_aids:
            diffs.append({
                "action": "=",
                "package": pkg_spec,
                "aid": target_aid,
                "detail": f"{pkg_spec.name} 已存在",
            })
        else:
            diffs.append({
                "action": "+",
                "package": pkg_spec,
                "aid": target_aid,
                "detail": f"install {pkg_spec.name} ({target_aid}) → {pkg_spec.cap}",
            })

    # ── 卡片上但 Profile 中没有的包 ──
    profile_aids: set[str] = set()
    for pkg_spec in profile.packages:
        if pkg_spec.aid:
            profile_aids.add(pkg_spec.aid)
        if pkg_spec.applet_aid:
            profile_aids.add(pkg_spec.applet_aid)

    for pkg in card_state.get("packages", []):
        aid = pkg.get("aid", "")
        # ISD 不算
        if aid == card_state.get("isd"):
            continue
        # javacard.* 基础包不算
        if aid.startswith("A000000062"):
            continue
        if aid not in profile_aids:
            diffs.append({
                "action": "?",
                "package": None,
                "aid": aid,
                "detail": f"卡上有 {aid} 但 Profile 中未定义，建议 deploy delete",
            })

    return diffs
