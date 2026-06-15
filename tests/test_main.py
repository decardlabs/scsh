"""测试入口点。"""

import sys
from unittest.mock import MagicMock, patch

import pytest


class TestMainInit:
    def test_build_registry_has_hardware_commands(self):
        """build_registry 注册 M1 硬件命令。"""
        from scsh.main import build_registry

        reg = build_registry()
        cmds = reg.all()
        assert "readers" in cmds
        assert "connect" in cmds
        assert "reconnect" in cmds
        assert "info" in cmds
        assert "reset" in cmds

    def test_main_module_imports(self):
        """main 模块可正常导入（不触发 scsh 依赖 import）。"""
        import scsh.main
        assert hasattr(scsh.main, "main")


class TestEnvironmentCheck:
    """运行环境预检。"""

    def test_check_python_packages_all_installed(self):
        """开发环境下所有 Python 包应已安装。"""
        from scsh.main import _check_python_packages
        missing = _check_python_packages()
        assert missing == [], f"缺失依赖: {missing}"

    def test_check_environment_returns_list(self):
        """check_environment 总是返回 list。"""
        from scsh.main import check_environment
        result = check_environment()
        assert isinstance(result, list)

    @patch("scsh.main._check_python_packages", return_value=["pyscard>=2.1"])
    @patch("scsh.main._check_system_services", return_value=[])
    def test_print_missing_output(self, mock_sys, mock_py, capsys):
        """print_missing 输出可读的缺失提示。"""
        from scsh.main import print_missing
        print_missing(["pyscard>=2.1"])
        captured = capsys.readouterr()
        assert "缺少运行依赖" in captured.err
        assert "pyscard" in captured.err
        assert "pip install" in captured.err

    def test_main_exits_on_missing_deps(self):
        """依赖缺失时 main() 应 exit(1)。"""
        with patch("scsh.main.check_environment", return_value=["pyscard"]), \
             patch("sys.argv", ["scsh"]):
            from scsh.main import main
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 1


class TestMainRun:
    def test_main_with_help_exits(self):
        """scsh --help 导致 SystemExit (argparse 默认行为)。"""
        from scsh.main import parse_args
        with pytest.raises(SystemExit):
            parse_args(["--help"])

    def test_main_with_file(self):
        """scsh --file 指定脚本文件。"""
        from scsh.main import parse_args
        args = parse_args(["--file", "test.scsh"])
        assert args.file == "test.scsh"

    def test_main_with_command(self):
        """scsh --command 指定单次命令。"""
        from scsh.main import parse_args
        args = parse_args(["--command", "readers"])
        assert args.command == "readers"

    def test_main_defaults(self):
        """无参数时进入交互模式。"""
        from scsh.main import parse_args
        args = parse_args([])
        assert args.file is None
        assert args.command is None


class TestScriptMode:
    """脚本模式（M5 先行测试）。"""

    def test_script_mode_executes_lines(self, capsys):
        """--file 模式逐行执行命令。"""
        from scsh.main import execute_script
        from scsh.commands import CommandRegistry

        registry = CommandRegistry()
        called = []
        registry.register("readers", "测试", lambda a, t: called.append(a))
        registry.register("info", "测试", lambda a, t: called.append(a))

        with patch("builtins.open", new_callable=MagicMock) as mock_open:
            mock_file = MagicMock()
            mock_file.__enter__.return_value = ["readers\n", "info\n"]
            mock_open.return_value = mock_file

            execute_script("dummy.scsh", registry, None)

        assert len(called) == 2

    def test_script_skips_comments(self, capsys):
        """脚本跳过注释行。"""
        from scsh.main import execute_script
        from scsh.commands import CommandRegistry

        registry = CommandRegistry()
        called = []
        registry.register("readers", "测试", lambda a, t: called.append(a))

        with patch("builtins.open", new_callable=MagicMock) as mock_open:
            mock_file = MagicMock()
            mock_file.__enter__.return_value = [
                "# 这是注释\n",
                "readers\n",
            ]
            mock_open.return_value = mock_file

            execute_script("dummy.scsh", registry, None)

        assert len(called) == 1

    def test_script_skips_empty_lines(self, capsys):
        """脚本跳过空行。"""
        from scsh.main import execute_script
        from scsh.commands import CommandRegistry

        registry = CommandRegistry()
        called = []
        registry.register("readers", "测试", lambda a, t: called.append(a))

        with patch("builtins.open", new_callable=MagicMock) as mock_open:
            mock_file = MagicMock()
            mock_file.__enter__.return_value = [
                "\n",
                "  \n",
                "readers\n",
            ]
            mock_open.return_value = mock_file

            execute_script("dummy.scsh", registry, None)

        assert len(called) == 1
