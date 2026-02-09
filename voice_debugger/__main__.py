# voice_debugger/__main__.py
"""CLI entry point for voice-debugger."""

import argparse


def main():
    parser = argparse.ArgumentParser(
        description="Voice-controlled AI debugging assistant"
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Run first-time setup wizard",
    )
    parser.add_argument(
        "--provider",
        choices=["claude"],
        default="claude",
        help="AI provider to use",
    )
    parser.add_argument(
        "--model",
        help="Specific model to use",
    )
    args = parser.parse_args()

    if args.setup:
        _run_setup()
        return

    from voice_debugger.app import VoiceDebuggerApp

    app = VoiceDebuggerApp()
    app.run()


def _run_setup():
    """Interactive setup wizard."""
    from voice_debugger.config import Config

    print("Voice Debugger Setup")
    print("=" * 40)

    config = Config.load()

    api_key = input(f"Anthropic API key [{config.api_key[:8]}...]: ").strip()
    if api_key:
        config.api_key = api_key

    model = input(f"Model [{config.ai_model}]: ").strip()
    if model:
        config.ai_model = model

    whisper = input(f"Whisper model [{config.whisper_model}]: ").strip()
    if whisper:
        config.whisper_model = whisper

    config.save()
    print(f"\nConfig saved. Run 'voice-debugger' to start.")


if __name__ == "__main__":
    main()
