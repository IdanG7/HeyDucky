"""Tests for session auto-save (orchestrator get_state / restore_state)."""

from unittest.mock import AsyncMock, Mock

import pytest

from heyducky.ai.orchestrator import Orchestrator


@pytest.fixture
def mock_provider():
    provider = AsyncMock()
    provider.model_name = Mock(return_value="claude-sonnet-4-5-20250929")
    provider.count_tokens = AsyncMock(return_value=0)
    return provider


def test_get_state(mock_provider):
    orch = Orchestrator(provider=mock_provider)
    orch._history = [{"role": "user", "content": "hello"}]
    orch.total_input_tokens = 100
    orch.total_output_tokens = 50
    orch.total_cost = 0.001
    orch.compaction_count = 2
    state = orch.get_state()
    assert state["history"] == [{"role": "user", "content": "hello"}]
    assert state["total_input_tokens"] == 100
    assert state["total_output_tokens"] == 50
    assert state["total_cost"] == 0.001
    assert state["compaction_count"] == 2


def test_restore_state(mock_provider):
    orch = Orchestrator(provider=mock_provider)
    state = {
        "history": [{"role": "user", "content": "test"}],
        "total_input_tokens": 200,
        "total_output_tokens": 100,
        "total_cost": 0.005,
        "compaction_count": 1,
    }
    orch.restore_state(state)
    assert orch._history == [{"role": "user", "content": "test"}]
    assert orch.total_input_tokens == 200
    assert orch.total_cost == 0.005
    assert orch.compaction_count == 1


def test_get_restore_round_trip(mock_provider):
    orch = Orchestrator(provider=mock_provider)
    orch._history = [{"role": "user", "content": "round trip"}]
    orch.total_input_tokens = 500
    orch.total_cost = 0.01
    state = orch.get_state()
    orch2 = Orchestrator(provider=mock_provider)
    orch2.restore_state(state)
    assert orch2._history == orch._history
    assert orch2.total_cost == orch.total_cost


def test_restore_state_empty_dict(mock_provider):
    orch = Orchestrator(provider=mock_provider)
    orch.restore_state({})
    assert orch._history == []
    assert orch.total_cost == 0.0


def test_restore_state_partial_dict(mock_provider):
    orch = Orchestrator(provider=mock_provider)
    orch.restore_state({"history": [{"role": "user", "content": "partial"}]})
    assert len(orch._history) == 1
    assert orch.total_cost == 0.0
