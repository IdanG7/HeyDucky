"""Tool/function definitions for debugger operations."""

DEBUGGER_TOOLS = [
    {
        "name": "set_breakpoint",
        "description": "Set a breakpoint at a specific line in a file",
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
        "description": "Read source code around a specific line in a file",
        "input_schema": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "File path"},
                "line": {
                    "type": "integer",
                    "description": "Center line number",
                },
                "context": {
                    "type": "integer",
                    "description": "Lines of context (default 10)",
                },
            },
            "required": ["file", "line"],
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
]
