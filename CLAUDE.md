# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install
python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"

# Run the REPL
scsh

# Non-interactive
scsh --command "select A0000006472F0001"
scsh --file test.scsh

# Tests
pytest tests/                         # all tests
pytest tests/test_apdu.py             # single file
pytest tests/test_apdu.py::TestSendCommand::test_send_apdu  # single test
pytest -v --tb=short                  # verbose, short traceback

# GP fallback (standalone script, no Java needed for list/info)
python scsh/gp_fallback.py --list
python scsh/gp_fallback.py --info
```

## Architecture Overview

A Python REPL tool for interacting with smart cards via PC/SC, with GlobalPlatform management via gp.jar subprocess bridging.

### Layers (bottom-up)

1. **Transport** — `scsh/transport/pcsc.py`: Thread-safe pyscard (WinSCard API) wrapper. `PCSCTransport` manages connect/disconnect/send_apdu with lock-based thread safety. Key detail: auto-detects T=0 vs T=1 protocol via test APDU, and auto-sends GET RESPONSE on T=0 61xx responses.

2. **Formats** — `scsh/formats/`:
   - `apdu.py`: APDU hex parsing (Case 1-4 including extended Lc/Le), formatting, INS/CLA name database, session logging
   - `tlv.py`: BER-TLV recursive decode/encode with constructed vs primitive tag handling
   - `sw.py`: ISO 7816-4 + GlobalPlatform status word database with range-based classification

3. **Commands** — `scsh/commands/`: All command handlers are `Callable[[str, Any], None]` — args string + transport object. Print output directly (no return value). Categories:
   - `hardware.py`: readers/connect/info/reset/reconnect/config
   - `apdu.py`: send/select/get-response/send-file + M5 helpers (repeat/timing/record)
   - `gp.py`: All gp-* commands (list/info/install/delete/lock/unlock/put-key/store-data/create-domain/rename-isd/load/uninstall/set-cplc/secure-apdu/mode + card lifecycle)
   - `system.py`: version command

4. **Registry** — `scsh/commands/__init__.py`: `CommandRegistry` maps command names to handlers, handles parsing (`parse_line`) and dispatch (`execute`). Built-in `help` command.

5. **REPL** — `scsh/repl.py`: `prompt_toolkit`-based interactive shell with `FileHistory` and tab completion. Prompt shows current reader index.

6. **GP Bridge** — `scsh/bridge/gp_jar.py`: Subprocess bridge to GlobalPlatformPro (`java -jar gp.jar`). Runs CLI commands, parses structured output. Fallback in `scsh/gp_fallback.py` can do basic list/info via raw APDU (no Java needed).

### Entry Point

`scsh/main.py`: Parse args → build `CommandRegistry` → create `PCSCTransport` → attach `GPJarBridge` → run REPL or execute script/command.

### Exception Hierarchy

Defined in `scsh/exceptions.py`: `ScshError` → `TransportError`/`APDUError`/`GPError` with specific subclasses (`NoReadersError`, `CardDisconnectedError`, `SWError`, `TLVParseError`, `GPBridgeError`, etc.).

### Notable Design Decisions

- Commands receive the `PCSCTransport` object directly and mutate it for state (`_last_apdu`, `_timing_enabled`, `_recording`, `_aid_aliases`, `_config`, `_gp_key`).
- All tests use `unittest.mock.MagicMock` for transport — no real card needed. Test output via `capsys`.
- GP bridge runs gp.jar as subprocess — keep output parsing in `_parse_list_output`/`_parse_info_output` if adding new gp commands.
- APDU send automatically handles T=0 GET RESPONSE chaining in `PCSCTransport.send_apdu`.
- `gp.py` has a duplicate `cmd_gp_install` definition — the second one (with --params/--privs/--default/--force support) is the live one.

### Project Config

- Python 3.13+, setuptools build, `scsh.main:main` console script
- Dependencies: `prompt-toolkit`, `pyscard`, `rich`
- Dev dependencies: `pytest`, `pytest-cov`
