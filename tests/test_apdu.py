"""测试 APDU 命令。"""

from unittest.mock import MagicMock

import pytest
from scsh.exceptions import CardDisconnectedError, TransportError


class TestSendCommand:
    def test_send_apdu(self, capsys):
        """send 命令发送 APDU 并显示响应。"""
        from scsh.commands.apdu import cmd_send
        transport = MagicMock()
        transport.send_apdu.return_value = (b"\x00" * 10, 0x9000)

        cmd_send("00A4040000", transport)
        captured = capsys.readouterr()
        assert "9000" in captured.out

    def test_send_no_args(self, capsys):
        """缺少参数时显示用法。"""
        from scsh.commands.apdu import cmd_send
        transport = MagicMock()
        cmd_send("", transport)
        captured = capsys.readouterr()
        assert "用法" in captured.out

    def test_send_invalid_hex(self, capsys):
        """无效 hex 显示错误。"""
        from scsh.commands.apdu import cmd_send
        transport = MagicMock()
        cmd_send("nothex", transport)
        captured = capsys.readouterr()
        assert "无效" in captured.out

    def test_send_not_connected(self, capsys):
        """未连接时提示。"""
        from scsh.commands.apdu import cmd_send
        transport = MagicMock()
        transport.send_apdu.side_effect = CardDisconnectedError()
        cmd_send("00A4040000", transport)
        captured = capsys.readouterr()
        assert "未连接" in captured.out


class TestSelectCommand:
    def test_select_aid(self, capsys):
        """select 命令构造 SELECT APDU 并发送。"""
        from scsh.commands.apdu import cmd_select
        transport = MagicMock()
        transport.send_apdu.return_value = (b"\x6F" * 10, 0x9000)

        cmd_select("A0000006472F0001", transport)
        captured = capsys.readouterr()
        assert "9000" in captured.out

    def test_select_no_args(self, capsys):
        """缺少 AID 时显示用法。"""
        from scsh.commands.apdu import cmd_select
        transport = MagicMock()
        cmd_select("", transport)
        captured = capsys.readouterr()
        assert "用法" in captured.out


class TestGetResponseCommand:
    def test_get_response(self, capsys):
        """get-response 命令。"""
        from scsh.commands.apdu import cmd_get_response
        transport = MagicMock()
        transport.send_apdu.return_value = (b"\x00" * 10, 0x9000)

        cmd_get_response("00", transport)
        captured = capsys.readouterr()
        assert "9000" in captured.out

    def test_get_response_no_args(self, capsys):
        """缺少 Le 时使用默认值 256。"""
        from scsh.commands.apdu import cmd_get_response
        transport = MagicMock()
        transport.send_apdu.return_value = (b"\x00" * 10, 0x9000)

        cmd_get_response("", transport)
        captured = capsys.readouterr()
        assert "9000" in captured.out


class TestSendFileCommand:
    def test_send_file(self, capsys):
        """send-file 从文件读取 APDU 并逐条发送。"""
        from scsh.commands.apdu import cmd_send_file
        transport = MagicMock()
        transport.send_apdu.return_value = (b"", 0x9000)

        with pytest.MonkeyPatch.context() as mp:
            import builtins
            mp.setattr(builtins, "open", MagicMock())
            builtins.open.return_value.__enter__.return_value = [
                "00A40400\n",
                "00C00000\n",
            ]

            cmd_send_file("test.apdu", transport)

        assert transport.send_apdu.call_count == 2

    def test_send_file_no_args(self, capsys):
        """缺少文件路径时显示用法。"""
        from scsh.commands.apdu import cmd_send_file
        transport = MagicMock()
        cmd_send_file("", transport)
        captured = capsys.readouterr()
        assert "用法" in captured.out
