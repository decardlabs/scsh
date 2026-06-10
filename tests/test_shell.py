"""Tests for scsh.shell module."""

import io
import tempfile
import textwrap
from pathlib import Path

import pytest

from scsh.apdu import CommandApdu
from scsh.reader import MockReader, ReaderManager
from scsh.shell import Shell


def _make_shell(connected: bool = True) -> Shell:
    """Helper: create a Shell with a mock reader."""
    manager = ReaderManager(mock=True)
    shell = Shell(manager)
    if connected:
        manager.connect(0)
    return shell


# ---------------------------------------------------------------------------
# Shell.execute – command dispatch
# ---------------------------------------------------------------------------

class TestShellDispatch:
    def test_help(self, capsys):
        shell = _make_shell()
        shell.execute("help")
        out = capsys.readouterr().out
        assert "readers" in out
        assert "connect" in out

    def test_readers_lists_reader(self, capsys):
        shell = _make_shell(connected=False)
        shell.execute("readers")
        out = capsys.readouterr().out
        assert "Mock" in out

    def test_connect_by_index(self, capsys):
        shell = _make_shell(connected=False)
        shell.execute("connect 0")
        out = capsys.readouterr().out
        assert "Connected" in out

    def test_disconnect(self, capsys):
        shell = _make_shell(connected=True)
        shell.execute("disconnect")
        out = capsys.readouterr().out
        assert "Disconnected" in out

    def test_disconnect_when_not_connected(self, capsys):
        shell = _make_shell(connected=False)
        shell.execute("disconnect")
        out = capsys.readouterr().out
        assert "Not connected" in out

    def test_atr(self, capsys):
        shell = _make_shell(connected=True)
        shell.execute("atr")
        out = capsys.readouterr().out
        assert "ATR:" in out

    def test_atr_not_connected(self, capsys):
        shell = _make_shell(connected=False)
        shell.execute("atr")
        out = capsys.readouterr().out
        assert "Not connected" in out

    def test_send_invalid_hex(self, capsys):
        shell = _make_shell()
        shell.execute("send ZZZZ")
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "invalid" in combined.lower() or "error" in combined.lower() or "Usage" in combined

    def test_send_raw_apdu_shorthand(self, capsys):
        shell = _make_shell()
        shell.execute("00 A4 04 00")
        out = capsys.readouterr().out
        # Should print a response line
        assert "->" in out

    def test_select_aid(self, capsys):
        shell = _make_shell()
        shell.execute("select A0000000031010")
        out = capsys.readouterr().out
        assert "->" in out

    def test_select_missing_arg(self, capsys):
        shell = _make_shell()
        shell.execute("select")
        out = capsys.readouterr().out
        assert "Usage" in out

    def test_exit_returns_exit(self):
        shell = _make_shell()
        result = shell.execute("exit")
        assert result == "exit"

    def test_quit_returns_exit(self):
        shell = _make_shell()
        result = shell.execute("quit")
        assert result == "exit"

    def test_unknown_command(self, capsys):
        shell = _make_shell()
        shell.execute("foobar")
        out = capsys.readouterr().out
        assert "Unknown" in out or "foobar" in out


# ---------------------------------------------------------------------------
# Shell.run_script
# ---------------------------------------------------------------------------

class TestRunScript:
    def _write_script(self, content: str) -> Path:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".scsh", delete=False
        )
        tmp.write(textwrap.dedent(content))
        tmp.flush()
        tmp.close()
        return Path(tmp.name)

    def test_simple_script(self, capsys):
        shell = _make_shell(connected=True)
        path = self._write_script(
            """\
            # Select master file
            00 A4 04 00 07 A0 00 00 00 03 10 10
            00 84 00 00 08
            """
        )
        failures = shell.run_script(str(path))
        assert isinstance(failures, int)
        path.unlink()

    def test_comments_ignored(self, capsys):
        shell = _make_shell(connected=True)
        path = self._write_script(
            """\
            # This is a comment
            # Another comment
            """
        )
        failures = shell.run_script(str(path))
        assert failures == 0
        path.unlink()

    def test_missing_file_raises(self):
        shell = _make_shell(connected=True)
        from scsh.exceptions import ScriptError
        with pytest.raises(ScriptError):
            shell.run_script("/nonexistent/path/script.scsh")
