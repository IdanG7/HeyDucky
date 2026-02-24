# heyducky/__main__.py
"""CLI entry point for ducky."""

import argparse
import multiprocessing
import os
import sys


BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"
RED = "\033[0;31m"
RESET = "\033[0m"


def main():
    # Must be set before any other multiprocessing usage.
    # Prevents "bad value in fds_to_keep" when ctranslate2/faster-whisper
    # initializes inside a worker thread (e.g. Textual @work).
    try:
        multiprocessing.set_start_method("spawn")
    except RuntimeError:
        pass  # Already set

    parser = argparse.ArgumentParser(
        prog="ducky",
        description="Voice-controlled AI debugging assistant",
        epilog="Run 'ducky --setup' on first use to configure your API key.",
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="Program to debug (e.g., script.py)",
    )
    parser.add_argument(
        "--project",
        help="Project root directory (auto-detected if not given)",
    )
    parser.add_argument(
        "--attach",
        metavar="HOST:PORT",
        help="Attach to a remote debug adapter (e.g., 192.168.1.50:5678)",
    )
    parser.add_argument(
        "--language",
        choices=["python", "cpp", "go", "rust"],
        help="Language of the remote program (required with --attach)",
    )
    parser.add_argument(
        "--path-map",
        metavar="REMOTE=LOCAL",
        action="append",
        default=[],
        help="Map remote paths to local (e.g., /home/user/proj=/Users/me/proj). Repeatable.",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Run first-time setup wizard",
    )
    args = parser.parse_args()

    if args.setup:
        _run_setup()
        return

    if args.attach and not args.language:
        parser.error("--language is required when using --attach")

    # Parse --path-map entries into a dict
    path_map: dict[str, str] = {}
    for mapping in args.path_map:
        if "=" not in mapping:
            parser.error(f"Invalid --path-map format: {mapping!r} (expected REMOTE=LOCAL)")
        remote, local = mapping.split("=", 1)
        path_map[remote] = local

    # Parse --attach into host and port
    attach_host: str | None = None
    attach_port: int | None = None
    if args.attach:
        try:
            host_part, port_part = args.attach.rsplit(":", 1)
            attach_host = host_part
            attach_port = int(port_part)
        except (ValueError, AttributeError):
            parser.error(f"Invalid --attach format: {args.attach!r} (expected HOST:PORT)")

    # First-launch: if no API key is configured anywhere, guide the user
    from heyducky.config import Config
    _config = Config.load()
    _has_key = _config.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not _has_key:
        print(f"\n{YELLOW}No Anthropic API key found.{RESET}")
        print(f"Run {BOLD}ducky --setup{RESET} to configure, "
              f"or set the {BOLD}ANTHROPIC_API_KEY{RESET} environment variable.\n")
        answer = input("Run setup now? [Y/n] ").strip()
        if answer == "" or answer.lower().startswith("y"):
            _run_setup()
            # Reload config after setup
            _config = Config.load()
            _has_key = _config.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
            if not _has_key:
                print(f"\n{RED}Still no API key configured. Exiting.{RESET}")
                sys.exit(1)
        else:
            print(f"{DIM}Starting without AI features...{RESET}\n")

    from heyducky.app import HeyDuckyApp

    app = HeyDuckyApp(
        target=args.target,
        project=args.project,
        attach_host=attach_host,
        attach_port=attach_port,
        attach_language=args.language,
        path_map=path_map or None,
    )
    app.run()


def _run_setup():
    """Interactive setup wizard with validation and sensible defaults."""
    from heyducky.config import Config

    print(f"\n{BOLD}HeyDucky Setup{RESET}")
    print(f"{DIM}{'─' * 40}{RESET}\n")

    config = Config.load()

    # ── 1. API Key ──────────────────────────────────────────────
    env_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if env_key:
        print(f"{GREEN}✓{RESET} Anthropic API key detected from environment variable")
        config.api_key = ""  # Don't store if env has it
    else:
        masked = config.api_key[:8] + "..." if config.api_key else "not set"
        print(f"  Anthropic API key [{DIM}{masked}{RESET}]")
        print(f"  {DIM}Get one at https://console.anthropic.com/settings/keys{RESET}")
        api_key = input(f"  Key: ").strip()
        if api_key:
            config.api_key = api_key

        # Validate the key if we have one
        effective_key = api_key or config.api_key
        if effective_key:
            print(f"  {DIM}Validating...{RESET}", end="", flush=True)
            if _validate_api_key(effective_key):
                print(f"\r  {GREEN}✓{RESET} API key is valid     ")
            else:
                print(f"\r  {YELLOW}?{RESET} Could not validate key (network issue?) — saved anyway")

    # ── 2. AI Model ─────────────────────────────────────────────
    print(f"\n  AI model [{DIM}{config.ai_model}{RESET}]")
    print(f"  {DIM}Options: claude-sonnet-4-5-20250929, claude-haiku-3-5-20241022{RESET}")
    model = input(f"  Model: ").strip()
    if model:
        config.ai_model = model

    # ── 3. Whisper Model ────────────────────────────────────────
    print(f"\n  Whisper model [{DIM}{config.whisper_model}{RESET}]")
    print(f"  {DIM}Options: tiny.en (fast), base.en (balanced), small.en (accurate){RESET}")
    whisper = input(f"  Whisper: ").strip()
    if whisper:
        config.whisper_model = whisper

    # ── 4. TTS (optional) ──────────────────────────────────────
    print(f"\n  Text-to-speech [{DIM}{'enabled' if config.tts_enabled else 'disabled'}{RESET}]")
    print(f"  {DIM}Requires an ElevenLabs API key{RESET}")
    tts_answer = input(f"  Enable TTS? [y/N] ").strip().lower()
    if tts_answer.startswith("y"):
        config.tts_enabled = True
        if not config.tts_api_key:
            tts_key = input(f"  ElevenLabs API key: ").strip()
            if tts_key:
                config.tts_api_key = tts_key
    elif tts_answer.startswith("n"):
        config.tts_enabled = False

    # ── Save ────────────────────────────────────────────────────
    config.save()

    print(f"\n{DIM}{'─' * 40}{RESET}")
    print(f"{GREEN}✓{RESET} {BOLD}Configuration saved{RESET}")
    print(f"  {DIM}Config file: ~/.config/ducky/config.toml{RESET}\n")
    print(f"  {BOLD}Get started:{RESET}")
    print(f"    ducky                            {DIM}# chat mode{RESET}")
    print(f"    ducky --project /path/to/code    {DIM}# project mode{RESET}")
    print(f"    ducky script.py                  {DIM}# debug a script{RESET}")
    print()


def _validate_api_key(key: str) -> bool:
    """Quick validation — sends a tiny request to the Anthropic API."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        client.messages.create(
            model="claude-haiku-3-5-20241022",
            max_tokens=1,
            messages=[{"role": "user", "content": "hi"}],
        )
        return True
    except Exception:
        return False


if __name__ == "__main__":
    main()
