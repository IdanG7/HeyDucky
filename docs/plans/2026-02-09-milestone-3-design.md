# Milestone 3: Project Browser + Git Workflow

## Scope

Add a project file browser to the Source tab and voice-driven git commands through Claude.

### What we're building:
1. File tree (DirectoryTree) in the Source tab — side-by-side split with source view (~25% tree, ~75% source)
2. Auto-detect project root from target file by walking up for project markers (.git, pyproject.toml, etc.)
3. Smart file filtering — hide .git, __pycache__, node_modules, build artifacts, IDE files by default
4. File tree ↔ debugger sync — tree highlights current debug file, auto-expands to it on breakpoint hit
5. Click file in tree → loads in source view (read-only browse)
6. Voice-driven git commands — new `run_git_command` AI tool so Claude can execute git operations
7. `--project` CLI flag as explicit override for project root

### Not in scope:
- File editing (this is a debugger, not an editor)
- Full PR/CI automation (Milestone 4)
- TTS output
- Remote filesystem browsing

## Architecture

### Source Tab Layout

```
┌──────────────────────────────────────────────────────┐
│ Source Tab                                            │
├────────────┬─────────────────────────────────────────┤
│ File Tree  │ Source View                              │
│ (~25%)     │ (~75%)                                   │
│            │                                          │
│ ▶ src/     │  1 │ def main():                         │
│   app.py   │  2 │●    x = None      ← breakpoint     │
│   config.  │  3 │→    print(x.val)  ← current line   │
│ ▶ tests/   │  4 │     return 0                        │
│   test_a.  │  5 │                                     │
│            │                                          │
├────────────┴─────────────────────────────────────────┤
```

Uses Textual's `Horizontal` container with `DirectoryTree` (left) and existing `SourceView` (right). CSS controls the 25/75 split.

### Project Root Detection

```python
def detect_project_root(start_path: Path) -> Path:
    """Walk up from start_path looking for project markers."""
    PROJECT_MARKERS = {
        ".git", "pyproject.toml", "setup.py", "Cargo.toml",
        "go.mod", "package.json", "CMakeLists.txt", "Makefile",
        ".sln", ".csproj",
    }
    current = start_path.resolve()
    if current.is_file():
        current = current.parent

    while current != current.parent:
        if any((current / marker).exists() for marker in PROJECT_MARKERS):
            return current
        current = current.parent

    return start_path.parent  # Fallback: target's directory
```

Priority: `--project` CLI flag > auto-detect from target > cwd.

### Filtered Directory Tree

Inherit from `DirectoryTree` and override `filter_paths`:

```python
IGNORE_PATTERNS = {
    # VCS
    ".git", ".svn", ".hg",
    # Python
    "__pycache__", ".venv", "venv", ".eggs", ".mypy_cache", ".ruff_cache",
    # JS/Node
    "node_modules",
    # Build
    "build", "dist", "target",
    # IDE
    ".idea", ".vscode", ".vs",
    # OS
    ".DS_Store", "Thumbs.db",
}

IGNORE_EXTENSIONS = {".pyc", ".pyo", ".egg-info"}

class ProjectTree(DirectoryTree):
    def filter_paths(self, paths):
        return [
            p for p in paths
            if p.name not in IGNORE_PATTERNS
            and p.suffix not in IGNORE_EXTENSIONS
        ]
```

### File Selection Flow

```
User clicks file in tree
    → DirectoryTree.FileSelected event
    → SourceView.load_source(path)
    → Source view updates with file content
```

### Debugger Sync

When debugger pauses at a breakpoint:
1. Source view loads the file and highlights current line (existing behavior)
2. **New**: File tree expands path to the debug file and highlights it
3. **New**: If the debug file is outside the project tree, show a system message

### Git Tool

New AI tool definition:

```python
{
    "name": "run_git_command",
    "description": "Execute a git command in the project directory. Use for status, diff, log, add, commit, branch, checkout, stash operations. Never use for push or destructive operations without explicit user confirmation.",
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Git subcommand and arguments (e.g., 'status', 'diff --staged', 'log --oneline -5')"
            }
        },
        "required": ["command"]
    }
}
```

**Safety constraints** (enforced in ToolExecutor):
- Allowlist of safe subcommands: status, diff, log, show, branch, add, commit, stash, blame, shortlog
- Block: push, force, reset --hard, clean -f, rebase
- Working directory set to project root
- Output truncated to 4000 chars (stay within context window)

### Updated System Prompt

Add to DEBUGGER_SYSTEM_PROMPT:
- Awareness of project file tree and ability to reference files by path
- Git tool usage guidelines: check status before committing, write clear messages
- Project root path injected as context

### CLI Changes

```
ducky [target] [--project PATH] [--setup]
```

If `--project` is given, use it. Otherwise auto-detect from target. If neither, use cwd.

## Components Summary

| Component | Type | New/Modified |
|-----------|------|-------------|
| `ProjectTree` | Widget | New — extends DirectoryTree |
| `SourceView` | Widget | Modified — split layout integration |
| `project.py` | Utility | New — detect_project_root() |
| `app.py` | App | Modified — new layout, file selection, git tool |
| `__main__.py` | CLI | Modified — --project flag |
| `functions.py` | AI tools | Modified — add run_git_command |
| `tool_executor.py` | Bridge | Modified — execute git commands |
| `prompts.py` | AI | Modified — project context in system prompt |

## Testing Strategy

- `test_project.py`: detect_project_root with various marker combos, fallback behavior
- `test_project_tree.py`: filter_paths hides expected patterns, shows source files
- `test_git_tool.py`: allowlist enforcement, output truncation, working dir
- `test_app.py`: source tab has tree + source side by side, file selection loads source
- Integration: tree syncs with debugger breakpoint file
