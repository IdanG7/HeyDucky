"""Safe git command execution with allowlist enforcement."""

from __future__ import annotations

import subprocess


class GitCommandBlocked(Exception):
    """Raised when a git command is not in the allowlist."""


ALLOWED_SUBCOMMANDS = frozenset({
    "status", "diff", "log", "show", "branch", "add", "commit",
    "stash", "blame", "shortlog", "tag", "remote", "version",
})

BLOCKED_SUBCOMMANDS = frozenset({
    "push", "clean", "rebase", "reset", "force-push",
})


class GitExecutor:
    """Executes git commands with safety constraints.

    Only allows a predefined set of safe subcommands.
    Blocks destructive operations like push, reset --hard, clean -f.
    Truncates output to stay within AI context limits.
    """

    def __init__(self, project_root: str, max_output_chars: int = 4000) -> None:
        self._project_root = project_root
        self._max_output_chars = max_output_chars

    def is_allowed(self, command: str) -> bool:
        """Check if a git command string is allowed."""
        parts = command.strip().split()
        if not parts:
            return False

        subcommand = parts[0]

        # Explicit block check
        if subcommand in BLOCKED_SUBCOMMANDS:
            return False

        # Must be in allowlist
        return subcommand in ALLOWED_SUBCOMMANDS

    def run(self, command: str) -> str:
        """Execute a git command and return output.

        Raises:
            GitCommandBlocked: If the command is not allowed.
        """
        if not self.is_allowed(command):
            raise GitCommandBlocked(f"Blocked git command: {command}")

        parts = command.strip().split()
        try:
            result = subprocess.run(
                ["git"] + parts,
                cwd=self._project_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout
            if result.returncode != 0 and result.stderr:
                output += f"\nSTDERR: {result.stderr}"

            if len(output) > self._max_output_chars:
                output = output[: self._max_output_chars] + "\n... (output truncated)"

            return output.strip() if output.strip() else "(no output)"
        except subprocess.TimeoutExpired:
            return "Command timed out after 30 seconds"
        except FileNotFoundError:
            return "git is not installed or not in PATH"
