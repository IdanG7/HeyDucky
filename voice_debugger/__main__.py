"""CLI entry point for voice-debugger."""

def main():
    from voice_debugger.app import VoiceDebuggerApp
    app = VoiceDebuggerApp()
    app.run()

if __name__ == "__main__":
    main()
