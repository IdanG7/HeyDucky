"""Bridge between AI tool calls and DAP client operations."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from voice_debugger.debugger.dap_client import DAPClient
    from voice_debugger.ai.provider import ToolCall


class ToolExecutor:
    """Executes AI tool calls against the DAP client.

    Maps tool names (e.g. ``set_breakpoint``, ``inspect_variable``) to
    the corresponding high-level methods on :class:`DAPClient` and returns
    a human-readable result string that can be fed back to the AI.
    """

    def __init__(self, dap_client: DAPClient) -> None:
        self._dap = dap_client

    async def execute(self, tool_call: ToolCall) -> str:
        """Execute a tool call and return a human-readable result string."""
        name = tool_call.name
        args = tool_call.arguments

        handler = getattr(self, f"_exec_{name}", None)
        if handler is None:
            return f"Unknown tool: {name}"
        return await handler(args)

    # ------------------------------------------------------------------
    # Breakpoints
    # ------------------------------------------------------------------

    async def _exec_set_breakpoint(self, args: dict) -> str:
        resp = await self._dap.set_breakpoint(
            args["file"], args["line"], args.get("condition", "")
        )
        if resp.success:
            bps = resp.body.get("breakpoints", [])
            verified = all(bp.get("verified", False) for bp in bps)
            status = "verified" if verified else "pending"
            return f"Breakpoint set at {args['file']}:{args['line']} ({status})"
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
        file_path = args["file"]
        line = args.get("line", 1)
        context = args.get("context", 10)
        try:
            content = Path(file_path).read_text()
            all_lines = content.split("\n")
            start = max(0, line - context - 1)
            end = min(len(all_lines), line + context)
            snippet = []
            for i, src_line in enumerate(all_lines[start:end], start + 1):
                marker = ">>>" if i == line else "   "
                snippet.append(f"{marker} {i:4d} | {src_line}")
            return "\n".join(snippet)
        except OSError as e:
            return f"Could not read {file_path}: {e}"
