"""CLI entry point for scsh."""

from __future__ import annotations

import os
import sys
from typing import Optional

import click

from scsh import __version__
from scsh.exceptions import ScshError
from scsh.reader import ReaderManager
from scsh.shell import Shell


def _make_manager(mock: bool) -> ReaderManager:
    """Create a :class:`ReaderManager`, honouring ``SCSH_MOCK`` env var."""
    if not mock:
        mock = os.environ.get("SCSH_MOCK", "").lower() in ("1", "true", "yes")
    return ReaderManager(mock=mock)


@click.group(invoke_without_command=True, context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, "-V", "--version", prog_name="scsh")
@click.option("--mock", is_flag=True, default=False, help="Use mock reader (no hardware needed).")
@click.pass_context
def main(ctx: click.Context, mock: bool) -> None:
    """scsh – Smart Card Shell.

    An interactive CLI for smart card development and testing.

    Run without a sub-command to start the interactive shell.
    """
    ctx.ensure_object(dict)
    ctx.obj["mock"] = mock
    if ctx.invoked_subcommand is None:
        manager = _make_manager(mock)
        shell = Shell(manager)
        shell.run()


@main.command("readers")
@click.pass_context
def cmd_readers(ctx: click.Context) -> None:
    """List available smart card readers."""
    mock = ctx.obj.get("mock", False)
    manager = _make_manager(mock)
    readers = manager.list_readers()
    if not readers:
        click.echo("No readers found.")
        return
    for i, reader in enumerate(readers):
        click.echo(f"  [{i}] {reader.name}")


@main.command("send")
@click.argument("apdu_hex")
@click.option("-r", "--reader", "reader_index", default=0, show_default=True,
              help="Reader index to use.")
@click.option("--reader-name", default=None, help="Connect by reader name substring.")
@click.pass_context
def cmd_send(ctx: click.Context, apdu_hex: str, reader_index: int, reader_name: Optional[str]) -> None:
    """Transmit a single APDU and print the response.

    APDU_HEX is a hex string such as \"00 A4 04 00\" or \"00A40400\".
    """
    from scsh.apdu import CommandApdu

    mock = ctx.obj.get("mock", False)
    manager = _make_manager(mock)
    try:
        apdu = CommandApdu.from_hex(apdu_hex)
    except (ValueError, ScshError) as exc:
        click.echo(f"Invalid APDU: {exc}", err=True)
        sys.exit(1)

    try:
        if reader_name:
            manager.connect_by_name(reader_name)
        else:
            manager.connect(reader_index)
    except ScshError as exc:
        click.echo(f"Connect error: {exc}", err=True)
        sys.exit(1)

    try:
        resp = manager.transmit(apdu)
    except ScshError as exc:
        click.echo(f"Transmit error: {exc}", err=True)
        sys.exit(1)
    finally:
        manager.disconnect()

    click.echo(f"Response: {resp.to_hex()}")
    click.echo(f"SW: {resp.sw1:02X} {resp.sw2:02X}  {resp.description}")
    if not resp.ok:
        sys.exit(1)


@main.command("select")
@click.argument("aid_hex")
@click.option("-r", "--reader", "reader_index", default=0, show_default=True,
              help="Reader index to use.")
@click.option("--reader-name", default=None, help="Connect by reader name substring.")
@click.pass_context
def cmd_select(ctx: click.Context, aid_hex: str, reader_index: int, reader_name: Optional[str]) -> None:
    """Send a SELECT (by AID) command.

    AID_HEX is a hex string such as \"A0000000031010\".
    """
    from scsh.apdu import CommandApdu, bytes_from_hex

    mock = ctx.obj.get("mock", False)
    manager = _make_manager(mock)
    try:
        aid = bytes_from_hex(aid_hex)
    except ValueError as exc:
        click.echo(f"Invalid AID: {exc}", err=True)
        sys.exit(1)

    apdu = CommandApdu.select_by_aid(aid)

    try:
        if reader_name:
            manager.connect_by_name(reader_name)
        else:
            manager.connect(reader_index)
    except ScshError as exc:
        click.echo(f"Connect error: {exc}", err=True)
        sys.exit(1)

    try:
        resp = manager.transmit(apdu)
    except ScshError as exc:
        click.echo(f"Transmit error: {exc}", err=True)
        sys.exit(1)
    finally:
        manager.disconnect()

    click.echo(f"Response: {resp.to_hex()}")
    click.echo(f"SW: {resp.sw1:02X} {resp.sw2:02X}  {resp.description}")
    if not resp.ok:
        sys.exit(1)


@main.command("script")
@click.argument("file", type=click.Path(exists=True, readable=True, dir_okay=False))
@click.option("-r", "--reader", "reader_index", default=0, show_default=True,
              help="Reader index to use.")
@click.option("--reader-name", default=None, help="Connect by reader name substring.")
@click.option("--stop-on-error", is_flag=True, default=False,
              help="Stop execution on first APDU error.")
@click.pass_context
def cmd_script(
    ctx: click.Context,
    file: str,
    reader_index: int,
    reader_name: Optional[str],
    stop_on_error: bool,
) -> None:
    """Execute a script file containing APDU commands.

    Each non-blank, non-comment line must be a hex APDU.
    Lines starting with '#' are treated as comments.
    """
    from scsh.apdu import parse_script_line
    from pathlib import Path

    mock = ctx.obj.get("mock", False)
    manager = _make_manager(mock)

    try:
        if reader_name:
            manager.connect_by_name(reader_name)
        else:
            manager.connect(reader_index)
    except ScshError as exc:
        click.echo(f"Connect error: {exc}", err=True)
        sys.exit(1)

    failures = 0
    try:
        path = Path(file)
        with path.open() as fh:
            for lineno, raw in enumerate(fh, start=1):
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    apdu = parse_script_line(line)
                    if apdu is None:
                        continue
                    resp = manager.transmit(apdu)
                    status = "OK" if resp.ok else "ERR"
                    click.echo(f"[{lineno:04d}] {apdu.to_hex()} -> {resp.to_hex()} [{status}]")
                    if not resp.ok:
                        failures += 1
                        if stop_on_error:
                            click.echo("Stopping on error (--stop-on-error).", err=True)
                            break
                except ScshError as exc:
                    click.echo(f"[{lineno:04d}] ERROR: {exc}", err=True)
                    failures += 1
                    if stop_on_error:
                        break
    finally:
        manager.disconnect()

    if failures:
        click.echo(f"\n{failures} command(s) failed.", err=True)
        sys.exit(1)
    else:
        click.echo("\nScript completed successfully.")
