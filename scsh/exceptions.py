"""Custom exceptions for scsh."""


class ScshError(Exception):
    """Base class for all scsh errors."""


class NoReaderError(ScshError):
    """Raised when no smart card reader is available."""


class NoCardError(ScshError):
    """Raised when no card is present in the reader."""


class CardConnectionError(ScshError):
    """Raised when a connection to the card cannot be established."""


class ApduError(ScshError):
    """Raised when an APDU transaction fails."""

    def __init__(self, message: str, sw1: int = 0, sw2: int = 0) -> None:
        super().__init__(message)
        self.sw1 = sw1
        self.sw2 = sw2

    @property
    def sw(self) -> int:
        """Combined status word as a 16-bit integer."""
        return (self.sw1 << 8) | self.sw2

    def __str__(self) -> str:
        return f"{super().__str__()} (SW: {self.sw1:02X} {self.sw2:02X})"


class ScriptError(ScshError):
    """Raised when a script file cannot be parsed or executed."""

    def __init__(self, message: str, line: int = 0) -> None:
        super().__init__(message)
        self.line = line

    def __str__(self) -> str:
        prefix = f"line {self.line}: " if self.line else ""
        return f"{prefix}{super().__str__()}"
