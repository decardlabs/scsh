"""GP Fallback: 用 pyscard 实现 gp --list / --info。
绕过 JDK 11 javax.smartcardio 在 macOS 上的兼容问题。
需要安全通道的操作（install/delete）回退到 gp.jar。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCSH_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCSH_DIR))

from scsh.transport.pcsc import PCSCTransport


def gp_list() -> int:
    """列出卡片基本信息和已安装内容（需要 gp.jar 做 SCP02 认证）。"""
    t = PCSCTransport()
    readers = t.list_readers()
    idx = 0
    for i, r in enumerate(readers):
        if "ACS" in r["name"] or "ACR" in r["name"]:
            idx = i
            break
    t.connect(idx)

    try:
        # 探测 ISD
        for aid, name in [
            ("00A4040008A000000003000000", "v1"),
            ("00A4040008A000000151000000", "v2"),
        ]:
            data, sw = t.send_apdu(bytes.fromhex(aid))
            if sw == 0x9000:
                print(f"ISD: A0000000{'03000000' if '03' in aid else '151000000'} ({name})")
                break
        else:
            print("无法选取 ISD", file=sys.stderr)
            return 1

        # CPLC
        data, sw = t.send_apdu(bytes.fromhex("80CA9F7F00"))
        if sw == 0x9000 and data:
            print(f"CPLC: {data.hex()}")

        # 提示
        print()
        print("完整列表需要 SCP02 安全通道，使用 gp.jar:")
        print(f"  ~/.local/bin/gp --list  # 如果 gp.jar 可用")
        print(f"  或直接: java -jar {SCSH_DIR / 'tools' / 'gp.jar'} --list")

        t.disconnect()
        return 0
    finally:
        try:
            t.disconnect()
        except Exception:
            pass


def gp_info() -> int:
    """显示卡片 GP 详细信息。"""
    t = PCSCTransport()
    readers = t.list_readers()
    idx = 0
    for i, r in enumerate(readers):
        if "ACS" in r["name"] or "ACR" in r["name"]:
            idx = i
            break
    t.connect(idx)

    try:
        # SELECT ISD
        data, sw = t.send_apdu(bytes.fromhex("00A4040008A000000003000000"))
        isd = "A000000003000000"
        if sw == 0x6A82:
            data, sw = t.send_apdu(bytes.fromhex("00A4040008A000000151000000"))
            isd = "A000000151000000"

        print(f"ISD: {isd}  (SELECT: SW={sw:04X})")

        queries = [
            ("CPLC",       "80CA9F7F00"),
            ("Card Data",  "80CA006600"),
            ("Key Info",   "80CA00E000"),
        ]
        for name, apdu in queries:
            d, s = t.send_apdu(bytes.fromhex(apdu))
            if d:
                print(f"\n{name}: {d.hex()}" if s == 0x9000 else f"\n{name}: {d.hex()}  SW={s:04X}")
            else:
                print(f"\n{name}: SW={s:04X}")

        t.disconnect()
        return 0
    finally:
        try:
            t.disconnect()
        except Exception:
            pass


def main() -> int:
    args = sys.argv[1:]

    if "--list" in args or "-l" in args:
        return gp_list()
    elif "--info" in args or "-i" in args:
        return gp_info()
    else:
        # 其他操作回退到 gp.jar
        from scsh.bridge.gp_jar import GPJarBridge
        java_bin = GPJarBridge._find_java()
        gp_jar = SCSH_DIR / "tools" / "gp.jar"
        cmd = [java_bin, "-jar", str(gp_jar)] + args
        result = subprocess.run(cmd)
        return result.returncode


if __name__ == "__main__":
    sys.exit(main())
