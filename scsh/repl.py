"""REPL 主循环 — prompt_toolkit 交互式 Shell。

v0.4.0: 使用 execute_line() 支持子系统命令路由。
"""

from __future__ import annotations

from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import FileHistory

from scsh.commands import CommandRegistry
from scsh.session import Session


class ScshRepl:
    """scsh 交互式 REPL。"""

    def __init__(
        self,
        registry: CommandRegistry,
        session: Session,
    ) -> None:
        self.registry = registry
        self.session = session
        self._session: PromptSession | None = None
        self._running = True

    def _prompt(self) -> str:
        idx = getattr(self.session.transport, '_reader_index', None)
        if not isinstance(idx, int):
            idx = "N"
        return f"[scsh:{idx}] > "

    def _get_completions(self) -> list[str]:
        """收集所有可用补全词（子系统名 + 子命令 + 扁平命令）。"""
        words: list[str] = []

        # 扁平命令（含别名）
        words.extend(self.registry.all_commands().keys())

        # 子系统名
        for sys_name in self.registry.all_subsystems():
            words.append(sys_name)
            # 子命令（格式：subsystem subcmd，补全时只显示 subcmd）
            subsystem = self.registry.all_subsystems()[sys_name]
            for subcmd_name in subsystem.subcommands:
                # 完整补全格式
                words.append(f"{sys_name} {subcmd_name}")

        words.extend(["help", "exit", "quit"])
        return sorted(set(words))

    def _process_line(self, line: str) -> None:
        """处理一行用户输入。

        v0.4.0: 先检测 exit/quit，然后使用 execute_line() 支持子系统路由。
        """
        stripped = line.strip()
        if not stripped:
            return

        # 检测退出命令
        first_word = stripped.split()[0]
        if first_word in ("exit", "quit"):
            self._running = False
            return

        # 使用新的 execute_line（支持子系统路由）
        self.registry.execute_line(line, self.session)

    def run(self) -> None:
        """启动 REPL 主循环。"""
        self._running = True
        self._session = PromptSession(
            history=FileHistory(".scsh_history"),
        )

        while self._running:
            try:
                line = self._session.prompt(self._prompt())
                self._process_line(line)
            except (EOFError, KeyboardInterrupt):
                self._running = False
                break
