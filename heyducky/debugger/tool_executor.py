"""Bridge between AI tool calls and DAP client operations."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from heyducky.debugger.dap_client import DAPClient
    from heyducky.ai.provider import ToolCall
    from heyducky.remote.file_client import RemoteFileClient


class ToolExecutor:
    """Executes AI tool calls against the DAP client.

    Maps tool names (e.g. ``set_breakpoint``, ``inspect_variable``) to
    the corresponding high-level methods on :class:`DAPClient` and returns
    a human-readable result string that can be fed back to the AI.
    """

    def __init__(
        self,
        dap_client: DAPClient | None,
        project_root: str | None = None,
        path_map: dict[str, str] | None = None,
        dap_source_fallback: bool = False,
        remote_files: RemoteFileClient | None = None,
    ) -> None:
        self._dap = dap_client
        self._project_root = project_root
        self._path_map: dict[str, str] = path_map or {}
        self._dap_source_fallback = dap_source_fallback
        self._remote_files = remote_files
        self._on_watch: callable | None = None
        self._on_unwatch: callable | None = None

    def _resolve_path(self, remote_path: str) -> str:
        """Translate a remote path to its local equivalent using path_map."""
        for remote_prefix, local_prefix in self._path_map.items():
            if remote_path.startswith(remote_prefix):
                return remote_path.replace(remote_prefix, local_prefix, 1)
        return remote_path

    def _to_remote_path(self, local_path: str) -> str:
        """Translate a local path back to its remote equivalent."""
        for remote_prefix, local_prefix in self._path_map.items():
            if local_path.startswith(local_prefix):
                return local_path.replace(local_prefix, remote_prefix, 1)
        return local_path

    async def execute(self, tool_call: ToolCall) -> str:
        """Execute a tool call and return a human-readable result string."""
        name = tool_call.name
        args = tool_call.arguments

        handler = getattr(self, f"_exec_{name}", None)
        if handler is None:
            return f"Unknown tool: {name}"

        # Some tools don't need a DAP client
        no_dap_tools = {"run_git_command", "watch_variable", "unwatch_variable", "read_source", "list_files"}
        if name not in no_dap_tools and self._dap is None:
            return f"No debug session active. Cannot execute {name}."

        return await handler(args)

    # ------------------------------------------------------------------
    # Breakpoints
    # ------------------------------------------------------------------

    async def _exec_set_breakpoint(self, args: dict) -> str:
        file_path = self._to_remote_path(args["file"])
        resp = await self._dap.set_breakpoint(
            file_path, args["line"], args.get("condition", "")
        )
        if resp.success:
            bps = resp.body.get("breakpoints", [])
            verified = all(bp.get("verified", False) for bp in bps)
            status = "verified" if verified else "pending"
            condition = args.get("condition", "")
            cond_text = f" when {condition}" if condition else ""
            return f"Breakpoint set at {args['file']}:{args['line']}{cond_text} ({status})"
        return f"Failed to set breakpoint: {resp.message}"

    # ------------------------------------------------------------------
    # Stepping / execution control
    # ------------------------------------------------------------------

    async def _exec_step_over(self, args: dict) -> str:
        await self._dap.step_over()
        return "Stepped over"

    async def _exec_step_into(self, args: dict) -> str:
        await self._dap.step_into()
        return "Stepped into"

    async def _exec_step_out(self, args: dict) -> str:
        await self._dap.step_out()
        return "Stepped out"

    async def _exec_continue_execution(self, args: dict) -> str:
        await self._dap.continue_execution()
        return "Continuing execution"

    # ------------------------------------------------------------------
    # Inspection / evaluation
    # ------------------------------------------------------------------

    async def _exec_inspect_variable(self, args: dict) -> str:
        resp = await self._dap.evaluate(args["name"], None)
        if resp.success:
            val = resp.body.get("result", "?")
            vtype = resp.body.get("type", "")
            return f"{args['name']} = {val}" + (f" ({vtype})" if vtype else "")
        return f"Could not inspect {args['name']}: {resp.message}"

    async def _exec_evaluate_expression(self, args: dict) -> str:
        resp = await self._dap.evaluate(args["expression"], None)
        if resp.success:
            return f"Result: {resp.body.get('result', '?')}"
        return f"Evaluation failed: {resp.message}"

    async def _exec_get_call_stack(self, args: dict) -> str:
        resp = await self._dap.get_stack_trace()
        if resp.success:
            frames = resp.body.get("stackFrames", [])
            lines = []
            for f in frames:
                source = f.get("source", {})
                path = source.get("path", "?") if isinstance(source, dict) else "?"
                lines.append(
                    f"  {f.get('name', '?')} at {path}:{f.get('line', '?')}"
                )
            return "Call stack:\n" + "\n".join(lines) if lines else "Empty call stack"
        return f"Could not get call stack: {resp.message}"

    # ------------------------------------------------------------------
    # Source reading (file-system only, no DAP call needed)
    # ------------------------------------------------------------------

    async def _exec_read_source(self, args: dict) -> str:
        raw_path = args["file"]
        local_path = self._resolve_path(raw_path)
        line = args.get("line")
        context = min(args.get("context", 10), 200)

        content: str | None = None

        # Try remote file client first (remote debugging with agent)
        if self._remote_files:
            content = await self._remote_files.read_file(raw_path)

        # Try local filesystem (with path mapping applied)
        if content is None:
            try:
                content = Path(local_path).read_text()
            except OSError:
                pass

        # Last resort: ask the debug adapter for the source
        if content is None and self._dap_source_fallback and self._dap:
            try:
                resp = await self._dap.get_source(0)
                if resp.success:
                    content = resp.body.get("content", "")
            except Exception:
                pass

        if content is None:
            return f"Could not read {raw_path}: file not found"

        all_lines = content.split("\n")

        if line is None:
            cap = min(len(all_lines), 500)
            snippet = []
            for i, src_line in enumerate(all_lines[:cap], 1):
                snippet.append(f"   {i:4d} | {src_line}")
            result = "\n".join(snippet)
            if len(all_lines) > cap:
                result += f"\n... ({len(all_lines) - cap} more lines)"
            return result
        else:
            start = max(0, line - context - 1)
            end = min(len(all_lines), line + context)
            snippet = []
            for i, src_line in enumerate(all_lines[start:end], start + 1):
                marker = ">>>" if i == line else "   "
                snippet.append(f"{marker} {i:4d} | {src_line}")
            return "\n".join(snippet)

    async def _exec_list_files(self, args: dict) -> str:
        raw_path = args.get("path", self._project_root or ".")
        path = self._resolve_path(raw_path)
        recursive = args.get("recursive", False)

        # Try remote file client first
        if self._remote_files:
            entries = await self._remote_files.list_dir(raw_path, recursive=recursive)
            if entries is not None:
                if not entries:
                    return f"Empty directory: {raw_path}"
                formatted = [f"  {e}" for e in entries]
                return f"{raw_path}/\n" + "\n".join(formatted)

        # Fall back to local filesystem
        try:
            target = Path(path)
            if not target.is_dir():
                return f"Not a directory: {path}"

            skip = {".git", "__pycache__", "node_modules", ".venv", "venv",
                    ".eggs", ".tox", ".mypy_cache", ".pytest_cache"}

            entries_local = []
            if recursive:
                for item in sorted(target.rglob("*")):
                    if any(p.name in skip for p in item.parents):
                        continue
                    if item.name in skip:
                        continue
                    rel = item.relative_to(target)
                    suffix = "/" if item.is_dir() else ""
                    entries_local.append(f"  {rel}{suffix}")
                    if len(entries_local) >= 200:
                        entries_local.append("  ... (truncated)")
                        break
            else:
                for item in sorted(target.iterdir()):
                    if item.name in skip or item.name.startswith("."):
                        continue
                    suffix = "/" if item.is_dir() else ""
                    entries_local.append(f"  {item.name}{suffix}")

            if not entries_local:
                return f"Empty directory: {path}"
            return f"{path}/\n" + "\n".join(entries_local)
        except OSError as e:
            return f"Could not list {path}: {e}"

    # ------------------------------------------------------------------
    # Git commands
    # ------------------------------------------------------------------

    async def _exec_run_git_command(self, args: dict) -> str:
        if not self._project_root:
            return "No project root configured. Cannot run git commands."
        from heyducky.git_executor import GitExecutor, GitCommandBlocked
        executor = GitExecutor(self._project_root)
        try:
            return executor.run(args["command"])
        except GitCommandBlocked as e:
            return f"Blocked: {e}"

    # ------------------------------------------------------------------
    # Variable watch panel
    # ------------------------------------------------------------------

    async def _exec_watch_variable(self, args: dict) -> str:
        name = args["name"]
        if self._on_watch:
            self._on_watch(name)
        return f"Now watching: {name}"

    async def _exec_unwatch_variable(self, args: dict) -> str:
        name = args["name"]
        if self._on_unwatch:
            self._on_unwatch(name)
        return f"Stopped watching: {name}"
