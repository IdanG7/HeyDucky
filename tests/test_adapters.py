"""Tests for debug adapter registry."""

import pytest
from voice_debugger.debugger.adapters import (
    AdapterConfig,
    ADAPTER_REGISTRY,
    detect_language,
    get_adapter_config,
)


def test_adapter_registry_has_python():
    """Registry includes Python adapter."""
    assert "python" in ADAPTER_REGISTRY
    cfg = ADAPTER_REGISTRY["python"]
    assert cfg.transport == "stdio"
    assert "debugpy" in " ".join(cfg.command)


def test_adapter_registry_has_cpp():
    """Registry includes C++ adapter."""
    assert "cpp" in ADAPTER_REGISTRY


def test_adapter_registry_has_go():
    """Registry includes Go adapter."""
    assert "go" in ADAPTER_REGISTRY


def test_adapter_registry_has_rust():
    """Registry includes Rust adapter."""
    assert "rust" in ADAPTER_REGISTRY


def test_detect_language_python():
    """Detects Python from .py extension."""
    assert detect_language("script.py") == "python"
    assert detect_language("/path/to/main.py") == "python"


def test_detect_language_cpp():
    """Detects C++ from .cpp/.c/.h extensions."""
    assert detect_language("main.cpp") == "cpp"
    assert detect_language("lib.c") == "cpp"


def test_detect_language_go():
    """Detects Go from .go extension."""
    assert detect_language("main.go") == "go"


def test_detect_language_rust():
    """Detects Rust from .rs extension."""
    assert detect_language("main.rs") == "rust"


def test_detect_language_unknown():
    """Returns None for unknown extensions."""
    assert detect_language("file.xyz") is None


def test_get_adapter_config():
    """get_adapter_config returns config for known languages."""
    cfg = get_adapter_config("python")
    assert isinstance(cfg, AdapterConfig)
    assert cfg.transport == "stdio"


def test_get_adapter_config_unknown():
    """get_adapter_config returns None for unknown languages."""
    assert get_adapter_config("brainfuck") is None
