"""v0.6.0 Deployment 测试。

覆盖：
- Profile TOML 解析
- diff_profile_vs_card 差异计算
- deploy install 参数解析
- deploy plan 输出
- deploy provision dry-run/step 模式
"""

from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

from scsh.session import Session
from scsh.profile import Profile, PackageSpec, ProfileError, diff_profile_vs_card


# ── 辅助 ──


def _make_session(bridge=None):
    """创建测试 Session。"""
    return Session(
        transport=MagicMock(),
        gp_bridge=bridge,
        config_manager=None,
    )


def _write_toml(content: str, path: str) -> None:
    """写入 TOML 文件。"""
    with open(path, "w") as f:
        f.write(content)


# ── Profile 解析测试 ──


class TestProfileParsing:
    """Profile TOML 文件解析。"""

    def test_basic_profile(self):
        """解析基本 Profile。"""
        toml_content = """
[card]
isd_aid = "A000000151000000"
scp = "02"
key = "404142434445464748494A4B4C4D4E4F"

[packages.helloworld]
cap = "my-applet/build/javacard/my-applet.cap"
aid = "com.example.HelloWorld"
applet_aid = "com.example.HelloWorld"
default = false

[aliases]
isd = "A000000151000000"
"""
        with tempfile.NamedTemporaryFile(suffix=".toml", mode="w", delete=False) as f:
            f.write(toml_content)
            path = f.name

        try:
            profile = Profile.from_toml(path)
            assert profile.isd_aid == "A000000151000000"
            assert len(profile.packages) == 1
            assert profile.packages[0].name == "helloworld"
            assert profile.packages[0].cap == "my-applet/build/javacard/my-applet.cap"
            assert profile.packages[0].aid == "com.example.HelloWorld"
            assert profile.packages[0].default is False
            assert profile.aliases.get("isd") == "A000000151000000"
        finally:
            os.unlink(path)

    def test_multi_package_profile(self):
        """解析多个 Package 的 Profile。"""
        toml_content = """
[card]
isd_aid = "A000000151000000"

[packages.fido2]
cap = "FIDO2Applet/build/FIDO2Applet.cap"
aid = "A0000006472F0001"
applet_aid = "A0000006472F000101"
params = "0102"

[packages.helloworld]
cap = "my-applet/build/javacard/my-applet.cap"
aid = "com.example.HelloWorld"
privs = "CREATABLE"
default = true
force = true
"""
        with tempfile.NamedTemporaryFile(suffix=".toml", mode="w", delete=False) as f:
            f.write(toml_content)
            path = f.name

        try:
            profile = Profile.from_toml(path)
            assert len(profile.packages) == 2
            assert profile.packages[0].name == "fido2"
            assert profile.packages[0].params == "0102"
            assert profile.packages[1].name == "helloworld"
            assert profile.packages[1].privs == "CREATABLE"
            assert profile.packages[1].default is True
            assert profile.packages[1].force is True
        finally:
            os.unlink(path)

    def test_missing_cap_field(self):
        """缺少 cap 字段报错。"""
        toml_content = """
[card]
isd_aid = "A000000151000000"

[packages.broken]
aid = "A0000006472F0001"
"""
        with tempfile.NamedTemporaryFile(suffix=".toml", mode="w", delete=False) as f:
            f.write(toml_content)
            path = f.name

        try:
            with pytest.raises(ProfileError, match="缺少 cap"):
                Profile.from_toml(path)
        finally:
            os.unlink(path)

    def test_missing_file(self):
        """Profile 文件不存在。"""
        with pytest.raises(ProfileError, match="不存在"):
            Profile.from_toml("/nonexistent/scsh.toml")

    def test_use_config_reference(self):
        """use_config 引用 Config 配置名。"""
        toml_content = """
[card]
isd_aid = "A000000151000000"
use_config = "production"

[packages.test]
cap = "test.cap"
"""
        with tempfile.NamedTemporaryFile(suffix=".toml", mode="w", delete=False) as f:
            f.write(toml_content)
            path = f.name

        try:
            profile = Profile.from_toml(path)
            assert profile.use_config == "production"
        finally:
            os.unlink(path)


class TestProfileResolvePaths:
    """CAP 路径解析。"""

    def test_absolute_path(self):
        """绝对路径不变。"""
        pkg = PackageSpec(name="test", cap="/tmp/test.cap")
        profile = Profile()
        result = profile.resolve_cap_path(pkg, "/project")
        assert result == "/tmp/test.cap"

    def test_relative_path(self):
        """相对路径基于项目目录。"""
        pkg = PackageSpec(name="test", cap="build/test.cap")
        profile = Profile()
        result = profile.resolve_cap_path(pkg, "/project")
        assert result == "/project/build/test.cap"


# ── diff_profile_vs_card 测试 ──


class TestDiffProfileVsCard:
    """Profile vs 卡片状态差异计算。"""

    def test_empty_card_all_install(self):
        """空卡片 → 全部需安装。"""
        profile = Profile()
        profile.packages = [
            PackageSpec(name="hw", cap="hw.cap", aid="A00001"),
            PackageSpec(name="fido", cap="fido.cap", aid="A00002"),
        ]

        card_state = {"isd": "A000000151000000", "packages": []}
        diffs = diff_profile_vs_card(profile, card_state)

        assert len(diffs) == 2
        assert diffs[0]["action"] == "+"
        assert diffs[1]["action"] == "+"

    def test_existing_package_skip(self):
        """已有包 → 跳过。"""
        profile = Profile()
        profile.packages = [
            PackageSpec(name="hw", cap="hw.cap", aid="A00001"),
        ]

        card_state = {
            "isd": "A000000151000000",
            "packages": [
                {"aid": "A00001", "state": "LOADED", "applets": []},
            ],
        }
        diffs = diff_profile_vs_card(profile, card_state)

        assert len(diffs) == 1
        assert diffs[0]["action"] == "="

    def test_unknown_package_on_card(self):
        """卡片上有但 Profile 没有 → 待审核。"""
        profile = Profile()
        profile.packages = []

        card_state = {
            "isd": "A000000151000000",
            "packages": [
                {"aid": "A00001", "state": "LOADED", "applets": []},
            ],
        }
        diffs = diff_profile_vs_card(profile, card_state)

        assert len(diffs) == 1
        assert diffs[0]["action"] == "?"
        assert diffs[0]["aid"] == "A00001"

    def test_javacard_base_packages_not_flagged(self):
        """javacard.* 基础包不算待审核。"""
        profile = Profile()
        profile.packages = []

        card_state = {
            "isd": "A000000151000000",
            "packages": [
                {"aid": "A0000000620102", "state": "LOADED", "applets": []},
                {"aid": "A0000000620201", "state": "LOADED", "applets": []},
            ],
        }
        diffs = diff_profile_vs_card(profile, card_state)

        assert len(diffs) == 0

    def test_mixed_scenario(self):
        """混合场景：部分安装、部分存在、部分未知。"""
        profile = Profile()
        profile.packages = [
            PackageSpec(name="hw", cap="hw.cap", aid="A00001"),
            PackageSpec(name="new", cap="new.cap", aid="A00003"),
        ]

        card_state = {
            "isd": "A000000151000000",
            "packages": [
                {"aid": "A00001", "state": "LOADED", "applets": []},
                {"aid": "A00002", "state": "LOADED", "applets": []},
            ],
        }
        diffs = diff_profile_vs_card(profile, card_state)

        actions = {d["action"] for d in diffs}
        assert "=" in actions  # hw 已存在
        assert "+" in actions  # new 需安装
        assert "?" in actions  # A00002 未知


# ── deploy install 参数解析测试 ──


class TestDeployInstallArgParsing:
    """deploy install 参数解析。"""

    def test_basic_args(self):
        """基本参数解析。"""
        from scsh.commands.deploy import _parse_install_args
        result = _parse_install_args("my-applet.cap")
        assert result["cap_path"] == "my-applet.cap"
        assert result["force"] is False
        assert result["step"] is False

    def test_full_args(self):
        """完整参数解析。"""
        from scsh.commands.deploy import _parse_install_args
        result = _parse_install_args(
            "my-applet.cap --params 0102 --privs CREATABLE --default --force --step"
        )
        assert result["cap_path"] == "my-applet.cap"
        assert result["params"] == "0102"
        assert result["privs"] == "CREATABLE"
        assert result["default"] is True
        assert result["force"] is True
        assert result["step"] is True

    def test_load_only(self):
        """--load-only 参数。"""
        from scsh.commands.deploy import _parse_install_args
        result = _parse_install_args("my-applet.cap --load-only")
        assert result["load_only"] is True

    def test_install_only_with_applet(self):
        """--install-only 需 --applet。"""
        from scsh.commands.deploy import _parse_install_args
        result = _parse_install_args("my-applet.cap --install-only --applet A00001")
        assert result["install_only"] is True
        assert result["applet_aid"] == "A00001"

    def test_empty_args(self):
        """空参数返回空 dict。"""
        from scsh.commands.deploy import _parse_install_args
        result = _parse_install_args("")
        assert result == {}


# ── deploy install 功能测试 ──


class TestDeployInstallExecution:
    """deploy install 执行逻辑。"""

    def test_standard_install(self, capsys):
        """标准安装模式。"""
        from scsh.commands.deploy import cmd_deploy_install

        bridge = MagicMock()
        bridge.install.return_value = "success"
        session = _make_session(bridge)

        # 需要 CAP 文件存在才能测试
        with tempfile.NamedTemporaryFile(suffix=".cap", delete=False) as f:
            cap_path = f.name

        try:
            cmd_deploy_install(cap_path, session)
            bridge.install.assert_called_once()
            captured = capsys.readouterr()
            assert "安装成功" in captured.out
        finally:
            os.unlink(cap_path)

    def test_force_mode_delete_first(self, capsys):
        """--force 模式先删除再装。"""
        from scsh.commands.deploy import cmd_deploy_install

        bridge = MagicMock()
        bridge.delete.return_value = "deleted"
        bridge.install.return_value = "success"
        session = _make_session(bridge)

        with tempfile.NamedTemporaryFile(suffix=".cap", delete=False) as f:
            cap_path = f.name

        try:
            cmd_deploy_install(f"{cap_path} --force --applet A00001", session)
            bridge.delete.assert_called_once_with("A00001")
            bridge.install.assert_called_once()
            captured = capsys.readouterr()
            assert "force" in captured.out
        finally:
            os.unlink(cap_path)

    def test_load_only(self, capsys):
        """--load-only 仅加载。"""
        from scsh.commands.deploy import cmd_deploy_install

        bridge = MagicMock()
        bridge.load.return_value = "loaded"
        session = _make_session(bridge)

        with tempfile.NamedTemporaryFile(suffix=".cap", delete=False) as f:
            cap_path = f.name

        try:
            cmd_deploy_install(f"{cap_path} --load-only", session)
            bridge.load.assert_called_once_with(cap_path)
            captured = capsys.readouterr()
            assert "已加载" in captured.out
        finally:
            os.unlink(cap_path)

    def test_nonexistent_cap(self, capsys):
        """CAP 文件不存在时报错。"""
        from scsh.commands.deploy import cmd_deploy_install

        bridge = MagicMock()
        session = _make_session(bridge)

        cmd_deploy_install("/nonexistent.cap", session)
        bridge.install.assert_not_called()
        captured = capsys.readouterr()
        assert "不存在" in captured.out


# ── deploy plan 测试 ──


class TestDeployPlan:
    """deploy plan 输出。"""

    def test_plan_with_profile(self, capsys):
        """有 Profile 时显示差异。"""
        from scsh.commands.deploy import cmd_deploy_plan

        toml_content = """
[card]
isd_aid = "A000000151000000"

[packages.hw]
cap = "hw.cap"
aid = "A00001"
"""
        with tempfile.NamedTemporaryFile(suffix=".toml", mode="w", delete=False) as f:
            f.write(toml_content)
            toml_path = f.name

        bridge = MagicMock()
        bridge.list.return_value = {
            "isd": "A000000151000000",
            "packages": [],
        }
        session = _make_session(bridge)

        # patch _find_profile_path
        with patch("scsh.commands.deploy._find_profile_path", return_value=toml_path):
            cmd_deploy_plan("", session)

        captured = capsys.readouterr()
        assert "[Plan]" in captured.out

        os.unlink(toml_path)

    def test_plan_no_profile(self, capsys):
        """没有 Profile 时提示创建。"""
        from scsh.commands.deploy import cmd_deploy_plan

        bridge = MagicMock()
        session = _make_session(bridge)

        with patch("scsh.commands.deploy._find_profile_path", return_value=None):
            cmd_deploy_plan("", session)

        captured = capsys.readouterr()
        assert "未找到" in captured.out


# ── deploy provision 测试 ──


class TestDeployProvision:
    """deploy provision 自动编排。"""

    def test_dry_run(self, capsys):
        """--dry-run 只显示计划。"""
        from scsh.commands.deploy import cmd_deploy_provision

        toml_content = """
[card]
isd_aid = "A000000151000000"

[packages.hw]
cap = "hw.cap"
aid = "A00001"
"""
        with tempfile.NamedTemporaryFile(suffix=".toml", mode="w", delete=False) as f:
            f.write(toml_content)
            toml_path = f.name

        bridge = MagicMock()
        bridge.list.return_value = {
            "isd": "A000000151000000",
            "packages": [],
        }
        session = _make_session(bridge)

        with patch("scsh.commands.deploy._find_profile_path", return_value=toml_path):
            cmd_deploy_provision("--dry-run", session)

        captured = capsys.readouterr()
        assert "[Provision]" in captured.out
        assert "dry-run" in captured.out
        bridge.install.assert_not_called()  # dry-run 不执行

        os.unlink(toml_path)

    def test_all_already_installed(self, capsys):
        """全部已存在时无需操作。"""
        from scsh.commands.deploy import cmd_deploy_provision

        toml_content = """
[card]
isd_aid = "A000000151000000"

[packages.hw]
cap = "hw.cap"
aid = "A00001"
"""
        with tempfile.NamedTemporaryFile(suffix=".toml", mode="w", delete=False) as f:
            f.write(toml_content)
            toml_path = f.name

        bridge = MagicMock()
        bridge.list.return_value = {
            "isd": "A000000151000000",
            "packages": [{"aid": "A00001", "state": "LOADED", "applets": []}],
        }
        session = _make_session(bridge)

        with patch("scsh.commands.deploy._find_profile_path", return_value=toml_path):
            cmd_deploy_provision("", session)

        captured = capsys.readouterr()
        assert "已存在" in captured.out
        bridge.install.assert_not_called()

        os.unlink(toml_path)

    def test_no_profile(self, capsys):
        """没有 Profile 时提示创建。"""
        from scsh.commands.deploy import cmd_deploy_provision

        bridge = MagicMock()
        session = _make_session(bridge)

        with patch("scsh.commands.deploy._find_profile_path", return_value=None):
            cmd_deploy_provision("", session)

        captured = capsys.readouterr()
        assert "未找到" in captured.out


# ── pytest import ──

import pytest
