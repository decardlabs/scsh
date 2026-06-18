"""测试命令注册表。

v0.7.0 update: 移除 execute()/parse_line() 遗留测试，改用 execute_line()。
"""

import pytest
from unittest.mock import MagicMock

from scsh.commands import Command, CommandRegistry, Subsystem, Session


class TestCommand:
    def test_create_command(self):
        """创建命令对象。"""
        def handler(args, session):
            return "ok"
        cmd = Command(name="test", help_text="测试命令", handler=handler)
        assert cmd.name == "test"
        assert cmd.help_text == "测试命令"
        assert cmd.handler is handler

    def test_command_repr(self):
        """命令的 repr 包含名称。"""
        cmd = Command(name="test", help_text="测试", handler=lambda a, s: "")
        assert "test" in repr(cmd)


class TestCommandRegistry:
    def test_empty_registry(self):
        """新注册表不包含任何命令。"""
        reg = CommandRegistry()
        assert reg.all() == {}

    def test_register(self):
        """注册命令后可通过名称获取。"""
        reg = CommandRegistry()
        reg.register("test", "测试命令", lambda a, s: "ok")
        cmd = reg.get("test")
        assert cmd is not None
        assert cmd.name == "test"

    def test_get_nonexistent(self):
        """获取未注册的命令返回 None。"""
        reg = CommandRegistry()
        assert reg.get("nonexistent") is None

    def test_register_duplicate(self):
        """重复注册同一名称覆盖旧命令。"""
        reg = CommandRegistry()
        reg.register("test", "原版", lambda a, s: "old")
        reg.register("test", "新版", lambda a, s: "new")
        assert reg.get("test").help_text == "新版"

    def test_register_multiple(self):
        """注册多个命令。"""
        reg = CommandRegistry()
        reg.register("cmd1", "命令1", lambda a, s: "1")
        reg.register("cmd2", "命令2", lambda a, s: "2")
        assert len(reg.all()) == 2

    def test_all_returns_copy(self):
        """all() 返回的字典是副本，修改不影响内部。"""
        reg = CommandRegistry()
        reg.register("test", "t", lambda a, s: "")
        cmds = reg.all()
        cmds["new"] = "hack"
        assert "new" not in reg.all()

    def test_execute_line_unknown(self, capsys):
        """执行未知命令打印错误。"""
        reg = CommandRegistry()
        session = MagicMock()
        reg.execute_line("unknown_cmd", session)
        captured = capsys.readouterr()
        assert "未知命令" in captured.out

    def test_execute_line_command(self, capsys):
        """执行已注册命令。"""
        reg = CommandRegistry()
        def handler(args, session):
            print(f"执行: {args}")
        reg.register("hello", "测试", handler)
        session = MagicMock()
        reg.execute_line("hello world", session)
        captured = capsys.readouterr()
        assert "执行: world" in captured.out

    def test_execute_line_empty(self, capsys):
        """空行不执行任何操作。"""
        reg = CommandRegistry()
        session = MagicMock()
        reg.execute_line("", session)
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_execute_line_whitespace_only(self, capsys):
        """仅空白行不执行任何操作。"""
        reg = CommandRegistry()
        session = MagicMock()
        reg.execute_line("   ", session)
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_execute_line_subsystem(self, capsys):
        """子系统命令路由正确。"""
        reg = CommandRegistry()
        reg.register_subsystem("card", "卡片子系统")
        def handler(args, session):
            print(f"card info: {args}")
        reg.register_subcommand("card", "info", "显示信息", handler)
        session = MagicMock()
        reg.execute_line("card info", session)
        captured = capsys.readouterr()
        assert "card info" in captured.out

    def test_execute_line_help(self, capsys):
        """help 命令列出所有已注册命令。"""
        reg = CommandRegistry()
        reg.register("readers", "列出读卡器", lambda a, s: "")
        reg.register("connect", "连接读卡器", lambda a, s: "")
        session = MagicMock()
        reg.execute_line("help", session)
        captured = capsys.readouterr()
        assert "readers" in captured.out
        assert "connect" in captured.out

    def test_execute_line_help_specific(self, capsys):
        """help <cmd> 显示该命令详情。"""
        reg = CommandRegistry()
        reg.register("send", "发送 APDU", lambda a, s: "")
        session = MagicMock()
        reg.execute_line("help send", session)
        captured = capsys.readouterr()
        assert "send" in captured.out
        assert "发送 APDU" in captured.out

    def test_execute_line_help_unknown(self, capsys):
        """help <未知命令> 提示未找到。"""
        reg = CommandRegistry()
        session = MagicMock()
        reg.execute_line("help unknown_cmd", session)
        captured = capsys.readouterr()
        assert "未找到" in captured.out
