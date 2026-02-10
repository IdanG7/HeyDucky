# voice_debugger/__main__.py
"""CLI entry point for voice-debugger."""

import argparse
import multiprocessing


def main():
    # Must be set before any other multiprocessing usage.
    # Prevents "bad value in fds_to_keep" when ctranslate2/faster-whisper
    # initializes inside a worker thread (e.g. Textual @work).
    try:
        multiprocessing.set_start_method("spawn")
    except RuntimeError:
        pass  # Already set

    parser = argparse.ArgumentParser(
        description="Voice-controlled AI debugging assistant"
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
        "--setup",
        action="store_true",
        help="Run first-time setup wizard",
    )
    args = parser.parse_args()

    if args.setup:
        _run_setup()
        return

    from voice_debugger.app import VoiceDebuggerApp

    app = VoiceDebuggerApp(target=args.target, project=args.project)
    app.run()


def _run_setup():
    """Interactive setup wizard."""
    from voice_debugger.config import Config

    print("Voice Debugger Setup")
    print("=" * 40)

    config = Config.load()

    api_key_display = config.api_key[:8] if config.api_key else "not set"
    api_key = input(f"Anthropic API key [{api_key_display}]: ").strip()
    if api_key:
        config.api_key = api_key

    model = input(f"Model [{config.ai_model}]: ").strip()
    if model:
        config.ai_model = model

    whisper = input(f"Whisper model [{config.whisper_model}]: ").strip()
    if whisper:
        config.whisper_model = whisper

    config.save()
    print("\nConfig saved. Run 'voice-debugger' to start.")


if __name__ == "__main__":
    main()
