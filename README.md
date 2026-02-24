# HeyDucky 🦆

**Your AI rubber duck that actually talks back.**

HeyDucky is a voice-controlled AI debugging assistant that runs in your terminal. Press Space, describe your problem out loud, and the AI reads your code, sets breakpoints, steps through execution, and explains what it finds — all hands-free.

Think [rubber duck debugging](https://en.wikipedia.org/wiki/Rubber_duck_debugging), except the duck is an AI that understands your codebase, controls your debugger, and talks back.

Built with [Textual](https://textual.textualize.io/) for the TUI, [Claude](https://anthropic.com/) for the AI, and [faster-whisper](https://github.com/SYSTRAN/faster-whisper) for local speech-to-text.

<!-- TODO: Add screenshot/demo recording here -->

## Install

**macOS (recommended):**

```bash
curl -fsSL https://raw.githubusercontent.com/IdanG7/HeyDucky/master/install.sh | bash
```

**Homebrew:**

```bash
brew tap IdanG7/heyducky https://github.com/IdanG7/HeyDucky
brew install heyducky
```

**pipx (if you already have portaudio):**

```bash
pipx install heyducky[tts]
```

**From source:**

```bash
git clone https://github.com/IdanG7/HeyDucky.git
cd TalkToMe
pip install -e ".[tts,dev]"
```

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

## How It Works

HeyDucky combines three things that make debugging less painful:

1. **Voice input** — explain your bug out loud instead of typing. Local Whisper transcription keeps your audio private.
2. **AI understanding** — Claude reads your code, understands the context, and drives the debugger for you.
3. **Real debugger control** — not just chat. HeyDucky sets breakpoints, steps through code, inspects variables, and evaluates expressions via the Debug Adapter Protocol (DAP).

## Usage

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

```bash
# On the remote machine:
debugpy --listen 0.0.0.0:5678 --wait-for-client script.py

# On your machine:
ducky --attach 192.168.1.50:5678 --language python \
    --path-map /home/user/project=/Users/me/project
```

Connects to a debug adapter running on another machine. Use `--path-map` to map remote paths to local source.

**Supported languages:** Python, C/C++, Go, Rust

## Keyboard Shortcuts

| Key       | Action                        |
|-----------|-------------------------------|
| `Space`   | Push-to-talk (hold or toggle) |
| `1`-`5`   | Switch tabs (Source, Chat, Variables, Stack, Output) |
| `t`       | Toggle focus: file tree / source |
| `o`       | Open a different project      |
| `h`       | Browse chat history           |
| `s`       | Settings                      |
| `e`       | Export session to markdown     |
| `m`       | Mute/unmute TTS               |
| `F5`      | Continue execution            |
| `F10`     | Step over                     |
| `F11`     | Step into                     |
| `q`       | Quit                          |

## Configuration

Config lives at `~/.config/ducky/config.toml`. Run `ducky --setup` to edit interactively, or edit the file directly:

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

- **macOS** (primary platform)
- **Python 3.10+**
- **portaudio** (`brew install portaudio`) — for microphone access
- **Anthropic API key** — for Claude
- **Microphone** — for voice input

Optional:
- **ElevenLabs API key** — for text-to-speech (the duck talks back!)
- **debugpy** (included) — for Python debugging
- **lldb-dap** — for C/C++ debugging
- **delve** — for Go debugging
- **codelldb** — for Rust debugging

## Development

```bash
git clone https://github.com/IdanG7/HeyDucky.git
cd TalkToMe
make install    # editable install with dev deps
make test       # run tests
make lint       # run ruff
make check      # lint + format check + tests
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for full development setup and guidelines.

## License

[MIT](LICENSE)
