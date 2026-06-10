"""Interactive shell for scsh.

Provides a REPL that exposes smart card operations as shell commands.  The
shell is built on top of :mod:`prompt_toolkit` for readline-style editing,
history, and auto-completion.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List, Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style

from scsh.apdu import (
    CommandApdu,
    bytes_from_hex,
    bytes_to_hex,
    parse_script_line,
)
from scsh.exceptions import ScshError, ScriptError
from scsh.reader import ReaderManager

# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------

SHELL_STYLE = Style.from_dict(
    {
        "prompt": "ansigreen bold",
        "rprompt": "ansigray",
    }
)

_COMMANDS = [
    "readers",
    "connect",
    "disconnect",
    "atr",
    "send",
    "select",
    "apdu",
    "script",
    "help",
    "exit",
    "quit",
]

_COMPLETER = WordCompleter(_COMMANDS, ignore_case=True)

# ---------------------------------------------------------------------------
# Shell
# ---------------------------------------------------------------------------

class Shell:
    """Interactive smart card shell."""

    PROMPT = "scsh> "

    def __init__(self, manager: Optional[ReaderManager] = None) -> None:
        self.manager = manager or ReaderManager()
        self._history_file = Path.home() / ".scsh_history"

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Start the interactive REPL loop."""
        session: PromptSession = PromptSession(
            history=FileHistory(str(self._history_file)),
            auto_suggest=AutoSuggestFromHistory(),
            completer=_COMPLETER,
            style=SHELL_STYLE,
        )
        self._print_banner()
        while True:
            try:
                raw = session.prompt(self.PROMPT)
            except KeyboardInterrupt:
                continue
            except EOFError:
                print("exit")
                break
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if self._dispatch(line) == "exit":
                break

    def run_script(self, path: str) -> int:
        """Execute a script file.  Returns the number of failed commands."""
        script_path = Path(path)
        if not script_path.exists():
            raise ScriptError(f"Script file not found: {path}")
        failures = 0
        with script_path.open() as fh:
            for lineno, raw in enumerate(fh, start=1):
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    apdu = parse_script_line(line)
                    if apdu is None:
                        continue
                    resp = self.manager.transmit(apdu)
                    status = "OK" if resp.ok else "ERR"
                    print(
                        f"[{lineno:04d}] {apdu.to_hex()} -> {resp.to_hex()} [{status}]"
                    )
                    if not resp.ok:
                        failures += 1
                except ScshError as exc:
                    print(f"[{lineno:04d}] ERROR: {exc}", file=sys.stderr)
                    failures += 1
        return failures

    def execute(self, line: str) -> Optional[str]:
        """Execute a single command line and return ``'exit'`` if the shell
        should terminate, otherwise ``None``."""
        return self._dispatch(line.strip())

    # ------------------------------------------------------------------
    # Internal dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, line: str) -> Optional[str]:
        parts = line.split(None, 1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        handler = {
            "readers": self._cmd_readers,
            "connect": self._cmd_connect,
            "disconnect": self._cmd_disconnect,
            "atr": self._cmd_atr,
            "send": self._cmd_send,
            "select": self._cmd_select,
            "apdu": self._cmd_send,  # alias
            "script": self._cmd_script,
            "help": self._cmd_help,
            "exit": lambda _: "exit",
            "quit": lambda _: "exit",
        }.get(cmd)

        if handler is None:
            # Try to parse the whole line as a raw hex APDU
            try:
                apdu = CommandApdu.from_hex(line)
                return self._send_and_print(apdu)
            except (ValueError, Exception):
                print(f"Unknown command: {cmd!r}  (type 'help' for a list)")
            return None

        try:
            return handler(args)
        except ScshError as exc:
            print(f"Error: {exc}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001
            print(f"Unexpected error: {exc}", file=sys.stderr)
        return None

    # ------------------------------------------------------------------
    # Command implementations
    # ------------------------------------------------------------------

    def _cmd_readers(self, _args: str) -> None:
        readers = self.manager.list_readers()
        if not readers:
            print("No readers found.")
            return
        for i, reader in enumerate(readers):
            marker = "*" if (self.manager.active and reader.name == self.manager.active.name) else " "
            print(f"  [{i}]{marker} {reader.name}")

    def _cmd_connect(self, args: str) -> None:
        args = args.strip()
        if args.isdigit():
            reader = self.manager.connect(int(args))
        elif args:
            reader = self.manager.connect_by_name(args)
        else:
            reader = self.manager.connect(0)
        atr_hex = bytes_to_hex(reader.atr)
        print(f"Connected to: {reader.name}")
        print(f"ATR: {atr_hex}")

    def _cmd_disconnect(self, _args: str) -> None:
        if self.manager.active is None:
            print("Not connected.")
            return
        name = self.manager.active.name
        self.manager.disconnect()
        print(f"Disconnected from: {name}")

    def _cmd_atr(self, _args: str) -> None:
        if not self.manager.active or not self.manager.active.connected:
            print("Not connected.")
            return
        print(f"ATR: {bytes_to_hex(self.manager.active.atr)}")

    def _cmd_send(self, args: str) -> Optional[str]:
        args = args.strip()
        if not args:
            print("Usage: send <APDU hex>")
            return None
        try:
            apdu = CommandApdu.from_hex(args)
        except (ValueError, Exception) as exc:
            print(f"Invalid APDU: {exc}")
            return None
        return self._send_and_print(apdu)

    def _cmd_select(self, args: str) -> Optional[str]:
        args = args.strip()
        if not args:
            print("Usage: select <AID hex>")
            return None
        try:
            aid = bytes_from_hex(args)
        except ValueError as exc:
            print(f"Invalid AID: {exc}")
            return None
        apdu = CommandApdu.select_by_aid(aid)
        return self._send_and_print(apdu)

    def _cmd_script(self, args: str) -> None:
        path = args.strip()
        if not path:
            print("Usage: script <file>")
            return
        try:
            failures = self.run_script(path)
            if failures:
                print(f"Script completed with {failures} failure(s).")
            else:
                print("Script completed successfully.")
        except ScriptError as exc:
            print(f"Script error: {exc}", file=sys.stderr)

    @staticmethod
    def _cmd_help(_args: str) -> None:
        print(
            "\nAvailable commands:\n"
            "  readers              – list available smart card readers\n"
            "  connect [n|name]     – connect to reader by index or name substring\n"
            "  disconnect           – disconnect from the current reader\n"
            "  atr                  – show the ATR of the connected card\n"
            "  send <hex>           – transmit a raw APDU (hex)\n"
            "  select <AID hex>     – send SELECT by AID\n"
            "  apdu <hex>           – alias for 'send'\n"
            "  script <file>        – execute a script file\n"
            "  help                 – show this help message\n"
            "  exit / quit          – exit the shell\n"
            "\nRaw APDU mode:\n"
            "  You may also type a bare hex APDU (e.g. 00 A4 04 00) directly.\n"
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _send_and_print(self, apdu: CommandApdu) -> Optional[str]:
        try:
            resp = self.manager.transmit(apdu)
        except ScshError as exc:
            print(f"Transmit error: {exc}", file=sys.stderr)
            return None
        status = "OK" if resp.ok else "ERR"
        print(f"-> {resp.to_hex()}")
        print(f"   SW: {resp.sw1:02X} {resp.sw2:02X}  {resp.description}  [{status}]")
        return None

    @staticmethod
    def _print_banner() -> None:
        from scsh import __version__

        print(
            f"\nscsh {__version__}  –  Smart Card Shell\n"
            "Type 'help' for a list of commands, 'exit' to quit.\n"
        )
