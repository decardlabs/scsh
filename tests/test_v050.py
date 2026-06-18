"""v0.5.0 测试 — Operations 层。

测试内容：
1. card lifecycle — 状态机验证 + 各操作
2. card applet-state — SET STATUS + 状态查询
3. 不可逆操作保护 — 确认机制
4. lifecycle 自动检测 — 无参数时显示状态
5. GPJarBridge 新方法 — terminate_card + set_applet_status
"""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest

from scsh.commands._safety import (
    LIFECYCLE_STATES,
    LIFECYCLE_ACTION_MAP,
    APPLET_STATES,
    APPLET_STATE_NAMES,
    validate_transition,
    is_irreversible,
    confirm_irreversible,
    IRREVERSIBLE_OPERATIONS,
)
from scsh.commands.card import (
    cmd_card_lifecycle,
    cmd_card_applet_state,
    cmd_card_info,
    _get_current_lifecycle,
    _show_lifecycle_status,
)
from scsh.session import Session
from scsh.exceptions import GPBridgeError


# ── 辅助 ──

def _make_session(bridge=...):
    """创建测试 Session。

    bridge=... 表示使用默认 MagicMock；bridge=None 表示无 bridge。
    """
    if bridge is ...:
        bridge = MagicMock()
    return Session(
        transport=MagicMock(),
        gp_bridge=bridge,
        config_manager=None,
    )


def _mock_bridge():
    """创建 mock GPJarBridge。"""
    bridge = MagicMock()
    bridge.list.return_value = {
        "isd": "A000000151000000",
        "isd_state": "SECURED",
        "packages": [
            {
                "aid": "A0000006472F0001",
                "state": "LOADED",
                "applets": [
                    {"aid": "A0000006472F000101", "state": "SELECTABLE"},
                ],
            },
        ],
    }
    bridge.info.return_value = {
        "scp": "02",
        "gp_version": "GP 2.2.1",
        "jc_version": "JavaCard v2",
        "key_version": "1",
        "security_level": "MAC+ENC",
        "cplc": {},
        "card_data": [],
        "card_capabilities": [],
    }
    return bridge


# ── 1. 状态机验证 ──


class TestLifecycleStateMachine:
    """生命周期状态转换验证。"""

    def test_valid_transitions(self):
        """合法状态转换应该允许。"""
        # OP_READY → INITIALIZED
        ok, reason = validate_transition("OP_READY", "init")
        assert ok is True

        # INITIALIZED → SECURED
        ok, reason = validate_transition("INITIALIZED", "secure")
        assert ok is True

        # SECURED → CARD_LOCKED
        ok, reason = validate_transition("SECURED", "lock")
        assert ok is True

        # CARD_LOCKED → SECURED (unlock)
        ok, reason = validate_transition("CARD_LOCKED", "unlock")
        assert ok is True

        # CARD_LOCKED → TERMINATED
        ok, reason = validate_transition("CARD_LOCKED", "terminate")
        assert ok is True

    def test_invalid_transitions(self):
        """非法状态转换应该拒绝。"""
        # OP_READY → SECURED（不能跳过 init）
        ok, reason = validate_transition("OP_READY", "secure")
        assert ok is False
        assert "不允许" in reason

        # OP_READY → CARD_LOCKED
        ok, reason = validate_transition("OP_READY", "lock")
        assert ok is False

        # OP_READY → TERMINATED
        ok, reason = validate_transition("OP_READY", "terminate")
        assert ok is False

        # INITIALIZED → CARD_LOCKED（不能跳过 secure）
        ok, reason = validate_transition("INITIALIZED", "lock")
        assert ok is False

        # TERMINATED → 任何状态
        ok, reason = validate_transition("TERMINATED", "unlock")
        assert ok is False
        assert "终态" in reason or "无" in reason

    def test_unknown_action(self):
        """未知操作应拒绝。"""
        ok, reason = validate_transition("SECURED", "invalid_action")
        assert ok is False
        assert "未知" in reason

    def test_unknown_current_state(self):
        """未知当前状态应放行（卡片可能有非标准状态）。"""
        ok, reason = validate_transition("CUSTOM_STATE", "init")
        assert ok is True

    def test_all_actions_mapped(self):
        """所有 lifecycle action 都有目标状态映射。"""
        expected = {"init", "secure", "lock", "unlock", "terminate"}
        assert set(LIFECYCLE_ACTION_MAP.keys()) == expected


class TestLifecycleStatesData:
    """生命周期状态数据完整性。"""

    def test_all_states_have_index(self):
        """每个状态都有 index 编号。"""
        for name, info in LIFECYCLE_STATES.items():
            assert "index" in info
            assert isinstance(info["index"], int)

    def test_all_states_have_desc(self):
        """每个状态都有描述。"""
        for name, info in LIFECYCLE_STATES.items():
            assert "desc" in info
            assert len(info["desc"]) > 0

    def test_terminated_no_allowed_next(self):
        """TERMINATED 状态不允许任何转换。"""
        assert LIFECYCLE_STATES["TERMINATED"]["allowed_next"] == []


# ── 2. card lifecycle 命令 ──


class TestCardLifecycle:
    """card lifecycle 命令执行。"""

    def test_lifecycle_no_args_shows_status(self, capsys):
        """card lifecycle 无参数时显示当前状态。"""
        bridge = _mock_bridge()
        session = _make_session(bridge)

        cmd_card_lifecycle("", session)
        captured = capsys.readouterr()

        assert "SECURED" in captured.out
        assert "状态机" in captured.out
        assert "secure" in captured.out

    def test_lifecycle_init_from_op_ready(self, capsys):
        """card lifecycle init 从 OP_READY 转换。"""
        bridge = _mock_bridge()
        bridge.list.return_value["isd_state"] = "OP_READY"
        session = _make_session(bridge)

        cmd_card_lifecycle("init", session)
        captured = capsys.readouterr()

        bridge.initialize_card.assert_called_once()
        assert "✅" in captured.out
        assert "INITIALIZED" in captured.out

    def test_lifecycle_init_from_secured_allowed(self, capsys):
        """card lifecycle init 从 SECURED 允许（re-personalization）。"""
        bridge = _mock_bridge()
        bridge.list.return_value["isd_state"] = "SECURED"
        session = _make_session(bridge)

        cmd_card_lifecycle("init", session)
        captured = capsys.readouterr()

        bridge.initialize_card.assert_called_once()
        assert "✅" in captured.out

    def test_lifecycle_terminate_requires_confirm(self, capsys):
        """card lifecycle terminate 需要二次确认。"""
        bridge = _mock_bridge()
        bridge.list.return_value["isd_state"] = "CARD_LOCKED"
        session = _make_session(bridge)

        # 用户输入 "yes" 确认
        with patch("builtins.input", return_value="yes"):
            cmd_card_lifecycle("terminate", session)
        captured = capsys.readouterr()

        bridge.terminate_card.assert_called_once()
        assert "✅" in captured.out
        assert "TERMINATED" in captured.out

    def test_lifecycle_terminate_cancelled(self, capsys):
        """card lifecycle terminate 用户取消。"""
        bridge = _mock_bridge()
        bridge.list.return_value["isd_state"] = "CARD_LOCKED"
        session = _make_session(bridge)

        # 用户输入 "no" 取消
        with patch("builtins.input", return_value="no"):
            cmd_card_lifecycle("terminate", session)
        captured = capsys.readouterr()

        bridge.terminate_card.assert_not_called()
        assert "取消" in captured.out

    def test_lifecycle_lock_from_secured(self, capsys):
        """card lifecycle lock 从 SECURED 转换。"""
        bridge = _mock_bridge()
        bridge.list.return_value["isd_state"] = "SECURED"
        session = _make_session(bridge)

        with patch("builtins.input", return_value="yes"):
            cmd_card_lifecycle("lock", session)
        captured = capsys.readouterr()

        bridge.lock_card.assert_called_once()
        assert "✅" in captured.out

    def test_lifecycle_unlock_from_card_locked(self, capsys):
        """card lifecycle unlock 从 CARD_LOCKED 转换。"""
        bridge = _mock_bridge()
        bridge.list.return_value["isd_state"] = "CARD_LOCKED"
        session = _make_session(bridge)

        cmd_card_lifecycle("unlock", session)
        captured = capsys.readouterr()

        bridge.unlock_card.assert_called_once()
        assert "✅" in captured.out

    def test_lifecycle_unknown_action(self, capsys):
        """未知操作提示错误。"""
        session = _make_session()
        cmd_card_lifecycle("invalid", session)
        captured = capsys.readouterr()
        assert "未知" in captured.out

    def test_lifecycle_no_bridge(self, capsys):
        """无 bridge 时提示错误。"""
        session = _make_session(bridge=None)
        cmd_card_lifecycle("", session)
        captured = capsys.readouterr()
        assert "未就绪" in captured.out


# ── 3. 不可逆操作保护 ──


class TestIrreversibleProtection:
    """不可逆操作保护机制。"""

    def test_terminate_is_irreversible(self):
        """terminate 是不可逆操作。"""
        assert is_irreversible("terminate") is True

    def test_lock_card_is_irreversible(self):
        """lock-card 是不可逆操作。"""
        assert is_irreversible("lock-card") is True

    def test_init_not_irreversible(self):
        """init 不是不可逆操作。"""
        assert is_irreversible("init") is False

    def test_confirm_yes(self):
        """用户输入 yes 确认执行。"""
        session = _make_session()
        with patch("builtins.input", return_value="yes"):
            result = confirm_irreversible("terminate", session)
        assert result is True

    def test_confirm_no(self):
        """用户输入 no 取消操作。"""
        session = _make_session()
        with patch("builtins.input", return_value="no"):
            result = confirm_irreversible("terminate", session)
        assert result is False

    def test_confirm_eof(self):
        """EOFError（非交互模式）自动取消。"""
        session = _make_session()
        with patch("builtins.input", side_effect=EOFError):
            result = confirm_irreversible("terminate", session)
        assert result is False

    def test_confirm_keyboard_interrupt(self):
        """Ctrl-C 取消操作。"""
        session = _make_session()
        with patch("builtins.input", side_effect=KeyboardInterrupt):
            result = confirm_irreversible("terminate", session)
        assert result is False

    def test_non_defined_action_passes(self):
        """非预定义不可逆操作默认放行。"""
        assert confirm_irreversible("some-random-action", _make_session()) is True

    def test_irreversible_ops_have_warning(self):
        """所有不可逆操作都有警告文本。"""
        for name, info in IRREVERSIBLE_OPERATIONS.items():
            assert "warning" in info
            assert "⚠️" in info["warning"]


# ── 4. card applet-state ──


class TestCardAppletState:
    """card applet-state 命令执行。"""

    def test_applet_state_no_args(self, capsys):
        """无参数显示用法提示。"""
        session = _make_session()
        cmd_card_applet_state("", session)
        captured = capsys.readouterr()
        assert "用法" in captured.out

    def test_applet_state_query_only(self, capsys):
        """只给 AID 不给状态 → 查询当前状态。"""
        bridge = _mock_bridge()
        session = _make_session(bridge)

        cmd_card_applet_state("A0000006472F000101", session)
        captured = capsys.readouterr()

        assert "SELECTABLE" in captured.out
        assert "可选" in captured.out

    def test_applet_state_set_locked(self, capsys):
        """设置 Applet 为 locked。"""
        bridge = _mock_bridge()
        bridge.set_applet_status.return_value = "OK"
        session = _make_session(bridge)

        cmd_card_applet_state("A0000006472F000101 locked", session)
        captured = capsys.readouterr()

        bridge.set_applet_status.assert_called_once_with(
            "A0000006472F000101", 0x02
        )
        assert "✅" in captured.out
        assert "LOCKED" in captured.out

    def test_applet_state_set_selectable(self, capsys):
        """设置 Applet 为 selectable。"""
        bridge = _mock_bridge()
        bridge.set_applet_status.return_value = "OK"
        session = _make_session(bridge)

        cmd_card_applet_state("A0000006472F000101 selectable", session)
        captured = capsys.readouterr()

        bridge.set_applet_status.assert_called_once_with(
            "A0000006472F000101", 0x01
        )
        assert "✅" in captured.out
        assert "SELECTABLE" in captured.out

    def test_applet_state_set_blocked(self, capsys):
        """设置 Applet 为 blocked。"""
        bridge = _mock_bridge()
        bridge.set_applet_status.return_value = "OK"
        session = _make_session(bridge)

        cmd_card_applet_state("A0000006472F000101 blocked", session)
        captured = capsys.readouterr()

        bridge.set_applet_status.assert_called_once_with(
            "A0000006472F000101", 0x03
        )
        assert "✅" in captured.out
        assert "BLOCKED" in captured.out

    def test_applet_state_unknown_state(self, capsys):
        """未知 Applet 状态提示错误。"""
        session = _make_session()
        cmd_card_applet_state("AID invalid_state", session)
        captured = capsys.readouterr()
        assert "未知" in captured.out

    def test_applet_state_not_found(self, capsys):
        """Applet AID 未在卡上找到。"""
        bridge = _mock_bridge()
        session = _make_session(bridge)

        cmd_card_applet_state("A000000099999999", session)
        captured = capsys.readouterr()

        assert "未在卡片上找到" in captured.out

    def test_applet_state_bridge_error(self, capsys):
        """SET STATUS APDU 失败。"""
        bridge = _mock_bridge()
        bridge.set_applet_status.side_effect = GPBridgeError("6985")
        session = _make_session(bridge)

        cmd_card_applet_state("A0000006472F000101 locked", session)
        captured = capsys.readouterr()

        assert "❌" in captured.out
        assert "6985" in captured.out

    def test_applet_states_mapping(self):
        """Applet 状态映射完整性。"""
        assert APPLET_STATES == {"selectable": 1, "locked": 2, "blocked": 3}
        assert APPLET_STATE_NAMES == {1: "SELECTABLE", 2: "LOCKED", 3: "BLOCKED"}

    def test_applet_state_aid_alias(self, capsys):
        """AID 别名展开。"""
        bridge = _mock_bridge()
        bridge.set_applet_status.return_value = "OK"
        session = _make_session(bridge)
        session.aid_aliases = {"fido": "A0000006472F000101"}

        cmd_card_applet_state("fido locked", session)
        captured = capsys.readouterr()

        bridge.set_applet_status.assert_called_once_with(
            "A0000006472F000101", 0x02
        )


# ── 5. GPJarBridge 新方法 ──


class TestGPJarBridgeNewMethods:
    """v0.5.0 新增的 bridge 方法。"""

    def test_terminate_card(self):
        """terminate_card 方法调用正确参数。"""
        from scsh.bridge.gp_jar import GPJarBridge

        bridge = GPJarBridge.__new__(GPJarBridge)
        bridge.jar_path = "gp.jar"
        bridge._auth_key = None
        bridge._auth_scp = None
        bridge._auth_mode = None

        with patch.object(bridge, "_run", return_value="terminated") as mock_run:
            result = bridge.terminate_card()
            mock_run.assert_called_once_with("--terminate-card")
            assert result == "terminated"

    def test_set_applet_status_selectable(self):
        """set_applet_status 构建 SELECTABLE APDU。"""
        from scsh.bridge.gp_jar import GPJarBridge

        bridge = GPJarBridge.__new__(GPJarBridge)
        bridge.jar_path = "gp.jar"
        bridge._auth_key = None
        bridge._auth_scp = None
        bridge._auth_mode = None

        with patch.object(bridge, "send_secure_apdu", return_value="9000") as mock_sapdu:
            result = bridge.set_applet_status("A0000006472F000101", 0x01)
            # AID "A0000006472F000101" = 9 bytes (18 hex chars), Lc = 9 + 1 = 0x0A
            mock_sapdu.assert_called_once_with("80E602000AA0000006472F00010101")
            assert result == "9000"

    def test_set_applet_status_locked(self):
        """set_applet_status 构建 LOCKED APDU。"""
        from scsh.bridge.gp_jar import GPJarBridge

        bridge = GPJarBridge.__new__(GPJarBridge)
        bridge.jar_path = "gp.jar"
        bridge._auth_key = None
        bridge._auth_scp = None
        bridge._auth_mode = None

        with patch.object(bridge, "send_secure_apdu", return_value="9000") as mock_sapdu:
            result = bridge.set_applet_status("A0000006472F000101", 0x02)
            mock_sapdu.assert_called_once_with("80E602000AA0000006472F00010102")

    def test_set_applet_status_blocked(self):
        """set_applet_status 构建 BLOCKED APDU。"""
        from scsh.bridge.gp_jar import GPJarBridge

        bridge = GPJarBridge.__new__(GPJarBridge)
        bridge.jar_path = "gp.jar"
        bridge._auth_key = None
        bridge._auth_scp = None
        bridge._auth_mode = None

        with patch.object(bridge, "send_secure_apdu", return_value="9000") as mock_sapdu:
            result = bridge.set_applet_status("A0000006472F000101", 0x03)
            mock_sapdu.assert_called_once_with("80E602000AA0000006472F00010103")

    def test_set_applet_status_error(self):
        """set_applet_status 失败抛 GPBridgeError。"""
        from scsh.bridge.gp_jar import GPJarBridge

        bridge = GPJarBridge.__new__(GPJarBridge)
        bridge.jar_path = "gp.jar"
        bridge._auth_key = None
        bridge._auth_scp = None
        bridge._auth_mode = None

        with patch.object(bridge, "send_secure_apdu", side_effect=GPBridgeError("6985")):
            with pytest.raises(GPBridgeError, match="SET STATUS"):
                bridge.set_applet_status("A0000006472F000101", 0x02)


# ── 6. card info 三合一 ──


class TestCardInfo:
    """card info 三合一命令。"""

    def test_info_calls_bridge_info_and_list(self, capsys):
        """card info 同时调用 bridge.info() 和 bridge.list()。"""
        bridge = _mock_bridge()
        session = _make_session(bridge)

        cmd_card_info("", session)
        captured = capsys.readouterr()

        bridge.info.assert_called_once()
        bridge.list.assert_called_once()
        assert "基本信息" in captured.out
        assert "Card Status" in captured.out

    def test_info_shows_scp(self, capsys):
        """card info 输出包含 SCP 信息。"""
        bridge = _mock_bridge()
        session = _make_session(bridge)

        cmd_card_info("", session)
        captured = capsys.readouterr()

        assert "SCP" in captured.out

    def test_info_bridge_error(self, capsys):
        """card info 查询失败。"""
        bridge = MagicMock()
        bridge.info.side_effect = GPBridgeError("查询失败")
        session = _make_session(bridge)

        cmd_card_info("", session)
        captured = capsys.readouterr()

        assert "失败" in captured.out


# ── 7. lifecycle 自动检测 ──


class TestLifecycleAutoDetect:
    """lifecycle 自动检测当前状态。"""

    def test_get_current_lifecycle_secured(self):
        """查询 SECURED 状态。"""
        bridge = _mock_bridge()
        session = _make_session(bridge)

        result = _get_current_lifecycle(session)
        assert result == "SECURED"

    def test_get_current_lifecycle_op_ready(self):
        """查询 OP_READY 状态。"""
        bridge = _mock_bridge()
        bridge.list.return_value["isd_state"] = "OP_READY"
        session = _make_session(bridge)

        result = _get_current_lifecycle(session)
        assert result == "OP_READY"

    def test_get_current_lifecycle_no_bridge(self):
        """无 bridge 返回 未知。"""
        session = _make_session(bridge=None)

        result = _get_current_lifecycle(session)
        assert result == "未知"

    def test_get_current_lifecycle_bridge_error(self):
        """bridge 查询失败返回 未知。"""
        bridge = MagicMock()
        bridge.list.side_effect = GPBridgeError("fail")
        session = _make_session(bridge)

        result = _get_current_lifecycle(session)
        assert result == "未知"

    def test_show_lifecycle_status_with_allowed_transitions(self, capsys):
        """显示当前状态和允许的转换。"""
        bridge = _mock_bridge()
        bridge.list.return_value["isd_state"] = "SECURED"
        session = _make_session(bridge)

        _show_lifecycle_status(session)
        captured = capsys.readouterr()

        assert "SECURED" in captured.out
        assert "状态机" in captured.out
        # SECURED → CARD_LOCKED 和 SECURED(由 CARD_LOCKED unlock 回来)
        assert "lock" in captured.out

    def test_show_lifecycle_status_terminated(self, capsys):
        """TERMINATED 状态无可执行操作。"""
        bridge = _mock_bridge()
        bridge.list.return_value["isd_state"] = "TERMINATED"
        session = _make_session(bridge)

        _show_lifecycle_status(session)
        captured = capsys.readouterr()

        assert "TERMINATED" in captured.out
        assert "不可逆" in captured.out or "终态" in captured.out or "无可执行" in captured.out


# ── 8. gp.py 新增 terminate 命令 ──


class TestGpTerminateCard:
    """gp-terminate-card 命令。"""

    def test_cmd_gp_terminate_card_confirmed(self, capsys):
        """确认后执行终止。"""
        from scsh.commands.gp import cmd_gp_terminate_card

        bridge = MagicMock()
        session = _make_session(bridge)

        with patch("builtins.input", return_value="yes"):
            cmd_gp_terminate_card("", session)  # @gp_command 自动注入 bridge

        bridge.terminate_card.assert_called_once()
        captured = capsys.readouterr()
        assert "终止" in captured.out

    def test_cmd_gp_terminate_card_cancelled(self, capsys):
        """取消终止操作。"""
        from scsh.commands.gp import cmd_gp_terminate_card

        bridge = MagicMock()
        session = _make_session(bridge)

        with patch("builtins.input", return_value="no"):
            cmd_gp_terminate_card("", session)  # @gp_command 自动注入 bridge

        bridge.terminate_card.assert_not_called()


# ── 9. 注册和别名 ──


class TestRegistrationAndAliases:
    """v0.5.0 新增别名注册。"""

    def test_gp_terminate_card_alias_registered(self):
        """gp-terminate-card 别名已注册。"""
        from scsh.commands import CommandRegistry
        from scsh.commands.card import register_card_subsystem

        registry = CommandRegistry()
        register_card_subsystem(registry)

        cmd = registry.get("gp-terminate-card")
        assert cmd is not None
        assert "terminate" in cmd.help_text or "lifecycle" in cmd.help_text

    def test_card_lifecycle_alias_handlers_match(self):
        """gp-xxx lifecycle 别名指向同一 handler。"""
        from scsh.commands import CommandRegistry
        from scsh.commands.card import register_card_subsystem

        registry = CommandRegistry()
        register_card_subsystem(registry)

        lifecycle_cmd = registry.get_subcommand("card", "lifecycle")
        for alias_name in ["gp-init-card", "gp-secure-card", "gp-lock-card", "gp-unlock-card", "gp-terminate-card"]:
            alias_cmd = registry.get(alias_name)
            assert alias_cmd is not None
            assert alias_cmd.handler == lifecycle_cmd.handler
