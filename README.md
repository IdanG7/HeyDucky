# HeyDucky 🦆

[![CI](https://github.com/IdanG7/HeyDucky/actions/workflows/ci.yml/badge.svg)](https://github.com/IdanG7/HeyDucky/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/heyducky)](https://pypi.org/project/heyducky/)
[![Python](https://img.shields.io/pypi/pyversions/heyducky)](https://pypi.org/project/heyducky/)
[![License: MIT](https://img.shields.io/github/license/IdanG7/HeyDucky)](LICENSE)

**Your AI rubber duck that actually talks back.**

HeyDucky is a voice-controlled AI debugging assistant that runs in your terminal. Press Space, describe your problem out loud, and the AI reads your code, sets breakpoints, steps through execution, and explains what it finds — all hands-free.

Think [rubber duck debugging](https://en.wikipedia.org/wiki/Rubber_duck_debugging), except the duck is an AI that understands your codebase, controls your debugger, and talks back.

Built with [Textual](https://textual.textualize.io/) for the TUI, [Claude](https://anthropic.com/) for the AI, and [faster-whisper](https://github.com/SYSTRAN/faster-whisper) for local speech-to-text.

## Install

**macOS (recommended):**

```bash
curl -fsSL https://raw.githubusercontent.com/IdanG7/HeyDucky/master/install.sh | bash
```

The installer handles everything — Homebrew, portaudio, Python, pipx, and the `ducky` command. It will prompt you to run the setup wizard at the end.

**Homebrew:**

```bash
brew tap IdanG7/heyducky https://github.com/IdanG7/HeyDucky
brew install heyducky
```

**pipx (if you already have portaudio):**

```bash
pipx install heyducky[tts]
```

**pip:**

```bash
pip install heyducky[tts]
```

**From source:**

```bash
git clone https://github.com/IdanG7/HeyDucky.git
cd TalkToMe
pip install -e ".[tts,dev]"
```

> **Linux users:** The macOS installer script won't work on Linux. Use `pip install heyducky[tts]` instead. You will need to install portaudio through your system package manager (e.g. `apt install portaudio19-dev`).

## Quick Start

```bash
# First-time setup — configure your Anthropic API key
ducky --setup

# Talk to the duck about a project
ducky --project /path/to/your/code

# Debug a Python script
ducky script.py

# Just launch in the current directory
ducky
```

If no API key is configured, HeyDucky will prompt you to run the setup wizard on first launch.

## How It Works

HeyDucky combines three things that make debugging less painful:

1. **Voice input** — explain your bug out loud instead of typing. Local Whisper transcription keeps your audio private.
2. **AI understanding** — Claude reads your code, understands the context, and drives the debugger for you.
3. **Real debugger control** — not just chat. HeyDucky sets breakpoints, steps through code, inspects variables, and evaluates expressions via the Debug Adapter Protocol (DAP).

## Usage

HeyDucky has three modes: **Chat**, **Debug**, and **Remote Debug**.

### Chat Mode

```bash
ducky
ducky --project ~/myapp
```

Press Space to talk. The AI can read files, browse the project tree, run git commands, and discuss your code. No debugger attached — this is pure conversation with full tool access.

### Debug Mode

```bash
ducky script.py
ducky --project ~/myapp src/main.py
```

Launches the script under a debug adapter. The AI can set breakpoints, step through code, inspect variables, and evaluate expressions — all via voice.

### Remote Debug

Debug programs running on another machine. There are two ways to set this up:

#### Using `ducky-remote` (recommended)

On the remote machine, install HeyDucky and run the remote agent:

```bash
# GUI mode (requires PySide6)
pip install heyducky[remote]
ducky-remote

# Headless / CLI mode
ducky-remote --headless script.py
```

The remote agent starts a debug adapter and a file server, then displays connection instructions. On your local machine, either press `r` in the HeyDucky TUI and enter the host/port, or connect from the command line:

```bash
ducky --attach 192.168.1.50:5678 --language python
```

`ducky-remote` options:

| Flag | Description |
|------|-------------|
| `--headless` | Run without the GUI (requires a program argument) |
| `--host` | Interface to listen on (default: `0.0.0.0`) |
| `--port` | DAP port (default: `5678`) |
| `--file-port` | File server port (default: auto-assigned) |

#### Manual setup (any DAP-compatible adapter)

If you prefer to launch the debug adapter yourself:

```bash
# On the remote machine:
debugpy --listen 0.0.0.0:5678 --wait-for-client script.py

# On your machine:
ducky --attach 192.168.1.50:5678 --language python \
    --path-map /home/user/project=/Users/me/project
```

Use `--path-map` to translate remote file paths to local paths so HeyDucky can display the correct source.

**Supported languages:** Python, C/C++, Go, Rust

## Features

### AI Tools

When connected, the AI can use these tools on your behalf:

- **set_breakpoint** — set breakpoints (with optional conditions)
- **step_over / step_into / step_out** — step through code
- **continue_execution** — resume until the next breakpoint
- **inspect_variable** — check the value of any variable
- **evaluate_expression** — evaluate arbitrary expressions in the debug context
- **watch_variable / unwatch_variable** — pin variables to the watch panel
- **get_call_stack** — view the current call stack
- **read_source** — read any file in the project
- **list_files** — browse the project directory
- **run_git_command** — run git commands (status, diff, log, blame, commit, etc.)

### Text-to-Speech

HeyDucky can speak its responses aloud using [ElevenLabs](https://elevenlabs.io/). Enable it in the setup wizard or in settings (`s`). Requires an ElevenLabs API key. Press `m` to mute/unmute during a session.

### Chat History

Conversations are saved automatically to `~/.config/ducky/history/`. Press `h` to browse past sessions and reload them into the conversation view.

### Session Export

Press `e` to export the current conversation as a markdown file to your Desktop.

### Context Compaction

Long conversations are automatically compacted when they approach the model's context window limit. The AI summarizes the conversation so far and continues with full awareness of what was discussed. A notification appears in the status bar when compaction occurs.

### Crash Recovery

HeyDucky auto-saves your AI conversation state every 30 seconds. If the app crashes, the session is automatically restored on next launch (within 1 hour).

## Keyboard Shortcuts

| Key       | Action                        |
|-----------|-------------------------------|
| `Space`   | Push-to-talk (hold or toggle) |
| `1`-`5`   | Switch tabs (Source, Chat, Variables, Stack, Output) |
| `t`       | Toggle focus: file tree / source |
| `o`       | Open a different project      |
| `r`       | Connect to a remote debugger  |
| `h`       | Browse chat history           |
| `s`       | Settings                      |
| `e`       | Export session to markdown     |
| `m`       | Mute/unmute TTS               |
| `F5`      | Continue execution            |
| `F10`     | Step over                     |
| `F11`     | Step into                     |
| `q`       | Quit                          |

## CLI Reference

### `ducky`

```
ducky [target] [options]

Arguments:
  target                  Program to debug (e.g., script.py)

Options:
  --project DIR           Project root directory (auto-detected if not given)
  --attach HOST:PORT      Attach to a remote debug adapter
  --language LANG         Language of the remote program (python|cpp|go|rust)
                          Required with --attach
  --path-map REMOTE=LOCAL Map remote paths to local (repeatable)
  --setup                 Run the first-time setup wizard
```

### `ducky-remote`

```
ducky-remote [program] [options]

Arguments:
  program                 Program to debug in headless mode

Options:
  --headless              Run in headless (CLI) mode instead of the GUI
  --host HOST             Interface to listen on (default: 0.0.0.0)
  --port PORT             DAP port (default: 5678)
  --file-port PORT        File server port (default: auto-assign)
```

## Configuration

Config lives at `~/.config/ducky/config.toml`. Run `ducky --setup` to edit interactively, or press `s` inside the app, or edit the file directly:

```toml
[ai]
provider = "claude"
model = "claude-sonnet-4-5-20250929"
api_key = "sk-ant-..."
compaction_enabled = true

[voice]
whisper_model = "base.en"       # tiny.en | base.en | small.en
sample_rate = 16000
silence_threshold = 0.02
silence_duration = 1.5

[tts]
enabled = false
api_key = ""                    # ElevenLabs API key
voice_id = "UgBBYS2sOqTuMpoF3BR0"

[appearance]
theme = "textual-dark"
```

You can also set `ANTHROPIC_API_KEY` as an environment variable instead of putting it in the config file.

## Requirements

- **Python 3.10+**
- **macOS** (primary platform) or **Linux**
- **portaudio** — for microphone access (`brew install portaudio` on macOS)
- **Anthropic API key** — for Claude
- **Microphone** — for voice input

Optional:
- **ElevenLabs API key** — for text-to-speech (install with `pip install heyducky[tts]`)
- **PySide6** — for the remote agent GUI (install with `pip install heyducky[remote]`)
- **debugpy** (included) — for Python debugging
- **lldb-dap** — for C/C++ debugging
- **delve** (`dlv`) — for Go debugging
- **codelldb** — for Rust debugging

## Development

```bash
git clone https://github.com/IdanG7/HeyDucky.git
cd TalkToMe
python3 -m venv .venv
source .venv/bin/activate
make install    # editable install with dev deps
make test       # run tests
make lint       # run ruff
make fmt        # auto-format
make check      # lint + format check + tests
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for full development setup and guidelines.

## License

[MIT](LICENSE)
