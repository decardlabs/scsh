"""统一异常层级。

所有 scsh 异常继承自 ScshError，从 Transport/APDU/GP 三个维度展开。
REPL 层可通过捕获 ScshError 统一处理所有已知错误。"""


class ScshError(Exception):
    """scsh 所有异常的基类。"""

    def __init__(self, message: str = "") -> None:
        self.message = message
        super().__init__(message)


# ── 传输层 ──────────────────────────────────────────────


class TransportError(ScshError):
    """PC/SC 传输层异常基类。"""


class NoReadersError(TransportError):
    """未检测到读卡器。"""


class CardDisconnectedError(TransportError):
    """卡片在操作中断开连接。"""


class CardMovedError(TransportError):
    """卡片被移除或移动到其他读卡器。"""


# ── APDU 层 ─────────────────────────────────────────────


class APDUError(ScshError):
    """APDU 协议层异常基类。"""


class InvalidHexError(APDUError):
    """无效的十六进制输入。"""


class TLVParseError(APDUError):
    """BER-TLV 解析错误。"""


class SWError(APDUError):
    """APDU 响应中的状态字不为 0x9000。

    Attributes:
        sw: 响应中的 2 字节状态字。
    """

    def __init__(self, message: str = "", *, sw: int = 0x0000) -> None:
        self.sw = sw
        super().__init__(message)


# ── GP 层 ───────────────────────────────────────────────


class GPError(ScshError):
    """GlobalPlatform 协议层异常基类。"""


class GPBridgeError(GPError):
    """gp.jar 桥接执行错误。"""


class GPCryptoError(GPError):
    """GP 加密/解密错误。"""


class GPSecureChannelError(GPError):
    """GP 安全通道建立或通信错误。"""
