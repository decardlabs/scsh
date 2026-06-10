"""测试异常层级。"""

import pytest
from scsh.exceptions import (
    ScshError,
    TransportError,
    NoReadersError,
    CardDisconnectedError,
    CardMovedError,
    APDUError,
    InvalidHexError,
    TLVParseError,
    SWError,
    GPError,
    GPBridgeError,
    GPCryptoError,
    GPSecureChannelError,
)


class TestScshError:
    """ScshError 是所有异常的基类。"""

    def test_is_base_exception(self):
        """所有自定义异常继承自 ScshError。"""
        assert issubclass(TransportError, ScshError)
        assert issubclass(APDUError, ScshError)
        assert issubclass(GPError, ScshError)

    def test_message(self):
        """异常的 message 属性可用。"""
        err = ScshError("测试消息")
        assert str(err) == "测试消息"

    def test_default_message(self):
        """不传参时可创建异常。"""
        err = ScshError()
        assert str(err) == ""


class TestTransportError:
    """传输层异常层级。"""

    def test_inheritance(self):
        """传输异常继承 TransportError。"""
        assert issubclass(NoReadersError, TransportError)
        assert issubclass(CardDisconnectedError, TransportError)
        assert issubclass(CardMovedError, TransportError)

    @pytest.mark.parametrize("exc_cls", [
        NoReadersError,
        CardDisconnectedError,
        CardMovedError,
    ])
    def test_instantiate(self, exc_cls):
        """所有 TransportError 子类可正常实例化。"""
        err = exc_cls("test")
        assert str(err) == "test"


class TestAPDUError:
    """APDU 层异常层级。"""

    def test_inheritance(self):
        """APDU 异常继承 APDUError。"""
        assert issubclass(InvalidHexError, APDUError)
        assert issubclass(TLVParseError, APDUError)
        assert issubclass(SWError, APDUError)

    def test_sw_error_has_sw(self):
        """SWError 包含 SW 状态字属性。"""
        err = SWError("文件未找到", sw=0x6A82)
        assert err.sw == 0x6A82
        assert "文件未找到" in str(err)

    def test_sw_error_default(self):
        """SWError 默认 sw 为 0x0000。"""
        err = SWError()
        assert err.sw == 0x0000


class TestGPError:
    """GP 层异常层级。"""

    def test_inheritance(self):
        """GP 异常继承 GPError。"""
        assert issubclass(GPBridgeError, GPError)
        assert issubclass(GPCryptoError, GPError)
        assert issubclass(GPSecureChannelError, GPError)

    @pytest.mark.parametrize("exc_cls", [
        GPBridgeError,
        GPCryptoError,
        GPSecureChannelError,
    ])
    def test_instantiate(self, exc_cls):
        """所有 GPError 子类可正常实例化。"""
        err = exc_cls("test")
        assert str(err) == "test"


class TestCatchHierarchy:
    """验证按层级捕获的正确性。"""

    def test_catch_base(self):
        """捕获 ScshError 可捕获所有子类异常。"""
        for exc in [
            TransportError(),
            CardDisconnectedError(),
            APDUError(),
            SWError(sw=0x9000),
            GPError(),
        ]:
            assert isinstance(exc, ScshError)

    def test_catch_specific(self):
        """子类异常不被同层其他兄弟异常捕获。"""
        assert not isinstance(TransportError(), APDUError)
        assert not isinstance(APDUError(), GPError)
