"""gp.jar subprocess 桥接层。

通过 subprocess 调用 GlobalPlatformPro (gp.jar) 执行 GP 管理命令。
这是过渡方案，计划 M6 替换为纯 Python GP 实现。
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from typing import Any

from scsh.exceptions import GPBridgeError


class GPJarBridge:
    """gp.jar 命令桥接。"""

    def __init__(self, jar_path: str | None = None) -> None:
        self.jar_path = jar_path or self._find_jar()

    @staticmethod
    def _find_jar() -> str:
        """在系统路径中查找 gp.jar。"""
        path = shutil.which("gp.jar")
        if path:
            return path
        # 常见安装路径
        candidates = [
            "/usr/local/bin/gp.jar",
            "/opt/homebrew/bin/gp.jar",
            os.path.expanduser("~/.local/bin/gp.jar"),
            "gp.jar",
        ]
        for c in candidates:
            if shutil.which(c) or c == "gp.jar":
                return c
        return "gp.jar"

    @staticmethod
    def _find_java() -> str:
        """查找 java 可执行文件，优先使用 JAVA_HOME。"""
        java_home = os.environ.get("JAVA_HOME")
        if java_home:
            candidate = os.path.join(java_home, "bin", "java")
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
        system_java = shutil.which("java")
        if system_java:
            return system_java
        # macOS 常见路径
        for path in [
            "/usr/bin/java",
            "/Library/Java/JavaVirtualMachines/*/Contents/Home/bin/java",
        ]:
            if os.path.isfile(path):
                return path
        return "java"

    def _run(self, *args: str) -> str:
        """执行 gp.jar 命令。"""
        java_bin = self._find_java()
        cmd = [java_bin, "-jar", self.jar_path, *args]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except FileNotFoundError:
            raise GPBridgeError(
                "找不到 java 命令或 gp.jar。请确保已安装 Java 和 GlobalPlatformPro。"
            )
        except subprocess.TimeoutExpired:
            raise GPBridgeError("gp.jar 命令执行超时")

        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip()
            raise GPBridgeError(f"gp.jar 执行失败: {error_msg}")

        return result.stdout

    def get_version(self) -> str:
        """获取 gp.jar 版本信息。"""
        try:
            output = self._run("--version")
        except GPBridgeError:
            raise
        except Exception as exc:
            raise GPBridgeError(f"找不到 gp.jar: {exc}")

        # 解析版本行
        for line in output.splitlines():
            if "GlobalPlatformPro" in line:
                return line.strip()
        return output.strip()

    def list(self) -> dict[str, Any]:
        """列出已安装的 ISD / Package / Applet。"""
        try:
            output = self._run("--list")
        except GPBridgeError as exc:
            raise GPBridgeError(f"GP list 失败: {exc}")

        return self._parse_list_output(output)

    def info(self) -> dict[str, Any]:
        """获取 GP 详细信息。"""
        try:
            output = self._run("--info")
        except GPBridgeError as exc:
            raise GPBridgeError(f"GP info 失败: {exc}")

        return self._parse_info_output(output)

    def execute_apdu(self, apdu_hex: str) -> str:
        """通过 GP 发送 APDU。"""
        try:
            output = self._run("--apdu", apdu_hex)
        except GPBridgeError as exc:
            raise GPBridgeError(f"GP APDU 失败: {exc}")

        return output.strip()

    def install(self, cap_path: str) -> str:
        """安装 CAP 文件。"""
        try:
            output = self._run("--install", cap_path)
        except GPBridgeError as exc:
            raise GPBridgeError(f"GP install 失败: {exc}")
        return output.strip()

    def delete(self, aid: str) -> str:
        """删除 Applet/Package。"""
        try:
            output = self._run("--delete", aid)
        except GPBridgeError as exc:
            raise GPBridgeError(f"GP delete 失败: {exc}")
        return output.strip()

    def lock(self, aid: str) -> str:
        """锁定 Applet。"""
        try:
            output = self._run("--lock", aid)
        except GPBridgeError as exc:
            raise GPBridgeError(f"GP lock 失败: {exc}")
        return output.strip()

    def unlock(self, aid: str) -> str:
        """解锁 Applet。"""
        try:
            output = self._run("--unlock", aid)
        except GPBridgeError as exc:
            raise GPBridgeError(f"GP unlock 失败: {exc}")
        return output.strip()

    # ── 输出解析 ──────────────────────────────────────────

    @staticmethod
    def _parse_list_output(output: str) -> dict[str, Any]:
        """解析 gp --list 输出。

        输出格式示例:
            ISD: A000000003000000 (OP_READY)
              PKG: A0000006472F0001 (LOADED)
                Applet: A0000006472F000101 (SELECTABLE)
        """
        result: dict[str, Any] = {
            "isd": None,
            "packages": [],
        }

        lines = [l for l in output.splitlines() if l.strip() and not l.strip().startswith("#")]

        current_pkg: dict[str, Any] | None = None

        for line in lines:
            stripped = line.strip()

            if stripped.startswith("No applets"):
                return result

            # ISD: AID (STATE)
            if stripped.startswith("ISD:") and not stripped.startswith("  "):
                parts = stripped[4:].strip().split()
                aid = parts[0] if parts else None
                result["isd"] = aid
                current_pkg = None
                continue

            #   PKG: AID (STATE)
            pkg_match = re.match(r"PKG:\s*([0-9A-Fa-f]+)\s*(?:\((\w+)\))?", stripped)
            if pkg_match and not stripped.startswith("     "):
                pkg = {
                    "aid": pkg_match.group(1),
                    "state": pkg_match.group(2) or "",
                    "applets": [],
                }
                result["packages"].append(pkg)
                current_pkg = pkg
                continue

            #     Applet: AID (STATE)
            app_match = re.match(r"Applet:\s*([0-9A-Fa-f]+)\s*(?:\((\w+)\))?", stripped)
            if app_match and current_pkg is not None:
                current_pkg["applets"].append({
                    "aid": app_match.group(1),
                    "state": app_match.group(2) or "",
                })
                continue

        return result

    @staticmethod
    def _parse_info_output(output: str) -> dict[str, Any]:
        """解析 gp --info 输出。"""
        result: dict[str, Any] = {
            "scp": None,
            "gp_version": None,
            "key_version": None,
            "security_level": None,
        }

        for line in output.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue

            if "SCP:" in stripped:
                m = re.search(r"SCP:\s*(\S+)", stripped)
                if m:
                    result["scp"] = m.group(1)

            if "GP Version:" in stripped:
                m = re.search(r"GP Version:\s*(\S+)", stripped)
                if m:
                    result["gp_version"] = m.group(1)

            if "Key Version:" in stripped:
                m = re.search(r"Key Version:\s*(\S+)", stripped)
                if m:
                    result["key_version"] = m.group(1)

            if "Security Level:" in stripped:
                m = re.search(r"Security Level:\s*(\S+)", stripped)
                if m:
                    result["security_level"] = m.group(1)

        return result
