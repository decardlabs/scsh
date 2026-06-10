# scsh – Smart Card Shell

`scsh` is an interactive command-line shell for smart card development and testing.  
It lets you explore smart card readers, send raw APDU commands, run script files, 
and perform common ISO/IEC 7816-4 operations — all from your terminal.

---

## Features

- **Interactive REPL** with history, auto-completion, and inline help
- **Send raw APDU commands** and see human-readable status word descriptions
- **Script execution** — run `.scsh` files with sequences of APDU commands
- **SELECT by AID** convenience command
- **PC/SC backend** via [pyscard](https://pyscard.sourceforge.io/) when hardware is available
- **Mock mode** for development and CI without physical hardware (`--mock` / `SCSH_MOCK=1`)

---

## Installation

```bash
pip install scsh
```

For PC/SC hardware support (requires `libpcsclite-dev` on Linux):

```bash
pip install "scsh[pcsc]"
```

---

## Quick Start

### Interactive shell

```
$ scsh
scsh 0.1.0  –  Smart Card Shell
Type 'help' for a list of commands, 'exit' to quit.

scsh> readers
  [0] ACS ACR122U 00 00

scsh> connect 0
Connected to: ACS ACR122U 00 00
ATR: 3B 8F 80 01 80 4F 0C A0 00 00 03 06 03 00 01 00 00 00 00 6A

scsh> select A0000000031010
-> 6F 19 84 07 A0 00 00 00 03 10 10 A5 0E 50 0A 56 49 53 41 20 44 45 42 49 54 90 00
   SW: 90 00  Normal processing – success  [OK]

scsh> send 00 84 00 00 08
-> 3B C1 7A 09 6E 34 12 F9 90 00
   SW: 90 00  Normal processing – success  [OK]

scsh> exit
```

### One-shot commands

```bash
# List readers
scsh readers

# Send a single APDU
scsh send "00 A4 04 00 07 A0 00 00 00 03 10 10 00"

# SELECT by AID
scsh select A0000000031010

# Execute a script file
scsh script my_session.scsh
```

### Mock mode (no hardware)

```bash
scsh --mock readers
# or
SCSH_MOCK=1 scsh
```

---

## Script Files

A script file is a plain-text file where each line is a hex APDU command.  
Lines starting with `#` are comments; blank lines are ignored.

```
# my_session.scsh

# Select the Visa Debit application
00 A4 04 00 07 A0 00 00 00 03 10 10 00

# Get Processing Options (empty PDOL)
80 A8 00 00 02 83 00 00
```

Run it:

```bash
scsh script my_session.scsh
# or inside the REPL:
scsh> script my_session.scsh
```

---

## Shell Commands

| Command | Description |
|---------|-------------|
| `readers` | List available smart card readers |
| `connect [n\|name]` | Connect to reader by index or name substring |
| `disconnect` | Disconnect from the current reader |
| `atr` | Show the ATR of the connected card |
| `send <hex>` | Transmit a raw APDU |
| `apdu <hex>` | Alias for `send` |
| `select <AID>` | Send `SELECT` by AID |
| `script <file>` | Execute a script file |
| `help` | Show command reference |
| `exit` / `quit` | Exit the shell |

You can also type a bare hex APDU directly (e.g. `00 A4 04 00`) without a command prefix.

---

## CLI Reference

```
scsh [OPTIONS] COMMAND [ARGS]...

Options:
  -V, --version   Show the version and exit.
  --mock          Use mock reader (no hardware needed).
  -h, --help      Show this message and exit.

Commands:
  readers   List available smart card readers.
  send      Transmit a single APDU and print the response.
  select    Send a SELECT (by AID) command.
  script    Execute a script file containing APDU commands.
```

---

## Development

```bash
git clone https://github.com/decardlabs/scsh
cd scsh
pip install -e ".[dev]"
pytest
```

---

## License

MIT
