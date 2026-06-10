"""命令注册表。

提供 Command/CommandRegistry 核心抽象，所有 scsh 命令通过
registry 注册，REPL 层通过 registry 分发执行。
"""

from __future__ import annotations

import shlex
from typing import Any, Callable


HandlerFunc = Callable[[str, Any], None]


class Command:
    """单个命令的元信息。"""

    def __init__(
        self,
        name: str,
        help_text: str,
        handler: HandlerFunc,
    ) -> None:
        self.name = name
        self.help_text = help_text
        self.handler = handler

    def __repr__(self) -> str:
        return f"<Command '{self.name}'>"


class CommandRegistry:
    """命令注册表 — 管理所有可用命令的注册与分发。"""

    def __init__(self) -> None:
        self._commands: dict[str, Command] = {}

    def register(
        self,
        name: str,
        help_text: str,
        handler: HandlerFunc,
    ) -> None:
        """注册一个命令。"""
        self._commands[name] = Command(name, help_text, handler)

    def get(self, name: str) -> Command | None:
        """按名称获取命令，不存在返回 None。"""
        return self._commands.get(name)

    def all(self) -> dict[str, Command]:
        """返回所有命令的副本。"""
        return dict(self._commands)

    @staticmethod
    def parse_line(line: str) -> tuple[str, str]:
        """将输入行解析为 (命令名, 参数) 元组。

        Args:
            line: 用户输入的原始行。

        Returns:
            (命令名, 参数字符串)。空行返回 ("", "")。
        """
        stripped = line.strip()
        if not stripped:
            return ("", "")
        parts = stripped.split(maxsplit=1)
        name = parts[0]
        args = parts[1] if len(parts) > 1 else ""
        return (name, args)

    def execute(self, name: str, args: str, transport: Any) -> None:
        """执行指定命令。

        Args:
            name: 命令名。
            args: 参数字符串。
            transport: PCSCTransport 实例，传递给命令 handler。
        """
        name = name.strip()
        if not name:
            return

        if name == "help":
            self._do_help(args)
            return

        cmd = self.get(name)
        if cmd is None:
            print(f"未知命令: {name}。输入 help 查看可用命令。")
            return

        cmd.handler(args, transport)

    def _do_help(self, topic: str) -> None:
        """处理 help 命令。"""
        if topic:
            cmd = self.get(topic)
            if cmd:
                print(f"{cmd.name} — {cmd.help_text}")
            else:
                print(f"未找到命令: {topic}")
        else:
            print("可用命令:")
            for name in sorted(self._commands):
                cmd = self._commands[name]
                print(f"  {name:<20s} {cmd.help_text}")
