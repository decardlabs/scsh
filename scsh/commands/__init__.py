"""命令注册表。

提供 Command/Subsystem/CommandRegistry 核心抽象，支持：
1. 扁平命令：name → handler（如 help, version, exit, gp-list）
2. 子系统命令：subsystem → subcommand → handler（如 card list, deploy install）
3. 别名映射：gp-list → card list 的 handler

v0.4.0 新增 Subsystem 二级路由 + 三层 Help（命令层/APDU层/诊断层）。
v0.7.0 新增 SW 自动引导（GP 命令失败时自动显示诊断帮助）。
"""

from __future__ import annotations

from typing import Any, Callable

from scsh.session import Session


HandlerFunc = Callable[[str, Session], None]


class Command:
    """单个命令的元信息。"""

    def __init__(
        self,
        name: str,
        help_text: str,
        handler: HandlerFunc,
        help_data: dict[str, Any] | None = None,
    ) -> None:
        self.name = name
        self.help_text = help_text
        self.handler = handler
        self.help_data: dict[str, Any] = help_data or {}

    def __repr__(self) -> str:
        return f"<Command '{self.name}'>"


class Subsystem:
    """子系统命令组。"""

    def __init__(self, name: str, description: str) -> None:
        self.name = name
        self.description = description
        self.subcommands: dict[str, Command] = {}

    def __repr__(self) -> str:
        return f"<Subsystem '{self.name}' ({len(self.subcommands)} subcommands)>"


class CommandRegistry:
    """命令注册表 — 管理所有可用命令的注册与分发。

    支持两种命令模式：
    1. 扁平命令：name → handler（如 version, gp-list 等别名）
    2. 子系统命令：subsystem → subcommand → handler（如 card list, deploy install）

    别名（如 gp-list）注册为扁平命令，handler 指向子系统子命令的同一 handler，
    享受 config 自动注入等高层特性。
    """

    def __init__(self) -> None:
        self._commands: dict[str, Command] = {}
        self._subsystems: dict[str, Subsystem] = {}

    # ── 注册 ──

    def register(
        self,
        name: str,
        help_text: str,
        handler: HandlerFunc,
        help_data: dict[str, Any] | None = None,
    ) -> None:
        """注册一个扁平命令。"""
        self._commands[name] = Command(name, help_text, handler, help_data)

    def register_subsystem(self, name: str, description: str) -> None:
        """注册一个子系统。"""
        self._subsystems[name] = Subsystem(name, description)

    def register_subcommand(
        self,
        subsystem_name: str,
        cmd_name: str,
        help_text: str,
        handler: HandlerFunc,
        help_data: dict[str, Any] | None = None,
    ) -> None:
        """注册子系统下的子命令。

        Args:
            subsystem_name: 子系统名（需先 register_subsystem）。
            cmd_name: 子命令名（如 list, info, install）。
            help_text: 帮助文本。
            handler: 命令处理函数 (args: str, session: Session) → None。
            help_data: 三层帮助数据（apdu/diagnostic/usage）。
        """
        subsystem = self._subsystems.get(subsystem_name)
        if subsystem is None:
            raise ValueError(f"子系统 '{subsystem_name}' 未注册，请先 register_subsystem()")
        full_name = f"{subsystem_name} {cmd_name}"
        subsystem.subcommands[cmd_name] = Command(full_name, help_text, handler, help_data)

    def register_alias(
        self,
        alias: str,
        subsystem_name: str,
        subcmd_name: str,
        help_text: str | None = None,
    ) -> None:
        """注册别名映射到子系统子命令。

        别名注册为扁平命令，handler 直接指向子系统子命令的 handler。
        别名用户享受 config 注入、错误引导等高层特性。
        """
        subsystem = self._subsystems.get(subsystem_name)
        if subsystem is None:
            raise ValueError(f"子系统 '{subsystem_name}' 未注册")
        subcmd = subsystem.subcommands.get(subcmd_name)
        if subcmd is None:
            raise ValueError(
                f"子命令 '{subcmd_name}' 未注册于子系统 '{subsystem_name}'"
            )
        alias_help = help_text or f"(别名 → {subsystem_name} {subcmd_name}) {subcmd.help_text}"
        self._commands[alias] = Command(alias, alias_help, subcmd.handler, subcmd.help_data)

    # ── 查询 ──

    def get(self, name: str) -> Command | None:
        """按名称获取扁平命令，不存在返回 None。"""
        return self._commands.get(name)

    def get_subcommand(self, subsystem_name: str, cmd_name: str) -> Command | None:
        """获取子系统下的子命令。"""
        subsystem = self._subsystems.get(subsystem_name)
        if subsystem is None:
            return None
        return subsystem.subcommands.get(cmd_name)

    def all(self) -> dict[str, Command]:
        """返回所有扁平命令的副本。"""
        return dict(self._commands)

    def all_commands(self) -> dict[str, Command]:
        """返回所有扁平命令的副本（all() 的别名）。"""
        return dict(self._commands)

    def all_subsystems(self) -> dict[str, Subsystem]:
        """返回所有子系统的副本。"""
        return dict(self._subsystems)

    # ── 解析 ──

    @staticmethod
    def parse_line(line: str) -> tuple[str, str]:
        """将输入行解析为 (命令名, 参数) 元组。

        保留向后兼容。新代码应使用 execute_line()。
        """
        stripped = line.strip()
        if not stripped:
            return ("", "")
        parts = stripped.split(maxsplit=1)
        name = parts[0]
        args = parts[1] if len(parts) > 1 else ""
        return (name, args)

    # ── 执行 ──

    def execute(self, name: str, args: str, session: Session) -> None:
        """按命令名执行（兼容旧调用方式）。

        仅处理扁平命令，不处理子系统路由。
        新代码应使用 execute_line()。
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

        cmd.handler(args, session)

    def execute_line(self, line: str, session: Session) -> None:
        """解析整行输入并执行（支持子系统路由）。

        v0.4.0 新增推荐执行入口：
        - "card list" → subsystem=card, subcmd=list
        - "gp-list" → flat alias → card list handler
        - "version" → flat command
        """
        stripped = line.strip()
        if not stripped:
            return

        parts = stripped.split(maxsplit=1)
        first = parts[0]
        rest = parts[1] if len(parts) > 1 else ""

        # ── 子系统路由 ──
        if first in self._subsystems:
            self._execute_subsystem(first, rest, session)
            return

        # ── help ──
        if first == "help":
            self._do_help(rest)
            return

        # ── 扁平命令（含别名）──
        cmd = self._commands.get(first)
        if cmd is None:
            print(f"未知命令: {first}。输入 help 查看可用命令。")
            return

        cmd.handler(rest, session)

    def _execute_subsystem(
        self, subsystem_name: str, rest: str, session: Session
    ) -> None:
        """执行子系统子命令。"""
        if not rest:
            self._show_subsystem_help(subsystem_name)
            return

        sub_parts = rest.split(maxsplit=1)
        subcmd_name = sub_parts[0]
        subargs = sub_parts[1] if len(sub_parts) > 1 else ""

        subsystem = self._subsystems[subsystem_name]
        cmd = subsystem.subcommands.get(subcmd_name)
        if cmd is None:
            print(f"未知子命令: {subsystem_name} {subcmd_name}")
            print(f"输入 'help {subsystem_name}' 查看可用子命令。")
            return

        cmd.handler(subargs, session)

    # ── Help ──

    def _show_subsystem_help(self, subsystem_name: str) -> None:
        """显示子系统帮助信息。"""
        subsystem = self._subsystems.get(subsystem_name)
        if subsystem is None:
            print(f"未知子系统: {subsystem_name}")
            return
        print(f"{subsystem_name} — {subsystem.description}")
        print("子命令:")
        for name in sorted(subsystem.subcommands):
            cmd = subsystem.subcommands[name]
            print(f"  {subsystem_name} {name:<16s} {cmd.help_text}")

    def _do_help(self, topic: str) -> None:
        """处理 help 命令（支持三层帮助）。"""
        if not topic:
            self._show_all_help()
            return

        topic = topic.strip()

        # 子系统名 → 显示子系统帮助
        if topic in self._subsystems:
            self._show_subsystem_help(topic)
            return

        # 子系统子命令（如 "card list"）
        parts = topic.split(maxsplit=1)
        if len(parts) == 2 and parts[0] in self._subsystems:
            cmd = self.get_subcommand(parts[0], parts[1])
            if cmd:
                self._print_detailed_help(cmd)
                return

        # 扁平命令或别名
        cmd = self._commands.get(topic)
        if cmd:
            self._print_detailed_help(cmd)
            return

        print(f"未找到命令: {topic}")

    def _show_all_help(self) -> None:
        """显示全部帮助（子系统 + 扁平命令）。"""
        print("子系统命令:")
        for name in sorted(self._subsystems):
            subsystem = self._subsystems[name]
            count = len(subsystem.subcommands)
            print(f"  {name:<16s} {subsystem.description} ({count} 子命令)")
        print("")
        print("扁平命令 / 别名:")
        for name in sorted(self._commands):
            cmd = self._commands[name]
            print(f"  {name:<20s} {cmd.help_text}")
        print("")
        print("输入 'help <子系统名>' 查看子系统子命令")
        print("输入 'help <命令名>' 查看三层帮助（命令层 + APDU层 + 诊断层）")

    def _print_detailed_help(self, cmd: Command) -> None:
        """打印命令的三层帮助信息。"""
        print(f"{cmd.name} — {cmd.help_text}")

        help_data = cmd.help_data
        if not help_data:
            return

        # ── APDU 层 ──
        apdu_info = help_data.get("apdu")
        if apdu_info:
            gp_op = apdu_info.get("gp_op", "")
            gp_jar = apdu_info.get("gp_jar", "")
            apdu_flow = apdu_info.get("apdu_flow", [])
            if gp_op:
                print(f"\n底层 GP 操作: {gp_op}")
            if gp_jar:
                print(f"gp.jar 映射: {gp_jar}")
            if apdu_flow:
                print("APDU 流程:")
                for step in apdu_flow:
                    print(f"  {step}")

        # ── 诊断层 ──
        diagnostic = help_data.get("diagnostic")
        if diagnostic:
            print("\n常见状态字:")
            for sw, info in diagnostic.items():
                cause = info.get("cause", "")
                fix = info.get("fix", "")
                print(f"  {sw}  {cause} → {fix}")

        # ── 用法层 ──
        usage = help_data.get("usage")
        if usage:
            print("\n用法:")
            for line in usage:
                print(f"  {line}")
