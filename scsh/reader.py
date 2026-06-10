"""Smart card reader abstraction layer.

Provides a unified interface over PC/SC (via pyscard when available) and a
built-in mock backend for testing or offline use.
"""

from __future__ import annotations

import abc
from typing import List, Optional, Tuple

from scsh.apdu import CommandApdu, ResponseApdu
from scsh.exceptions import (
    CardConnectionError,
    NoCardError,
    NoReaderError,
)

# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class AbstractReader(abc.ABC):
    """Abstract base class for a smart card reader backend."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Human-readable reader name."""

    @abc.abstractmethod
    def connect(self) -> None:
        """Connect to the card in this reader."""

    @abc.abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the current card."""

    @abc.abstractmethod
    def transmit(self, apdu: CommandApdu) -> ResponseApdu:
        """Transmit *apdu* and return the response."""

    @property
    @abc.abstractmethod
    def atr(self) -> bytes:
        """Return the Answer-To-Reset bytes of the connected card."""

    @property
    @abc.abstractmethod
    def connected(self) -> bool:
        """``True`` if a card connection is currently active."""


# ---------------------------------------------------------------------------
# PC/SC backend (pyscard)
# ---------------------------------------------------------------------------

class PcscReader(AbstractReader):
    """Reader backed by a real PC/SC reader via pyscard."""

    def __init__(self, reader) -> None:  # type: ignore[annotation-unchecked]
        self._reader = reader
        self._connection = None

    @property
    def name(self) -> str:
        return str(self._reader)

    def connect(self) -> None:
        try:
            self._connection = self._reader.createConnection()
            self._connection.connect()
        except Exception as exc:
            self._connection = None
            raise CardConnectionError(f"Could not connect to card: {exc}") from exc

    def disconnect(self) -> None:
        if self._connection is not None:
            try:
                self._connection.disconnect()
            finally:
                self._connection = None

    def transmit(self, apdu: CommandApdu) -> ResponseApdu:
        if self._connection is None:
            raise CardConnectionError("Not connected – call connect() first")
        try:
            data, sw1, sw2 = self._connection.transmit(apdu.to_list())
        except Exception as exc:
            raise CardConnectionError(f"Transmit failed: {exc}") from exc
        return ResponseApdu(data=bytes(data), sw1=sw1, sw2=sw2)

    @property
    def atr(self) -> bytes:
        if self._connection is None:
            raise CardConnectionError("Not connected – call connect() first")
        return bytes(self._connection.getATR())

    @property
    def connected(self) -> bool:
        return self._connection is not None


# ---------------------------------------------------------------------------
# Mock backend (for testing / offline use)
# ---------------------------------------------------------------------------

class MockResponse:
    """A canned APDU response used by :class:`MockReader`."""

    def __init__(self, data: bytes, sw1: int = 0x90, sw2: int = 0x00) -> None:
        self.data = data
        self.sw1 = sw1
        self.sw2 = sw2


class MockReader(AbstractReader):
    """An in-memory mock reader for testing and offline demonstrations."""

    def __init__(
        self,
        name: str = "Mock Reader 0",
        atr: bytes = bytes.fromhex("3B6F00FF4A434F5033315632"),
    ) -> None:
        self._name = name
        self._atr = atr
        self._connected = False
        # Map (cla, ins, p1, p2) -> MockResponse
        self._responses: dict[Tuple[int, int, int, int], MockResponse] = {}
        self._default_response = MockResponse(b"", 0x6D, 0x00)  # INS not supported

    @property
    def name(self) -> str:
        return self._name

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def add_response(
        self,
        cla: int,
        ins: int,
        p1: int,
        p2: int,
        data: bytes,
        sw1: int = 0x90,
        sw2: int = 0x00,
    ) -> None:
        """Register a canned response for a specific command header."""
        self._responses[(cla, ins, p1, p2)] = MockResponse(data, sw1, sw2)

    def transmit(self, apdu: CommandApdu) -> ResponseApdu:
        if not self._connected:
            raise CardConnectionError("Not connected – call connect() first")
        key = (apdu.cla, apdu.ins, apdu.p1, apdu.p2)
        resp = self._responses.get(key, self._default_response)
        return ResponseApdu(data=resp.data, sw1=resp.sw1, sw2=resp.sw2)

    @property
    def atr(self) -> bytes:
        if not self._connected:
            raise CardConnectionError("Not connected – call connect() first")
        return self._atr

    @property
    def connected(self) -> bool:
        return self._connected


# ---------------------------------------------------------------------------
# Reader manager
# ---------------------------------------------------------------------------

class ReaderManager:
    """Manages the available readers and the active connection.

    Automatically uses pyscard when available; falls back to mock mode
    if the ``SCSH_MOCK`` environment variable is set or pyscard is absent.
    """

    def __init__(self, *, mock: bool = False) -> None:
        self._mock = mock
        self._active: Optional[AbstractReader] = None

    # ------------------------------------------------------------------
    # Listing readers
    # ------------------------------------------------------------------

    def list_readers(self) -> List[AbstractReader]:
        """Return a list of available readers."""
        if self._mock:
            return [MockReader()]
        readers = self._pcsc_readers()
        if readers is None:
            return [MockReader()]
        return [PcscReader(r) for r in readers]

    @staticmethod
    def _pcsc_readers():
        """Return raw pyscard readers or None if pyscard is unavailable."""
        try:
            from smartcard.System import readers as sc_readers
            return sc_readers()
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Active reader
    # ------------------------------------------------------------------

    @property
    def active(self) -> Optional[AbstractReader]:
        """Currently connected reader, or ``None``."""
        return self._active

    def connect(self, index: int = 0) -> AbstractReader:
        """Connect to the reader at *index* in the list returned by
        :meth:`list_readers`.

        Disconnects any existing active connection first.
        """
        if self._active is not None and self._active.connected:
            self._active.disconnect()

        readers = self.list_readers()
        if not readers:
            raise NoReaderError("No smart card readers found")
        if index >= len(readers):
            raise NoReaderError(
                f"Reader index {index} out of range (found {len(readers)} reader(s))"
            )
        reader = readers[index]
        reader.connect()
        self._active = reader
        return reader

    def connect_by_name(self, name: str) -> AbstractReader:
        """Connect to the first reader whose name contains *name* (case-insensitive)."""
        readers = self.list_readers()
        needle = name.lower()
        for reader in readers:
            if needle in reader.name.lower():
                reader.connect()
                self._active = reader
                return reader
        raise NoReaderError(f"No reader matching {name!r} found")

    def disconnect(self) -> None:
        """Disconnect the active reader."""
        if self._active is not None:
            self._active.disconnect()
            self._active = None

    def transmit(self, apdu: CommandApdu) -> ResponseApdu:
        """Transmit *apdu* via the active reader."""
        if self._active is None or not self._active.connected:
            raise CardConnectionError("No active card connection")
        return self._active.transmit(apdu)
