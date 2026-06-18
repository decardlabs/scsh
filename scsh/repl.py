"""REPL 主循环 — prompt_toolkit 交互式 Shell。

v0.7.0: ScshCompleter 层级补全 + AID/路径上下文补全。
"""

from __future__ import annotations

import glob
import os
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import FileHistory

from scsh.commands import CommandRegistry
from scsh.session import Session


# ── 上下文感知补全 ──

def _get_known_aids(session: Session) -> list[str]:
    """收集已知 AID（来自 config aliases + card list 缓存）。"""
    aids: list[str] = []

    # config aliases
    config_mgr = getattr(session, "config_manager", None)
    if config_mgr:
        aliases = config_mgr.get("aliases", {})
        if isinstance(aliases, dict):
            aids.extend(aliases.values())

    # session aliases
    session_aliases = getattr(session, "aid_aliases", {})
    aids.extend(session_aliases.values())

    return sorted(set(aids))


def _get_cap_files() -> list[str]:
    """搜索当前目录及子目录下的 .cap 文件。"""
    caps = glob.glob("**/*.cap", recursive=True)
    return sorted(caps)


class ScshCompleter(Completer):
    """scsh 自定义补全器。

    v0.7.0: 支持三层补全策略：
    1. 第一词 → 子系统名 + 扁平命令 + help/exit/quit
    2. 第二词（子系统上下文）→ 子命令名 + 选项
    3. 第三词+ → 上下文感知补全（AID、文件路径、选项值）
    """

    def __init__(self, registry: CommandRegistry, session: Session) -> None:
        self.registry = registry
        self.session = session

    def get_completions(
        self, document: Any, complete_event: Any
    ) -> Any:
        """根据输入上下文提供补全建议。"""
        text = document.text_before_cursor
        words = text.split()

        # ── 正在输入第一词 ──
        if len(words) == 0:
            yield from self._complete_first_word("", document, complete_event)
        elif len(words) == 1 and not text.endswith(" "):
            yield from self._complete_first_word(words[0], document, complete_event)
        elif len(words) == 1 and text.endswith(" "):
            # 第一词已完成，空格后 → 补全第二词
            yield from self._complete_second_word(words[0], "", document, complete_event)

        # ── 两词以上：上下文补全 ──
        elif len(words) >= 2:
            first = words[0]
            if first in self.registry.all_subsystems():
                # 子系统上下文
                subcmd = words[1] if len(words) > 1 else ""
                yield from self._complete_subsystem_args(
                    first, subcmd, words, text, document, complete_event
                )
            else:
                # 扁平命令上下文 → 上下文补全
                yield from self._complete_flat_args(
                    first, words, text, document, complete_event
                )

    def _complete_first_word(
        self, partial: str, document: Any, complete_event: Any
    ) -> Any:
        """补全第一词：子系统 + 扁平命令 + help/exit/quit。"""
        candidates: list[str] = []

        # 子系统名
        for name in self.registry.all_subsystems():
            candidates.append(name)

        # 扁平命令（含别名）
        for name in self.registry.all_commands():
            candidates.append(name)

        # 内建命令
        candidates.extend(["help", "exit", "quit"])

        for c in sorted(set(candidates)):
            if c.startswith(partial):
                yield Completion(c, start_position=-len(partial))

    def _complete_second_word(
        self, first: str, partial: str, document: Any, complete_event: Any
    ) -> Any:
        """补全第二词。"""
        if first in self.registry.all_subsystems():
            # 子系统 → 补全子命令
            subsystem = self.registry.all_subsystems()[first]
            for name in sorted(subsystem.subcommands):
                if name.startswith(partial):
                    yield Completion(name, start_position=-len(partial))
        else:
            # 扁平命令 → 补全命令参数
            yield from self._complete_flat_args(
                first, [first], first + " " + partial, document, complete_event
            )

    def _complete_subsystem_args(
        self, subsystem: str, subcmd: str, words: list[str],
        text: str, document: Any, complete_event: Any
    ) -> Any:
        """补全子系统子命令的参数。"""
        # 如果还在输入子命令名
        if len(words) == 2 and not text.endswith(" "):
            subsystem_obj = self.registry.all_subsystems()[subsystem]
            partial = words[1]
            for name in sorted(subsystem_obj.subcommands):
                if name.startswith(partial):
                    yield Completion(name, start_position=-len(partial))
            return

        # 子命令已完成，补全参数
        context_key = f"{subsystem} {subcmd}"

        # AID 相关命令 → 补全已知 AID
        aid_commands = {
            "card applet-state", "card make-selectable", "card create-domain",
            "card rename-isd", "deploy delete", "apdu select",
            "apdu secure-send",
        }
        if context_key in aid_commands:
            yield from self._complete_aids(words, text, document, arg_offset=2)

        # 文件路径命令 → 补全 .cap 文件
        file_commands = {"deploy install", "deploy load"}
        if context_key in file_commands:
            yield from self._complete_cap_paths(words, text, document, arg_offset=2)

        # lifecycle → 补全操作名
        if context_key == "card lifecycle":
            yield from self._complete_lifecycle_actions(words, text, document)

        # config mode → 补全模式值
        if context_key == "config mode":
            for mode in ["CLR", "MAC", "ENC", "RMAC", "MAC+ENC"]:
                partial = words[-1] if len(words) > 2 else ""
                if mode.startswith(partial.upper()):
                    yield Completion(mode, start_position=-len(partial))

        # 选项补全（--开头）
        last_word = words[-1] if words else ""
        if last_word.startswith("--"):
            yield from self._complete_options(context_key, last_word)

    def _complete_flat_args(
        self, cmd: str, words: list[str], text: str,
        document: Any, complete_event: Any
    ) -> Any:
        """补全扁平命令的参数。"""
        aid_aliases = {
            "gp-list", "gp-info", "gp-scp", "gp-status",
            "gp-delete", "gp-lock", "gp-unlock",
            "gp-store-data", "gp-create-domain", "gp-make-selectable",
            "gp-set-default", "gp-rename-isd",
            "gp-lock-card", "gp-unlock-card", "gp-terminate-card",
            "gp-init-card", "gp-secure-card",
        }
        file_aliases = {"gp-install", "gp-load"}

        if cmd in aid_aliases:
            yield from self._complete_aids(words, text, document, arg_offset=1)
        elif cmd in file_aliases:
            yield from self._complete_cap_paths(words, text, document, arg_offset=1)
        elif cmd == "gp-key":
            pass  # 密钥值不补全（安全）
        elif cmd == "gp-mode":
            for mode in ["CLR", "MAC", "ENC", "RMAC", "MAC+ENC"]:
                partial = words[-1] if len(words) > 1 else ""
                if mode.startswith(partial.upper()):
                    yield Completion(mode, start_position=-len(partial))
        elif cmd == "gp":
            # gp 透传 → 补全常见 gp.jar 选项
            common_flags = [
                "--list", "--info", "--install", "--load", "--delete",
                "--key", "--scp", "--mode", "--apdu", "--secure-apdu",
                "--domain", "--store-data", "--version", "-v", "-f",
                "--privs", "--params", "--default", "--make-default",
                "--lock-card", "--unlock-card", "--terminate-card",
                "--initialize-card", "--secure-card",
                "--lock", "--unlock", "--rename-isd",
            ]
            partial = words[-1] if len(words) > 1 else ""
            for flag in sorted(common_flags):
                if flag.startswith(partial):
                    yield Completion(flag, start_position=-len(partial))

    def _complete_aids(
        self, words: list[str], text: str, document: Any,
        arg_offset: int = 2,
    ) -> Any:
        """补全已知 AID。

        arg_offset: 参数在 words 中的起始位置。
            子系统命令: words=["card", "delete", "A000"] → offset=2
            扁平命令:   words=["gp-delete", "A000"] → offset=1
        """
        known_aids = _get_known_aids(self.session)
        # 如果 text 以空格结尾，用户开始输入新参数，partial = ""
        # 否则取当前正在输入的词
        if text.endswith(" "):
            partial = ""
        elif len(words) > arg_offset:
            partial = words[-1]
        else:
            partial = ""
        for aid in known_aids:
            if aid.upper().startswith(partial.upper()):
                yield Completion(aid, start_position=-len(partial))

    def _complete_cap_paths(
        self, words: list[str], text: str, document: Any,
        arg_offset: int = 2,
    ) -> Any:
        """补全 .cap 文件路径。"""
        cap_files = _get_cap_files()
        if text.endswith(" "):
            partial = ""
        elif len(words) > arg_offset:
            partial = words[-1]
        else:
            partial = ""
        for path in cap_files:
            if path.startswith(partial):
                yield Completion(path, start_position=-len(partial))

    def _complete_lifecycle_actions(
        self, words: list[str], text: str, document: Any
    ) -> Any:
        """补全 lifecycle 操作名。"""
        actions = ["init", "secure", "lock", "unlock", "terminate"]
        partial = words[-1] if len(words) > 2 else ""
        for action in actions:
            if action.startswith(partial):
                yield Completion(action, start_position=-len(partial))

    def _complete_options(self, context_key: str, partial: str) -> Any:
        """补全命令选项 (--xxx)。"""
        option_map: dict[str, list[str]] = {
            "deploy install": [
                "--applet", "--params", "--privs", "--default",
                "--force", "-f", "--step", "--load-only", "--install-only",
            ],
            "deploy provision": ["--dry-run", "--step"],
            "card set-cplc": ["--pre-perso", "--perso", "--today"],
            "key put": [
                "--master", "--enc", "--mac", "--dek",
                "--key-ver", "--new-keyver",
            ],
        }
        options = option_map.get(context_key, [])
        for opt in sorted(options):
            if opt.startswith(partial):
                yield Completion(opt, start_position=-len(partial))


# ── ScshRepl ──

class ScshRepl:
    """scsh 交互式 REPL。

    v0.7.0: ScshCompleter 层级补全 + SW 自动引导。
    """

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

    def _process_line(self, line: str) -> None:
        """处理一行用户输入。

        v0.7.0: exit/quit 检测 → execute_line。
        """
        stripped = line.strip()
        if not stripped:
            return

        # 检测退出命令
        first_word = stripped.split()[0]
        if first_word in ("exit", "quit"):
            self._running = False
            return

        # 使用 execute_line（支持子系统路由）
        self.registry.execute_line(line, self.session)

    def run(self) -> None:
        """启动 REPL 主循环。"""
        self._running = True
        completer = ScshCompleter(self.registry, self.session)
        self._session = PromptSession(
            history=FileHistory(".scsh_history"),
            completer=completer,
        )

        while self._running:
            try:
                line = self._session.prompt(self._prompt())
                self._process_line(line)
            except (EOFError, KeyboardInterrupt):
                self._running = False
                break
