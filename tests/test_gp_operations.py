"""测试 GP 操作命令。"""

from unittest.mock import MagicMock

import pytest

from scsh.exceptions import GPBridgeError


class TestGPInstallCommand:
    def test_gp_install_success(self, capsys):
        """gp-install 安装 CAP 文件。"""
        from scsh.commands.gp import cmd_gp_install
        session = MagicMock()
        session.gp_bridge = MagicMock()
        session.gp_bridge.install.return_value = "Installation successful"

        cmd_gp_install("/path/applet.cap", session)
        captured = capsys.readouterr()
        assert "成功" in captured.out or "successful" in captured.out.lower()

    def test_gp_install_no_args(self, capsys):
        """缺少参数时显示用法。"""
        from scsh.commands.gp import cmd_gp_install
        session = MagicMock()
        cmd_gp_install("", session)
        captured = capsys.readouterr()
        assert "用法" in captured.out

    def test_gp_install_no_bridge(self, capsys):
        """无 bridge 时提示。"""
        from scsh.commands.gp import cmd_gp_install
        session = MagicMock()
        session.gp_bridge = None
        cmd_gp_install("/path/applet.cap", session)
        captured = capsys.readouterr()
        assert "Java" in captured.out or "安装" in captured.out


class TestGPDeleteCommand:
    def test_gp_delete_success(self, capsys):
        """gp-delete 删除 Applet。"""
        from scsh.commands.gp import cmd_gp_delete
        session = MagicMock()
        session.gp_bridge = MagicMock()
        session.gp_bridge.delete.return_value = "Deleted successfully"

        cmd_gp_delete("A0000006472F000101", session)
        captured = capsys.readouterr()
        assert "成功" in captured.out or "delete" in captured.out.lower()

    def test_gp_delete_no_args(self, capsys):
        """缺少 AID 时显示用法。"""
        from scsh.commands.gp import cmd_gp_delete
        session = MagicMock()
        cmd_gp_delete("", session)
        captured = capsys.readouterr()
        assert "用法" in captured.out


class TestGPLockUnlockCommand:
    def test_gp_lock_success(self, capsys):
        """gp-lock 锁定 Applet。"""
        from scsh.commands.gp import cmd_gp_lock
        session = MagicMock()
        session.gp_bridge = MagicMock()
        session.gp_bridge.lock.return_value = "Locked"

        cmd_gp_lock("A0000006472F000101", session)
        captured = capsys.readouterr()
        assert "成功" in captured.out or "lock" in captured.out.lower()

    def test_gp_unlock_success(self, capsys):
        """gp-unlock 解锁 Applet。"""
        from scsh.commands.gp import cmd_gp_unlock
        session = MagicMock()
        session.gp_bridge = MagicMock()
        session.gp_bridge.unlock.return_value = "Unlocked"

        cmd_gp_unlock("A0000006472F000101", session)
        captured = capsys.readouterr()
        assert "成功" in captured.out or "unlock" in captured.out.lower()

    def test_gp_lock_no_args(self, capsys):
        """缺少 AID 时显示用法。"""
        from scsh.commands.gp import cmd_gp_lock
        session = MagicMock()
        cmd_gp_lock("", session)
        captured = capsys.readouterr()
        assert "用法" in captured.out


class TestGPKeyCommand:
    def test_gp_key_set(self, capsys):
        """gp-key 设置密钥。"""
        from scsh.commands.gp import cmd_gp_key
        session = MagicMock()
        session.gp_bridge = MagicMock()

        cmd_gp_key("404142434445464748494A4B4C4D4E4F", session)
        captured = capsys.readouterr()
        assert "密钥" in captured.out

    def test_gp_key_no_args(self, capsys):
        """缺少密钥时显示用法。"""
        from scsh.commands.gp import cmd_gp_key
        session = MagicMock()
        cmd_gp_key("", session)
        captured = capsys.readouterr()
        assert "用法" in captured.out
