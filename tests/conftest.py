"""Shared test fixtures for the HeyDucky test suite."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from heyducky.config import Config

# -- Config -------------------------------------------------------------------


@pytest.fixture
def test_config():
    """A Config with a dummy API key pre-set."""
    config = Config()
    config.api_key = "test-key-123"
    return config


@pytest.fixture
def config_path(tmp_path):
    """Temporary path for a config.toml file."""
    return tmp_path / "config.toml"


@pytest.fixture
def saved_config(test_config, config_path):
    """A Config saved to a temporary file; returns the path."""
    test_config.save(config_path)
    return config_path


# -- Mock transport -----------------------------------------------------------


@pytest.fixture
def mock_transport():
    """AsyncMock transport with send/start/close stubs."""
    transport = AsyncMock()
    transport.send = AsyncMock()
    transport.start = AsyncMock()
    transport.close = AsyncMock()
    return transport


# -- Mock DAP client ----------------------------------------------------------


@pytest.fixture
def mock_dap_client():
    """AsyncMock DAP client with common debugger methods."""
    client = AsyncMock()
    client.set_breakpoint = AsyncMock()
    client.step_over = AsyncMock()
    client.step_into = AsyncMock()
    client.step_out = AsyncMock()
    client.continue_execution = AsyncMock()
    client.evaluate = AsyncMock()
    client.get_stack_trace = AsyncMock()
    client.initialize = AsyncMock()
    client.launch = AsyncMock()
    client.attach = AsyncMock()
    client.configuration_done = AsyncMock()
    client.on_event = MagicMock()
    return client


# -- Mock AI provider ---------------------------------------------------------


@pytest.fixture
def mock_ai_provider():
    """AsyncMock AI provider returning a canned AIResponse."""
    from heyducky.ai.provider import AIResponse

    provider = AsyncMock()
    provider.send_message = AsyncMock(
        return_value=AIResponse(
            text="Test response",
            tool_calls=[],
            input_tokens=50,
            output_tokens=20,
        )
    )
    provider.model_name = MagicMock(return_value="claude-sonnet-4-5-20250929")
    provider.count_tokens = AsyncMock(return_value=0)
    return provider


# -- Patch helpers ------------------------------------------------------------


@pytest.fixture
def mock_whisper():
    """Patch faster_whisper.WhisperModel for voice handler tests."""
    with patch("heyducky.voice.WhisperModel") as mock:
        yield mock


@pytest.fixture
def mock_anthropic():
    """Patch AsyncAnthropic and return the mock client instance."""
    with patch("heyducky.ai.claude.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="Test response.")]
        mock_response.stop_reason = "end_turn"
        mock_response.usage = MagicMock(input_tokens=50, output_tokens=20)
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client
        yield mock_client


# -- DAP protocol helpers -----------------------------------------------------


def make_dap_bytes(msg: dict) -> bytes:
    """Encode a dict as a Content-Length framed DAP message."""
    payload = json.dumps(msg).encode("utf-8")
    header = f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii")
    return header + payload
