"""Tests for scsh.reader module."""

import pytest

from scsh.apdu import CommandApdu
from scsh.exceptions import CardConnectionError, NoReaderError
from scsh.reader import MockReader, ReaderManager


# ---------------------------------------------------------------------------
# MockReader
# ---------------------------------------------------------------------------

class TestMockReader:
    def setup_method(self):
        self.reader = MockReader(name="Test Reader", atr=bytes.fromhex("3B6F00FF"))

    def test_name(self):
        assert self.reader.name == "Test Reader"

    def test_not_connected_initially(self):
        assert self.reader.connected is False

    def test_connect_disconnect(self):
        self.reader.connect()
        assert self.reader.connected is True
        self.reader.disconnect()
        assert self.reader.connected is False

    def test_atr_when_connected(self):
        self.reader.connect()
        assert self.reader.atr == bytes.fromhex("3B6F00FF")

    def test_atr_when_not_connected_raises(self):
        with pytest.raises(CardConnectionError):
            _ = self.reader.atr

    def test_transmit_default_response(self):
        self.reader.connect()
        apdu = CommandApdu(0x00, 0xB0, 0x00, 0x00)
        resp = self.reader.transmit(apdu)
        # Default is 6D00 (INS not supported)
        assert resp.sw1 == 0x6D
        assert resp.sw2 == 0x00

    def test_transmit_canned_response(self):
        self.reader.connect()
        self.reader.add_response(0x00, 0xA4, 0x04, 0x00, data=b"\x01\x02", sw1=0x90, sw2=0x00)
        apdu = CommandApdu(0x00, 0xA4, 0x04, 0x00)
        resp = self.reader.transmit(apdu)
        assert resp.data == b"\x01\x02"
        assert resp.ok is True

    def test_transmit_not_connected_raises(self):
        apdu = CommandApdu(0x00, 0xA4, 0x04, 0x00)
        with pytest.raises(CardConnectionError):
            self.reader.transmit(apdu)


# ---------------------------------------------------------------------------
# ReaderManager (mock mode)
# ---------------------------------------------------------------------------

class TestReaderManagerMock:
    def setup_method(self):
        self.manager = ReaderManager(mock=True)

    def test_list_readers_returns_mock(self):
        readers = self.manager.list_readers()
        assert len(readers) == 1
        assert "Mock" in readers[0].name

    def test_connect_index_zero(self):
        reader = self.manager.connect(0)
        assert reader.connected is True
        assert self.manager.active is reader

    def test_connect_out_of_range(self):
        with pytest.raises(NoReaderError):
            self.manager.connect(99)

    def test_connect_by_name(self):
        reader = self.manager.connect_by_name("mock")
        assert reader.connected is True

    def test_connect_by_name_not_found(self):
        with pytest.raises(NoReaderError):
            self.manager.connect_by_name("nonexistent reader xyz")

    def test_disconnect(self):
        self.manager.connect(0)
        self.manager.disconnect()
        assert self.manager.active is None

    def test_disconnect_when_not_connected(self):
        # Should not raise
        self.manager.disconnect()

    def test_transmit_without_connection_raises(self):
        apdu = CommandApdu(0x00, 0xA4, 0x04, 0x00)
        with pytest.raises(CardConnectionError):
            self.manager.transmit(apdu)

    def test_transmit_after_connect(self):
        self.manager.connect(0)
        apdu = CommandApdu(0x00, 0xA4, 0x04, 0x00)
        resp = self.manager.transmit(apdu)
        assert resp is not None

    def test_reconnect_closes_previous(self):
        reader1 = self.manager.connect(0)
        reader2 = self.manager.connect(0)
        # After reconnecting the manager holds a fresh active reader
        assert self.manager.active is reader2
        # Old reader should be disconnected
        assert reader1.connected is False
