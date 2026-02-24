"""Tests for tool executor bridging AI tool calls to debugger."""

import pytest
from unittest.mock import AsyncMock
from heyducky.debugger.tool_executor import ToolExecutor
from heyducky.ai.provider import ToolCall
from heyducky.debugger.types import DAPResponse


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
    await executor.execute(
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
    await executor.execute(
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
async def test_execute_set_breakpoint_condition_in_result(mock_dap):
    """ToolExecutor includes condition in the confirmation string."""
    executor = ToolExecutor(mock_dap)
    result = await executor.execute(
        ToolCall(
            id="t12",
            name="set_breakpoint",
            arguments={"file": "app.py", "line": 42, "condition": "x > 10"},
        )
    )
    assert "when x > 10" in result
    assert "app.py:42" in result
    assert "verified" in result.lower()


@pytest.mark.asyncio
async def test_execute_set_breakpoint_no_condition_in_result(mock_dap):
    """ToolExecutor omits condition text when no condition is given."""
    executor = ToolExecutor(mock_dap)
    result = await executor.execute(
        ToolCall(
            id="t13",
            name="set_breakpoint",
            arguments={"file": "app.py", "line": 10},
        )
    )
    assert "when" not in result
    assert "app.py:10" in result
    assert "verified" in result.lower()


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


# ------------------------------------------------------------------
# Watch / unwatch variable
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_watch_variable(mock_dap):
    """ToolExecutor handles watch_variable and calls the callback."""
    watched = []
    executor = ToolExecutor(mock_dap)
    executor._on_watch = lambda name: watched.append(name)
    result = await executor.execute(
        ToolCall(id="w1", name="watch_variable", arguments={"name": "x"})
    )
    assert result == "Now watching: x"
    assert watched == ["x"]


@pytest.mark.asyncio
async def test_execute_unwatch_variable(mock_dap):
    """ToolExecutor handles unwatch_variable and calls the callback."""
    unwatched = []
    executor = ToolExecutor(mock_dap)
    executor._on_unwatch = lambda name: unwatched.append(name)
    result = await executor.execute(
        ToolCall(id="w2", name="unwatch_variable", arguments={"name": "x"})
    )
    assert result == "Stopped watching: x"
    assert unwatched == ["x"]


@pytest.mark.asyncio
async def test_watch_variable_no_dap_needed():
    """watch_variable works without a DAP client."""
    executor = ToolExecutor(None)
    executor._on_watch = lambda name: None
    result = await executor.execute(
        ToolCall(id="w3", name="watch_variable", arguments={"name": "y"})
    )
    assert result == "Now watching: y"


@pytest.mark.asyncio
async def test_unwatch_variable_no_dap_needed():
    """unwatch_variable works without a DAP client."""
    executor = ToolExecutor(None)
    executor._on_unwatch = lambda name: None
    result = await executor.execute(
        ToolCall(id="w4", name="unwatch_variable", arguments={"name": "y"})
    )
    assert result == "Stopped watching: y"


@pytest.mark.asyncio
async def test_watch_variable_no_callback(mock_dap):
    """watch_variable still returns result even without a callback."""
    executor = ToolExecutor(mock_dap)
    result = await executor.execute(
        ToolCall(id="w5", name="watch_variable", arguments={"name": "z"})
    )
    assert result == "Now watching: z"


# ------------------------------------------------------------------
# read_source whole-file mode
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_source_whole_file(tmp_path):
    """read_source without line arg reads the entire file."""
    src = tmp_path / "whole.py"
    src.write_text("a\nb\nc\nd\ne\n")
    executor = ToolExecutor(None, project_root=str(tmp_path))
    result = await executor.execute(
        ToolCall(id="rs1", name="read_source", arguments={"file": str(src)})
    )
    assert "a" in result
    assert "e" in result
    # No >>> marker when no line specified
    assert ">>>" not in result


@pytest.mark.asyncio
async def test_read_source_whole_file_capped(tmp_path):
    """read_source caps whole-file reads at 500 lines."""
    src = tmp_path / "big.py"
    src.write_text("\n".join(f"line{i}" for i in range(600)))
    executor = ToolExecutor(None, project_root=str(tmp_path))
    result = await executor.execute(
        ToolCall(id="rs2", name="read_source", arguments={"file": str(src)})
    )
    assert "more lines" in result


# ------------------------------------------------------------------
# list_files tool
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_files_basic(tmp_path):
    """list_files shows files in a directory."""
    (tmp_path / "foo.py").write_text("x")
    (tmp_path / "bar.py").write_text("y")
    (tmp_path / "sub").mkdir()
    executor = ToolExecutor(None, project_root=str(tmp_path))
    result = await executor.execute(
        ToolCall(id="lf1", name="list_files", arguments={"path": str(tmp_path)})
    )
    assert "foo.py" in result
    assert "bar.py" in result
    assert "sub/" in result


@pytest.mark.asyncio
async def test_list_files_default_project_root(tmp_path):
    """list_files defaults to project root."""
    (tmp_path / "main.py").write_text("x")
    executor = ToolExecutor(None, project_root=str(tmp_path))
    result = await executor.execute(
        ToolCall(id="lf2", name="list_files", arguments={})
    )
    assert "main.py" in result


@pytest.mark.asyncio
async def test_list_files_recursive(tmp_path):
    """list_files recursive mode finds nested files."""
    sub = tmp_path / "src"
    sub.mkdir()
    (sub / "app.py").write_text("x")
    executor = ToolExecutor(None, project_root=str(tmp_path))
    result = await executor.execute(
        ToolCall(id="lf3", name="list_files", arguments={"path": str(tmp_path), "recursive": True})
    )
    assert "app.py" in result


@pytest.mark.asyncio
async def test_list_files_skips_git(tmp_path):
    """list_files hides .git and other noise directories."""
    (tmp_path / ".git").mkdir()
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "real.py").write_text("x")
    executor = ToolExecutor(None, project_root=str(tmp_path))
    result = await executor.execute(
        ToolCall(id="lf4", name="list_files", arguments={"path": str(tmp_path)})
    )
    assert "real.py" in result
    assert ".git" not in result
    assert "__pycache__" not in result


@pytest.mark.asyncio
async def test_list_files_no_dap_needed():
    """list_files works without a DAP client."""
    executor = ToolExecutor(None)
    result = await executor.execute(
        ToolCall(id="lf5", name="list_files", arguments={"path": "."})
    )
    # Should work, just list the current directory
    assert isinstance(result, str)
