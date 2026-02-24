# Contributing to HeyDucky

Thanks for your interest in contributing to HeyDucky!

## Development Setup

```bash
git clone https://github.com/IdanG7/HeyDucky.git
cd TalkToMe
python3 -m venv .venv
source .venv/bin/activate
make install   # editable install with all extras
```

On macOS, you'll also need portaudio for microphone access:

```bash
brew install portaudio
```

## Running Tests

```bash
make test
```

## Code Style

This project uses [ruff](https://docs.astral.sh/ruff/) for linting and formatting. Before submitting a PR:

```bash
make lint      # check for issues
make fmt       # auto-format
make check     # full check (lint + format + tests)
```

CI will reject PRs that fail lint or format checks.

## Making Changes

1. Fork the repo and create a feature branch from `master`.
2. Write tests for new functionality.
3. Ensure all tests pass and linting is clean.
4. Submit a pull request with a clear description of the change.

## Project Structure

```
heyducky/
├── __main__.py          # CLI entry point (`ducky` command)
├── app.py               # Textual TUI application
├── config.py            # Configuration management
├── voice.py             # Whisper speech-to-text
├── tts.py               # Text-to-speech (ElevenLabs)
├── ai/                  # AI provider (Claude)
│   ├── claude.py        # Claude API client with streaming
│   ├── functions.py     # Tool definitions
│   └── prompts.py       # System prompts
├── debugger/            # Debug adapter protocol
│   ├── dap_client.py    # DAP client implementation
│   ├── session.py       # Debug session management
│   ├── tool_executor.py # AI tool execution bridge
│   └── adapters.py      # Language-specific adapter configs
├── widgets/             # Textual TUI widgets
└── remote/              # Remote debugging agent
```

## Releasing

Releases are triggered by pushing a git tag:

```bash
git tag v0.2.0
git push origin v0.2.0
```

Then create a GitHub Release from the tag — the publish workflow will upload to PyPI automatically.
