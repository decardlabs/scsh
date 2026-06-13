"""系统命令：version / about 等。"""

from __future__ import annotations

import sys
from typing import Any

from scsh import __version__


def cmd_version(args: str, transport: Any) -> None:
    """显示 scsh 版本信息。

    Usage:
        version
        version --verbose   # 同时显示 Python / pyscard / gp.jar 版本
    """
    verbose = "--verbose" in args or "-v" in args

    print(f"scsh  {__version__}")
    print(f"Python  {sys.version.split()[0]}")
    print(f"pyscard {_get_pyscard_version()}")

    if verbose:
        _print_gp_jar_version(transport)
        _print_java_version()


def _get_pyscard_version() -> str:
    try:
        import pyscard

        return pyscard.__version__
    except Exception:
        return "(未安装)"


def _print_java_version() -> None:
    import subprocess

    for bin in ("java", "/usr/bin/java", "/usr/local/bin/java"):
        try:
            result = subprocess.run(
                [bin, "-version"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            line = (result.stdout or result.stderr or "").splitlines()[0]
            print(f"Java    {line}")
            return
        except Exception:
            continue
    print("Java    (未找到)")


def _print_gp_jar_version(transport: Any) -> None:
    bridge = getattr(transport, "gp_bridge", None)
    if bridge is None:
        print("gp.jar  (未初始化)")
        return
    try:
        ver = bridge.get_version()
        print(f"gp.jar  {ver}")
    except Exception as exc:
        print(f"gp.jar  (获取失败: {exc})")
