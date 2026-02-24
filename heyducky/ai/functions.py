"""Tool/function definitions for debugger operations."""

DEBUGGER_TOOLS = [
    {
        "name": "set_breakpoint",
        "description": "Set a breakpoint at a specific line in a file. For conditional breakpoints, translate natural language conditions to Python expressions in the 'condition' parameter (e.g., 'x > 10', 'name is None').",
        "input_schema": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "File path"},
                "line": {"type": "integer", "description": "Line number"},
                "condition": {
                    "type": "string",
                    "description": "Optional breakpoint condition",
                },
            },
            "required": ["file", "line"],
        },
    },
    {
        "name": "inspect_variable",
        "description": "Inspect the value of a variable in the current scope",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Variable name"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "step_over",
        "description": "Execute the current line and move to the next",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "step_into",
        "description": "Step into a function call on the current line",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "step_out",
        "description": "Step out of the current function",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "continue_execution",
        "description": "Resume execution until the next breakpoint",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "evaluate_expression",
        "description": "Evaluate an expression in the current debug context",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Expression to evaluate",
                },
            },
            "required": ["expression"],
        },
    },
    {
        "name": "get_call_stack",
        "description": "Get the current call stack",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "read_source",
        "description": "Read source code from a file. Call with just 'file' to read the whole file. Optionally pass 'line' to center on a specific line with surrounding context.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "File path"},
                "line": {
                    "type": "integer",
                    "description": "Optional center line number. Omit to read entire file.",
                },
                "context": {
                    "type": "integer",
                    "description": "Lines of context around 'line' (default 10, max 200). Ignored if line is omitted.",
                },
            },
            "required": ["file"],
        },
    },
    {
        "name": "list_files",
        "description": "List files and directories in a given path. Use to discover project structure or find files the user mentions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to list. Defaults to project root if omitted.",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "List recursively (default false). Use sparingly on large dirs.",
                },
            },
        },
    },
    {
        "name": "run_git_command",
        "description": "Execute a git command in the project directory. Use for: status, diff, log, show, branch, add, commit, stash, blame. BLOCKED: push, reset, clean, rebase. Always check 'status' before committing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Git subcommand and arguments (e.g., 'status', 'diff --staged', 'log --oneline -5', 'commit -m \"fix null check\"')",
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "watch_variable",
        "description": "Pin a variable to the watch panel so it auto-refreshes on each debug step",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Variable name to watch",
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "unwatch_variable",
        "description": "Remove a variable from the watch panel",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Variable name to unwatch",
                },
            },
            "required": ["name"],
        },
    },
]
