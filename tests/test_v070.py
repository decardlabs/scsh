"""v0.7.0 UX 层测试。

覆盖：
1. ScshCompleter 层级补全（第一词/第二词/上下文）
2. AID/路径上下文补全
3. APDU history/replay/search
4. SW 自动引导（extract_sw_from_error / sw_guidance / sw_tip）
5. Session.apdu_history ApduRecord
"""

from __future__ import annotations

import time
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from scsh.commands import CommandRegistry, Command, Subsystem
from scsh.session import Session, ApduRecord
from scsh.commands._sw_guidance import (
    extract_sw_from_error, sw_guidance, sw_tip, ALL_HELP_DATA,
)
from scsh.commands.apdu_history import (
    cmd_apdu_history, cmd_apdu_replay, cmd_apdu_search, record_apdu,
)


# ── 辅助 ──

def _make_session(**overrides) -> Session:
    """创建测试 Session，transport/bridge 用 MagicMock。"""
    defaults = {
        "transport": MagicMock(),
        "gp_bridge": MagicMock(),
        "config_manager": MagicMock(),
    }
    defaults.update(overrides)
    return Session(**defaults)


def _make_registry() -> CommandRegistry:
    """创建带基本子系统结构的测试 registry。"""
    registry = CommandRegistry()
    registry.register_subsystem("card", "卡片管理子系统")
    registry.register_subsystem("deploy", "部署管理子系统")
    registry.register_subsystem("apdu", "APDU 交互子系统")
    registry.register_subsystem("config", "配置子系统")
    registry.register_subsystem("key", "密钥子系统")
    registry.register_subsystem("session", "会话子系统")

    # 注册一些子命令
    registry.register_subcommand("card", "list", "列出", MagicMock())
    registry.register_subcommand("card", "info", "信息", MagicMock())
    registry.register_subcommand("card", "lifecycle", "生命周期", MagicMock())
    registry.register_subcommand("deploy", "install", "安装", MagicMock())
    registry.register_subcommand("deploy", "delete", "删除", MagicMock())
    registry.register_subcommand("deploy", "load", "加载", MagicMock())
    registry.register_subcommand("apdu", "send", "发送", MagicMock())
    registry.register_subcommand("apdu", "select", "选择", MagicMock())
    registry.register_subcommand("apdu", "history", "历史", MagicMock())
    registry.register_subcommand("apdu", "replay", "重放", MagicMock())
    registry.register_subcommand("apdu", "search", "搜索", MagicMock())

    # 注册别名
    registry.register_alias("gp-list", "card", "list")
    registry.register_alias("gp-install", "deploy", "install")
    registry.register_alias("gp-delete", "deploy", "delete")
    registry.register("gp", "gp透传", MagicMock())
    registry.register("version", "版本", MagicMock())

    return registry


# ── ScshCompleter 测试 ──

class TestScshCompleter:
    """ScshCompleter 层级补全测试。"""

    def test_complete_first_word_subsystem(self):
        """第一词补全：子系统名。"""
        from scsh.repl import ScshCompleter
        registry = _make_registry()
        session = _make_session()
        completer = ScshCompleter(registry, session)

        # 模拟 document
        doc = MagicMock()
        doc.text_before_cursor = "car"
        event = MagicMock()

        completions = list(completer.get_completions(doc, event))
        texts = [c.text for c in completions]
        assert "card" in texts

    def test_complete_first_word_alias(self):
        """第一词补全：别名。"""
        from scsh.repl import ScshCompleter
        registry = _make_registry()
        session = _make_session()
        completer = ScshCompleter(registry, session)

        doc = MagicMock()
        doc.text_before_cursor = "gp-"
        event = MagicMock()

        completions = list(completer.get_completions(doc, event))
        texts = [c.text for c in completions]
        assert "gp-list" in texts
        assert "gp-install" in texts

    def test_complete_first_word_help_exit_quit(self):
        """第一词补全：help/exit/quit。"""
        from scsh.repl import ScshCompleter
        registry = _make_registry()
        session = _make_session()
        completer = ScshCompleter(registry, session)

        doc = MagicMock()
        doc.text_before_cursor = "h"
        event = MagicMock()

        completions = list(completer.get_completions(doc, event))
        texts = [c.text for c in completions]
        assert "help" in texts

    def test_complete_subsystem_subcommand(self):
        """子系统上下文 → 补全子命令名。"""
        from scsh.repl import ScshCompleter
        registry = _make_registry()
        session = _make_session()
        completer = ScshCompleter(registry, session)

        # 输入 "card li" → 补全 "list"
        doc = MagicMock()
        doc.text_before_cursor = "card li"
        event = MagicMock()

        completions = list(completer.get_completions(doc, event))
        texts = [c.text for c in completions]
        assert "list" in texts

    def test_complete_flat_gp_passthrough(self):
        """gp 透传命令 → 补全 gp.jar 选项。"""
        from scsh.repl import ScshCompleter
        registry = _make_registry()
        session = _make_session()
        completer = ScshCompleter(registry, session)

        doc = MagicMock()
        doc.text_before_cursor = "gp --l"
        event = MagicMock()

        completions = list(completer.get_completions(doc, event))
        texts = [c.text for c in completions]
        assert "--list" in texts
        assert "--load" in texts

    def test_complete_aid_commands(self):
        """AID 相关命令 → 补全已知 AID。"""
        from scsh.repl import ScshCompleter
        registry = _make_registry()
        session = _make_session()
        # 添加 AID 别名
        session.aid_aliases = {"isd": "A000000003000000"}
        completer = ScshCompleter(registry, session)

        # deploy delete 后补全 AID
        doc = MagicMock()
        doc.text_before_cursor = "deploy delete "
        event = MagicMock()

        completions = list(completer.get_completions(doc, event))
        texts = [c.text for c in completions]
        assert "A000000003000000" in texts


# ── APDU History 测试 ──

class TestApduHistory:
    """apdu history/replay/search 测试。"""

    def test_apdu_history_empty(self, capsys):
        """空历史。"""
        session = _make_session()
        cmd_apdu_history("", session)
        captured = capsys.readouterr()
        assert "APDU 历史为空" in captured.out

    def test_apdu_history_show_recent(self, capsys):
        """显示最近 20 条。"""
        session = _make_session()
        for i in range(25):
            record_apdu(session, f"00A4040000{i:02X}", "9000", "test")

        cmd_apdu_history("", session)
        captured = capsys.readouterr()
        assert "最近 20 条" in captured.out
        assert "共 25 条" in captured.out

    def test_apdu_history_show_n(self, capsys):
        """显示最近 N 条。"""
        session = _make_session()
        for i in range(30):
            record_apdu(session, f"00A404{i:04X}0000", "9000", "test")

        cmd_apdu_history("5", session)
        captured = capsys.readouterr()
        assert "最近 5 条" in captured.out

    def test_apdu_history_show_all(self, capsys):
        """显示全部。"""
        session = _make_session()
        for i in range(5):
            record_apdu(session, f"APDU{i}", "9000", "test")

        cmd_apdu_history("--all", session)
        captured = capsys.readouterr()
        assert "最近 5 条" in captured.out

    def test_apdu_replay_last(self, capsys):
        """重放最后一条。"""
        session = _make_session()
        record_apdu(session, "00A4040000A000", "9000", "select")
        record_apdu(session, "80E60200010203", "6985", "applet-state")

        # Mock apdu send
        with patch("scsh.commands.apdu.cmd_send") as mock_send:
            cmd_apdu_replay("last", session)
            mock_send.assert_called_once_with("80E60200010203", session)

        captured = capsys.readouterr()
        assert "重放 #2" in captured.out

    def test_apdu_replay_by_index(self, capsys):
        """重放指定编号。"""
        session = _make_session()
        record_apdu(session, "00A4040000A000", "9000", "select")
        record_apdu(session, "80E60200010203", "6985", "applet-state")

        with patch("scsh.commands.apdu.cmd_send") as mock_send:
            cmd_apdu_replay("1", session)
            mock_send.assert_called_once_with("00A4040000A000", session)

    def test_apdu_replay_invalid_index(self, capsys):
        """无效编号。"""
        session = _make_session()
        record_apdu(session, "APDU1", "9000", "test")

        cmd_apdu_replay("99", session)
        captured = capsys.readouterr()
        assert "不存在" in captured.out

    def test_apdu_search_by_keyword(self, capsys):
        """搜索关键词。"""
        session = _make_session()
        record_apdu(session, "00A4040000A000000151000000", "9000", "card list")
        record_apdu(session, "80E6020001A000", "6985", "applet-state")
        record_apdu(session, "00A4040000A000", "6A82", "apdu select")

        cmd_apdu_search("6985", session)
        captured = capsys.readouterr()
        assert "匹配 1 条" in captured.out
        assert "6985" in captured.out

    def test_apdu_search_no_match(self, capsys):
        """搜索无匹配。"""
        session = _make_session()
        record_apdu(session, "APDU1", "9000", "test")

        cmd_apdu_search("NONEXIST", session)
        captured = capsys.readouterr()
        assert "未找到" in captured.out

    def test_apdu_search_by_context(self, capsys):
        """搜索上下文。"""
        session = _make_session()
        record_apdu(session, "00A40400", "9000", "card list")
        record_apdu(session, "80E602", "9000", "deploy install")

        cmd_apdu_search("card", session)
        captured = capsys.readouterr()
        assert "匹配 1 条" in captured.out


# ── SW 自动引导测试 ──

class TestSwGuidance:
    """SW 自动引导测试。"""

    def test_extract_sw_6985(self):
        """提取 SW 6985。"""
        assert extract_sw_from_error("gp.jar 执行失败: 6985") == "6985"

    def test_extract_sw_0x6a82(self):
        """提取 0x6A82 格式。"""
        assert extract_sw_from_error("returned 0x6A82") == "6A82"

    def test_extract_sw_in_brackets(self):
        """提取括号中的 SW。"""
        assert extract_sw_from_error("INSTALL [for install] (6985)") == "6985"

    def test_extract_sw_no_match(self):
        """无 SW 匹配。"""
        assert extract_sw_from_error("general error") is None

    def test_sw_guidance_known_sw(self):
        """已知 SW 的诊断引导。"""
        result = sw_guidance("6985")
        assert result is not None
        assert "6985" in result

    def test_sw_guidance_with_context(self):
        """指定上下文的诊断引导。"""
        result = sw_guidance("6985", "card list")
        assert result is not None
        assert "安全条件不满足" in result

    def test_sw_guidance_unknown_sw(self):
        """未知 SW 无引导。"""
        result = sw_guidance("FFFF")
        assert result is None

    def test_sw_tip_prints_guidance(self, capsys):
        """sw_tip 打印引导。"""
        exc = Exception("gp.jar 执行失败: 6985")
        sw_tip(exc, "card list")
        captured = capsys.readouterr()
        assert "💡" in captured.out
        assert "6985" in captured.out

    def test_sw_tip_no_sw(self, capsys):
        """无 SW 时不打印。"""
        exc = Exception("general error")
        sw_tip(exc)
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_sw_guidance_deploy_install_6438(self):
        """deploy install 的 6438 引导。"""
        result = sw_guidance("6438", "deploy install")
        assert result is not None
        assert "包依赖未找到" in result

    def test_sw_guidance_card_list_6a82(self):
        """card list 的 6A82 引导。"""
        result = sw_guidance("6A82", "card list")
        assert result is not None
        assert "ISD 未找到" in result


# ── ApduRecord 测试 ──

class TestApduRecord:
    """ApduRecord dataclass 测试。"""

    def test_apdu_record_creation(self):
        """创建 ApduRecord。"""
        rec = ApduRecord(
            index=1,
            apdu="00A4040000A000",
            response="9000",
            context="card list",
            timestamp=time.time(),
        )
        assert rec.index == 1
        assert rec.apdu == "00A4040000A000"
        assert rec.response == "9000"
        assert rec.context == "card list"

    def test_session_has_apdu_history(self):
        """Session 包含 apdu_history 字段。"""
        session = _make_session()
        assert hasattr(session, "apdu_history")
        assert isinstance(session.apdu_history, list)
        assert len(session.apdu_history) == 0

    def test_record_apdu_adds_to_history(self):
        """record_apdu 添加到 session.apdu_history。"""
        session = _make_session()
        record_apdu(session, "00A4040000", "9000", "test")
        assert len(session.apdu_history) == 1
        assert session.apdu_history[0].index == 1
        assert session.apdu_history[0].apdu == "00A4040000"

    def test_record_apdu_sequential_index(self):
        """record_apdu 序号递增。"""
        session = _make_session()
        record_apdu(session, "APDU1", "9000", "test")
        record_apdu(session, "APDU2", "6985", "test")
        assert session.apdu_history[0].index == 1
        assert session.apdu_history[1].index == 2


# ── 上下文感知补全辅助函数 ──

class TestContextHelpers:
    """补全辅助函数测试。"""

    def test_get_known_aids_from_config(self):
        """从 config aliases 收集 AID。"""
        from scsh.repl import _get_known_aids
        session = _make_session()
        session.config_manager = MagicMock()
        session.config_manager.get = MagicMock(return_value={"isd": "A000000003000000"})
        aids = _get_known_aids(session)
        assert "A000000003000000" in aids

    def test_get_known_aids_from_session(self):
        """从 session aliases 收集 AID。"""
        from scsh.repl import _get_known_aids
        session = _make_session()
        session.aid_aliases = {"pkg": "A0000006472F0001"}
        aids = _get_known_aids(session)
        assert "A0000006472F0001" in aids
