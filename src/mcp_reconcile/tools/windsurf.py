"""Parser for Windsurf MCP configuration."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .models import MCPServer, ToolName

WINDSURF_HOME = Path.home() / ".codeium" / "windsurf" / "mcp_config.json"


def parse_windsurf_json(path: Path) -> list[MCPServer]:
    """Parse Windsurf MCP servers from a JSON config file."""
    servers = []
    if not path.exists():
        return servers
    
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, IOError):
        return servers
    
    mcp_servers = data.get("mcpServers", {})
    for name, cfg in mcp_servers.items():
        server = _make_server(name, cfg, ToolName.WINDSURF, str(path))
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


def get_windsurf_servers() -> list[MCPServer]:
    """Get all Windsurf MCP servers."""
    return parse_windsurf_json(WINDSURF_HOME)
