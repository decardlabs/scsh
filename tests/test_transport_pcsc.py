"""测试 PC/SC 传输封装层。"""

import threading
from unittest.mock import MagicMock, patch, call

import pytest

from scsh.exceptions import (
    CardDisconnectedError,
    NoReadersError,
    TransportError,
)
from scsh.transport.pcsc import PCSCTransport


# ── Fixtures ────────────────────────────────────────────


@pytest.fixture
def mock_scard():
    """Mock 整个 smartcard.scard 模块，使用整数常量。"""
    with patch("scsh.transport.pcsc.scard") as mock:
        # SCard API 常量（整数）
        mock.SCARD_STATE_PRESENT = 0x20
        mock.SCARD_STATE_UNAWARE = 0x00
        mock.SCARD_SCOPE_USER = 0x00
        mock.SCARD_SHARE_SHARED = 0x02
        mock.SCARD_PROTOCOL_T0 = 0x01
        mock.SCARD_PROTOCOL_T1 = 0x02
        mock.SCARD_LEAVE_CARD = 0x00
        mock.SCARD_RESET_CARD = 0x01

        # 函数返回模拟值（使用 macOS 格式: (reader_name, event_state, atr)）
        mock.SCardEstablishContext.return_value = (0, 12345)
        mock.SCardListReaders.return_value = (0, ["ACS ACR39U 0", "OMNIKEY 3x21 0"])
        mock.SCardGetStatusChange.return_value = (0, [
            ("ACS ACR39U 0", 0, b""),
            ("OMNIKEY 3x21 0", 0, b""),
        ])
        mock.SCardConnect.return_value = (0, 67890, 1)
        mock.SCardTransmit.return_value = (0, b"\x00" * 10)
        mock.SCardReconnect.return_value = (0, 1)
        mock.SCardStatus.return_value = (0, "ACS ACR39U 0", 0, 1, b"\x3B\xAA\x55\x00" * 2)

        yield mock


@pytest.fixture
def transport(mock_scard):
    """已初始化的 PCSCTransport 实例。"""
    return PCSCTransport()


# ── 初始化 ──────────────────────────────────────────────


class TestInit:
    def test_establish_context(self, mock_scard):
        """初始化时建立 SCard 上下文。"""
        PCSCTransport()
        mock_scard.SCardEstablishContext.assert_called_once()

    def test_establish_context_failure(self, mock_scard):
        """上下文建立失败时抛出 TransportError。"""
        mock_scard.SCardEstablishContext.return_value = (6, None)
        with pytest.raises(TransportError, match="建立 PC/SC 上下文失败"):
            PCSCTransport()


# ── list_readers ────────────────────────────────────────


class TestListReaders:
    def test_returns_reader_list(self, transport):
        """返回读卡器列表，每项包含 name/card_present。"""
        readers = transport.list_readers()
        assert len(readers) == 2
        assert readers[0]["name"] == "ACS ACR39U 0"
        assert readers[1]["name"] == "OMNIKEY 3x21 0"

    def test_no_readers(self, mock_scard, transport):
        """无读卡器时抛出 NoReadersError。"""
        mock_scard.SCardListReaders.return_value = (0, [])
        with pytest.raises(NoReadersError):
            transport.list_readers()

    def test_card_present_detection(self, mock_scard, transport):
        """检测读卡器中是否有卡和 MUTE 状态。"""
        mock_scard.SCardGetStatusChange.return_value = (0, [
            ("ACS ACR39U 0", mock_scard.SCARD_STATE_PRESENT, b""),
            ("OMNIKEY 3x21 0", 0, b""),
        ])
        readers = transport.list_readers()
        assert readers[0]["card_present"] is True
        assert readers[1]["card_present"] is False

    def test_thread_safe(self, mock_scard, transport):
        """list_readers 使用锁保护。"""
        original_lock = transport._lock
        transport._lock = MagicMock(wraps=threading.Lock())
        transport.list_readers()
        transport._lock.__enter__.assert_called_once()


# ── connect ─────────────────────────────────────────────


class TestConnect:
    def test_connect_success(self, mock_scard, transport):
        """成功连接返回 ATR 和协议。"""
        result = transport.connect(0)
        assert "atr" in result
        assert "protocol" in result
        assert result["reader_name"] == "ACS ACR39U 0"
        mock_scard.SCardConnect.assert_called_once()

    def test_connect_out_of_range(self, mock_scard, transport):
        """越界索引抛出 IndexError。"""
        with pytest.raises(IndexError):
            transport.connect(99)

    def test_connect_already_connected(self, mock_scard, transport):
        """已连接时先断开再重新连接。"""
        transport.connect(0)
        transport.connect(1)
        # 应该调用了 disconnect 再 connect
        assert mock_scard.SCardDisconnect.called


# ── send_apdu ──────────────────────────────────────────


class TestSendAPDU:
    def test_send_and_receive(self, mock_scard, transport):
        """发送 APDU 并接收响应。"""
        transport.connect(0)
        data, sw = transport.send_apdu(b"\x00\xA4\x04\x00\x08" + b"\x00" * 8)
        assert isinstance(data, bytes)
        assert isinstance(sw, int)

    def test_not_connected(self, mock_scard, transport):
        """未连接时发送 APDU 抛出 CardDisconnectedError。"""
        with pytest.raises(CardDisconnectedError):
            transport.send_apdu(b"\x00\xA4\x04\x00\x00")

    def test_transmit_failure(self, mock_scard, transport):
        """发送失败时抛出 TransportError。"""
        transport.connect(0)
        mock_scard.SCardTransmit.return_value = (6, None)
        with pytest.raises(TransportError, match="APDU 发送失败"):
            transport.send_apdu(b"\x00\xA4\x04\x00\x00")

    def test_card_disconnected_during_send(self, mock_scard, transport):
        """发送时卡片拔出抛出 CardDisconnectedError。"""
        transport.connect(0)
        mock_scard.SCardTransmit.side_effect = Exception(
            "The smart card has been removed"
        )
        with pytest.raises(CardDisconnectedError):
            transport.send_apdu(b"\x00\xA4\x04\x00\x00")


# ── reset / reconnect ──────────────────────────────────


class TestReset:
    def test_reset_returns_atr(self, mock_scard, transport):
        """reset 返回新的 ATR。"""
        transport.connect(0)
        atr = transport.reset()
        assert isinstance(atr, bytes)

    def test_reset_not_connected(self, mock_scard, transport):
        """未连接时 reset 抛出 CardDisconnectedError。"""
        with pytest.raises(CardDisconnectedError):
            transport.reset()


class TestReconnect:
    def test_reconnect_returns_info(self, mock_scard, transport):
        """reconnect 返回重新连接信息。"""
        transport.connect(0)
        result = transport.reconnect()
        assert "atr" in result
        mock_scard.SCardReconnect.assert_called_once()

    def test_reconnect_not_connected(self, mock_scard, transport):
        """未连接时 reconnect 抛出 CardDisconnectedError。"""
        with pytest.raises(CardDisconnectedError):
            transport.reconnect()


# ── disconnect & cleanup ───────────────────────────────


class TestDisconnect:
    def test_disconnect_success(self, mock_scard, transport):
        """断开连接后可以重新连接。"""
        transport.connect(0)
        transport.disconnect()
        assert transport._card is None
        assert transport._reader_index is None
        transport.connect(0)  # Should work

    def test_disconnect_when_not_connected(self, mock_scard, transport):
        """未连接时 disconnect 不报错。"""
        transport.disconnect()  # Should not raise


class TestContextManager:
    def test_context_manager(self, mock_scard, transport):
        """支持 with 语句。"""
        transport.connect(0)
        with transport:
            data, sw = transport.send_apdu(b"\x00\xA4\x04\x00\x00")
            assert isinstance(data, bytes)

    def test_close_releases_context(self, mock_scard, transport):
        """close 释放 SCard 上下文。"""
        transport.close()
        mock_scard.SCardReleaseContext.assert_called_once()
