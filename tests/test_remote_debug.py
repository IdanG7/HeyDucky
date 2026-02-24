"""Tests for remote debugging: attach mode, path mapping, and source fallback."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from heyducky.ai.provider import ToolCall
from heyducky.debugger.adapters import AdapterConfig, get_adapter_config
from heyducky.debugger.dap_client import DAPClient
from heyducky.debugger.session import DebugSession
from heyducky.debugger.tool_executor import ToolExecutor
from heyducky.debugger.types import DAPResponse

# ------------------------------------------------------------------
# DAPClient.attach()
# ------------------------------------------------------------------


@pytest.fixture
def mock_transport():
    transport = AsyncMock()
    transport.send = AsyncMock()
    transport.start = AsyncMock()
    transport.close = AsyncMock()
    return transport


@pytest.fixture
def client(mock_transport):
    c = DAPClient.__new__(DAPClient)
    c._transport = mock_transport
    c._seq = 1
    c._pending: dict = {}
    c._event_handlers: dict = {}
    c.state = "idle"
    c.current_file = None
    c.current_line = None
    c.thread_id = None
    c.breakpoints: dict = {}
    return c


@pytest.mark.asyncio
async def test_attach_sends_request(client, mock_transport):
    """DAPClient.attach() sends an attach request and sets state to running."""

    async def fake_send(req):
        response_data = {
            "seq": 1,
            "type": "response",
            "request_seq": req.seq,
            "success": True,
            "command": "attach",
            "body": {},
        }
        await client._handle_message(response_data)

    mock_transport.send = fake_send
    resp = await client.attach(justMyCode=False)
    assert resp.success is True
    assert resp.command == "attach"
    assert client.state == "running"


@pytest.mark.asyncio
async def test_get_source_sends_request(client, mock_transport):
    """DAPClient.get_source() sends a source request."""

    async def fake_send(req):
        response_data = {
            "seq": 1,
            "type": "response",
            "request_seq": req.seq,
            "success": True,
            "command": "source",
            "body": {"content": "print('hello')"},
        }
        await client._handle_message(response_data)

    mock_transport.send = fake_send
    resp = await client.get_source(42)
    assert resp.success is True
    assert resp.body["content"] == "print('hello')"


# ------------------------------------------------------------------
# AdapterConfig.attach_args
# ------------------------------------------------------------------


def test_python_adapter_has_attach_args():
    cfg = get_adapter_config("python")
    assert cfg is not None
    assert "justMyCode" in cfg.attach_args


def test_adapter_config_attach_args_default():
    cfg = AdapterConfig(command=["test"])
    assert cfg.attach_args == {}


# ------------------------------------------------------------------
# DebugSession.start_attach()
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_session_start_attach():
    """DebugSession.start_attach() connects via TCP and sends attach."""
    with patch("heyducky.debugger.session.DAPClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.initialize = AsyncMock(return_value=MagicMock(success=True))
        mock_client.attach = AsyncMock(return_value=MagicMock(success=True))
        mock_client.configuration_done = AsyncMock(return_value=MagicMock(success=True))
        mock_client.on_event = MagicMock()
        mock_client.start_tcp = AsyncMock()
        mock_cls.return_value = mock_client

        session = DebugSession(on_state_change=AsyncMock(), on_output=AsyncMock())
        path_map = {"/remote/src": "/local/src"}
        await session.start_attach("10.0.0.5", 5678, "python", path_map=path_map)

        mock_client.start_tcp.assert_called_once_with("10.0.0.5", 5678)
        mock_client.initialize.assert_called_once()
        mock_client.attach.assert_called_once()
        mock_client.configuration_done.assert_called_once()

        assert session.is_remote is True
        assert session.language == "python"
        assert session.path_map == {"/remote/src": "/local/src"}


def test_session_translate_path():
    """DebugSession translates remote paths to local."""
    session = DebugSession.__new__(DebugSession)
    session._path_map = {"/home/user/project": "/Users/me/project"}
    session._dap_client = None
    session._on_state_change = None
    session._on_output = None
    session.program = None
    session.language = None
    session.is_remote = True

    assert session._translate_path("/home/user/project/main.py") == "/Users/me/project/main.py"
    assert session._translate_path("/other/path.py") == "/other/path.py"


# ------------------------------------------------------------------
# ToolExecutor path mapping
# ------------------------------------------------------------------


def test_tool_executor_resolve_path():
    """ToolExecutor resolves remote paths to local."""
    executor = ToolExecutor(
        dap_client=None,
        project_root="/local/proj",
        path_map={"/remote/proj": "/local/proj"},
    )
    assert executor._resolve_path("/remote/proj/src/main.py") == "/local/proj/src/main.py"
    assert executor._resolve_path("/unrelated/file.py") == "/unrelated/file.py"


def test_tool_executor_to_remote_path():
    """ToolExecutor maps local paths back to remote."""
    executor = ToolExecutor(
        dap_client=None,
        project_root="/local/proj",
        path_map={"/remote/proj": "/local/proj"},
    )
    assert executor._to_remote_path("/local/proj/src/main.py") == "/remote/proj/src/main.py"
    assert executor._to_remote_path("/unrelated/file.py") == "/unrelated/file.py"


@pytest.mark.asyncio
async def test_read_source_with_path_mapping(tmp_path):
    """read_source translates remote path to local before reading."""
    src = tmp_path / "app.py"
    src.write_text("line1\nline2\nline3\n")

    executor = ToolExecutor(
        dap_client=None,
        project_root=str(tmp_path),
        path_map={"/remote/proj": str(tmp_path)},
    )
    result = await executor.execute(
        ToolCall(id="r1", name="read_source", arguments={"file": "/remote/proj/app.py"})
    )
    assert "line1" in result
    assert "line2" in result


@pytest.mark.asyncio
async def test_read_source_fallback_to_dap_source():
    """When local file doesn't exist and dap_source_fallback is on, ask the adapter."""
    mock_dap = AsyncMock()
    mock_dap.get_source = AsyncMock(
        return_value=DAPResponse(
            seq=1,
            request_seq=1,
            success=True,
            command="source",
            body={"content": "remote_line1\nremote_line2\n"},
        )
    )

    executor = ToolExecutor(
        dap_client=mock_dap,
        project_root="/nonexistent",
        dap_source_fallback=True,
    )
    result = await executor.execute(
        ToolCall(id="r2", name="read_source", arguments={"file": "/remote/missing.py"})
    )
    assert "remote_line1" in result
    mock_dap.get_source.assert_called_once()


@pytest.mark.asyncio
async def test_read_source_no_fallback_shows_error():
    """Without dap_source_fallback, missing files return an error."""
    executor = ToolExecutor(
        dap_client=None,
        project_root="/nonexistent",
        dap_source_fallback=False,
    )
    result = await executor.execute(
        ToolCall(id="r3", name="read_source", arguments={"file": "/no/such/file.py"})
    )
    assert "could not read" in result.lower()


@pytest.mark.asyncio
async def test_list_files_with_path_mapping(tmp_path):
    """list_files translates remote path to local directory."""
    (tmp_path / "hello.py").write_text("x")

    executor = ToolExecutor(
        dap_client=None,
        project_root=str(tmp_path),
        path_map={"/remote/proj": str(tmp_path)},
    )
    result = await executor.execute(
        ToolCall(id="l1", name="list_files", arguments={"path": "/remote/proj"})
    )
    assert "hello.py" in result


@pytest.mark.asyncio
async def test_set_breakpoint_sends_remote_path():
    """set_breakpoint translates local paths back to remote for the adapter."""
    mock_dap = AsyncMock()
    mock_dap.set_breakpoint = AsyncMock(
        return_value=DAPResponse(
            seq=1,
            request_seq=1,
            success=True,
            command="setBreakpoints",
            body={"breakpoints": [{"verified": True, "line": 10}]},
        )
    )

    executor = ToolExecutor(
        dap_client=mock_dap,
        project_root="/local/proj",
        path_map={"/remote/proj": "/local/proj"},
    )
    await executor.execute(
        ToolCall(
            id="b1",
            name="set_breakpoint",
            arguments={"file": "/local/proj/main.py", "line": 10},
        )
    )
    mock_dap.set_breakpoint.assert_called_once_with("/remote/proj/main.py", 10, "")
