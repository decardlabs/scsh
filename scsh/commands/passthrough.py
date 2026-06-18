"""gp 透传命令 — 原样透传给 gp.jar。

底层安全阀：任何 gp.jar 支持但 scsh 还没封装的功能，
用户都能通过 `gp <raw_args>` 直接使用。

scsh 只拼接 java -jar gp.jar <raw_args>，零解析零改写。
"""

from __future__ import annotations

from typing import Any

from scsh.session import Session


def cmd_gp_passthrough(args: str, session: Session) -> None:
    """gp 透传命令：原样传递给 gp.jar。

    用法:
        gp <任意gp.jar参数>
        gp --list --verbose --key 4041...
    """
    if not args:
        print("用法: gp <gp.jar参数>")
        print("示例: gp --list --verbose")
        print("示例: gp --info --key 404142434445464748494A4B4C4D4E4F")
        return

    bridge = getattr(session, "gp_bridge", None)
    if bridge is None:
        print("GP 桥接未就绪。需要安装 Java 和 GlobalPlatformPro (gp.jar)。")
        return
        print("用法: gp <gp.jar参数>")
        print("示例: gp --list --verbose")
        print("示例: gp --info --key 404142434445464748494A4B4C4D4E4F")
        return

    # 透传：直接调用 bridge._run()，不做任何参数解析或改写
    try:
        # shlex split 以支持带引号的参数
        import shlex
        raw_args = shlex.split(args)
        output = bridge._run(*raw_args)
        print(output)
    except Exception as exc:
        print(f"gp 透传失败: {exc}")


GP_HELP: dict[str, Any] = {
    "apdu": {
        "gp_op": "原样透传给 gp.jar（零解析零改写）",
        "gp_jar": "java -jar gp.jar <raw_args>",
    },
    "usage": [
        "gp <任意gp.jar参数>",
        "gp --list --verbose",
        "gp --info --key 404142434445464748494A4B4C4D4E4F",
        "",
        "⚠️ 这是底层安全阀，scsh 不做任何参数处理。",
        "所有配置注入（密钥、SCP模式等）不生效。",
        "推荐优先使用 card/deploy/config 等子系统命令。",
    ],
}


def register_gp_passthrough(registry: Any) -> None:
    """注册 gp 透传命令。"""
    registry.register("gp", "gp.jar 原样透传命令（底层安全阀）", cmd_gp_passthrough, GP_HELP)
