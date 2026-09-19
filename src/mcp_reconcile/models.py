"""Data models for MCP Reconcile."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ToolName(str, Enum):
    """Supported AI coding tools."""
    CLAUDE = "claude"
    CURSOR = "cursor"
    COPILOT = "copilot"
    CODEX = "codex"
    WINDSURF = "windsurf"
    VSCODE = "vscode"


class DriftType(str, Enum):
    """Types of configuration drift."""
    VERSION = "version"       # Same server, different version tags
    ARGS = "args"             # Same server, different arguments
    MISSING = "missing"       # Server in some tools but not others
    ORPHAN = "orphan"         # Server only in one tool
    COMMAND = "command"       # Same server, different launcher command
    ENV = "env"               # Same server, different env vars


@dataclass(frozen=True)
class MCPServer:
    """Represents a single MCP server configuration."""
    name: str
    command: str
    args: tuple[str, ...] = ()
    env: tuple[tuple[str, str], ...] = ()
    tool: ToolName = ToolName.CLAUDE
    source: str = ""  # config file path
    
    @property
    def full_command(self) -> str:
        """Return the full command string."""
        parts = [self.command] + list(self.args)
        return " ".join(parts)
    
    @property
    def version(self) -> Optional[str]:
        """Extract version from args (e.g., '@foo/bar@v1.2.3' -> 'v1.2.3')."""
        for arg in self.args:
            if "@v" in arg:
                return arg.split("@v")[-1]
        return None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "command": self.command,
            "args": list(self.args),
            "env": dict(self.env),
            "tool": self.tool.value,
            "source": self.source,
        }


@dataclass
class Drift:
    """Represents a detected drift between tools."""
    server_name: str
    drift_type: DriftType
    description: str
    canonical: Optional[MCPServer] = None  # The "correct" version
    drifts: list[MCPServer] = field(default_factory=list)  # Servers with drift
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "server_name": self.server_name,
            "drift_type": self.drift_type.value,
            "description": self.description,
            "canonical": self.canonical.to_dict() if self.canonical else None,
            "drifts": [s.to_dict() for s in self.drifts],
        }


@dataclass
class ScanResult:
    """Result of scanning all tool configurations."""
    servers: list[MCPServer] = field(default_factory=list)
    drifts: list[Drift] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    
    @property
    def has_drift(self) -> bool:
        return len(self.drifts) > 0
    
    @property
    def server_count(self) -> int:
        return len(self.servers)
    
    @property
    def tool_count(self) -> int:
        return len({s.tool for s in self.servers})
    
    def by_tool(self, tool: ToolName) -> list[MCPServer]:
        return [s for s in self.servers if s.tool == tool]
    
    def by_name(self, name: str) -> list[MCPServer]:
        return [s for s in self.servers if s.name == name]
