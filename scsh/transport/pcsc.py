"""PC/SC 传输封装层。

使用 pyscard (smartcard.scard) 封装 WinSCard API，提供线程安全的
读卡器连接 / 断开 / 收发 APDU 操作。
"""

from __future__ import annotations

import threading
from typing import Any

import smartcard.scard as scard

from scsh.exceptions import (
    CardDisconnectedError,
    NoReadersError,
    TransportError,
)


def _check(hresult: int, context: str = "") -> None:
    """检查 SCard API 返回码，非 0 时抛出 TransportError。"""
    if hresult != 0:
        msg = f"{context} (错误码: {hresult})" if context else f"错误码: {hresult}"
        raise TransportError(msg)


class PCSCTransport:
    """PC/SC 传输封装，线程安全。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._context: int | None = None
        self._card: int | None = None
        self._reader_index: int | None = None
        self._reader_name: str | None = None
        self._protocol: int = 0
        self._establish_context()

    # ── 内部方法 ──────────────────────────────────────────

    def _establish_context(self) -> None:
        with self._lock:
            hresult, ctx = scard.SCardEstablishContext(scard.SCARD_SCOPE_USER)
            _check(hresult, "建立 PC/SC 上下文失败")
            self._context = ctx

    def _ensure_connected(self) -> None:
        if self._card is None:
            raise CardDisconnectedError("未连接到读卡器")

    def _reader_states(self) -> list[tuple[Any, ...]]:
        """查询所有读卡器状态。"""
        assert self._context is not None
        hresult, readers = scard.SCardListReaders(self._context, [])
        if hresult != 0 or not readers:
            return []
        states = [
            (reader, scard.SCARD_STATE_UNAWARE) for reader in readers
        ]
        hresult, new_states = scard.SCardGetStatusChange(
            self._context, 0, states
        )
        if hresult != 0:
            return []
        return new_states

    def _get_atr_and_protocol(self) -> tuple[bytes, int]:
        """获取当前连接的 ATR 和协议。"""
        assert self._card is not None
        result = scard.SCardStatus(self._card)
        # SCardStatus 返回格式因平台/版本而异:
        #   (hresult, reader, state, protocol, atr) — tuple 或 list
        #   atr 可能是 bytes 或 [int, int, ...]
        if isinstance(result, (tuple, list)) and len(result) >= 4:
            hresult = result[0]
            protocol = result[3] if len(result) >= 4 else 0
            atr_raw = result[4] if len(result) >= 5 else b""
        else:
            raise TransportError(f"SCardStatus 返回格式异常: {result}")
        _check(hresult, "获取卡片状态失败")
        atr = bytes(atr_raw) if isinstance(atr_raw, (list, bytes, bytearray)) else b""
        return atr, protocol

    # ── 公共 API ──────────────────────────────────────────

    def list_readers(self) -> list[dict[str, Any]]:
        """列出所有读卡器及其状态。

        Returns:
            每项包含 name / card_present 的列表。
        """
        with self._lock:
            assert self._context is not None
            hresult, readers = scard.SCardListReaders(self._context, [])

            if hresult != 0 or not readers:
                raise NoReadersError("未检测到读卡器")

            states = self._reader_states()
            state_map: dict[str, dict] = {}
            for st in states:
                reader = st[0] if len(st) > 0 else ""
                event_state = st[2] if len(st) >= 4 else (st[1] if len(st) >= 2 else 0)
                state_map[reader] = {
                    "card_present": bool(event_state & scard.SCARD_STATE_PRESENT),
                    "muted": bool(event_state & 0x40),       # SCARD_STATE_MUTE
                    "inuse": bool(event_state & 0x08),       # SCARD_STATE_INUSE
                    "unpowered": bool(event_state & 0x04),   # SCARD_STATE_UNPOWERED
                    "event_state": event_state,
                }

            result = [
                {
                    "name": reader,
                    "card_present": state_map.get(reader, {}).get("card_present", False),
                    "muted": state_map.get(reader, {}).get("muted", False),
                    "inuse": state_map.get(reader, {}).get("inuse", False),
                    "event_state": state_map.get(reader, {}).get("event_state", 0),
                }
                for reader in readers
            ]
            return result

    def connect(self, index: int) -> dict[str, Any]:
        """连接到指定索引的读卡器。

        Args:
            index: reades() 返回列表中的索引。

        Returns:
            包含 atr / protocol / reader_name 的字典。
        """
        with self._lock:
            assert self._context is not None

            # 如果已连接，先断开
            if self._card is not None:
                scard.SCardDisconnect(self._card, scard.SCARD_LEAVE_CARD)

            # 获取读卡器列表
            hresult, readers = scard.SCardListReaders(self._context, [])
            _check(hresult, "获取读卡器列表失败")

            if index < 0 or index >= len(readers):
                raise IndexError(
                    f"读卡器索引 {index} 超出范围 (0-{len(readers) - 1})"
                )

            reader_name = readers[index]

            # 连接
            hresult, hcard, protocol = scard.SCardConnect(
                self._context,
                reader_name,
                scard.SCARD_SHARE_SHARED,
                scard.SCARD_PROTOCOL_T0 | scard.SCARD_PROTOCOL_T1,
            )
            _check(hresult, f"连接读卡器 {reader_name} 失败")

            self._card = hcard
            self._reader_index = index
            self._reader_name = reader_name
            self._protocol = protocol

            atr, _ = self._get_atr_and_protocol()

            return {
                "atr": atr,
                "protocol": protocol,
                "reader_name": reader_name,
            }

    def disconnect(self) -> None:
        """断开当前读卡器连接。"""
        with self._lock:
            if self._card is not None:
                scard.SCardDisconnect(self._card, scard.SCARD_LEAVE_CARD)
                self._card = None
                self._reader_index = None
                self._reader_name = None

    def reconnect(self) -> dict[str, Any]:
        """重新连接当前读卡器。"""
        with self._lock:
            self._ensure_connected()
            assert self._card is not None

            hresult, protocol = scard.SCardReconnect(
                self._card,
                scard.SCARD_SHARE_SHARED,
                scard.SCARD_PROTOCOL_T0 | scard.SCARD_PROTOCOL_T1,
                scard.SCARD_LEAVE_CARD,
            )
            _check(hresult, "重连失败")

            self._protocol = protocol
            atr, _ = self._get_atr_and_protocol()
            return {"atr": atr, "protocol": protocol}

    def reset(self) -> bytes:
        """冷复位卡片。

        Returns:
            新的 ATR。
        """
        with self._lock:
            self._ensure_connected()
            assert self._card is not None

            hresult, protocol = scard.SCardReconnect(
                self._card,
                scard.SCARD_SHARE_SHARED,
                scard.SCARD_PROTOCOL_T0 | scard.SCARD_PROTOCOL_T1,
                scard.SCARD_RESET_CARD,
            )
            _check(hresult, "卡片复位失败")

            self._protocol = protocol
            atr, _ = self._get_atr_and_protocol()
            return bytes(atr)

    def send_apdu(self, apdu: bytes | list[int]) -> tuple[bytes, int]:
        """发送 APDU 指令并接收响应。

        Args:
            apdu: 完整的 APDU 指令字节。

        Returns:
            (响应数据, 状态字 SW) 的元组。
        """
        with self._lock:
            self._ensure_connected()
            assert self._card is not None

            # pyscard 版本差异: 有些要求 APDU 为 list of ints
            apdu_param = list(apdu) if isinstance(apdu, (bytes, bytearray)) else apdu

            try:
                hresult, response = scard.SCardTransmit(
                    self._card, self._protocol, apdu_param
                )
            except Exception as exc:
                msg = str(exc).lower()
                if "remove" in msg or "disconnect" in msg:
                    self._card = None
                    raise CardDisconnectedError(
                        f"卡片已断开: {exc}"
                    ) from exc
                raise TransportError(f"APDU 发送失败: {exc}") from exc

            if hresult != 0:
                raise TransportError(f"APDU 发送失败 (错误码: {hresult})")

            # 响应可能是 bytes 或 list of ints
            if isinstance(response, (bytes, bytearray)):
                response_bytes = response
            elif isinstance(response, list):
                response_bytes = bytes(response)
            else:
                response_bytes = b""

            if len(response_bytes) < 2:
                return (b"", 0)

            data = response_bytes[:-2]
            sw = (response_bytes[-2] << 8) | response_bytes[-1]
            return (data, sw)

    def close(self) -> None:
        """释放所有资源。"""
        with self._lock:
            if self._card is not None:
                scard.SCardDisconnect(self._card, scard.SCARD_LEAVE_CARD)
                self._card = None
            if self._context is not None:
                scard.SCardReleaseContext(self._context)
                self._context = None

    # ── 上下文管理器 ──────────────────────────────────────

    def __enter__(self) -> PCSCTransport:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
