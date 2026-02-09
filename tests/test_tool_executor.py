"""Tests for tool executor bridging AI tool calls to debugger."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from voice_debugger.debugger.tool_executor import ToolExecutor
from voice_debugger.ai.provider import ToolCall
from voice_debugger.debugger.types import DAPResponse


@pytest.fixture
def mock_dap():
    """Create a mock DAP client."""
    client = AsyncMock()
    client.set_breakpoint = AsyncMock(
        return_value=DAPResponse(
            seq=1,
            request_seq=1,
            success=True,
            command="setBreakpoints",
            body={"breakpoints": [{"verified": True, "line": 10}]},
        )
    )
    client.step_over = AsyncMock(
        return_value=DAPResponse(
            seq=2, request_seq=2, success=True, command="next", body={}
        )
    )
    client.continue_execution = AsyncMock(
        return_value=DAPResponse(
            seq=3, request_seq=3, success=True, command="continue", body={}
        )
    )
    client.evaluate = AsyncMock(
        return_value=DAPResponse(
            seq=4,
            request_seq=4,
            success=True,
            command="evaluate",
            body={"result": "42", "type": "int"},
        )
    )
    client.get_stack_trace = AsyncMock(
        return_value=DAPResponse(
            seq=5,
            request_seq=5,
            success=True,
            command="stackTrace",
            body={
                "stackFrames": [
                    {"name": "main", "line": 10, "source": {"path": "test.py"}}
                ]
            },
        )
    )
    return client


@pytest.mark.asyncio
async def test_execute_set_breakpoint(mock_dap):
    """ToolExecutor handles set_breakpoint tool call."""
    executor = ToolExecutor(mock_dap)
    result = await executor.execute(
        ToolCall(id="t1", name="set_breakpoint", arguments={"file": "test.py", "line": 10})
    )
    mock_dap.set_breakpoint.assert_called_once_with("test.py", 10, "")
    assert "verified" in result.lower() or "set" in result.lower()


@pytest.mark.asyncio
async def test_execute_step_over(mock_dap):
    """ToolExecutor handles step_over."""
    executor = ToolExecutor(mock_dap)
    result = await executor.execute(
        ToolCall(id="t2", name="step_over", arguments={})
    )
    mock_dap.step_over.assert_called_once()


@pytest.mark.asyncio
async def test_execute_inspect_variable(mock_dap):
    """ToolExecutor handles inspect_variable via evaluate."""
    executor = ToolExecutor(mock_dap)
    result = await executor.execute(
        ToolCall(id="t3", name="inspect_variable", arguments={"name": "x"})
    )
    mock_dap.evaluate.assert_called_once_with("x", None)
    assert "42" in result


@pytest.mark.asyncio
async def test_execute_unknown_tool(mock_dap):
    """ToolExecutor handles unknown tool names gracefully."""
    executor = ToolExecutor(mock_dap)
    result = await executor.execute(
        ToolCall(id="t4", name="nonexistent_tool", arguments={})
    )
    assert "unknown" in result.lower()


@pytest.mark.asyncio
async def test_execute_continue(mock_dap):
    """ToolExecutor handles continue_execution."""
    executor = ToolExecutor(mock_dap)
    result = await executor.execute(
        ToolCall(id="t5", name="continue_execution", arguments={})
    )
    mock_dap.continue_execution.assert_called_once()
    assert "continu" in result.lower()


@pytest.mark.asyncio
async def test_execute_evaluate_expression(mock_dap):
    """ToolExecutor handles evaluate_expression."""
    executor = ToolExecutor(mock_dap)
    result = await executor.execute(
        ToolCall(
            id="t6",
            name="evaluate_expression",
            arguments={"expression": "1 + 1"},
        )
    )
    mock_dap.evaluate.assert_called_once_with("1 + 1", None)
    assert "42" in result


@pytest.mark.asyncio
async def test_execute_get_call_stack(mock_dap):
    """ToolExecutor handles get_call_stack."""
    executor = ToolExecutor(mock_dap)
    result = await executor.execute(
        ToolCall(id="t7", name="get_call_stack", arguments={})
    )
    mock_dap.get_stack_trace.assert_called_once()
    assert "main" in result
    assert "test.py" in result


@pytest.mark.asyncio
async def test_execute_read_source(mock_dap, tmp_path):
    """ToolExecutor reads source from a file."""
    src = tmp_path / "example.py"
    src.write_text("line1\nline2\nline3\nline4\nline5\n")
    executor = ToolExecutor(mock_dap)
    result = await executor.execute(
        ToolCall(
            id="t8",
            name="read_source",
            arguments={"file": str(src), "line": 3, "context": 1},
        )
    )
    assert ">>>" in result
    assert "line3" in result


@pytest.mark.asyncio
async def test_execute_read_source_missing_file(mock_dap):
    """ToolExecutor handles missing file gracefully."""
    executor = ToolExecutor(mock_dap)
    result = await executor.execute(
        ToolCall(
            id="t9",
            name="read_source",
            arguments={"file": "/nonexistent/path.py", "line": 1},
        )
    )
    assert "could not read" in result.lower()


@pytest.mark.asyncio
async def test_execute_set_breakpoint_with_condition(mock_dap):
    """ToolExecutor passes condition to set_breakpoint."""
    executor = ToolExecutor(mock_dap)
    result = await executor.execute(
        ToolCall(
            id="t10",
            name="set_breakpoint",
            arguments={"file": "app.py", "line": 5, "condition": "x > 10"},
        )
    )
    mock_dap.set_breakpoint.assert_called_once_with("app.py", 5, "x > 10")


@pytest.mark.asyncio
async def test_execute_set_breakpoint_failure(mock_dap):
    """ToolExecutor reports breakpoint failure."""
    mock_dap.set_breakpoint = AsyncMock(
        return_value=DAPResponse(
            seq=1,
            request_seq=1,
            success=False,
            command="setBreakpoints",
            body={},
            message="File not found",
        )
    )
    executor = ToolExecutor(mock_dap)
    result = await executor.execute(
        ToolCall(
            id="t11",
            name="set_breakpoint",
            arguments={"file": "missing.py", "line": 1},
        )
    )
    assert "failed" in result.lower()
    assert "File not found" in result


@pytest.mark.asyncio
async def test_execute_git_status(mock_dap, tmp_path):
    """ToolExecutor handles run_git_command for git status."""
    import subprocess
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)

    executor = ToolExecutor(mock_dap, project_root=str(tmp_path))
    result = await executor.execute(
        ToolCall(id="g1", name="run_git_command", arguments={"command": "status"})
    )
    assert isinstance(result, str)
    assert "branch" in result.lower() or "nothing" in result.lower() or "no commits" in result.lower()


@pytest.mark.asyncio
async def test_execute_git_push_blocked(mock_dap, tmp_path):
    """ToolExecutor blocks dangerous git commands."""
    executor = ToolExecutor(mock_dap, project_root=str(tmp_path))
    result = await executor.execute(
        ToolCall(id="g2", name="run_git_command", arguments={"command": "push origin main"})
    )
    assert "blocked" in result.lower()


@pytest.mark.asyncio
async def test_execute_git_no_project_root(mock_dap):
    """ToolExecutor without project_root returns error for git commands."""
    executor = ToolExecutor(mock_dap)
    result = await executor.execute(
        ToolCall(id="g3", name="run_git_command", arguments={"command": "status"})
    )
    assert "no project" in result.lower()
