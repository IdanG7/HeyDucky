"""Debug adapter registry - maps languages to adapter launch configs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AdapterConfig:
    """Configuration for launching a debug adapter."""

    command: list[str]
    transport: str = "stdio"  # "stdio" or "tcp"
    host: str = "127.0.0.1"
    port: int = 0
    launch_args: dict[str, Any] = field(default_factory=dict)
    attach_args: dict[str, Any] = field(default_factory=dict)


ADAPTER_REGISTRY: dict[str, AdapterConfig] = {
    "python": AdapterConfig(
        command=["python", "-m", "debugpy.adapter"],
        transport="stdio",
        launch_args={"justMyCode": False, "console": "internalConsole"},
        attach_args={"justMyCode": False},
    ),
    "cpp": AdapterConfig(
        command=["lldb-dap"],
        transport="stdio",
        attach_args={},
    ),
    "go": AdapterConfig(
        command=["dlv", "dap"],
        transport="stdio",
        attach_args={"mode": "remote"},
    ),
    "rust": AdapterConfig(
        command=["codelldb"],
        transport="tcp",
        port=13000,
    ),
}

_EXTENSION_MAP: dict[str, str] = {
    ".py": "python",
    ".c": "cpp",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".h": "cpp",
    ".hpp": "cpp",
    ".go": "go",
    ".rs": "rust",
}


def detect_language(file_path: str) -> str | None:
    """Detect programming language from file extension."""
    ext = Path(file_path).suffix.lower()
    return _EXTENSION_MAP.get(ext)


def get_adapter_config(language: str) -> AdapterConfig | None:
    """Get adapter configuration for a language."""
    return ADAPTER_REGISTRY.get(language)
