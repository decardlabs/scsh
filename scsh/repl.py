"""REPL 主循环 — prompt_toolkit 交互式 Shell。"""

from __future__ import annotations

from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import FileHistory

from scsh.commands import CommandRegistry


class ScshRepl:
    """scsh 交互式 REPL。"""

    def __init__(
        self,
        registry: CommandRegistry,
        transport: Any,
    ) -> None:
        self.registry = registry
        self.transport = transport
        self._session: PromptSession | None = None
        self._running = True

    def _prompt(self) -> str:
        reader = self.transport._reader_index if hasattr(self.transport, '_reader_index') else None
        idx = str(reader) if reader is not None else "N"
        return f"[scsh:{idx}] > "

    def _get_completions(self) -> list[str]:
        words = list(self.registry.all().keys())
        words.extend(["help", "exit", "quit"])
        return sorted(set(words))

    def _process_line(self, line: str) -> None:
        """处理一行用户输入。"""
        name, args = self.registry.parse_line(line)
        if name in ("exit", "quit"):
            self._running = False
            return
        self.registry.execute(name, args, self.transport)

    @staticmethod
    def _handle_exit(args: str, transport: Any) -> bool:
        return False

    @staticmethod
    def _handle_quit(args: str, transport: Any) -> bool:
        return False

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
