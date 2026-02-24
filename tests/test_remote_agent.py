"""Tests for the remote debug agent: file server, file client, and ToolExecutor integration."""

import pytest

from heyducky.ai.provider import ToolCall
from heyducky.debugger.tool_executor import ToolExecutor
from heyducky.remote.file_client import RemoteFileClient
from heyducky.remote.file_server import FileServer

# ------------------------------------------------------------------
# FileServer + FileClient integration
# ------------------------------------------------------------------


@pytest.fixture
async def file_server(tmp_path):
    """Start a file server rooted at tmp_path, yield (server, port), then stop."""
    (tmp_path / "hello.py").write_text("print('hello')\nprint('world')\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "nested.py").write_text("x = 1\n")

    server = FileServer(str(tmp_path), host="127.0.0.1", port=0)
    port = await server.start()
    yield server, port, tmp_path
    await server.stop()


@pytest.fixture
async def file_client(file_server):
    """Connect a client to the test file server."""
    _server, port, root = file_server
    client = RemoteFileClient("127.0.0.1", port)
    await client.connect()
    yield client, root
    await client.close()


@pytest.mark.asyncio
async def test_ping(file_client):
    client, root = file_client
    project_root = await client.ping()
    assert project_root == str(root)


@pytest.mark.asyncio
async def test_read_file(file_client):
    client, root = file_client
    content = await client.read_file(str(root / "hello.py"))
    assert "print('hello')" in content
    assert "print('world')" in content


@pytest.mark.asyncio
async def test_read_file_relative(file_client):
    client, _root = file_client
    content = await client.read_file("hello.py")
    assert content is not None
    assert "hello" in content


@pytest.mark.asyncio
async def test_read_file_missing(file_client):
    client, _ = file_client
    content = await client.read_file("/nonexistent/file.py")
    assert content is None


@pytest.mark.asyncio
async def test_list_dir(file_client):
    client, root = file_client
    entries = await client.list_dir(str(root))
    assert entries is not None
    assert "hello.py" in entries
    assert "sub/" in entries


@pytest.mark.asyncio
async def test_list_dir_recursive(file_client):
    client, root = file_client
    entries = await client.list_dir(str(root), recursive=True)
    assert entries is not None
    found = [e for e in entries if "nested.py" in e]
    assert len(found) > 0


@pytest.mark.asyncio
async def test_list_dir_missing(file_client):
    client, _ = file_client
    entries = await client.list_dir("/nonexistent/dir")
    assert entries is None


# ------------------------------------------------------------------
# ToolExecutor with remote file client
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_executor_read_source_via_remote(file_client):
    """ToolExecutor uses RemoteFileClient for read_source."""
    client, root = file_client
    executor = ToolExecutor(
        dap_client=None,
        project_root=str(root),
        remote_files=client,
    )
    result = await executor.execute(
        ToolCall(id="r1", name="read_source", arguments={"file": str(root / "hello.py")})
    )
    assert "print('hello')" in result
    assert "print('world')" in result


@pytest.mark.asyncio
async def test_tool_executor_list_files_via_remote(file_client):
    """ToolExecutor uses RemoteFileClient for list_files."""
    client, root = file_client
    executor = ToolExecutor(
        dap_client=None,
        project_root=str(root),
        remote_files=client,
    )
    result = await executor.execute(
        ToolCall(id="l1", name="list_files", arguments={"path": str(root)})
    )
    assert "hello.py" in result
    assert "sub/" in result


@pytest.mark.asyncio
async def test_tool_executor_falls_back_to_local_when_no_remote(tmp_path):
    """Without a remote client, ToolExecutor reads from local filesystem."""
    src = tmp_path / "local.py"
    src.write_text("local_content\n")
    executor = ToolExecutor(
        dap_client=None,
        project_root=str(tmp_path),
        remote_files=None,
    )
    result = await executor.execute(
        ToolCall(id="r2", name="read_source", arguments={"file": str(src)})
    )
    assert "local_content" in result


# ------------------------------------------------------------------
# FileServer directly (unit tests)
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_file_server_skips_hidden_dirs(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "real.py").write_text("x")

    server = FileServer(str(tmp_path), host="127.0.0.1", port=0)
    port = await server.start()

    client = RemoteFileClient("127.0.0.1", port)
    await client.connect()

    entries = await client.list_dir(str(tmp_path))
    assert "real.py" in entries
    assert ".git/" not in entries
    assert "__pycache__/" not in entries

    await client.close()
    await server.stop()
