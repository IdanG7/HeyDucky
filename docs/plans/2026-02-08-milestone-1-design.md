# Milestone 1: Voice + AI Conversation in TUI

## Scope

Build a terminal TUI where you can:
1. Press Space to talk (push-to-talk)
2. Speech transcribed via faster-whisper (local)
3. Transcript appears in conversation view
4. Claude responds with natural, pair-programmer-style text
5. Response appears in conversation view (no voice output)

### Not in scope
- Debugger integration (DAP)
- Code editing / git / PRs
- TTS output
- GPT/Gemini providers
- Working source view (placeholder only)

## Architecture

### TUI Layout (Textual)

```
+-------------------------------------+
|  Source View (placeholder)      40%  |
|  Shows "No file loaded" initially   |
+-------------------------------------+
|  Conversation View              50%  |
|  Scrollable chat history             |
|  User messages right-aligned         |
|  AI responses left-aligned           |
|  Shows [listening...] indicator      |
+-------------------------------------+
|  Status Bar                     3h   |
|  Mic state | Provider: Claude | $0   |
+-------------------------------------+
```

### Keybindings
- Space (hold): Push-to-talk
- q: Quit
- s: Settings screen

### Voice Pipeline
- Push-to-talk via Space key
- Audio: 16kHz mono via sounddevice
- STT: faster-whisper base.en model, int8 quantization, CPU
- VAD: Simple RMS energy threshold, trim silence
- Latency target: ~1-2s for typical utterances

### AI Integration
- Provider: Claude (anthropic SDK)
- System prompt: Pair programmer personality, casual, short responses
- Post-processing: humanize_response() removes AI-isms
- Function calling: Debugger tools defined but stubbed (log-only)
- Context: Full history up to token limit, then summarize
- Cost tracking: Per-request token usage, session total in status bar

## Project Structure (Milestone 1)

```
voice_debugger/
  __init__.py
  __main__.py          # CLI entry point
  app.py               # Textual app
  voice.py             # VoiceHandler (STT only)
  config.py            # Configuration
  ai/
    __init__.py
    provider.py        # Abstract base
    claude.py          # Claude implementation
    orchestrator.py    # Manages conversation + context
    prompts.py         # System prompts
    functions.py       # Tool schemas (stubbed)
  widgets/
    __init__.py
    source_view.py     # Placeholder
    conversation.py    # Chat display
    status_bar.py      # Mic state, provider, cost
tests/
  test_voice.py
  test_ai.py
  test_app.py
pyproject.toml
```

## Dependencies (Milestone 1 only)
- textual >= 0.50.0
- rich >= 13.7.0
- faster-whisper >= 0.10.0
- sounddevice >= 0.4.6
- numpy >= 1.26.0
- anthropic >= 0.15.0
- toml >= 0.10.2
- aiofiles >= 23.2.1

## Success Criteria
- Can launch TUI with `python -m voice_debugger`
- Can hold Space, speak, and see transcript in conversation
- Claude responds naturally within 3s
- Cost shown in status bar
- Settings screen for API key configuration
- Graceful error if no mic / no API key
