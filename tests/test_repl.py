"""测试 REPL 主循环。"""

from unittest.mock import MagicMock, patch

import pytest

from scsh.commands import CommandRegistry


class TestReplInit:
    def test_repl_creation(self):
        """创建 REPL 实例。"""
        reg = CommandRegistry()
        session = MagicMock()

        with patch("scsh.repl.PromptSession") as MockSession:
            from scsh.repl import ScshRepl
            repl = ScshRepl(registry=reg, session=session)
            assert repl.registry is reg
            assert repl.session is session

    def test_repl_prompt_format(self):
        """REPL 提示符格式正确。"""
        reg = CommandRegistry()
        session = MagicMock()

        with patch("scsh.repl.PromptSession"):
            from scsh.repl import ScshRepl
            repl = ScshRepl(registry=reg, session=session)
            prompt = repl._prompt()
            assert prompt.startswith("[scsh:")
            assert prompt.endswith("] > ")

    def test_prompt_shows_reader_index(self):
        """提示符显示当前读卡器索引。"""
        reg = CommandRegistry()
        session = MagicMock()
        session.transport._reader_index = 1

        with patch("scsh.repl.PromptSession"):
            from scsh.repl import ScshRepl
            repl = ScshRepl(registry=reg, session=session)
            prompt = repl._prompt()
            assert "[scsh:1]" in prompt

    def test_prompt_no_reader(self):
        """未连接读卡器时提示符用 N 表示。"""
        reg = CommandRegistry()
        session = MagicMock()
        session._reader_index = None

        with patch("scsh.repl.PromptSession"):
            from scsh.repl import ScshRepl
            repl = ScshRepl(registry=reg, session=session)
            prompt = repl._prompt()
            assert "[scsh:N]" in prompt


class TestReplCompleter:
    def test_completer_returns_command_names(self):
        """补全器返回已注册的命令名。"""
        reg = CommandRegistry()
        reg.register("readers", "列出读卡器", lambda a, t: None)
        reg.register("connect", "连接读卡器", lambda a, t: None)
        session = MagicMock()

        with patch("scsh.repl.PromptSession"):
            from scsh.repl import ScshRepl
            repl = ScshRepl(registry=reg, session=session)
            words = repl._get_completions()
            assert "readers" in words
            assert "connect" in words

    def test_completer_excludes_builtins(self):
        """补全器不返回 help/exit 以外的内部命令。"""
        reg = CommandRegistry()
        session = MagicMock()

        with patch("scsh.repl.PromptSession"):
            from scsh.repl import ScshRepl
            repl = ScshRepl(registry=reg, session=session)
            words = repl._get_completions()
            assert "help" in words
            assert "exit" in words


class TestReplExit:
    def test_exit_returns_false(self):
        """exit 命令返回 False 以退出循环。"""
        reg = CommandRegistry()
        session = MagicMock()

        with patch("scsh.repl.PromptSession"):
            from scsh.repl import ScshRepl
            repl = ScshRepl(registry=reg, session=session)
            result = repl._handle_exit("", session)
            assert result is False

    def test_quit_also_exits(self):
        """quit 也退出。"""
        reg = CommandRegistry()
        session = MagicMock()

        with patch("scsh.repl.PromptSession"):
            from scsh.repl import ScshRepl
            repl = ScshRepl(registry=reg, session=session)
            result = repl._handle_quit("", session)
            assert result is False


class TestReplIntegration:
    def test_process_line_triggers_command(self, capsys):
        """处理一行输入触发对应命令。"""
        reg = CommandRegistry()
        called = []
        def test_cmd(args, session):
            called.append(args)

        reg.register("testcmd", "测试", test_cmd)
        session = MagicMock()

        with patch("scsh.repl.PromptSession"):
            from scsh.repl import ScshRepl
            repl = ScshRepl(registry=reg, session=session)
            repl._process_line("testcmd arg1")

        assert called == ["arg1"]

    def test_process_line_unknown(self, capsys):
        """未知命令给出友好提示。"""
        reg = CommandRegistry()
        session = MagicMock()

        with patch("scsh.repl.PromptSession"):
            from scsh.repl import ScshRepl
            repl = ScshRepl(registry=reg, session=session)
            repl._process_line("unknown_cmd")

        captured = capsys.readouterr()
        assert "未知命令" in captured.out
