"""Parser for Codex MCP configuration."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from ..models import MCPServer, ToolName

CODEX_HOME = Path.home() / ".codex" / "config.toml"

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None


def parse_codex_toml(path: Path) -> list[MCPServer]:
    """Parse Codex MCP servers from a TOML config file."""
    servers = []
    if not path.exists():
        return servers
    
    if tomllib is None:
        return servers
    
    try:
        data = tomllib.loads(path.read_text())
    except Exception:
        return servers
    
    mcp_servers = data.get("mcp_servers", {})
    for name, cfg in mcp_servers.items():
        server = _make_server(name, cfg, ToolName.CODEX, str(path))
        if server:
            servers.append(server)
    
    return servers


def _make_server(
    name: str,
    cfg: dict | str,
    tool: ToolName,
    source: str,
) -> Optional[MCPServer]:
    """Create an MCPServer from a config dict."""
    if isinstance(cfg, str):
        return MCPServer(name=name, command=cfg, tool=tool, source=source)
    
    command = cfg.get("command", "")
    if not command:
        return None
    
    args = tuple(cfg.get("args", []))
    env_items = cfg.get("env", {})
    env = tuple(sorted(env_items.items())) if isinstance(env_items, dict) else ()
    
    return MCPServer(
        name=name,
        command=command,
        args=args,
        env=env,
        tool=tool,
        source=source,
    )


def get_codex_servers() -> list[MCPServer]:
    """Get all Codex MCP servers."""
    return parse_codex_toml(CODEX_HOME)
