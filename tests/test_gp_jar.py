"""测试 gp.jar 桥接层。"""

import json
from unittest.mock import MagicMock, patch

import pytest

from scsh.exceptions import GPBridgeError


# ── Fixtures: gp.jar 模拟输出 ──────────────────────────

GP_LIST_OUTPUT = """# GlobalPlatformPro 25.10
# Reader: ACS ACR39U 0
ISD: A000000003000000 (OP_READY)
  PKG: A0000006472F0001 (LOADED)
    Applet: A0000006472F000101 (SELECTABLE)
  PKG: A000000003000001 (LOADED)
    Applet: A00000000300000101 (SELECTABLE)
"""

GP_INFO_OUTPUT = """# GlobalPlatformPro 25.10
ISD: A000000003000000
  CPLC:
    IC Fabricator: 4799
    IC Type: 0001
    ROM Key: 0000
  GP Version: 2.1.1
  SCP: 02 (i=15)
  Key Version: 0
  Security Level: MAC
"""

GP_LIST_EMPTY_OUTPUT = """# GlobalPlatformPro 25.10
# Reader: ACS ACR39U 0
No applets found.
"""


@pytest.fixture
def mock_subprocess_run():
    """Mock subprocess.run 返回成功结果。"""
    with patch("scsh.bridge.gp_jar.subprocess.run") as mock:
        yield mock


def _make_result(stdout: str, returncode: int = 0, stderr: str = ""):
    """创建一个模拟的 subprocess.CompletedProcess。"""
    result = MagicMock()
    result.stdout = stdout
    result.stderr = stderr
    result.returncode = returncode
    return result


class TestGPJarBridgeInit:
    def test_default_jar_path(self):
        """默认查找系统路径下的 gp.jar。"""
        from scsh.bridge.gp_jar import GPJarBridge
        bridge = GPJarBridge()
        assert bridge.jar_path is not None

    def test_custom_jar_path(self):
        """可指定自定义 gp.jar 路径。"""
        from scsh.bridge.gp_jar import GPJarBridge
        bridge = GPJarBridge(jar_path="/opt/gp.jar")
        assert bridge.jar_path == "/opt/gp.jar"


class TestGPJarRun:
    def test_version_detection(self, mock_subprocess_run):
        """检测 gp.jar 版本。"""
        mock_subprocess_run.return_value = _make_result(
            "GlobalPlatformPro 25.10"
        )
        from scsh.bridge.gp_jar import GPJarBridge
        bridge = GPJarBridge(jar_path="/usr/local/bin/gp.jar")
        version = bridge.get_version()
        assert version is not None
        assert "25.10" in version

    def test_version_not_found(self, mock_subprocess_run):
        """gp.jar 找不到时抛出 GPBridgeError。"""
        mock_subprocess_run.side_effect = FileNotFoundError()
        from scsh.bridge.gp_jar import GPJarBridge
        bridge = GPJarBridge(jar_path="/nonexistent/gp.jar")
        with pytest.raises(GPBridgeError, match="找不到"):
            bridge.get_version()


class TestGPListParsing:
    def test_parse_list_output(self, mock_subprocess_run):
        """解析 gp --list 输出。"""
        mock_subprocess_run.return_value = _make_result(GP_LIST_OUTPUT)
        from scsh.bridge.gp_jar import GPJarBridge
        bridge = GPJarBridge()
        result = bridge.list()

        assert result["isd"] == "A000000003000000"
        assert len(result["packages"]) == 2
        assert result["packages"][0]["aid"] == "A0000006472F0001"
        assert result["packages"][0]["state"] == "LOADED"
        assert len(result["packages"][0]["applets"]) == 1
        assert result["packages"][0]["applets"][0]["aid"] == "A0000006472F000101"

    def test_parse_empty_list(self, mock_subprocess_run):
        """空列表返回空结构。"""
        mock_subprocess_run.return_value = _make_result(GP_LIST_EMPTY_OUTPUT)
        from scsh.bridge.gp_jar import GPJarBridge
        bridge = GPJarBridge()
        result = bridge.list()
        assert result["isd"] is None
        assert result["packages"] == []

    def test_list_command_args(self, mock_subprocess_run):
        """list 命令使用正确的参数。"""
        mock_subprocess_run.return_value = _make_result(GP_LIST_OUTPUT)
        from scsh.bridge.gp_jar import GPJarBridge
        bridge = GPJarBridge(jar_path="/opt/gp.jar")
        bridge.list()

        args = mock_subprocess_run.call_args[0][0]
        assert any(a.endswith("java") for a in args) or "java" in args
        assert "-jar" in args
        assert "/opt/gp.jar" in args
        assert "--list" in args


class TestGPInfoParsing:
    def test_parse_info_output(self, mock_subprocess_run):
        """解析 gp --info 输出。"""
        mock_subprocess_run.return_value = _make_result(GP_INFO_OUTPUT)
        from scsh.bridge.gp_jar import GPJarBridge
        bridge = GPJarBridge()
        result = bridge.info()

        assert result["scp"] == "02"
        assert result["gp_version"] == "2.1.1"
        assert result["key_version"] == "0"


class TestGPExecute:
    def test_execute_apdu(self, mock_subprocess_run):
        """发送 GP APDU 命令。"""
        mock_subprocess_run.return_value = _make_result(
            "Response: 9000"
        )
        from scsh.bridge.gp_jar import GPJarBridge
        bridge = GPJarBridge()
        result = bridge.execute_apdu("00A40400")
        assert "9000" in result

    def test_execute_failure(self, mock_subprocess_run):
        """GP 命令失败时抛出 GPBridgeError。"""
        mock_subprocess_run.return_value = _make_result(
            "Error: SCP not established", returncode=1
        )
        from scsh.bridge.gp_jar import GPJarBridge
        bridge = GPJarBridge()
        with pytest.raises(GPBridgeError, match="SCP"):
            bridge.execute_apdu("00A40400")
