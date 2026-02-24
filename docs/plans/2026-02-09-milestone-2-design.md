# Milestone 2: Debug Any Program with Voice

## Scope

Debug any program (Python, C/C++, Go, Rust) with voice commands in an IDE-like tabbed TUI.

### What we're building:
1. Generic DAP client (~200 lines) that speaks the Debug Adapter Protocol over stdio/TCP
2. Adapter launchers for Python (debugpy), C/C++ (lldb-dap), Go (delve), Rust (codelldb)
3. Tabbed TUI layout: Source, Conversation, Variables, Call Stack, Output
4. Working source view with syntax highlighting, breakpoint markers, current line
5. Variables panel showing locals/globals for current scope
6. Call stack panel with frame navigation
7. Debug output panel (program stdout/stderr)
8. AI tool calls connected to real debugger operations (no more stubs)
9. Tool execution loop: AI calls tool -> execute on debugger -> feed result back -> AI responds

### Not in scope:
- Git/workflow automation (Milestone 3)
- TTS output
- Streaming AI responses

## Architecture

### DAP Client

Generic client that communicates with any DAP-compliant debug adapter.

**Wire protocol**: JSON messages with Content-Length headers over stdio or TCP.

```
Content-Length: 119\r\n
\r\n
{"seq": 1, "type": "request", "command": "next", "arguments": {"threadId": 3}}
```

**Transport abstraction**:
- StdioTransport: Spawn adapter as subprocess, pipe stdin/stdout
- TCPTransport: Connect to adapter listening on host:port

**State machine**: idle -> initializing -> running -> paused -> stopped -> terminated

**Adapter registry**:
```python
ADAPTERS = {
    "python": {"command": ["python", "-m", "debugpy.adapter"], "transport": "stdio"},
    "cpp":    {"command": ["lldb-dap"], "transport": "stdio"},
    "go":     {"command": ["dlv", "dap"], "transport": "stdio"},
    "rust":   {"command": ["codelldb"], "transport": "tcp", "port": 13000},
}
```

### Tabbed TUI Layout

```
  [1: Source] [2: Conversation] [3: Variables] [4: Call Stack] [5: Output]
+----------------------------------------------------------------------+
|                                                                      |
|  (Full-screen content of selected tab)                               |
|                                                                      |
+----------------------------------------------------------------------+
|  Status: Paused at script.py:42 | Claude | $0.003 | Space: Talk     |
+----------------------------------------------------------------------+
```

Navigation:
- 1-5: Switch tabs
- Space: Toggle voice recording (works on any tab)
- F5/c: Continue
- F10/n: Step Over
- F11/i: Step Into
- Shift+F11/o: Step Out
- b: Toggle breakpoint

Default tab: Conversation (Tab 2). Auto-switches to Source on breakpoint hit.

### AI Tool Execution Loop

When Claude calls a debugger tool:
1. Orchestrator receives AIResponse with tool_calls
2. For each tool call, execute on DAPClient
3. Collect results
4. Send tool results back to Claude via add_tool_result()
5. Get Claude's final response
6. Display in conversation

New tool added: `read_source(file, line, context)` - lets Claude see code context.

### Source View Widget

- Rich.Syntax for language-aware syntax highlighting
- Gutter shows line numbers + breakpoint markers (red dot)
- Current execution line highlighted with arrow marker
- Auto-scrolls to current line on debugger stop events

### Variables Panel

- Tree view showing locals and globals
- Expandable for objects/dicts/lists
- Updates on each debugger stop event
- Shows type and value

### Call Stack Panel

- List of stack frames: function name, file, line
- Current frame highlighted
- Selecting a frame updates variables and source view

### Debug Output Panel

- Program stdout/stderr captured from DAP output events
- Scrollable log

## Project Structure (new/modified files)

```
heyducky/
  debugger/
    __init__.py
    dap_client.py        # Generic DAP client
    transport.py         # Stdio + TCP transports
    adapters.py          # Adapter registry and launcher
    types.py             # DAP message types
  widgets/
    source_view.py       # Upgraded with syntax highlighting
    variables.py         # New: variables panel
    call_stack.py        # New: call stack panel
    debug_output.py      # New: program output
    tab_bar.py           # New: tab navigation
  app.py                 # Updated with tabs + debug integration
  ai/
    orchestrator.py      # Updated with tool execution loop
    functions.py         # Updated with read_source tool
tests/
  test_dap_client.py
  test_transport.py
  test_adapters.py
  test_source_view.py
  test_tool_execution.py
```

## Dependencies (new for Milestone 2)

- debugpy >= 1.8.0 (Python debug adapter, already works as DAP server)
- No new external deps for DAP client (pure Python implementation)

## Success Criteria

- Can launch: `ducky run script.py`
- Source view shows script with syntax highlighting
- Can say "set breakpoint on line 10" and it works
- Can say "run" and program runs to breakpoint
- Variables panel shows current scope
- Call stack shows frames
- Can say "step over" / "step into" / "step out"
- Can say "what is x?" and Claude inspects via debugger
- Debug output shows program output
- Works with Python (debugpy) at minimum
- Adapter configs exist for C++, Go, Rust
