"""测试 APDU 命令。"""

from unittest.mock import MagicMock, mock_open, patch

import pytest
from scsh.exceptions import CardDisconnectedError, TransportError


class TestSendCommand:
    def test_send_apdu(self, capsys):
        """send 命令发送 APDU 并显示响应。"""
        from scsh.commands.apdu import cmd_send
        session = MagicMock()
        session.transport.send_apdu.return_value = (b"\x00" * 10, 0x9000)

        cmd_send("00A4040000", session)
        captured = capsys.readouterr()
        assert "9000" in captured.out

    def test_send_no_args(self, capsys):
        """缺少参数时显示用法。"""
        from scsh.commands.apdu import cmd_send
        session = MagicMock()
        cmd_send("", session)
        captured = capsys.readouterr()
        assert "用法" in captured.out

    def test_send_invalid_hex(self, capsys):
        """无效 hex 显示错误。"""
        from scsh.commands.apdu import cmd_send
        session = MagicMock()
        cmd_send("nothex", session)
        captured = capsys.readouterr()
        assert "无效" in captured.out

    def test_send_not_connected(self, capsys):
        """未连接时提示。"""
        from scsh.commands.apdu import cmd_send
        session = MagicMock()
        session.transport.send_apdu.side_effect = CardDisconnectedError()
        cmd_send("00A4040000", session)
        captured = capsys.readouterr()
        assert "未连接" in captured.out


class TestSelectCommand:
    def test_select_aid(self, capsys):
        """select 命令构造 SELECT APDU 并发送。"""
        from scsh.commands.apdu import cmd_select
        session = MagicMock()
        session.transport.send_apdu.return_value = (b"\x6F" * 10, 0x9000)

        cmd_select("A0000006472F0001", session)
        captured = capsys.readouterr()
        assert "9000" in captured.out

    def test_select_no_args(self, capsys):
        """缺少 AID 时显示用法。"""
        from scsh.commands.apdu import cmd_select
        session = MagicMock()
        cmd_select("", session)
        captured = capsys.readouterr()
        assert "用法" in captured.out


class TestGetResponseCommand:
    def test_get_response(self, capsys):
        """get-response 命令。"""
        from scsh.commands.apdu import cmd_get_response
        session = MagicMock()
        session.transport.send_apdu.return_value = (b"\x00" * 10, 0x9000)

        cmd_get_response("00", session)
        captured = capsys.readouterr()
        assert "9000" in captured.out

    def test_get_response_no_args(self, capsys):
        """缺少 Le 时使用默认值 256。"""
        from scsh.commands.apdu import cmd_get_response
        session = MagicMock()
        session.transport.send_apdu.return_value = (b"\x00" * 10, 0x9000)

        cmd_get_response("", session)
        captured = capsys.readouterr()
        assert "9000" in captured.out


class TestSendFileCommand:
    def test_send_file(self, capsys):
        """send-file 从文件读取 APDU 并逐条发送。"""
        from scsh.commands.apdu import cmd_send_file
        session = MagicMock()
        session.transport.send_apdu.return_value = (b"", 0x9000)

        m = mock_open(read_data="00A40400\n00C00000\n")
        with patch("builtins.open", m):
            cmd_send_file("test.apdu", session)

        assert session.transport.send_apdu.call_count == 2

    def test_send_file_no_args(self, capsys):
        """缺少文件路径时显示用法。"""
        from scsh.commands.apdu import cmd_send_file
        session = MagicMock()
        cmd_send_file("", session)
        captured = capsys.readouterr()
        assert "用法" in captured.out
