"""测试 GP 查询命令。"""

from unittest.mock import MagicMock

import pytest

from scsh.exceptions import GPBridgeError


class TestGPListCommand:
    def test_gp_list_success(self, capsys):
        """gp-list 显示已安装内容。"""
        from scsh.commands.gp import cmd_gp_list
        session = MagicMock()
        session.gp_bridge = MagicMock()
        session.gp_bridge.list.return_value = {
            "isd": "A000000003000000",
            "packages": [
                {
                    "aid": "A0000006472F0001",
                    "state": "LOADED",
                    "applets": [{"aid": "A0000006472F000101", "state": "SELECTABLE"}],
                },
            ],
        }

        cmd_gp_list("", session)
        captured = capsys.readouterr()
        assert "ISD" in captured.out
        assert "A000000003000000" in captured.out
        assert "A0000006472F0001" in captured.out
        assert "A0000006472F000101" in captured.out

    def test_gp_list_no_bridge(self, capsys):
        """无 bridge 时提示。"""
        from scsh.commands.gp import cmd_gp_list
        session = MagicMock()
        session.gp_bridge = None
        cmd_gp_list("", session)
        captured = capsys.readouterr()
        assert "JVM" in captured.out or "Java" in captured.out or "安装" in captured.out

    def test_gp_list_error(self, capsys):
        """GP list 失败时显示错误。"""
        from scsh.commands.gp import cmd_gp_list
        session = MagicMock()
        session.gp_bridge = MagicMock()
        session.gp_bridge.list.side_effect = GPBridgeError("连接失败")
        cmd_gp_list("", session)
        captured = capsys.readouterr()
        assert "失败" in captured.out


class TestGPInfoCommand:
    def test_gp_info_success(self, capsys):
        """gp-info 显示详细信息。"""
        from scsh.commands.gp import cmd_gp_info
        session = MagicMock()
        session.gp_bridge = MagicMock()
        session.gp_bridge.info.return_value = {
            "scp": "02",
            "gp_version": "2.1.1",
            "key_version": "0",
            "security_level": "MAC",
        }

        cmd_gp_info("", session)
        captured = capsys.readouterr()
        assert "SCP: 02" in captured.out or "02" in captured.out
        assert "2.1.1" in captured.out

    def test_gp_info_no_bridge(self, capsys):
        """无 bridge 时提示。"""
        from scsh.commands.gp import cmd_gp_info
        session = MagicMock()
        session.gp_bridge = None
        cmd_gp_info("", session)
        captured = capsys.readouterr()
        assert "JVM" in captured.out or "Java" in captured.out or "安装" in captured.out


class TestGPAliasCommand:
    def test_gp_aid_register(self, capsys):
        """gp-aid 注册别名。"""
        from scsh.commands.gp import cmd_gp_aid
        session = MagicMock()
        session.aid_aliases = {}

        cmd_gp_aid("myapp A0000006472F0001", session)
        assert session.aid_aliases["myapp"] == "A0000006472F0001"
        captured = capsys.readouterr()
        assert "myapp" in captured.out

    def test_gp_aid_no_args(self, capsys):
        """缺少参数时显示用法。"""
        from scsh.commands.gp import cmd_gp_aid
        session = MagicMock()
        cmd_gp_aid("", session)
        captured = capsys.readouterr()
        assert "用法" in captured.out


class TestGPScpCommand:
    def test_gp_scp_success(self, capsys):
        """gp-scp 显示安全通道信息。"""
        from scsh.commands.gp import cmd_gp_scp
        session = MagicMock()
        session.gp_bridge = MagicMock()
        session.gp_bridge.info.return_value = {
            "scp": "02",
            "gp_version": "2.1.1",
            "key_version": "0",
        }

        cmd_gp_scp("", session)
        captured = capsys.readouterr()
        assert "SCP" in captured.out

    def test_gp_scp_no_bridge(self, capsys):
        """无 bridge 时提示。"""
        from scsh.commands.gp import cmd_gp_scp
        session = MagicMock()
        session.gp_bridge = None
        cmd_gp_scp("", session)
        captured = capsys.readouterr()
        assert "JVM" in captured.out or "Java" in captured.out or "安装" in captured.out
