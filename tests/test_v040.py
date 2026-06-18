"""v0.4.0 新功能测试。

覆盖：子系统路由、别名映射、Config TOML、gp 透传、三层 Help、gp-key Bug 修复。
"""

import os
import tempfile
import pytest

from scsh.commands import Command, CommandRegistry, Subsystem
from scsh.config import ConfigManager
from scsh.session import Session


# ── 子系统路由 ──

class TestSubsystemRouting:
    """子系统二级路由测试。"""

    def setup_method(self):
        self.reg = CommandRegistry()
        self.reg.register_subsystem("card", "卡片管理子系统")
        self.reg.register_subcommand(
            "card", "list", "列出 ISD/Package/Applet", lambda a, s: print(f"card list: {a}")
        )
        self.reg.register_subcommand(
            "card", "info", "完整卡片信息", lambda a, s: print(f"card info: {a}")
        )

    def test_subsystem_subcommand_execute(self, capsys):
        """card list 通过 execute_line 执行。"""
        self.reg.execute_line("card list", None)
        captured = capsys.readouterr()
        assert "card list" in captured.out

    def test_subsystem_with_args(self, capsys):
        """card info --verbose 传递参数。"""
        self.reg.execute_line("card info --verbose", None)
        captured = capsys.readouterr()
        assert "--verbose" in captured.out

    def test_subsystem_unknown_subcmd(self, capsys):
        """card unknown 提示未知子命令。"""
        self.reg.execute_line("card unknown", None)
        captured = capsys.readouterr()
        assert "未知子命令" in captured.out

    def test_subsystem_no_subcmd_shows_help(self, capsys):
        """card（无子命令）显示子系统帮助。"""
        self.reg.execute_line("card", None)
        captured = capsys.readouterr()
        assert "卡片管理子系统" in captured.out
        assert "list" in captured.out

    def test_subsystem_not_registered_error(self):
        """注册子命令到未注册子系统抛 ValueError。"""
        with pytest.raises(ValueError, match="未注册"):
            self.reg.register_subcommand("nonexist", "list", "test", lambda a, s: None)


# ── 别名映射 ──

class TestAliasMapping:
    """别名映射测试。"""

    def setup_method(self):
        self.reg = CommandRegistry()
        self.reg.register_subsystem("card", "卡片管理子系统")
        self.reg.register_subcommand(
            "card", "list", "列出已安装", lambda a, s: print(f"card list: {a}")
        )
        self.reg.register_alias("gp-list", "card", "list")

    def test_alias_executes_subsystem_handler(self, capsys):
        """gp-list 别名调用 card list handler。"""
        self.reg.execute_line("gp-list", None)
        captured = capsys.readouterr()
        assert "card list" in captured.out

    def test_alias_with_args(self, capsys):
        """gp-list --verbose 传递参数。"""
        self.reg.execute_line("gp-list --verbose", None)
        captured = capsys.readouterr()
        assert "--verbose" in captured.out

    def test_alias_help_text(self):
        """别名 help_text 包含子系统信息。"""
        cmd = self.reg.get("gp-list")
        assert cmd is not None
        assert "card list" in cmd.help_text.lower() or "别名" in cmd.help_text

    def test_alias_not_registered_error(self):
        """注册别名到未注册子系统抛 ValueError。"""
        with pytest.raises(ValueError):
            self.reg.register_alias("gp-xxx", "nonexist", "list")

    def test_alias_subcmd_not_registered_error(self):
        """注册别名到未注册子命令抛 ValueError。"""
        with pytest.raises(ValueError):
            self.reg.register_alias("gp-xxx", "card", "nonexist")


# ── Config TOML ──

class TestConfigTOML:
    """ConfigManager TOML 配置测试。"""

    def test_empty_config(self):
        """空 ConfigManager 返回默认值。"""
        mgr = ConfigManager()
        assert mgr.get("connection.key") is None
        assert mgr.get("connection.key", "default") == "default"

    def test_set_and_get(self):
        """设置后可查询。"""
        mgr = ConfigManager()
        mgr.set("connection.key", "404142434445464748494A4B4C4D4E4F")
        assert mgr.get("connection.key") == "404142434445464748494A4B4C4D4E4F"

    def test_dot_path_set_and_get(self):
        """dot-path 设置和查询。"""
        mgr = ConfigManager()
        mgr.set("aliases.isd", "A000000151000000")
        assert mgr.get("aliases.isd") == "A000000151000000"

    def test_all_returns_merged(self):
        """all() 返回合并配置。"""
        mgr = ConfigManager()
        mgr.set("connection.key", "abc")
        merged = mgr.all()
        assert merged["connection"]["key"] == "abc"

    def test_save_and_load_global(self):
        """持久化到 TOML 文件后可重新加载。"""
        mgr = ConfigManager()
        mgr.set("connection.key", "404142434445464748494A4B4C4D4E4F")
        mgr.set("connection.scp", "02")
        mgr.set("aliases.isd", "A000000151000000")

        # 使用临时目录避免污染用户 ~/.scsh/
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.toml")
            content = mgr._format_toml(mgr.all())
            with open(config_path, "w") as f:
                f.write(content)

            # 重新加载
            mgr2 = ConfigManager()
            # 手动设置 global path
            import scsh.config as cfg_mod
            old_path = cfg_mod.GLOBAL_CONFIG_PATH
            cfg_mod.GLOBAL_CONFIG_PATH = config_path
            mgr2.load_global()
            cfg_mod.GLOBAL_CONFIG_PATH = old_path

            assert mgr2.get("connection.key") == "404142434445464748494A4B4C4D4E4F"
            assert mgr2.get("connection.scp") == "02"
            assert mgr2.get("aliases.isd") == "A000000151000000"


# ── 三层 Help ──

class TestThreeLayerHelp:
    """三层 Help 系统测试。"""

    def setup_method(self):
        self.reg = CommandRegistry()
        self.reg.register_subsystem("card", "卡片管理子系统")
        self.reg.register_subcommand(
            "card", "list", "列出 ISD/Package/Applet",
            lambda a, s: None,
            help_data={
                "apdu": {
                    "gp_op": "GET STATUS",
                    "gp_jar": "--list",
                    "apdu_flow": ["1. SELECT ISD", "2. GET STATUS"],
                },
                "diagnostic": {
                    "6A82": {"cause": "ISD 未找到", "fix": "检查卡片 AID"},
                },
                "usage": ["card list", "gp-list"],
            },
        )
        self.reg.register_alias("gp-list", "card", "list")

    def test_help_shows_all(self, capsys):
        """help 显示子系统 + 扁平命令。"""
        self.reg.execute_line("help", None)
        captured = capsys.readouterr()
        assert "子系统命令" in captured.out
        assert "card" in captured.out
        assert "扁平命令" in captured.out

    def test_help_subsystem(self, capsys):
        """help card 显示子系统帮助。"""
        self.reg.execute_line("help card", None)
        captured = capsys.readouterr()
        assert "卡片管理子系统" in captured.out
        assert "list" in captured.out

    def test_help_subsystem_subcmd(self, capsys):
        """help card list 显示三层帮助。"""
        self.reg.execute_line("help card list", None)
        captured = capsys.readouterr()
        assert "GET STATUS" in captured.out
        assert "6A82" in captured.out
        assert "gp-list" in captured.out

    def test_help_alias(self, capsys):
        """help gp-list 显示三层帮助（别名 → 同样的 help_data）。"""
        self.reg.execute_line("help gp-list", None)
        captured = capsys.readouterr()
        assert "GET STATUS" in captured.out
        assert "6A82" in captured.out


# ── gp 透传 ──

class TestGPPassthrough:
    """gp 透传命令测试。"""

    def test_passthrough_no_args(self, capsys):
        """gp 无参数显示用法。"""
        from scsh.commands.passthrough import cmd_gp_passthrough
        session = Session(transport=None, gp_bridge=None)
        cmd_gp_passthrough("", session)
        captured = capsys.readouterr()
        assert "用法" in captured.out

    def test_passthrough_no_bridge_with_args(self, capsys):
        """gp 有参数但无 bridge 时提示错误。"""
        from scsh.commands.passthrough import cmd_gp_passthrough
        session = Session(transport=None, gp_bridge=None)
        cmd_gp_passthrough("--list", session)
        captured = capsys.readouterr()
        assert "未就绪" in captured.out


# ── gp-key Bug 修复 ──

class TestGPKeyBugFix:
    """gp-key Bug 修复验证。"""

    def test_set_key_stores_in_bridge(self):
        """set_key() 后 _auth_args 包含 --key 参数。"""
        from scsh.bridge.gp_jar import GPJarBridge

        bridge = GPJarBridge(jar_path="dummy.jar")
        bridge.set_key("404142434445464748494A4B4C4D4E4F")

        auth_args = bridge._auth_args()
        assert "--key" in auth_args
        assert "404142434445464748494A4B4C4D4E4F" in auth_args

    def test_set_scp_type(self):
        """set_scp_type() 后 _auth_args 包含 --scp 参数。"""
        from scsh.bridge.gp_jar import GPJarBridge

        bridge = GPJarBridge(jar_path="dummy.jar")
        bridge.set_scp_type("02")

        auth_args = bridge._auth_args()
        assert "--scp" in auth_args
        assert "02" in auth_args

    def test_set_mode_param(self):
        """set_mode_param() 后 _auth_args 包含 --mode 参数。"""
        from scsh.bridge.gp_jar import GPJarBridge

        bridge = GPJarBridge(jar_path="dummy.jar")
        bridge.set_mode_param("MAC")

        auth_args = bridge._auth_args()
        assert "--mode" in auth_args
        assert "MAC" in auth_args

    def test_no_auth_args_when_not_set(self):
        """未设置认证参数时 _auth_args 为空。"""
        from scsh.bridge.gp_jar import GPJarBridge

        bridge = GPJarBridge(jar_path="dummy.jar")
        assert bridge._auth_args() == []

    def test_all_auth_params_combined(self):
        """key + scp + mode 同时设置。"""
        from scsh.bridge.gp_jar import GPJarBridge

        bridge = GPJarBridge(jar_path="dummy.jar")
        bridge.set_key("404142434445464748494A4B4C4D4E4F")
        bridge.set_scp_type("02")
        bridge.set_mode_param("MAC")

        auth_args = bridge._auth_args()
        assert "--key" in auth_args
        assert "--scp" in auth_args
        assert "--mode" in auth_args

    def test_config_key_injects_bridge(self, capsys):
        """config key 命令实际注入密钥到 bridge。"""
        from scsh.commands.config_cmd import cmd_config_key
        from scsh.bridge.gp_jar import GPJarBridge

        bridge = GPJarBridge(jar_path="dummy.jar")
        session = Session(transport=None, gp_bridge=bridge)

        cmd_key_hex = "404142434445464748494A4B4C4D4E4F"
        cmd_config_key(cmd_key_hex, session)

        # 验证 bridge 内部已存储密钥
        assert bridge._auth_key == cmd_key_hex
        auth_args = bridge._auth_args()
        assert "--key" in auth_args
        assert cmd_key_hex in auth_args

    def test_config_key_without_bridge(self, capsys):
        """config key 无 bridge 时仍设置 session.gp_key。"""
        from scsh.commands.config_cmd import cmd_config_key

        session = Session(transport=None, gp_bridge=None)
        cmd_key_hex = "404142434445464748494A4B4C4D4E4F"
        cmd_config_key(cmd_key_hex, session)

        assert session.gp_key == cmd_key_hex
        captured = capsys.readouterr()
        assert "密钥已设置" in captured.out


# ── build_registry 验证 ──

class TestBuildRegistry:
    """验证 build_registry 注册了所有子系统和别名。"""

    def test_registry_has_all_subsystems(self):
        """build_registry 注册 6 个子系统。"""
        from scsh.main import build_registry
        reg = build_registry()
        subsystems = reg.all_subsystems()
        assert "card" in subsystems
        assert "deploy" in subsystems
        assert "config" in subsystems
        assert "key" in subsystems
        assert "apdu" in subsystems
        assert "session" in subsystems

    def test_registry_has_gp_aliases(self):
        """build_registry 注册 gp-xxx 别名。"""
        from scsh.main import build_registry
        reg = build_registry()
        cmds = reg.all_commands()
        # 检查关键别名
        assert "gp-list" in cmds
        assert "gp-install" in cmds
        assert "gp-delete" in cmds
        assert "gp-key" in cmds
        assert "gp-aid" in cmds
        assert "gp-mode" in cmds
        assert "gp-put-key" in cmds
        assert "gp-delete-key" in cmds

    def test_registry_has_flat_commands(self):
        """build_registry 注册扁平命令。"""
        from scsh.main import build_registry
        reg = build_registry()
        cmds = reg.all_commands()
        assert "version" in cmds
        assert "gp" in cmds  # 透传命令

    def test_registry_no_gp_create(self):
        """gp-create 不在注册表中（已废弃）。"""
        from scsh.main import build_registry
        reg = build_registry()
        cmds = reg.all_commands()
        assert "gp-create" not in cmds

    def test_card_subsystem_subcommands(self):
        """card 子系统包含所有子命令。"""
        from scsh.main import build_registry
        reg = build_registry()
        card = reg.all_subsystems()["card"]
        subcmds = card.subcommands
        assert "list" in subcmds
        assert "info" in subcmds
        assert "lifecycle" in subcmds
        assert "applet-state" in subcmds
        assert "store-data" in subcmds
        assert "create-domain" in subcmds
        assert "rename-isd" in subcmds
        assert "make-selectable" in subcmds
        assert "set-cplc" in subcmds

    def test_deploy_subsystem_subcommands(self):
        """deploy 子系统包含所有子命令。"""
        from scsh.main import build_registry
        reg = build_registry()
        deploy = reg.all_subsystems()["deploy"]
        subcmds = deploy.subcommands
        assert "install" in subcmds
        assert "delete" in subcmds
        assert "load" in subcmds
        assert "provision" in subcmds
        assert "plan" in subcmds


# ── execute_line 与 execute 兼容 ──

class TestExecuteCompat:
    """验证 execute_line 和 execute 兼容性。"""

    def setup_method(self):
        self.reg = CommandRegistry()
        self.reg.register("version", "版本", lambda a, s: print(f"version: {a}"))
        self.reg.register_subsystem("card", "卡片子系统")
        self.reg.register_subcommand("card", "list", "列表", lambda a, s: print(f"card list: {a}"))
        self.reg.register_alias("gp-list", "card", "list")

    def test_execute_line_flat_command(self, capsys):
        """execute_line 处理扁平命令。"""
        self.reg.execute_line("version", None)
        assert "version" in capsys.readouterr().out

    def test_execute_line_subsystem(self, capsys):
        """execute_line 处理子系统命令。"""
        self.reg.execute_line("card list", None)
        assert "card list" in capsys.readouterr().out

    def test_execute_old_style(self, capsys):
        """旧式 execute(name, args, session) 仍可用。"""
        self.reg.execute("version", "", None)
        assert "version" in capsys.readouterr().out

    def test_execute_line_alias(self, capsys):
        """execute_line 处理别名。"""
        self.reg.execute_line("gp-list", None)
        assert "card list" in capsys.readouterr().out

    def test_execute_line_unknown(self, capsys):
        """execute_line 未知命令报错。"""
        self.reg.execute_line("unknown_cmd", None)
        assert "未知命令" in capsys.readouterr().out

    def test_execute_line_empty(self, capsys):
        """execute_line 空行不输出。"""
        self.reg.execute_line("", None)
        assert capsys.readouterr().out == ""

    def test_execute_line_help(self, capsys):
        """execute_line 处理 help。"""
        self.reg.execute_line("help", None)
        assert "子系统" in capsys.readouterr().out


# ── Session config_manager ──

class TestSessionConfigManager:
    """Session 新增 config_manager 字段。"""

    def test_session_default_config_manager_is_none(self):
        """默认 Session.config_manager 为 None。"""
        session = Session(transport=None)
        assert session.config_manager is None

    def test_session_with_config_manager(self):
        """可以传入 ConfigManager。"""
        mgr = ConfigManager()
        session = Session(transport=None, config_manager=mgr)
        assert session.config_manager is mgr
