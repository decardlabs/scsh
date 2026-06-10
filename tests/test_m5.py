"""测试 M5 辅助命令 (repeat/timing/log/config/record)。"""

import json
from unittest.mock import MagicMock, mock_open, patch

import pytest


class TestRepeatCommand:
    def test_repeat_sends_previous_apdu(self, capsys):
        """repeat 重复上一条 APDU。"""
        from scsh.commands.apdu import cmd_repeat
        transport = MagicMock()
        transport._last_apdu = b"\x00\xA4\x04\x00\x00"
        transport._last_apdu_label = "00A4040000"
        transport.send_apdu.return_value = (b"\x00" * 10, 0x9000)

        cmd_repeat("", transport)
        assert transport.send_apdu.called
        captured = capsys.readouterr()
        assert "9000" in captured.out

    def test_repeat_with_count(self, capsys):
        """repeat N 发送 N 次。"""
        from scsh.commands.apdu import cmd_repeat
        transport = MagicMock()
        transport._last_apdu = b"\x00\xA4\x04\x00\x00"
        transport._last_apdu_label = "00A4040000"
        transport.send_apdu.return_value = (b"", 0x9000)

        cmd_repeat("3", transport)
        assert transport.send_apdu.call_count == 3

    def test_repeat_no_previous(self, capsys):
        """没有上一条 APDU 时提示。"""
        from scsh.commands.apdu import cmd_repeat
        transport = MagicMock()
        transport._last_apdu = None
        cmd_repeat("", transport)
        captured = capsys.readouterr()
        assert "没有" in captured.out or "APDU" in captured.out

    def test_repeat_not_connected(self, capsys):
        """未连接时提示。"""
        from scsh.commands.apdu import cmd_repeat
        transport = MagicMock()
        transport._last_apdu = b"\x00\xA4\x04\x00\x00"
        transport.send_apdu.side_effect = Exception("卡片未连接")
        cmd_repeat("", transport)
        captured = capsys.readouterr()
        assert "失败" in captured.out or "未连接" in captured.out


class TestTimingCommand:
    def test_timing_toggle_on(self, capsys):
        """timing on 启用计时。"""
        from scsh.commands.apdu import cmd_timing
        transport = MagicMock()
        transport._timing_enabled = False

        cmd_timing("on", transport)
        assert transport._timing_enabled is True
        captured = capsys.readouterr()
        assert "启用" in captured.out or "on" in captured.out.lower()

    def test_timing_toggle_off(self, capsys):
        """timing off 关闭计时。"""
        from scsh.commands.apdu import cmd_timing
        transport = MagicMock()
        transport._timing_enabled = True

        cmd_timing("off", transport)
        assert transport._timing_enabled is False
        captured = capsys.readouterr()
        assert "关闭" in captured.out or "off" in captured.out.lower()

    def test_timing_no_args_shows_status(self, capsys):
        """无参数显示当前状态。"""
        from scsh.commands.apdu import cmd_timing
        transport = MagicMock()
        transport._timing_enabled = True

        cmd_timing("", transport)
        captured = capsys.readouterr()
        assert "启用" in captured.out or "True" in captured.out or "on" in captured.out.lower()

    def test_timing_not_connected(self, capsys):
        """无读卡器连接时也可切换。"""
        from scsh.commands.apdu import cmd_timing
        transport = MagicMock()
        transport._timing_enabled = False
        cmd_timing("on", transport)
        assert transport._timing_enabled is True


class TestLogCommand:
    def test_log_apdu_to_file(self):
        """log 记录 APDU 到文件。"""
        from scsh.formats.apdu import log_apdu
        m = mock_open()
        with patch("builtins.open", m):
            log_apdu("/tmp/apdu.log", "00A40400", b"", 0x9000)

        m.assert_called_with("/tmp/apdu.log", "a")
        handle = m()
        handle.write.assert_called()


class TestConfigCommand:
    def test_config_show(self, capsys):
        """config 显示当前配置。"""
        from scsh.commands.hardware import cmd_config
        transport = MagicMock()
        transport._config = {"default_reader": 0, "gp_key": None}
        cmd_config("", transport)
        captured = capsys.readouterr()
        assert "default_reader" in captured.out or "配置" in captured.out

    def test_config_set(self, capsys):
        """config set <key> <value> 设置配置。"""
        from scsh.commands.hardware import cmd_config
        transport = MagicMock()
        transport._config = {}
        cmd_config("set default_reader 0", transport)
        captured = capsys.readouterr()
        assert "default_reader" in captured.out or "设置" in captured.out


class TestRecordCommand:
    def test_record_session(self):
        """record 录制会话。"""
        from scsh.commands.apdu import cmd_record
        transport = MagicMock()
        transport._recording = False

        m = mock_open()
        with patch("builtins.open", m):
            cmd_record("/tmp/session.scsh", transport)

        assert transport._recording is True
        m.assert_called_with("/tmp/session.scsh", "w")

    def test_record_appends_command(self):
        """录制模式下自动追加命令到记录文件。"""
        from scsh.commands.apdu import record_apdu
        m = mock_open()
        with patch("builtins.open", m):
            record_apdu("/tmp/session.scsh", "send 00A4040000")

        handle = m()
        handle.write.assert_called_with("send 00A4040000\n")
