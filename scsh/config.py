"""TOML 配置管理器。

支持全局 ~/.scsh/config.toml 和项目 ./scsh.toml 双层配置。
项目配置覆盖全局配置。

v0.4.0: 明文存储密钥。
"""

from __future__ import annotations

import os
import tomllib
from typing import Any


GLOBAL_CONFIG_DIR = os.path.expanduser("~/.scsh")
GLOBAL_CONFIG_PATH = os.path.join(GLOBAL_CONFIG_DIR, "config.toml")
PROJECT_CONFIG_FILENAME = "scsh.toml"


class ConfigManager:
    """配置管理器 — 加载、合并、查询、持久化。

    配置层级（优先级从高到低）：
    1. CLI 参数（未实现，v0.5.0）
    2. 项目 ./scsh.toml
    3. 全局 ~/.scsh/config.toml
    """

    def __init__(self) -> None:
        self._global: dict[str, Any] = {}
        self._project: dict[str, Any] = {}
        self._merged: dict[str, Any] = {}
        self._project_dir: str | None = None

    # ── 加载 ──

    def load_global(self) -> bool:
        """加载全局配置。返回是否找到配置文件。"""
        if os.path.isfile(GLOBAL_CONFIG_PATH):
            with open(GLOBAL_CONFIG_PATH, "rb") as f:
                self._global = tomllib.load(f)
            self._rebuild_merged()
            return True
        self._global = {}
        self._rebuild_merged()
        return False

    def load_project(self, project_dir: str | None = None) -> bool:
        """加载项目配置。返回是否找到配置文件。"""
        if project_dir:
            self._project_dir = project_dir
        if self._project_dir:
            path = os.path.join(self._project_dir, PROJECT_CONFIG_FILENAME)
            if os.path.isfile(path):
                with open(path, "rb") as f:
                    self._project = tomllib.load(f)
                self._rebuild_merged()
                return True
        self._project = {}
        self._rebuild_merged()
        return False

    def load_all(self, project_dir: str | None = None) -> None:
        """加载全部配置（全局 + 项目）。"""
        self.load_global()
        self.load_project(project_dir)

    def _rebuild_merged(self) -> None:
        """重建合并配置（项目覆盖全局）。"""
        self._merged = dict(self._global)
        for key, value in self._project.items():
            if isinstance(value, dict) and isinstance(self._merged.get(key), dict):
                self._merged[key] = {**self._merged[key], **value}
            else:
                self._merged[key] = value

    # ── 查询 ──

    def get(self, key: str, default: Any = None) -> Any:
        """查询配置值。支持 dot-path：'connection.key' → merged.connection.key。"""
        parts = key.split(".")
        current = self._merged
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        return current

    def all(self) -> dict[str, Any]:
        """返回合并配置的副本。"""
        return dict(self._merged)

    # ── 设置 ──

    def set(self, key: str, value: Any) -> None:
        """设置配置值（写入 merged，不自动持久化）。"""
        parts = key.split(".")
        current = self._merged
        for part in parts[:-1]:
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value

    # ── 持久化 ──

    def save_global(self) -> None:
        """持久化全局配置到 ~/.scsh/config.toml。"""
        self._ensure_dir(GLOBAL_CONFIG_DIR)
        content = self._format_toml(self._merged)
        with open(GLOBAL_CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(content)

    def save_project(self) -> None:
        """持久化项目配置到 ./scsh.toml。"""
        if not self._project_dir:
            print("未设置项目目录")
            return
        path = os.path.join(self._project_dir, PROJECT_CONFIG_FILENAME)
        content = self._format_toml(self._project)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    @staticmethod
    def _ensure_dir(path: str) -> None:
        """确保目录存在。"""
        if path and not os.path.isdir(path):
            os.makedirs(path, exist_ok=True)

    @staticmethod
    def _format_toml(data: dict[str, Any], indent: int = 0) -> str:
        """将 dict 格式化为 TOML 字符串。

        简易实现，支持 str/int/float/bool/list[str]/嵌套 dict。
        v0.4.0 不依赖第三方 TOML 写入库。
        """
        lines: list[str] = []
        prefix = "  " * indent

        # 先写简单值
        for key, value in data.items():
            if not isinstance(value, dict):
                lines.append(f"{prefix}{key} = {ConfigManager._toml_value(value)}")

        # 再写嵌套 section
        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"\n{prefix}[{key}]")
                lines.append(ConfigManager._format_toml(value, indent + 1))

        return "\n".join(lines) + "\n"

    @staticmethod
    def _toml_value(value: Any) -> str:
        """将 Python 值格式化为 TOML 值。"""
        if isinstance(value, str):
            return f'"{value}"'
        if isinstance(value, bool):
            return str(value).lower()
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, list):
            items = ", ".join(_toml_value(v) for v in value)
            return f"[{items}]"
        return f'"{value}"'
