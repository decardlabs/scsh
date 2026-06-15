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
        """在系统路径中查找 gp.jar。

        搜索顺序：PATH → 常见安装路径 → 项目 tools/ 目录 → 当前目录。
        """
        path = shutil.which("gp.jar")
        if path:
            return path
        # 常见安装路径
        candidates = [
            "/usr/local/bin/gp.jar",
            "/opt/homebrew/bin/gp.jar",
            os.path.expanduser("~/.local/bin/gp.jar"),
            "tools/gp.jar",
            "gp.jar",
        ]
        for c in candidates:
            if os.path.isfile(c):
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

    def install(self, cap_path: str, params: str | None = None,
                privs: str | None = None, make_default: bool = False,
                force: bool = False) -> str:
        """安装 CAP 文件。

        Args:
            cap_path: CAP 文件路径。
            params: 安装参数（十六进制字符串）。
            privs: 安装权限（如 CREATABLE, SELECTABLE 等）。
            make_default: 是否设为默认 Applet。
            force: 是否强制安装。
        """
        args: list[str] = ["--install", cap_path]
        if params:
            args.extend(["--params", params])
        if privs:
            args.extend(["--privs", privs])
        if make_default:
            args.append("--default")
        if force:
            args.append("-f")
        try:
            output = self._run(*args)
        except GPBridgeError as exc:
            raise GPBridgeError(f"GP install 失败: {exc}")
        return output.strip()

    def make_default(self, aid: str) -> str:
        """设置指定 AID 为默认 Applet（NFC 刷卡自动选择）。"""

        try:
            output = self._run("--make-default", aid)
        except GPBridgeError as exc:
            raise GPBridgeError(f"GP set-default 失败: {exc}")
        return output.strip()

    def lock_card(self) -> str:
        """锁定卡片（SECURED → CARD_LOCKED）。"""

        try:
            output = self._run("--lock-card")
        except GPBridgeError as exc:
            raise GPBridgeError(f"GP lock-card 失败: {exc}")
        return output.strip()

    def unlock_card(self) -> str:
        """解锁卡片（CARD_LOCKED → SECURED）。"""

        try:
            output = self._run("--unlock-card")
        except GPBridgeError as exc:
            raise GPBridgeError(f"GP unlock-card 失败: {exc}")
        return output.strip()

    def initialize_card(self) -> str:
        """初始化卡片（OP_READY → INITIALIZED）。"""

        try:
            output = self._run("--initialize-card")
        except GPBridgeError as exc:
            raise GPBridgeError(f"GP init-card 失败: {exc}")
        return output.strip()

    def secure_card(self) -> str:
        """安全化卡片（INITIALIZED → SECURED）。"""

        try:
            output = self._run("--secure-card")
        except GPBridgeError as exc:
            raise GPBridgeError(f"GP secure-card 失败: {exc}")
        return output.strip()

    def put_key(self, master_key: str | None = None,
                key_enc: str | None = None, key_mac: str | None = None,
                key_dek: str | None = None, key_ver: str | None = None,
                new_key_ver: str | None = None, kdf: str | None = None) -> str:
        """更新 SCP 密钥。

        Args:
            master_key: 主密钥（自动派生 ENC/MAC/DEK）。
            key_enc: 单独指定 ENC 密钥。
            key_mac: 单独指定 MAC 密钥。
            key_dek: 单独指定 DEK 密钥。
            key_ver: 当前密钥版本。
            new_key_ver: 新密钥版本。
            kdf: KDF 模板名称。
        """
        args: list[str] = []
        if master_key:
            args.extend(["--lock", master_key])
        else:
            if key_enc:
                args.extend(["--lock-enc", key_enc])
            if key_mac:
                args.extend(["--lock-mac", key_mac])
            if key_dek:
                args.extend(["--lock-dek", key_dek])
        if key_ver:
            args.extend(["--key-ver", key_ver])
        if new_key_ver:
            args.extend(["--new-keyver", new_key_ver])
        if kdf:
            args.extend(["--lock-kdf", kdf])
        try:
            output = self._run(*args)
        except GPBridgeError as exc:
            raise GPBridgeError(f"GP put-key 失败: {exc}")
        return output.strip()

    def delete_key(self, ver: str) -> str:
        """删除指定版本的密钥。"""

        try:
            output = self._run("--delete-key", ver)
        except GPBridgeError as exc:
            raise GPBridgeError(f"GP delete-key 失败: {exc}")
        return output.strip()

    def store_data(self, data_hex: str) -> str:
        """写入个人化数据（GP STORE DATA）。"""

        try:
            output = self._run("--store-data", data_hex)
        except GPBridgeError as exc:
            raise GPBridgeError(f"GP store-data 失败: {exc}")
        return output.strip()

    def store_data_chunk(self, data_hex: str) -> str:
        """分块写入 STORE DATA（大数据场景）。"""

        try:
            output = self._run("--store-data-chunk", data_hex)
        except GPBridgeError as exc:
            raise GPBridgeError(f"GP store-data-chunk 失败: {exc}")
        return output.strip()

    def create_domain(self, aid: str) -> str:
        """创建补充安全域（SSD）。"""

        try:
            output = self._run("--domain", aid)
        except GPBridgeError as exc:
            raise GPBridgeError(f"GP create-domain 失败: {exc}")
        return output.strip()

    def rename_isd(self, new_aid: str) -> str:
        """重命名 ISD AID。"""

        try:
            output = self._run("--rename-isd", new_aid)
        except GPBridgeError as exc:
            raise GPBridgeError(f"GP rename-isd 失败: {exc}")
        return output.strip()

    def load(self, cap_path: str) -> str:
        """仅加载 CAP 文件到卡片（不 INSTALL，分步操作）。"""

        try:
            output = self._run("--load", cap_path)
        except GPBridgeError as exc:
            raise GPBridgeError(f"GP load 失败: {exc}")
        return output.strip()

    def uninstall(self, target: str) -> str:
        """卸载 CAP 文件（需指定 CAP 路径或 AID）。"""

        try:
            output = self._run("--uninstall", target)
        except GPBridgeError as exc:
            raise GPBridgeError(f"GP uninstall 失败: {exc}")
        return output.strip()

    def set_cplc(self, pre_perso: str | None = None,
                  perso: str | None = None, today: bool = False) -> str:
        """设置 CPLC 个人化数据。

        Args:
            pre_perso: PrePerso 日期（十六进制，6 字节）。
            perso: Perso 日期（十六进制，6 字节）。
            today: 自动使用今天日期。
        """
        args: list[str] = []
        if pre_perso:
            args.extend(["--set-pre-perso", pre_perso])
        if perso:
            args.extend(["--set-perso", perso])
        if today:
            args.append("--today")
        if not args:
            raise GPBridgeError("set_cplc: 至少需要指定一个参数")
        try:
            output = self._run(*args)
        except GPBridgeError as exc:
            raise GPBridgeError(f"GP set-cplc 失败: {exc}")
        return output.strip()

    def send_secure_apdu(self, apdu_hex: str) -> str:
        """通过 SCP 安全通道发送 APDU。"""

        try:
            output = self._run("--secure-apdu", apdu_hex)
        except GPBridgeError as exc:
            raise GPBridgeError(f"GP secure-apdu 失败: {exc}")
        return output.strip()

    def set_mode(self, mode: str) -> str:
        """设置 SCP 安全通道模式。

        Args:
            mode: 模式字符串，如 "MAC", "ENC", "RMAC", "CLR" 或组合。
        """
        try:
            output = self._run("--mode", mode)
        except GPBridgeError as exc:
            raise GPBridgeError(f"GP set-mode 失败: {exc}")
        return output.strip()

    def set_scp(self, scp_type: str) -> str:
        """设置 SCP 类型（SCP02/SCP03）。"""

        try:
            output = self._run("--scp", scp_type)
        except GPBridgeError as exc:
            raise GPBridgeError(f"GP set-scp 失败: {exc}")
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
            "isd_state": None,
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
                isd_match = re.match(
                    r"ISD:\s*([0-9A-Fa-f]+)\s*(?:\((\w+)\))?",
                    stripped,
                )
                if isd_match:
                    result["isd"] = isd_match.group(1)
                    result["isd_state"] = isd_match.group(2) or None
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
        """解析 gp --info 输出。

        CPLC / Card Data / Card Capabilities 均提取到结果中。
        """
        result: dict[str, Any] = {
            "scp": None,
            "gp_version": None,
            "jc_version": None,
            "key_version": None,
            "security_level": None,
            "cplc": {},
            "card_data": {},
            "card_capabilities": [],
        }

        in_cplc = False
        in_card_data = False
        in_card_caps = False

        for line in output.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue

            # ── 分区检测 ──
            if stripped.startswith("CPLC:"):
                in_cplc = True
                in_card_data = False
                in_card_caps = False
                # "CPLC:" 后的第一个 key=value 可能在同一行
                rest = stripped[5:].strip()
                if "=" in rest:
                    k, _, v = rest.partition("=")
                    result["cplc"][k.strip()] = v.strip()
                continue

            if stripped.startswith("Card Data:"):
                in_cplc = False
                in_card_data = True
                in_card_caps = False
                continue

            if stripped.startswith("Card Capabilities:"):
                in_cplc = False
                in_card_data = False
                in_card_caps = True
                continue

            # ── 通用行跳过 ──
            if stripped in ("IIN:", "CIN:", "KDD:", "SSC:"):
                in_cplc = False
                in_card_data = False
                in_card_caps = False
                continue

            # ── CPLC 数据: 空格缩进后的 key=value ──
            if in_cplc and "=" in stripped:
                k, _, v = stripped.partition("=")
                result["cplc"][k.strip()] = v.strip()
                continue

            # ── Card Data: Tag OID 行 ──
            if in_card_data:
                # Tag XX: OID
                tag_match = re.match(r"Tag\s+(\d+[A-Za-z]?):\s+([\d.]+)", stripped)
                if tag_match:
                    tag_val = tag_match.group(1)
                    oid = tag_match.group(2)
                    result["card_data"][f"Tag_{tag_val}"] = oid
                    continue
                # 下一行 -> 描述文字
                desc_match = re.match(r"->\s*(.+)", stripped)
                if desc_match:
                    # 关联到上一个 Tag
                    desc = desc_match.group(1)
                    if "GP Version:" in desc:
                        result["gp_version"] = desc.split("GP Version:")[-1].strip()
                    if "JavaCard" in desc or "Java Card" in desc:
                        result["jc_version"] = desc.strip()
                    if "SCP" in desc:
                        scp_m = re.search(r"SCP(\d+)", desc)
                        if scp_m:
                            result["scp"] = scp_m.group(1)
                    continue

            # ── Card Capabilities: 密钥行 ──
            if in_card_caps:
                cap_match = re.match(
                    r"Version:\s*(\d+)(?:\s*\([^)]+\))?\s+ID:\s*(\d+)(?:\s*\([^)]+\))?\s+type:\s*(\S+)\s+length:\s*(\d+)",
                    stripped,
                )
                if cap_match:
                    result["card_capabilities"].append({
                        "version": int(cap_match.group(1)),
                        "id": int(cap_match.group(2)),
                        "type": cap_match.group(3),
                        "length": int(cap_match.group(4)),
                        "note": cap_match.group(5) if cap_match.lastindex and cap_match.lastindex >= 5 else "",
                    })
                    continue

            # ── 散落字段 ──
            if "SCP:" in stripped and not in_cplc:
                m = re.search(r"SCP:\s*(\S+)", stripped)
                if m:
                    result["scp"] = m.group(1)

            if "Key Version:" in stripped:
                m = re.search(r"Key Version:\s*(\S+)", stripped)
                if m:
                    result["key_version"] = m.group(1)

            if "Security Level:" in stripped:
                m = re.search(r"Security Level:\s*(\S+)", stripped)
                if m:
                    result["security_level"] = m.group(1)

        return result
