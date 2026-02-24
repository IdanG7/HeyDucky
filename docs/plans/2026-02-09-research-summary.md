# Research Summary: Chat Memory, Compaction, Settings, and Recent Chats

**Date:** 2026-02-09
**Scope:** Research findings with concrete implementation recommendations for the TalkToMe voice debugger TUI (Python Textual + Anthropic Claude API)

---

## Table of Contents

1. [Chat Memory Systems for AI Assistants](#1-chat-memory-systems-for-ai-assistants)
2. [Conversation Compaction / Context Window Management](#2-conversation-compaction--context-window-management)
3. [Settings Pages in Terminal TUI Apps](#3-settings-pages-in-terminal-tui-apps)
4. [Best Practices for Recent Chat Sections](#4-best-practices-for-recent-chat-sections)
5. [Implementation Recommendations for TalkToMe](#5-implementation-recommendations-for-talktome)

---

## 1. Chat Memory Systems for AI Assistants

### How Production Apps Handle Conversation Persistence

**ChatGPT:**
- Sidebar with chronological list of all conversations
- Date-grouped headers: "Today", "Yesterday", "Previous 7 Days", "Previous 30 Days" (though these were controversially removed in mid-2025 and users demanded them back)
- Full-text search bar at the top of the sidebar
- Each conversation has an auto-generated title derived from the first user message
- Conversations persist indefinitely unless explicitly deleted
- Memory feature extracts key facts across conversations for long-term recall
- Pinning/favoriting was heavily requested but only partially implemented

**Claude.ai:**
- Similar sidebar with recent conversations
- Chat search allows finding past conversations by content
- Memory system (Team/Enterprise) lets Claude recall facts across sessions
- Incognito mode for conversations that should not be saved or memorized
- Conversations stored with timestamps, metadata, and contextual signals
- Memory is explicit and user-controllable (users can view, edit, delete memories)

**Cursor / Claude Code / Aider (coding assistants):**
- Session-based persistence rather than permanent chat history
- Claude Code stores sessions in `~/.claude/projects/<project>/` with encoded directory names
- Claude Code supports `--continue` (resume most recent) and `--resume <id>` (resume specific session)
- CLAUDE.md files serve as cross-session persistent memory
- Auto-memory directories store learnings at `~/.claude/projects/<project>/memory/`
- Aider maintains repository-scoped context with git-aware file mapping

### Best UX Patterns Identified

1. **Auto-save on every message** -- never lose data; save incrementally, not just on exit
2. **Auto-generated titles** -- derive from first user message or AI summary of first exchange
3. **Date-grouped chronological list** -- "Today / Yesterday / This Week / Older" grouping is the gold standard
4. **Search** -- essential once history exceeds ~20 conversations
5. **Session vs. project scoping** -- coding tools benefit from project-scoped history (all sessions for a given project root)

---

## 2. Conversation Compaction / Context Window Management

### Techniques Overview

| Technique | Description | Pros | Cons |
|-----------|-------------|------|------|
| **Sliding Window** | Keep only the last N messages/tokens | Simple, predictable | Loses all older context |
| **Summarization** | LLM summarizes older turns into a compact block | Preserves key info | Summary quality varies; costs tokens |
| **Hierarchical Memory** | Multiple tiers: verbatim recent, compressed medium, extracted long-term | Best retention | Complex to implement |
| **Key-Fact Extraction** | Extract structured facts/decisions from conversation | Highly compressed | May miss nuance |
| **External Memory** | Write important context to files (CLAUDE.md pattern) | Persists across sessions | Requires user discipline |
| **Sub-agent Isolation** | Delegate expensive exploration to sub-agents that return summaries | Saves parent context | Architecture complexity |

### How Specific Tools Handle Compaction

**Claude Code:**
- Triggers auto-compaction at ~95% context capacity (configurable via `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`, 1-100)
- Users report 85-90% is a better threshold (95% is often too late)
- Manual `/compact` command with optional focus instructions (e.g., `/compact focus on todo items`)
- Summary prompt asks for: completed work, current state, in-progress work, next steps, constraints, critical context
- Summary wrapped in `<summary>` tags, replaces entire message history
- Reported ~58.6% token reduction per compaction (208K -> 86K tokens with 2 compactions)

**Anthropic Compaction API (beta, January 2026):**
- Server-side compaction via `context_management.edits` parameter
- Beta header: `compact-2026-01-12`
- Default trigger: 150,000 input tokens (minimum 50,000)
- Returns a `compaction` content block that replaces all prior messages when passed back
- `pause_after_compaction` flag allows injecting preserved messages after summary
- Custom summarization instructions replace the default prompt entirely
- Streaming supported: compaction block arrives as single delta (not streamed incrementally)
- Works with prompt caching: add `cache_control` on compaction blocks
- Usage tracking via `usage.iterations` array (compaction + message iterations)

**Cursor:**
- Auto-summarizes when context window fills up
- Uses smaller/faster models for summarization to reduce latency
- Stores chat history as files that can be referenced during summarization
- Manual `/compress` command
- "Dynamic context discovery" -- pulls in only necessary context on demand

**Aider:**
- Auto-summarizes when context size passes a configurable limit
- LLM reads existing context and produces abridged summary
- Summary replaces previous conversation
- Repository map provides structural context without consuming tokens

**OpenCode:**
- Separate "prune" mechanism: removes old tool outputs while protecting last 40K tokens
- Only prunes if >20K tokens are prunable
- Distinct summaries for UI display (2 sentences) vs. detailed compaction
- Disableable via `OPENCODE_DISABLE_AUTOCOMPACT`

**Forge Code:**
- Multi-condition triggers: token threshold, message count, user turn count, end-of-turn
- Configurable `retention_window` (recent messages kept verbatim) and `eviction_window` (% of compactable context)
- Uses faster models (e.g., Gemini Flash) for summarization to reduce latency
- Recommended thresholds: 150K-180K for 200K-window models
- Runs compaction in parallel alongside main request

### When to Trigger Compaction

| Strategy | Threshold | Notes |
|----------|-----------|-------|
| Conservative | 80-85% of context window | Best quality; more frequent compactions |
| Standard | 90% of context window | Good balance |
| Aggressive | 95% of context window | Risks mid-response failure |
| Token-count based | 100K-150K absolute tokens | Model-independent; predictable |
| Message-count based | Every 30-50 messages | Simple but imprecise |

**Recommendation for TalkToMe:** Use the Anthropic Compaction API (beta) with a trigger at 100,000 tokens. This is the simplest and most robust approach since the server handles summarization.

### Compaction Best Practices

1. **Preserve recent turns verbatim** -- at minimum the last 2-3 exchanges should not be summarized
2. **Use `pause_after_compaction`** to inject critical context back after the summary
3. **Custom instructions matter** -- tailor the summarization prompt to your domain (debugging context, file state, breakpoint positions)
4. **Track compaction count** -- quality degrades after 3-4+ sequential compactions; consider prompting task wrap-up
5. **Externalize critical state** -- write key decisions/state to files rather than relying on conversation memory
6. **Show compaction to the user** -- add a visual indicator in the conversation view when compaction occurs

---

## 3. Settings Pages in Terminal TUI Apps

### Available Textual Widgets for Settings

**Toggle/Boolean Settings:**
- `Switch` -- on/off toggle with visual state, best for binary preferences
- `Checkbox` -- classic checkbox, good for multiple independent options

**Selection Settings:**
- `RadioButton` / `RadioSet` -- mutually exclusive options (e.g., AI model selection)
- `Select` -- dropdown-style selection for categories with many options
- `OptionList` -- scrollable list of all options displayed at once
- `SelectionList` -- multi-select from a list

**Text/Numeric Input:**
- `Input` -- text field for API keys, file paths, numeric values
- Can set `placeholder`, `password` mode, validators

**Layout/Organization:**
- `TabbedContent` / `TabPane` -- separate settings into categories (AI, Voice, Debug, etc.)
- `Collapsible` -- expandable sections to reduce visual clutter
- `ModalScreen` -- push a settings screen on top of the main app

### Implementation Pattern: ModalScreen for Settings

The standard Textual pattern for a settings screen:

```python
from textual.screen import ModalScreen
from textual.containers import Vertical, Grid
from textual.widgets import Label, Button, Input, Switch, Select, RadioSet, RadioButton

class SettingsScreen(ModalScreen[dict | None]):
    """Modal settings screen that returns updated config or None if cancelled."""

    DEFAULT_CSS = """
    SettingsScreen {
        align: center middle;
    }
    #settings-container {
        width: 80;
        height: 80%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
        overflow-y: auto;
    }
    """

    BINDINGS = [Binding("escape", "cancel", "Close")]

    def __init__(self, config: Config):
        super().__init__()
        self._config = config

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-container"):
            yield Label("Settings", id="settings-title")

            # AI section using Collapsible
            with Collapsible(title="AI Settings", collapsed=False):
                yield Label("API Key:")
                yield Input(value=self._config.api_key, password=True, id="api-key")
                yield Label("Model:")
                yield Select(
                    [("Claude Sonnet 4.5", "claude-sonnet-4-5-20250929"),
                     ("Claude Haiku", "claude-haiku-3-5-20241022")],
                    value=self._config.ai_model,
                    id="model-select",
                )

            # Voice section
            with Collapsible(title="Voice Settings"):
                yield Label("Whisper Model:")
                with RadioSet(id="whisper-model"):
                    yield RadioButton("tiny.en", value=...)
                    yield RadioButton("base.en", value=...)
                    yield RadioButton("small.en", value=...)

            # Action buttons
            with Horizontal():
                yield Button("Save", variant="primary", id="save")
                yield Button("Cancel", variant="default", id="cancel")

    def action_cancel(self):
        self.dismiss(None)
```

### Key Design Principles for TUI Settings

1. **Use ModalScreen** -- settings should overlay the main UI, not replace it
2. **Group by category** -- use `Collapsible` or `TabbedContent` to organize
3. **Show current values** -- pre-populate all fields with current config
4. **Validate before saving** -- use Input validators and show errors inline
5. **Escape to cancel** -- always provide a quick exit that discards changes
6. **Save to TOML** -- the existing `Config.save()` pattern is already correct
7. **Instant preview** -- for settings like theme/colors, apply changes live

---

## 4. Best Practices for Recent Chat Sections

### Industry Standard Patterns

**Date-Grouped Chronological List (ChatGPT pattern):**
```
  PINNED
    [star] Project architecture discussion
    [star] Bug investigation #42

  TODAY
    Voice debugging session - app.py
    Help with async patterns

  YESTERDAY
    Setting up DAP protocol
    Git workflow questions

  THIS WEEK
    Initial project setup
    ...

  OLDER
    ...
```

**Key UX Elements:**

1. **Message Preview** -- show first 50-80 chars of the first user message as a subtitle
2. **Message Count Badge** -- "(12 msgs)" helps gauge conversation depth
3. **Unread/Active Indicators** -- highlight the currently active session
4. **Timestamps** -- relative ("2 hours ago") for today, absolute ("Feb 7") for older
5. **Quick Actions** -- delete, rename, pin/unpin via keyboard shortcuts
6. **Search Bar** -- at the top; searches both titles and message content
7. **Auto-Generated Titles** -- use the AI to generate a 3-5 word title from the first exchange

**Pinning/Favorites:**
- WhatsApp allows pinning up to 3 conversations to the top
- ChatGPT users heavily requested pinning; it was partially implemented
- Pinned items should appear in a separate "Pinned" section above the date groups
- Star/unstar toggle should be accessible from the list view

**Search Patterns:**
- Incremental/fuzzy search as you type
- Search both conversation titles and message content
- Highlight matching text in results
- Most recent results first

### Conversation List in TUI Context

For a terminal app, the conversation list works best as:
- An `OptionList` or `ListView` inside a `ModalScreen` (triggered by hotkey)
- Or a sidebar panel (if screen width allows, typically 30-40 chars wide)
- With keyboard navigation (j/k or arrow keys)
- And a search `Input` at the top that filters the list in real time

---

## 5. Implementation Recommendations for TalkToMe

### Current State Assessment

The existing codebase already has:
- `ChatHistory` class (`/Users/idang/Projects/TalkToMe/heyducky/chat_history.py`) -- JSON-file-per-session storage in `~/.config/ducky/history/`
- `HistoryScreen` (`/Users/idang/Projects/TalkToMe/heyducky/widgets/history_screen.py`) -- basic ModalScreen with OptionList
- `Config` class (`/Users/idang/Projects/TalkToMe/heyducky/config.py`) -- TOML-based config with AI and voice settings
- `Orchestrator` (`/Users/idang/Projects/TalkToMe/heyducky/ai/orchestrator.py`) -- manages conversation history in memory with no compaction

### Recommendation 1: Add Conversation Compaction to Orchestrator

**Priority: HIGH** -- Without compaction, long debugging sessions will hit the 200K context limit.

**Approach: Use the Anthropic Compaction API (beta)**

```python
# In orchestrator.py - modify the send_message call:

response = await self._provider.send_message(
    messages=list(self._history),
    system=DEBUGGER_SYSTEM_PROMPT,
    tools=DEBUGGER_TOOLS,
    context_management={
        "edits": [{
            "type": "compact_20260112",
            "trigger": {"type": "input_tokens", "value": 100000},
            "pause_after_compaction": True,
            "instructions": (
                "Summarize this debugging conversation. Preserve: "
                "1) Current file being debugged and breakpoint positions "
                "2) Variables and their values that were discussed "
                "3) Bugs identified and fixes applied "
                "4) User preferences and constraints mentioned "
                "5) Next steps the user wanted to take"
            ),
        }]
    },
)

# Handle compaction pause to preserve recent context
if response.stop_reason == "compaction":
    self._compaction_count += 1
    # Notify UI that compaction occurred
    # Re-send with preserved recent messages
```

**Fallback (if not using the beta API):** Implement client-side compaction:

```python
async def _compact_if_needed(self):
    """Check token count and compact if approaching limit."""
    token_count = await self._provider.count_tokens(self._history)
    if token_count > 100_000:  # ~50% of 200K window
        summary = await self._provider.send_message(
            messages=self._history,
            system="Summarize this conversation for continuity...",
        )
        self._history = [
            {"role": "assistant", "content": f"[Conversation summary]: {summary.text}"}
        ]
```

**Config additions for `config.toml`:**

```toml
[ai]
compaction_threshold = 100000   # tokens before compaction triggers
compaction_enabled = true
max_compactions = 5             # force wrap-up after this many
```

### Recommendation 2: Enhance Chat History with Search and Date Grouping

**Priority: MEDIUM** -- Becomes important as users accumulate sessions.

**Changes to `ChatHistory`:**

```python
# Add to ChatHistory class:

def search_sessions(self, query: str) -> list[dict]:
    """Search session titles and message content."""
    query_lower = query.lower()
    results = []
    for session in self.list_sessions():
        # Check preview
        if query_lower in session["preview"].lower():
            results.append(session)
            continue
        # Check full message content
        try:
            messages = self.load_session(session["path"])
            for msg in messages:
                if query_lower in msg.get("content", "").lower():
                    results.append(session)
                    break
        except Exception:
            continue
    return results

def sessions_grouped_by_date(self) -> dict[str, list[dict]]:
    """Return sessions grouped into date buckets."""
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    today = now.date()
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)

    groups = {
        "Today": [],
        "Yesterday": [],
        "This Week": [],
        "Older": [],
    }

    for session in self.list_sessions():
        created = session.get("created", "")
        try:
            dt = datetime.fromisoformat(created).date()
        except (ValueError, TypeError):
            groups["Older"].append(session)
            continue

        if dt == today:
            groups["Today"].append(session)
        elif dt == yesterday:
            groups["Yesterday"].append(session)
        elif dt >= week_ago:
            groups["This Week"].append(session)
        else:
            groups["Older"].append(session)

    return {k: v for k, v in groups.items() if v}  # omit empty groups
```

**Changes to `HistoryScreen`:**

```python
# Add search input at top:
def compose(self) -> ComposeResult:
    with Vertical(id="history-container"):
        yield Label("Chat History", id="history-title")
        yield Input(placeholder="Search conversations...", id="history-search")
        yield OptionList(id="history-list")

def on_input_changed(self, event: Input.Changed) -> None:
    """Filter sessions as user types."""
    query = event.value
    if query:
        sessions = self._chat_history.search_sessions(query)
    else:
        sessions = self._chat_history.list_sessions()
    self._rebuild_option_list(sessions)
```

**Add auto-generated titles** by sending the first exchange to Claude with a prompt like "Generate a 3-5 word title for this conversation" and storing it in the session JSON.

### Recommendation 3: Add Settings Screen

**Priority: MEDIUM** -- Currently config requires manual TOML editing.

**New file: `heyducky/widgets/settings_screen.py`**

```python
class SettingsScreen(ModalScreen[Config | None]):
    """Settings screen with categorized preferences."""

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-container"):
            yield Label("Settings", id="settings-title")

            with Collapsible(title="AI Configuration", collapsed=False):
                yield Label("API Key:")
                yield Input(
                    value=self._config.api_key,
                    password=True,
                    id="setting-api-key",
                )
                yield Label("Model:")
                yield Select(
                    [
                        ("Claude Sonnet 4.5", "claude-sonnet-4-5-20250929"),
                        ("Claude Haiku 3.5", "claude-haiku-3-5-20241022"),
                    ],
                    value=self._config.ai_model,
                    id="setting-model",
                )
                yield Label("Auto-Compaction:")
                yield Switch(value=True, id="setting-compaction")
                yield Label("Compaction Threshold (tokens):")
                yield Input(
                    value="100000",
                    id="setting-compaction-threshold",
                    type="integer",
                )

            with Collapsible(title="Voice Configuration"):
                yield Label("Whisper Model:")
                with RadioSet(id="setting-whisper"):
                    yield RadioButton("tiny.en (fastest)")
                    yield RadioButton("base.en (balanced)", value=True)
                    yield RadioButton("small.en (best quality)")
                yield Label("Silence Threshold:")
                yield Input(
                    value=str(self._config.silence_threshold),
                    id="setting-silence-threshold",
                )
                yield Label("Silence Duration (seconds):")
                yield Input(
                    value=str(self._config.silence_duration),
                    id="setting-silence-duration",
                )

            with Horizontal(id="settings-buttons"):
                yield Button("Save", variant="primary", id="settings-save")
                yield Button("Cancel", variant="default", id="settings-cancel")
```

**Add keybinding in `app.py`:**
```python
Binding("s", "show_settings", "Settings", show=False, priority=True)
```

**Config additions needed:**
```python
# In Config dataclass, add:
compaction_enabled: bool = True
compaction_threshold: int = 100_000
max_compactions: int = 5
```

### Recommendation 4: Upgrade Session Storage Format

**Priority: LOW** -- Current JSON format works but could be richer.

**Enhanced session JSON schema:**

```json
{
  "version": 2,
  "session_id": "20260209_143022",
  "title": "Debugging async handler",
  "created": "2026-02-09T14:30:22+00:00",
  "updated": "2026-02-09T15:12:45+00:00",
  "message_count": 24,
  "preview": "Help me debug the async handler in app.py",
  "project_root": "/Users/idang/Projects/TalkToMe",
  "pinned": false,
  "tags": [],
  "total_tokens": 45230,
  "total_cost": 0.0234,
  "compaction_count": 1,
  "messages": [
    {
      "role": "user",
      "content": "Help me debug the async handler in app.py",
      "timestamp": "2026-02-09T14:30:22+00:00"
    }
  ]
}
```

**Consider SQLite for scale:** If history grows beyond ~100 sessions, searching JSON files becomes slow. A single SQLite database with full-text search (FTS5) would be more performant:

```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    title TEXT,
    created TEXT,
    updated TEXT,
    message_count INTEGER,
    preview TEXT,
    project_root TEXT,
    pinned INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    total_cost REAL DEFAULT 0
);

CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT REFERENCES sessions(id),
    role TEXT,
    content TEXT,
    timestamp TEXT
);

-- Full-text search index
CREATE VIRTUAL TABLE messages_fts USING fts5(content, content=messages, content_rowid=id);
```

However, for the near term (fewer than 100 sessions), the current JSON-per-file approach is simpler and sufficient. Migrate to SQLite only when search performance becomes a bottleneck.

### Implementation Priority Order

| Priority | Feature | Effort | Impact |
|----------|---------|--------|--------|
| 1 | Compaction in Orchestrator (API-based) | ~2 hours | Critical for long sessions |
| 2 | Compaction config fields in Config | ~30 min | Enables user control |
| 3 | Settings ModalScreen | ~3 hours | Eliminates manual TOML editing |
| 4 | Date-grouped history screen | ~2 hours | Better session navigation |
| 5 | Search in history screen | ~1.5 hours | Essential at scale |
| 6 | Auto-generated session titles | ~1 hour | Better session identification |
| 7 | Session pinning | ~1 hour | Nice-to-have |
| 8 | Enhanced session metadata | ~1 hour | Future-proofing |
| 9 | SQLite migration | ~4 hours | Only if >100 sessions |

---

## Key Takeaways

1. **Use the Anthropic Compaction API** -- it is purpose-built for exactly this use case. Server-side compaction with `compact_20260112` is the lowest-effort, highest-quality approach. Trigger at 100K tokens with custom instructions tailored to debugging context.

2. **Date-grouped history is the gold standard** -- "Today / Yesterday / This Week / Older" is what users expect from ChatGPT and similar apps. The existing `HistoryScreen` should add this grouping plus a search input.

3. **Settings screens in Textual use ModalScreen + Collapsible** -- the pattern is well-established: push a modal, organize settings into collapsible sections, save on button press, escape to cancel.

4. **The existing architecture is solid** -- the `ChatHistory` JSON-per-session pattern, `Config` TOML pattern, and `HistoryScreen` modal pattern are all correct foundations. The main gaps are compaction (critical), search (important), and settings UI (convenient).
