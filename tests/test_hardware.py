"""测试硬件命令。"""

from unittest.mock import MagicMock

import pytest

from scsh.exceptions import NoReadersError, CardDisconnectedError, TransportError


class TestReadersCommand:
    def test_readers_lists_readers(self, capsys):
        """readers 命令列出读卡器。"""
        from scsh.commands.hardware import cmd_readers
        session = MagicMock()
        session.transport.list_readers.return_value = [
            {"name": "Reader 1", "card_present": True, "muted": False, "event_state": 0x20},
            {"name": "Reader 2", "card_present": False, "muted": False, "event_state": 0},
        ]
        cmd_readers("", session)
        captured = capsys.readouterr()
        assert "Reader 1" in captured.out
        assert "Reader 2" in captured.out
        assert "✅" in captured.out

    def test_readers_no_readers(self, capsys):
        """无读卡器时显示友好消息。"""
        from scsh.commands.hardware import cmd_readers
        session = MagicMock()
        session.transport.list_readers.side_effect = NoReadersError("未检测到读卡器")
        cmd_readers("", session)
        captured = capsys.readouterr()
        assert "未检测到" in captured.out or "读卡器" in captured.out

    def test_readers_empty_list(self, capsys):
        """空列表时显示提示。"""
        from scsh.commands.hardware import cmd_readers
        session = MagicMock()
        session.transport.list_readers.return_value = []
        cmd_readers("", session)
        captured = capsys.readouterr()
        assert "没有" in captured.out or "读卡器" in captured.out


class TestConnectCommand:
    def test_connect_success(self, capsys):
        """连接成功显示 ATR 和协议。"""
        from scsh.commands.hardware import cmd_connect
        session = MagicMock()
        session.transport.connect.return_value = {
            "atr": b"\x3B\xAA\x55\x00",
            "protocol": 2,
            "reader_name": "Reader 1",
        }
        cmd_connect("0", session)
        captured = capsys.readouterr()
        assert "Reader 1" in captured.out
        assert "3B" in captured.out

    def test_connect_no_args(self, capsys):
        """缺少参数时显示用法。"""
        from scsh.commands.hardware import cmd_connect
        session = MagicMock()
        cmd_connect("", session)
        captured = capsys.readouterr()
        assert "用法" in captured.out

    def test_connect_invalid_index(self, capsys):
        """非数字参数提示。"""
        from scsh.commands.hardware import cmd_connect
        session = MagicMock()
        cmd_connect("abc", session)
        captured = capsys.readouterr()
        assert "数字" in captured.out

    def test_connect_failure(self, capsys):
        """连接失败显示错误。"""
        from scsh.commands.hardware import cmd_connect
        session = MagicMock()
        session.transport.connect.side_effect = TransportError("连接失败: SCARD_E_NO_SMARTCARD")
        cmd_connect("0", session)
        captured = capsys.readouterr()
        assert "失败" in captured.out or "Error" in captured.out


class TestInfoCommand:
    def test_info_shows_atr(self, capsys):
        """info 显示卡片信息。"""
        from scsh.commands.hardware import cmd_info
        session = MagicMock()
        session.transport._get_atr_and_protocol = MagicMock(return_value=(b"\x3B\xAA\x55", 1))
        session.transport._reader_name = "Reader 1"
        session.transport._reader_index = 0

        cmd_info("", session)
        captured = capsys.readouterr()
        assert "Reader 1" in captured.out
        assert "3B" in captured.out

    def test_info_not_connected(self, capsys):
        """未连接时提示。"""
        from scsh.commands.hardware import cmd_info
        session = MagicMock()
        session.transport._get_atr_and_protocol.side_effect = CardDisconnectedError()
        session.transport._reader_name = None

        cmd_info("", session)
        captured = capsys.readouterr()
        assert "未连接" in captured.out


class TestResetCommand:
    def test_reset_success(self, capsys):
        """复位成功显示新 ATR。"""
        from scsh.commands.hardware import cmd_reset
        session = MagicMock()
        session.transport.reset.return_value = b"\x3B\x00\x00\x01"

        cmd_reset("", session)
        captured = capsys.readouterr()
        assert "3B" in captured.out

    def test_reset_not_connected(self, capsys):
        """未连接时提示。"""
        from scsh.commands.hardware import cmd_reset
        session = MagicMock()
        session.transport.reset.side_effect = CardDisconnectedError()

        cmd_reset("", session)
        captured = capsys.readouterr()
        assert "未连接" in captured.out


class TestReconnectCommand:
    def test_reconnect_success(self, capsys):
        """重连成功显示信息。"""
        from scsh.commands.hardware import cmd_reconnect
        session = MagicMock()
        session.transport.reconnect.return_value = {
            "atr": b"\x3B\xAA\x55",
            "protocol": 2,
        }

        cmd_reconnect("", session)
        captured = capsys.readouterr()
        assert "3B" in captured.out

    def test_reconnect_error(self, capsys):
        """重连失败提示。"""
        from scsh.commands.hardware import cmd_reconnect
        session = MagicMock()
        session.transport.reconnect.side_effect = CardDisconnectedError()

        cmd_reconnect("", session)
        captured = capsys.readouterr()
        assert "未连接" in captured.out or "失败" in captured.out
