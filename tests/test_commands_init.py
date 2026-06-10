"""测试命令注册表。"""

import pytest
from scsh.commands import Command, CommandRegistry


class TestCommand:
    def test_create_command(self):
        """创建命令对象。"""
        def handler(args, transport):
            return "ok"
        cmd = Command(name="test", help_text="测试命令", handler=handler)
        assert cmd.name == "test"
        assert cmd.help_text == "测试命令"
        assert cmd.handler is handler

    def test_command_repr(self):
        """命令的 repr 包含名称。"""
        cmd = Command(name="test", help_text="测试", handler=lambda a, t: "")
        assert "test" in repr(cmd)


class TestCommandRegistry:
    def test_empty_registry(self):
        """新注册表不包含任何命令。"""
        reg = CommandRegistry()
        assert reg.all() == {}

    def test_register(self):
        """注册命令后可通过名称获取。"""
        reg = CommandRegistry()
        reg.register("test", "测试命令", lambda a, t: "ok")
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
        reg.register("test", "原版", lambda a, t: "old")
        reg.register("test", "新版", lambda a, t: "new")
        assert reg.get("test").help_text == "新版"

    def test_register_multiple(self):
        """注册多个命令。"""
        reg = CommandRegistry()
        reg.register("cmd1", "命令1", lambda a, t: "1")
        reg.register("cmd2", "命令2", lambda a, t: "2")
        assert len(reg.all()) == 2

    def test_all_returns_copy(self):
        """all() 返回的字典是副本，修改不影响内部。"""
        reg = CommandRegistry()
        reg.register("test", "t", lambda a, t: "")
        cmds = reg.all()
        cmds["new"] = "hack"
        assert "new" not in reg.all()

    def test_execute_unknown(self, capsys):
        """执行未知命令打印错误。"""
        reg = CommandRegistry()
        reg.execute("unknown_cmd", "", None)
        captured = capsys.readouterr()
        assert "未知命令" in captured.out

    def test_execute_command(self, capsys):
        """执行已注册命令。"""
        reg = CommandRegistry()
        def handler(args, transport):
            print(f"执行: {args}")
        reg.register("hello", "测试", handler)
        reg.execute("hello", "world", None)
        captured = capsys.readouterr()
        assert "执行: world" in captured.out

    def test_execute_empty(self, capsys):
        """空行不执行任何操作。"""
        reg = CommandRegistry()
        reg.execute("", "", None)
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_execute_whitespace_only(self, capsys):
        """仅空白行不执行任何操作。"""
        reg = CommandRegistry()
        reg.execute("   ", "   ", None)
        captured = capsys.readouterr()
        assert captured.out == ""


class TestHelpSystem:
    def test_help_all(self, capsys):
        """help 命令列出所有已注册命令。"""
        reg = CommandRegistry()
        reg.register("readers", "列出读卡器", lambda a, t: "")
        reg.register("connect", "连接读卡器", lambda a, t: "")
        reg.execute("help", "", None)
        captured = capsys.readouterr()
        assert "readers" in captured.out
        assert "connect" in captured.out

    def test_help_specific(self, capsys):
        """help <cmd> 显示该命令详情。"""
        reg = CommandRegistry()
        reg.register("send", "发送 APDU", lambda a, t: "")
        reg.execute("help", "send", None)
        captured = capsys.readouterr()
        assert "send" in captured.out
        assert "发送 APDU" in captured.out

    def test_help_unknown(self, capsys):
        """help <未知命令> 提示未找到。"""
        reg = CommandRegistry()
        reg.execute("help", "unknown_cmd", None)
        captured = capsys.readouterr()
        assert "未找到" in captured.out


class TestCommandParsing:
    def test_split_name_and_args(self):
        """解析命令行为命令名和参数。"""
        reg = CommandRegistry()
        name, args = reg.parse_line("send 00A4")
        assert name == "send"
        assert args == "00A4"

    def test_split_with_extra_spaces(self):
        """多余空格不影响解析。"""
        reg = CommandRegistry()
        name, args = reg.parse_line("  connect   0  ")
        assert name == "connect"
        assert args == "0"

    def test_split_name_only(self):
        """只有命令名时 args 为空字符串。"""
        reg = CommandRegistry()
        name, args = reg.parse_line("readers")
        assert name == "readers"
        assert args == ""

    def test_empty_line(self):
        """空行返回空字符串。"""
        reg = CommandRegistry()
        assert reg.parse_line("") == ("", "")
        assert reg.parse_line("   ") == ("", "")
