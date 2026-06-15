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

GP_INFO_OUTPUT = """# GlobalPlatformPro v25.10.20
# Running on Mac OS X 26.5.1 aarch64, Java 21.0.10 by Homebrew
CPLC: ICFabricator=0081
      ICType=0017
      OperatingSystemID=0081
      OperatingSystemReleaseDate=2243 (2022-08-31)
      OperatingSystemReleaseLevel=33C0
      ICFabricationDate=2302 (2022-10-29)
      ICSerialNumber=BEFB8A64

IIN: 42045F49494E
CIN: 4502303A
KDD: CF0A00002302BEFB8A643435
SSC: C1020005

Card Data:
Tag 6: 1.2.840.114283.1
-> Global Platform card
Tag 60: 1.2.840.114283.2.2.1.1
-> GP Version: 2.1.1
Tag 63: 1.2.840.114283.3
-> GP card is uniquely identified by the Issuer Identification Number (IIN) and Card Image Number (CIN)
Tag 6: 1.2.840.114283.4.2.85
-> GP SCP02 (i=55)
Tag 66: 1.3.6.1.4.1.42.2.110.1.2
-> JavaCard v2

Card Capabilities:
Version: 255 (0xFF) ID:   1 (0x01) type: DES3         length:  16 (factory key)
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
        assert result["jc_version"] == "JavaCard v2"
        assert result["cplc"]["ICSerialNumber"] == "BEFB8A64"
        assert result["cplc"]["ICFabricator"] == "0081"
        assert result["card_capabilities"][0]["type"] == "DES3"
        assert result["card_capabilities"][0]["length"] == 16
        # card_data 列表结构
        assert result["card_data"][0]["tag"] == "6"
        assert result["card_data"][0]["oid"] == "1.2.840.114283.1"
        assert result["card_data"][0]["desc"] == "Global Platform card"
        assert result["card_data"][1]["tag"] == "60"
        assert result["card_data"][1]["oid"] == "1.2.840.114283.2.2.1.1"
        assert result["card_data"][1]["desc"] == "GP Version: 2.1.1"
        assert result["card_data"][2]["tag"] == "63"
        assert result["card_data"][2]["desc"] == (
            "GP card is uniquely identified by the Issuer Identification "
            "Number (IIN) and Card Image Number (CIN)"
        )
        assert result["card_data"][3]["tag"] == "6"
        assert result["card_data"][3]["desc"] == "GP SCP02 (i=55)"
        assert result["card_data"][4]["tag"] == "66"
        assert result["card_data"][4]["desc"] == "JavaCard v2"

    def test_parse_list_state(self, mock_subprocess_run):
        """解析 gp --list 中的 ISD 状态。"""
        mock_subprocess_run.return_value = _make_result(GP_LIST_OUTPUT)
        from scsh.bridge.gp_jar import GPJarBridge
        bridge = GPJarBridge()
        result = bridge.list()

        assert result["isd"] == "A000000003000000"
        assert result["isd_state"] == "OP_READY"


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
